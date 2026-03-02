import binascii

from mgtools.formats.gcx.blueprint import (
    escape_blueprint_string,
    parse_blueprint,
)
from mgtools.formats.gcx.commands import BUILTIN_COMMANDS, SCRIPT_COMMANDS
from mgtools.formats.gcx.nodes import GcxFile
from mgtools.formats.gcx.operators import EXPR_OPS
from mgtools.formats.gcx.reader import Reader
from mgtools.formats.gcx.resources import escape_resource_bytes, get_resource_data


class GcxDecompiler:
    """GcxDecompiler converts GCX binary data back into a human-readable GCL script format."""

    def __init__(self, gcx: GcxFile, dictionary: dict[int, str] | None = None):
        self.gcx = gcx
        self.dictionary = dictionary or {}
        self.indent = 0

    def decompile(self) -> str:
        """Decompile the entire GCX file to GCL script text."""
        lines: list[str] = []

        # Header metadata
        lines.append(f"// Timestamp: 0x{self.gcx.timestamp:08X}")
        lines.append(f"// Seed: 0x{self.gcx.seed:08X}")
        lines.append(f"// HasLCGB: {str(self.gcx.has_lcgb_header).lower()}")
        proc_flags = ", ".join(
            f"0x{(o >> 24) & 0xFF:02X}" for o in self.gcx.proc_offsets
        )
        lines.append(f"// ProcFlags: {proc_flags}")
        # Proc body order in binary (sorted by offset within proc blob)
        proc_order = sorted(
            range(len(self.gcx.proc_offsets)),
            key=lambda i: self.gcx.proc_offsets[i] & 0x00FFFFFF,
        )
        lines.append(f"// ProcOrder: {', '.join(str(i) for i in proc_order)}")
        lines.append("")

        # Main body
        r = Reader(self.gcx.main_body_data)
        size = r.get_block_size()
        end = r.pos + size

        lines.append("main {")
        self.indent = 1
        while r.pos < end:
            text = self._decompile_value(r, end)
            if text:
                lines.append(text)
        self.indent = 0
        lines.append("}")
        lines.append("")

        # Proc bodies
        for i, offset in enumerate(self.gcx.proc_offsets):
            r = Reader(self.gcx.proc_body_data, offset & 0x00FFFFFF)
            size = r.get_block_size()
            end = r.pos + size

            lines.append(f"proc_{i} {{")
            self.indent = 1
            while r.pos < end:
                text = self._decompile_value(r, end)
                if text:
                    lines.append(text)
            self.indent = 0
            lines.append("}")
            lines.append("")

        # String resources section
        if self.gcx.resource_entries:
            lines.append("[strings]")
            lines.append(
                "// String resources (index [flags]: text).  Edit the text after the colon."
            )
            lines.append(
                "// Escapes: \\n = newline, \\xHH = hex byte, \\\\ = backslash"
            )
            for i in range(len(self.gcx.resource_entries)):
                flags = (self.gcx.resource_entries[i] >> 24) & 0xFF
                data = get_resource_data(self.gcx, i)
                lines.append(f"{i} [0x{flags:02X}]: {escape_resource_bytes(data)}")
            lines.append("")

        # Blueprint / extra data section
        if self.gcx.extra_data:
            if self.gcx.has_lcgb_header and len(self.gcx.extra_data) >= 8:
                lines.extend(self._decompile_blueprint(self.gcx.extra_data))
            else:
                lines.append("[extra_data]")
                lines.append(self._hex_dump(self.gcx.extra_data))
                lines.append("")

        if self.gcx.font_data:
            lines.append("[font_data]")
            lines.append(self._hex_dump(self.gcx.font_data))
            lines.append("")

        if self.gcx.trailing_data:
            lines.append("[trailing_data]")
            lines.append(self._hex_dump(self.gcx.trailing_data))
            lines.append("")

        return "\n".join(lines)

    def _decompile_blueprint(self, data: bytes) -> list[str]:
        """Decompile blueprint extra_data into a readable [blueprint_data] section."""
        bp = parse_blueprint(data)
        lines: list[str] = []
        lines.append("[blueprint_data]")
        lines.append("// Blueprint string table.  Edit the text after the colon.")
        lines.append("// Escapes: \\n = newline, \\uXXXX = unicode, \\\\ = backslash")
        lines.append(f"// Prefix: {bp.prefix.hex()}")
        lines.append(f"// Groups: {', '.join(str(o) for o in bp.group_offsets)}")
        for i, s in enumerate(bp.strings):
            if s is None:
                lines.append(f"{i}: <null>")
            else:
                lines.append(f"{i}: {escape_blueprint_string(s)}")

        if bp.trailing_strings:
            lines.append("// Trailing strings (appended after last indexed entry):")
            for ts in bp.trailing_strings:
                lines.append(f"+: {escape_blueprint_string(ts)}")

        lines.append("")
        return lines

    @staticmethod
    def _hex_dump(data: bytes) -> str:
        """Encode binary data as hex string with line wrapping."""
        hex_str = binascii.hexlify(data).decode("ascii")
        # Wrap at 128 hex chars (64 bytes) per line
        lines = [hex_str[i : i + 128] for i in range(0, len(hex_str), 128)]
        return "\n".join(lines)

    def _indent(self) -> str:
        return "\t" * self.indent

    def _resolve_strcode(self, h: int) -> str:
        if h in self.dictionary:
            return self.dictionary[h]
        if h in BUILTIN_COMMANDS:
            return BUILTIN_COMMANDS[h]
        if h in SCRIPT_COMMANDS:
            return SCRIPT_COMMANDS[h]
        return f"[0x{h:X}]"

    def _decompile_value(self, r: Reader, block_end: int, inline: bool = False) -> str:
        """Decompile one value/node from the bytecode stream."""
        code = r.data[r.pos]
        tag = code & 0xF0
        if (code & 0xC0) == 0xC0:
            tag = 0xC0

        if tag == 0xC0:
            # Num
            r.pos += 1
            val = (code & 0x3F) - 1
            return f"{val}" if inline else f"{self._indent()}{val}"

        elif tag == 0x90:
            # Local
            r.pos += 1
            idx = code & 0x0F
            s = f"$local:{idx}"
            return s if inline else f"{self._indent()}{s}"

        elif tag == 0x80:
            # Proc block
            size = r.get_block_size()
            end = r.pos + size
            parts = []
            if not inline:
                parts.append(f"{self._indent()}proc {{")
            else:
                parts.append("proc {")
            self.indent += 1
            while r.pos < end:
                text = self._decompile_value(r, end)
                if text:
                    parts.append(text)
            self.indent -= 1
            parts.append(f"{self._indent()}}}")
            r.pos = end
            return "\n".join(parts)

        elif tag == 0x70:
            # Call
            size = r.get_block_size()
            end = r.pos + size
            proc_idx = r.u16()
            args = []
            while r.pos < end:
                peek = r.data[r.pos]
                if peek == 0x00:
                    r.pos += 1
                    break
                args.append(self._decompile_value(r, end, inline=True))
            s = f"@proc_{proc_idx}({', '.join(args)})"
            return s if inline else f"{self._indent()}{s}"

        elif tag == 0x60:
            # Command
            size = r.get_block_size()
            end = r.pos + size
            cmd_hash = r.u24()
            cmd_name = self._resolve_strcode(cmd_hash)
            short_size = r.get_short_size()
            arg_end = r.pos + short_size

            # Read command arguments
            args = []
            while r.pos < arg_end:
                args.append(self._decompile_value(r, arg_end, inline=True))
            r.pos = arg_end

            # Special handling for if/switch
            if cmd_name == "if":
                return self._decompile_if(r, end, args)
            elif cmd_name == "switch":
                return self._decompile_switch(r, end, args)

            # Read command body (params)
            body_parts = []
            while r.pos < end:
                body_parts.append(self._decompile_value(r, end))

            result_lines = []
            arg_str = ", ".join(args) if args else ""
            if not inline:
                result_lines.append(f"{self._indent()}.{cmd_name}({arg_str}) \\")
            else:
                result_lines.append(f".{cmd_name}({arg_str}) \\")
            if body_parts:
                self.indent += 1
                result_lines.extend(body_parts)
                self.indent -= 1

            r.pos = end
            return "\n".join(result_lines)

        elif tag == 0x50:
            # Param
            size = r.get_block_size()
            end = r.pos + size
            letter = r.u8()
            letter_char = chr(letter) if 32 <= letter < 127 else f"\\x{letter:02X}"

            values = []
            while r.pos < end:
                values.append(self._decompile_value(r, end, inline=True))
            r.pos = end

            val_str = ", ".join(values) if values else ""
            s = f"-{letter_char} {val_str}"
            return s if inline else f"{self._indent()}{s}"

        elif tag == 0x40:
            # Args
            r.pos += 1
            arg_id = code & 0xF
            if arg_id == 0xF:
                arg_id = r.u8() + 15
            s = f"$arg{arg_id}"
            return s if inline else f"{self._indent()}{s}"

        elif tag == 0x30:
            # Expr
            size = r.get_block_size()
            end = r.pos + size
            expr_text = self._decompile_expr(r, end)
            r.pos = end
            # Ensure expression is wrapped in parens so the compiler
            # knows to emit an expression block (tag 0x30).
            if not expr_text.startswith("("):
                expr_text = f"({expr_text})"
            return expr_text if inline else f"{self._indent()}{expr_text}"

        elif tag == 0x20:
            # VarArray
            varcode = r.u32be()
            region = self._get_var_region(varcode)
            offset = varcode & 0xFFFF
            extra_hi = (varcode >> 24) & 0x0F
            extra_mid = (varcode >> 16) & 0x0F
            arr_max = self._decompile_value(r, block_end, inline=True)
            arr_idx = self._decompile_value(r, block_end, inline=True)
            if extra_hi or extra_mid:
                s = f"$varr[0x{varcode:08X}][{arr_idx},{arr_max}]"
            else:
                s = f"$var:{region}[0x{offset:X}][{arr_idx},{arr_max}]"
            return s if inline else f"{self._indent()}{s}"

        elif tag == 0x10:
            # Var
            varcode = r.u32be()
            region = self._get_var_region(varcode)
            offset = varcode & 0xFFFF
            extra_hi = (varcode >> 24) & 0x0F
            extra_mid = (varcode >> 16) & 0x0F
            if extra_hi or extra_mid:
                s = f"$var[0x{varcode:08X}]"
            else:
                s = f"$var:{region}[0x{offset:X}]"
            return s if inline else f"{self._indent()}{s}"

        elif tag == 0:
            # Type-based (low nibble)
            return self._decompile_type(r, block_end, inline)

        else:
            raise ValueError(f"Unknown tag 0x{tag:02X} at offset 0x{r.pos:X}")

    def _decompile_type(self, r: Reader, block_end: int, inline: bool) -> str:
        code = r.u8()

        if code == 0x00:
            return ""  # End
        elif code == 0x01:
            val = r.i16()
            s = f"0x{val & 0xFFFF:04X}" if val >= 0 else str(val)
            return s if inline else f"{self._indent()}{s}"
        elif code in (0x02, 0x03, 0x04):
            val = r.u8()
            if code == 0x03:
                s = f"0x{val:02X}t3"
            elif code == 0x04:
                s = f"0x{val:02X}t4"
            else:
                s = f"0x{val:02X}"
            return s if inline else f"{self._indent()}{s}"
        elif code == 0x06:
            h = r.u24()
            name = self._resolve_strcode(h)
            s = name
            return s if inline else f"{self._indent()}{s}"
        elif code == 0x08:
            h = r.u16()
            s = f"[0x{h:04X}]"
            return s if inline else f"{self._indent()}{s}"
        elif code == 0x07:
            length = r.u8()
            raw = r.read_bytes(length)
            # Remove NUL terminator for display
            text = raw.rstrip(b"\x00")
            try:
                decoded = text.decode("euc-jp")
            except (UnicodeDecodeError, ValueError):
                decoded = text.decode("latin-1")
            s = f'"{decoded}"'
            return s if inline else f"{self._indent()}{s}"
        elif code in (0x09, 0x0A):
            val = r.u32()
            suffix = "i" if code == 0x09 else ""
            s = f"0x{val:08X}{suffix}"
            return s if inline else f"{self._indent()}{s}"
        elif code == 0x0D:
            # Array: 3-byte strcode + 1-byte index
            h = r.u24()
            idx = r.u8()
            name = self._resolve_strcode(h)
            s = f"{name}[{idx}]"
            return s if inline else f"{self._indent()}{s}"
        elif code == 0x0E:
            val = r.u16()
            s = f"$strres:{val}"
            return s if inline else f"{self._indent()}{s}"
        else:
            raise ValueError(
                f"Unknown type code 0x{code:02X} at offset 0x{r.pos - 1:X}"
            )

    def _decompile_expr(self, r: Reader, end: int) -> str:
        """Decompile an expression block (stack-based)."""
        stack: list[str] = []

        while r.pos < end:
            code = r.data[r.pos]
            if (code & 0xE0) == 0xA0:
                # Operator
                r.pos += 1
                op = code & 0x1F
                if op == 0:
                    break
                op_str = EXPR_OPS.get(op)
                if op_str is None:
                    stack.append(f"<unknown_op_{op}>")
                    continue

                if op in (0x01, 0x02, 0x03):
                    # Unary
                    if stack:
                        val = stack.pop()
                        if op == 0x01:
                            stack.append(f"(-{val})")
                        elif op == 0x02:
                            stack.append(f"(!{val})")
                        elif op == 0x03:
                            stack.append(f"(~{val})")
                elif op == 0x17:
                    # Passthrough – just keep top of stack
                    pass
                else:
                    # Binary
                    if len(stack) >= 2:
                        val1 = stack.pop()
                        val2 = stack.pop()
                        stack.append(f"({val2} {op_str} {val1})")
                    else:
                        stack.append("<stack_underflow>")
            else:
                val = self._decompile_value(r, end, inline=True)
                stack.append(val)

        if not stack:
            return "<empty_expr>"
        # Preserve all stack values for round-trip fidelity (dead values at
        # the bottom of the stack are emitted as comma-separated items).
        return ", ".join(stack)

    def _decompile_if(self, r: Reader, block_end: int, args: list[str]) -> str:
        """Decompile an if/elif/else chain."""
        lines = []
        arg_str = ", ".join(args) if args else ""
        lines.append(f"{self._indent()}.if({arg_str})")

        while r.pos < block_end:
            code = r.data[r.pos]
            tag = code & 0xF0
            if tag == 0x50:
                size = r.get_block_size()
                end = r.pos + size
                letter = r.u8()
                letter_char = chr(letter) if 32 <= letter < 127 else f"\\x{letter:02X}"

                if letter_char == "i":
                    # elif
                    values = []
                    while r.pos < end:
                        values.append(self._decompile_value(r, end, inline=True))
                    val_str = ", ".join(values) if values else ""
                    lines.append(f"{self._indent()}.elif({val_str})")
                elif letter_char == "e":
                    # else
                    values = []
                    while r.pos < end:
                        values.append(self._decompile_value(r, end, inline=True))
                    val_str = ", ".join(values) if values else ""
                    lines.append(f"{self._indent()}.else({val_str})")
                else:
                    # Regular param
                    values = []
                    while r.pos < end:
                        values.append(self._decompile_value(r, end, inline=True))
                    val_str = ", ".join(values) if values else ""
                    lines.append(f"{self._indent()}-{letter_char} {val_str}")
                r.pos = end
            else:
                text = self._decompile_value(r, block_end)
                if text:
                    lines.append(text)

        return "\n".join(lines)

    def _decompile_switch(self, r: Reader, block_end: int, args: list[str]) -> str:
        """Decompile a switch statement."""
        lines = []
        arg_str = ", ".join(args) if args else ""
        lines.append(f"{self._indent()}.switch({arg_str}) {{")
        self.indent += 1

        while r.pos < block_end:
            code = r.data[r.pos]
            tag = code & 0xF0
            if tag == 0x50:
                size = r.get_block_size()
                end = r.pos + size
                letter = r.u8()
                letter_char = chr(letter) if 32 <= letter < 127 else f"\\x{letter:02X}"

                values = []
                while r.pos < end:
                    values.append(self._decompile_value(r, end, inline=True))

                if letter_char == "c":
                    case_val = values[0] if values else "?"
                    body = ", ".join(values[1:]) if len(values) > 1 else ""
                    lines.append(f"{self._indent()}case {case_val}: {body}")
                elif letter_char == "d":
                    body = ", ".join(values) if values else ""
                    lines.append(f"{self._indent()}default: {body}")
                else:
                    val_str = ", ".join(values) if values else ""
                    lines.append(f"{self._indent()}-{letter_char} {val_str}")
                r.pos = end
            else:
                text = self._decompile_value(r, block_end)
                if text:
                    lines.append(text)

        self.indent -= 1
        lines.append(f"{self._indent()}}}")
        return "\n".join(lines)

    @staticmethod
    def _get_var_region(varcode: int) -> str:
        region = varcode & 0xF00000
        if region == 0x800000:
            return "linkvarbuf"
        elif region == 0x100000:
            return "localvarbuf"
        return "varbuf"
