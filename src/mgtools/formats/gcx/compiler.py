import binascii
import re

from mgtools.formats.gcx.blueprint import (
    BlueprintData,
    build_blueprint,
    unescape_blueprint_string,
)
from mgtools.formats.gcx.commands import BUILTIN_COMMANDS, SCRIPT_COMMANDS
from mgtools.formats.gcx.nodes import GcxFile
from mgtools.formats.gcx.operators import EXPR_OPS
from mgtools.formats.gcx.parser import Gcx
from mgtools.formats.gcx.resources import unescape_resource_text
from mgtools.formats.gcx.strcode import strcode
from mgtools.formats.gcx.tokenizer import Tokenizer
from mgtools.formats.gcx.writer import Writer

# Reverse lookup: operator string → opcode
OP_TO_CODE: dict[str, int] = {}
for _code, _name in EXPR_OPS.items():
    if _name is not None and _code != 0:
        OP_TO_CODE[_name] = _code

# Reverse lookup: command name → hash
CMD_NAME_TO_HASH: dict[str, int] = {}
for _h, _n in BUILTIN_COMMANDS.items():
    CMD_NAME_TO_HASH[_n] = _h
for _h, _n in SCRIPT_COMMANDS.items():
    CMD_NAME_TO_HASH[_n] = _h


class GclCompiler:
    """GclCompiler converts GCL script text into GCX binary data."""

    def __init__(self, script: str):
        self.tok = Tokenizer(script)
        # Reverse string→hash dictionary
        self._name2hash: dict[str, int] = dict(CMD_NAME_TO_HASH)

    # -- public API ---------------------------------------------------------

    def compile(self) -> bytes:
        # Parse header metadata comments
        metadata = self._parse_header_metadata()

        # Compile main block
        main_body = self._compile_toplevel_block("main")

        # Compile proc blocks
        proc_bodies: dict[int, bytes] = {}
        while not self.tok.at_end():
            self._skip_header()
            if self.tok.at_end():
                break
            # Check for section markers
            if self.tok.lookahead("["):
                break
            w = self.tok.peek_word()
            m = re.match(r"proc_(\d+)", w)
            if m:
                idx = int(m.group(1))
                proc_bodies[idx] = self._compile_toplevel_block(f"proc_{idx}")
            else:
                self.tok.skip_line()

        # Parse tagged sections ([strings], [extra_data], [blueprint_data], ...)
        string_entries: list[tuple[int, bytes]] | None = None
        extra_data = b""
        font_data = b""
        trailing_data = b""

        while not self.tok.at_end():
            self._skip_header()
            if self.tok.at_end():
                break
            if self.tok.lookahead("[strings]"):
                string_entries = self._parse_strings_section()
            elif self.tok.lookahead("[blueprint_data]"):
                extra_data = self._parse_blueprint_section()
            elif self.tok.lookahead("[extra_data]"):
                extra_data = self._parse_hex_section()
            elif self.tok.lookahead("[font_data]"):
                font_data = self._parse_hex_section()
            elif self.tok.lookahead("[trailing_data]"):
                trailing_data = self._parse_hex_section()
            else:
                self.tok.skip_line()

        # Rebuild proc offsets and data
        proc_flags = metadata.get("proc_flags", [])
        proc_order = metadata.get("proc_order", None)
        num_procs = max(len(proc_flags), max(proc_bodies.keys(), default=-1) + 1)
        # Pad proc_flags if needed
        while len(proc_flags) < num_procs:
            proc_flags.append(0)
        # Use original proc body order if available, otherwise index order
        if proc_order is None:
            proc_order = list(range(num_procs))

        # Write procs in the specified order
        all_procs = Writer()
        new_offsets: list[int] = [0] * num_procs
        for i in proc_order:
            flags = proc_flags[i] << 24
            new_offsets[i] = flags | all_procs.tell()
            if i in proc_bodies:
                all_procs.write(proc_bodies[i])

        # Build resource entries and string data
        resource_entries: list[int] = []
        string_data = b""
        if string_entries is not None:
            new_string_data = bytearray()
            for _idx, (res_flags, raw) in enumerate(string_entries):
                resource_entries.append((res_flags << 24) | len(new_string_data))
                new_string_data.extend(raw)
            string_data = bytes(new_string_data)

        # Build GcxFile
        gcx = GcxFile(
            has_lcgb_header=metadata.get("has_lcgb", False),
            timestamp=metadata.get("timestamp", 0),
            proc_offsets=new_offsets,
            proc_offset=0,  # placeholder, recalculated by to_bytes
            resource_table_offset=0,
            string_resources_offset=0,
            font_data_offset=0,
            seed=metadata.get("seed", 0),
            resource_entries=resource_entries,
            extra_data=extra_data,
            string_data=string_data,
            font_data=font_data,
            proc_body_data=all_procs.getvalue(),
            main_body_data=main_body,
            trailing_data=trailing_data,
        )

        return Gcx.to_bytes(gcx)

    # -- helpers ------------------------------------------------------------

    def _parse_header_metadata(self) -> dict:
        """Parse ``// Key: Value`` header comments into a metadata dict."""
        metadata: dict = {}
        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if not self.tok.lookahead("//"):
                break
            line = self.tok.read_until("\n")
            if not self.tok.at_end():
                self.tok.advance()
            line = line.lstrip("/").strip()
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "Timestamp":
                metadata["timestamp"] = int(value, 16)
            elif key == "Seed":
                metadata["seed"] = int(value, 16)
            elif key == "HasLCGB":
                metadata["has_lcgb"] = value.lower() == "true"
            elif key == "ProcFlags":
                if value:
                    metadata["proc_flags"] = [
                        int(f.strip(), 16) for f in value.split(",")
                    ]
                else:
                    metadata["proc_flags"] = []
            elif key == "ProcOrder":
                if value:
                    metadata["proc_order"] = [int(v.strip()) for v in value.split(",")]
        return metadata

    def _skip_header(self):
        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if self.tok.lookahead("//"):
                self.tok.skip_line()
            else:
                break

    def _parse_strings_section(self) -> list[tuple[int, bytes]]:
        """Parse a ``[strings]`` section and return a list of
        ``(flags_byte, raw_bytes)`` tuples (one per index)."""
        # Consume "[strings]"
        self.tok.read_until("\n")
        self.tok.skip_ws_nl()

        entries: dict[int, tuple[int, bytes]] = {}
        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if self.tok.lookahead("//"):
                self.tok.skip_line()
                continue
            # Detect next section
            if self.tok.lookahead("["):
                break
            # Read "index [0xNN]: text" or "index: text" (legacy)
            idx_s = self.tok.read_until(" :[")
            if not idx_s.strip().isdigit():
                break
            idx = int(idx_s.strip())
            self.tok.skip_ws()
            # Parse optional flags [0xNN]
            res_flags = 0x80  # default
            if not self.tok.at_end() and self.tok.peek() == "[":
                self.tok.advance()  # '['
                flags_s = self.tok.read_until("]").strip()
                self.tok.expect("]")
                res_flags = int(flags_s, 16)
                self.tok.skip_ws()
            self.tok.expect(":")
            # Skip single space after colon (if present)
            if not self.tok.at_end() and self.tok.peek() == " ":
                self.tok.advance()
            # Read the rest of the line as the escaped string value
            line = self.tok.read_until("\n")
            if not self.tok.at_end():
                self.tok.advance()  # consume \n
            entries[idx] = (res_flags, unescape_resource_text(line))

        # Build ordered list
        max_idx = max(entries.keys()) if entries else -1
        result: list[tuple[int, bytes]] = []
        for i in range(max_idx + 1):
            result.append(entries.get(i, (0x80, b"\x00")))
        return result

    def _parse_hex_section(self) -> bytes:
        """Parse a hex data section (``[name]`` followed by hex lines)."""
        # Consume section header line
        self.tok.read_until("\n")
        if not self.tok.at_end():
            self.tok.advance()

        hex_chars: list[str] = []
        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if self.tok.lookahead("//"):
                self.tok.skip_line()
                continue
            # Detect next section or non-hex content
            if self.tok.lookahead("["):
                break
            line = self.tok.read_until("\n")
            if not self.tok.at_end():
                self.tok.advance()
            stripped = line.strip()
            if stripped:
                hex_chars.append(stripped)

        if not hex_chars:
            return b""
        return binascii.unhexlify("".join(hex_chars))

    def _parse_blueprint_section(self) -> bytes:
        """Parse a ``[blueprint_data]`` section and rebuild binary extra_data."""
        # Consume section header line
        self.tok.read_until("\n")
        if not self.tok.at_end():
            self.tok.advance()

        prefix = b"\x00\x00\x00\x00"
        group_offsets = [0x18, 0x218]
        strings: dict[int, str | None] = {}
        trailing_strings: list[str] = []

        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if self.tok.lookahead("//"):
                line = self.tok.read_until("\n")
                if not self.tok.at_end():
                    self.tok.advance()
                # Parse metadata from comments
                stripped = line.lstrip("/").strip()
                if stripped.startswith("Prefix:"):
                    hex_val = stripped[len("Prefix:") :].strip()
                    if hex_val:
                        prefix = bytes.fromhex(hex_val)
                elif stripped.startswith("Groups:"):
                    vals = stripped[len("Groups:") :].strip()
                    if vals:
                        group_offsets = [int(v.strip()) for v in vals.split(",")]
                continue
            # Detect next section
            if self.tok.lookahead("["):
                break
            # Read line
            line = self.tok.read_until("\n")
            if not self.tok.at_end():
                self.tok.advance()
            stripped = line.strip()
            if not stripped:
                continue

            # Parse "+: text" (trailing string)
            if stripped.startswith("+:"):
                text = stripped[2:].strip()
                trailing_strings.append(unescape_blueprint_string(text))
                continue

            # Parse "index: text" or "index: <null>"
            colon_pos = stripped.find(":")
            if colon_pos < 0:
                continue
            idx_s = stripped[:colon_pos].strip()
            if not idx_s.isdigit():
                continue
            idx = int(idx_s)
            text = stripped[colon_pos + 1 :].strip()
            if text == "<null>":
                strings[idx] = None
            else:
                strings[idx] = unescape_blueprint_string(text)

        # Build ordered string list
        max_idx = max(strings.keys()) if strings else -1
        ordered: list[str | None] = []
        for i in range(max_idx + 1):
            if i in strings:
                ordered.append(strings[i])
            else:
                ordered.append(None)

        bp = BlueprintData(
            group_offsets=group_offsets,
            prefix=prefix,
            strings=ordered,
            trailing_strings=trailing_strings,
        )
        return build_blueprint(bp)

    def _compile_toplevel_block(self, name: str) -> bytes:
        """Parse ``name {`` ... ``}`` and return tag+size+body bytes."""
        self.tok.skip_ws_nl()
        _name = self.tok.read_until(" \t\n{")
        self.tok.skip_ws()
        self.tok.expect("{")

        body = self._compile_body()

        w = Writer()
        w.write_block_size(0x80, len(body))
        return w.getvalue() + body

    def _compile_body(self) -> bytes:
        """Compile statements until ``}``."""
        w = Writer()
        while not self.tok.at_end():
            self._skip_header()
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if self.tok.peek() == "}":
                self.tok.advance()
                break
            self._compile_statement(w)
        w.u8(0x00)  # block end marker
        return w.getvalue()

    # -- statement dispatch -------------------------------------------------

    def _compile_statement(self, w: Writer):
        self.tok.skip_ws()
        c = self.tok.peek()
        if c is None:
            return
        if c == ".":
            self._compile_command(w)
        elif c == "@":
            self._compile_call(w)
        elif c == "(":
            self._compile_expr(w)
        elif c == "-":
            self._compile_param(w)
        elif c == "p" and self.tok.lookahead("proc "):
            self._compile_inline_proc(w)
        elif c == "c" and self.tok.lookahead("case "):
            self._compile_case(w)
        elif c == "d" and self.tok.lookahead("default:"):
            self._compile_default(w)
        else:
            self._compile_value(w)

    # -- value compilation --------------------------------------------------

    def _compile_value(self, w: Writer):
        """Compile a single inline value."""
        self.tok.skip_ws()
        c = self.tok.peek()
        if c is None:
            return

        if c == '"':
            s = self.tok.read_string()
            raw = s.encode("euc-jp") + b"\x00"
            w.u8(0x07)
            w.u8(len(raw))
            w.write(raw)

        elif c == "$":
            self._compile_dollar(w)

        elif c == "[":
            # Strcode literal [0xHASH]
            self.tok.advance()
            self.tok.skip_ws()
            val_s = self.tok.read_until("]").strip()
            self.tok.expect("]")
            h = int(val_s, 16)
            # Determine encoding by hex digit count: 4 digits = u16 (code 0x08), else u24 (code 0x06)
            hex_part = val_s.strip()
            if hex_part.startswith(("0x", "0X")):
                hex_part = hex_part[2:]
            if len(hex_part) == 4:
                w.u8(0x08)
                w.u16(h)
            else:
                w.u8(0x06)
                w.u24(h)

        elif c == "(":
            self._compile_expr(w)

        elif c == "p" and self.tok.lookahead("proc "):
            self._compile_inline_proc(w)

        elif c == "@":
            self._compile_call(w)

        elif c == ".":
            self._compile_command(w)

        elif c == "-" or c.isdigit():
            self._compile_number(w)

        elif c == "0":
            self._compile_number(w)

        else:
            name = self.tok.read_word()
            if name in self._name2hash:
                w.u8(0x06)
                w.u24(self._name2hash[name])
            else:
                raise SyntaxError(f"Unknown token '{name}' at line {self.tok.line}")

    def _compile_number(self, w: Writer):
        self.tok.skip_ws()
        neg = False
        if self.tok.peek() == "-":
            neg = True
            self.tok.advance()
        num_s = self.tok.read_word()
        is_hex = num_s.startswith(("0x", "0X"))
        # Check for type suffixes: 'i' (signed i32), 't3' (code 0x03), 't4' (code 0x04)
        signed_long = False
        type_code = None
        if is_hex and num_s.endswith("i"):
            signed_long = True
            num_s = num_s[:-1]
        elif is_hex and num_s.endswith("t3"):
            type_code = 0x03
            num_s = num_s[:-2]
        elif is_hex and num_s.endswith("t4"):
            type_code = 0x04
            num_s = num_s[:-2]
        val = int(num_s, 16) if is_hex else int(num_s)
        if neg:
            val = -val
        if type_code is not None:
            w.u8(type_code)
            w.u8(val & 0xFF)
        elif is_hex:
            hex_digits = len(num_s) - 2
            if signed_long:
                # Code 0x09
                w.u8(0x09)
                w.u32(val & 0xFFFFFFFF)
            else:
                self._emit_number_typed(w, val, hex_digits)
        else:
            self._emit_number(w, val)

    @staticmethod
    def _emit_number(w: Writer, val: int):
        """Emit a number using optimal GclNum encoding (decimal source)."""
        if -1 <= val <= 62:
            w.u8(0xC0 | ((val + 1) & 0x3F))
        elif -32768 <= val <= 32767:
            w.u8(0x01)
            w.i16(val)
        elif 0 <= val <= 0xFF:
            w.u8(0x02)
            w.u8(val)
        elif 0 <= val <= 0xFFFFFFFF:
            w.u8(0x0A)
            w.u32(val)
        else:
            w.u8(0x09)
            w.u32(val & 0xFFFFFFFF)

    @staticmethod
    def _emit_number_typed(w: Writer, val: int, hex_digits: int):
        """Emit a number with encoding determined by hex digit width."""
        if hex_digits <= 2:
            # u8 (code 0x02)
            w.u8(0x02)
            w.u8(val & 0xFF)
        elif hex_digits <= 4:
            # i16 (code 0x01)
            w.u8(0x01)
            w.i16(val if val < 0x8000 else val - 0x10000)
        else:
            # u32 (code 0x0A)
            w.u8(0x0A)
            w.u32(val & 0xFFFFFFFF)

    # -- $ references -------------------------------------------------------

    def _compile_dollar(self, w: Writer):
        self.tok.advance()  # '$'
        kind = self.tok.read_until(":([, \t\n\r)]}\\0123456789")

        if kind == "var":
            # Check for raw varcode: $var[0xNNNNNNNN]
            c = self.tok.peek()
            if c == "[":
                # Raw Var varcode
                self.tok.expect("[")
                raw_s = self.tok.read_until("]").strip()
                self.tok.expect("]")
                varcode = int(raw_s, 16) if raw_s.startswith("0x") else int(raw_s)
                w.u32be(varcode)
                return

            self.tok.expect(":")
            region_name = self.tok.read_until("[")
            self.tok.expect("[")
            off_s = self.tok.read_until("]").strip()
            self.tok.expect("]")
            offset = int(off_s, 16) if off_s.startswith("0x") else int(off_s)

            if region_name == "linkvarbuf":
                region_bits = 0x800000
            elif region_name == "localvarbuf":
                region_bits = 0x100000
            else:
                region_bits = 0x000000

            # Peek for array subscript
            self.tok.skip_ws()
            if not self.tok.at_end() and self.tok.peek() == "[":
                # VarArray (tag 0x20)
                varcode = (0x20 << 24) | region_bits | (offset & 0xFFFF)
                w.u32be(varcode)
                self.tok.expect("[")
                # Read [idx, max] — idx/max can be complex (e.g. $var:...[0x0])
                idx_w = Writer()
                self._compile_value(idx_w)
                self.tok.skip_ws()
                if self.tok.peek() == ",":
                    self.tok.advance()
                    self.tok.skip_ws()
                    max_w = Writer()
                    self._compile_value(max_w)
                    self.tok.skip_ws()
                    self.tok.expect("]")
                else:
                    self.tok.expect("]")
                    # [idx][max]
                    self.tok.expect("[")
                    max_w = Writer()
                    self._compile_value(max_w)
                    self.tok.skip_ws()
                    self.tok.expect("]")
                # Binary order: max, then idx
                w.write(max_w.getvalue())
                w.write(idx_w.getvalue())
            else:
                # Var (tag 0x10)
                varcode = (0x10 << 24) | region_bits | (offset & 0xFFFF)
                w.u32be(varcode)

        elif kind == "varr":
            # Raw VarArray varcode: $varr[0xNNNNNNNN][idx,max]
            self.tok.expect("[")
            raw_s = self.tok.read_until("]").strip()
            self.tok.expect("]")
            varcode = int(raw_s, 16) if raw_s.startswith("0x") else int(raw_s)
            w.u32be(varcode)
            self.tok.expect("[")
            idx_w = Writer()
            self._compile_value(idx_w)
            self.tok.skip_ws()
            if self.tok.peek() == ",":
                self.tok.advance()
                self.tok.skip_ws()
                max_w = Writer()
                self._compile_value(max_w)
                self.tok.skip_ws()
                self.tok.expect("]")
            else:
                self.tok.expect("]")
                self.tok.expect("[")
                max_w = Writer()
                self._compile_value(max_w)
                self.tok.skip_ws()
                self.tok.expect("]")
            w.write(max_w.getvalue())
            w.write(idx_w.getvalue())

        elif kind == "local":
            self.tok.expect(":")
            idx_s = self.tok.read_word()
            idx = int(idx_s)
            w.u8(0x90 | (idx & 0x0F))

        elif kind == "arg":
            idx_s = self.tok.read_word()
            idx = int(idx_s)
            if idx >= 15:
                w.u8(0x4F)
                w.u8(idx - 15)
            else:
                w.u8(0x40 | (idx & 0x0F))

        elif kind == "strres":
            self.tok.expect(":")
            idx_s = self.tok.read_word()
            idx = int(idx_s)
            w.u8(0x0E)
            w.u16(idx)

        else:
            raise SyntaxError(f"Unknown $ kind '{kind}' at line {self.tok.line}")

    def _compile_value_str(self, w: Writer, s: str):
        """Compile a simple value from its string representation."""
        s = s.strip()
        if not s:
            return
        sub = GclCompiler.__new__(GclCompiler)
        sub.tok = Tokenizer(s)
        sub._name2hash = self._name2hash
        sub._compile_value(w)

    # -- expressions --------------------------------------------------------

    def _compile_expr(self, w: Writer):
        raw = self._compile_expr_inner()
        raw += bytes([0xA0])  # expression terminator (op==0 → end)
        w.write_block_size(0x30, len(raw))
        w.write(raw)

    def _compile_expr_inner(self) -> bytes:
        self.tok.skip_ws()
        self.tok.expect("(")
        self.tok.skip_ws()

        c = self.tok.peek()
        # Unary operators
        if c == "-" and (self.tok.peek(1) or "") not in "0123456789":
            self.tok.advance()
            operand = self._compile_expr_operand()
            self.tok.skip_ws()
            self.tok.expect(")")
            return operand + bytes([0xA0 | 0x01])

        if c == "!":
            self.tok.advance()
            operand = self._compile_expr_operand()
            self.tok.skip_ws()
            self.tok.expect(")")
            return operand + bytes([0xA0 | 0x02])

        if c == "~":
            self.tok.advance()
            operand = self._compile_expr_operand()
            self.tok.skip_ws()
            self.tok.expect(")")
            return operand + bytes([0xA0 | 0x03])

        # First operand
        left = self._compile_expr_operand()
        self.tok.skip_ws()

        # Possibly just a grouped value (no operator needed)
        if self.tok.peek() == ")":
            self.tok.advance()
            return left

        # Comma-separated multi-value expression (dead values on the stack)
        if self.tok.peek() == ",":
            result = left
            while self.tok.peek() == ",":
                self.tok.advance()  # skip ','
                self.tok.skip_ws()
                result += self._compile_expr_operand()
                self.tok.skip_ws()
            self.tok.expect(")")
            return result

        # Binary: read operator
        op_str = self.tok.read_until(" \t")
        self.tok.skip_ws()
        op_code = OP_TO_CODE.get(op_str)
        if op_code is None:
            raise SyntaxError(f"Unknown operator '{op_str}' at line {self.tok.line}")

        right = self._compile_expr_operand()
        self.tok.skip_ws()
        self.tok.expect(")")
        return left + right + bytes([0xA0 | op_code])

    def _compile_expr_operand(self) -> bytes:
        self.tok.skip_ws()
        if self.tok.peek() == "(":
            return self._compile_expr_inner()
        w = Writer()
        self._compile_value(w)
        return w.getvalue()

    # -- commands -----------------------------------------------------------

    def _compile_command(self, w: Writer):
        self.tok.advance()  # '.'
        cmd_name = self.tok.read_until("( \t")
        self.tok.skip_ws()

        # Dispatch special commands
        if cmd_name == "if":
            return self._compile_if(w)
        if cmd_name == "elif":
            return self._compile_elif(w)
        if cmd_name == "else":
            return self._compile_else(w)
        if cmd_name == "switch":
            return self._compile_switch(w)

        # Resolve hash
        if cmd_name in self._name2hash:
            cmd_hash = self._name2hash[cmd_name]
        elif cmd_name.startswith("unknown_command_"):
            cmd_hash = int(cmd_name.replace("unknown_command_", ""), 16)
        else:
            cmd_hash = strcode(cmd_name)
            self._name2hash[cmd_name] = cmd_hash

        # Arguments: (v1, v2, ...)
        args = b""
        if self.tok.peek() == "(":
            args = self._compile_arglist()

        # Skip trailing '\'
        self.tok.skip_ws()
        if not self.tok.at_end() and self.tok.peek() == "\\":
            self.tok.advance()

        # Body: params (lines starting with -)
        body = self._compile_cmd_body()

        inner = Writer()
        inner.u24(cmd_hash)
        inner.write_short_size(len(args))
        inner.write(args)
        inner.write(body)
        inner.u8(0x00)  # block end marker

        data = inner.getvalue()
        w.write_block_size(0x60, len(data))
        w.write(data)

    def _compile_arglist(self) -> bytes:
        self.tok.expect("(")
        w = Writer()
        self.tok.skip_ws()
        if self.tok.peek() == ")":
            self.tok.advance()
            return b""
        while True:
            self.tok.skip_ws()
            if self.tok.peek() == ")":
                self.tok.advance()
                break
            self._compile_value(w)
            self.tok.skip_ws()
            if self.tok.peek() == ",":
                self.tok.advance()
        return w.getvalue()

    def _compile_cmd_body(self) -> bytes:
        """Parse param lines (``-letter ...``) that belong to a command."""
        w = Writer()
        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if self.tok.peek() == "-":
                self._compile_param(w)
            else:
                break
        return w.getvalue()

    # -- param (-letter values) ---------------------------------------------

    def _compile_param(self, w: Writer):
        self.tok.advance()  # '-'
        letter = self.tok.advance()
        self.tok.skip_ws()

        vals = self._compile_csv_values()

        inner = Writer()
        inner.u8(ord(letter))
        inner.write(vals)
        data = inner.getvalue()
        w.write_block_size(0x50, len(data))
        w.write(data)

    def _compile_csv_values(self) -> bytes:
        """Compile comma-separated values until end of logical line."""
        w = Writer()
        while not self.tok.at_end():
            self.tok.skip_ws()
            c = self.tok.peek()
            if c is None or c in "\n\r":
                self.tok.skip_ws_nl()
                break
            if c == "\\":
                # Line continuation
                self.tok.advance()
                self.tok.skip_ws_nl()
                continue
            self._compile_value(w)
            self.tok.skip_ws()
            if not self.tok.at_end() and self.tok.peek() == ",":
                self.tok.advance()
        return w.getvalue()

    # -- proc call ----------------------------------------------------------

    def _compile_call(self, w: Writer):
        self.tok.advance()  # '@'
        name = self.tok.read_until("(")
        m = re.match(r"proc_(\d+)", name)
        if not m:
            raise SyntaxError(f"Invalid call '{name}' at line {self.tok.line}")
        proc_idx = int(m.group(1))

        args = b""
        if not self.tok.at_end() and self.tok.peek() == "(":
            args = self._compile_arglist()

        inner = Writer()
        inner.u16(proc_idx)
        inner.write(args)
        inner.u8(0x00)

        data = inner.getvalue()
        w.write_block_size(0x70, len(data))
        w.write(data)

    # -- inline proc --------------------------------------------------------

    def _compile_inline_proc(self, w: Writer):
        _word = self.tok.read_until(" \t{")
        self.tok.skip_ws()
        self.tok.expect("{")
        body = self._compile_body()
        w.write_block_size(0x80, len(body))
        w.write(body)

    # -- if / elif / else ---------------------------------------------------

    def _compile_if(self, w: Writer):
        """Compile ``.if(cond)`` plus following ``.elif``/``.else`` params."""
        args = self._compile_arglist()

        # Skip optional '\'
        self.tok.skip_ws()
        if not self.tok.at_end() and self.tok.peek() == "\\":
            self.tok.advance()

        body = self._compile_if_body()

        inner = Writer()
        inner.u24(CMD_NAME_TO_HASH["if"])
        inner.write_short_size(len(args))
        inner.write(args)
        inner.write(body)
        inner.u8(0x00)  # block end marker
        data = inner.getvalue()
        w.write_block_size(0x60, len(data))
        w.write(data)

    def _compile_if_body(self) -> bytes:
        w = Writer()
        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            c = self.tok.peek()
            if c == "-":
                self._compile_param(w)
            elif c == "." and self.tok.lookahead(".elif("):
                self.tok.advance()  # '.'
                self.tok.read_until("(")  # 'elif'
                self._compile_elif(w)
            elif c == "." and self.tok.lookahead(".else("):
                self.tok.advance()  # '.'
                self.tok.read_until("(")  # 'else'
                self._compile_else(w)
            else:
                break
        return w.getvalue()

    def _compile_elif(self, w: Writer):
        vals = self._compile_arglist()
        inner = Writer()
        inner.u8(ord("i"))
        inner.write(vals)
        data = inner.getvalue()
        w.write_block_size(0x50, len(data))
        w.write(data)

    def _compile_else(self, w: Writer):
        vals = self._compile_arglist()
        inner = Writer()
        inner.u8(ord("e"))
        inner.write(vals)
        data = inner.getvalue()
        w.write_block_size(0x50, len(data))
        w.write(data)

    # -- switch / case / default --------------------------------------------

    def _compile_switch(self, w: Writer):
        args = self._compile_arglist()

        self.tok.skip_ws_nl()
        self.tok.expect("{")

        body = self._compile_switch_body()

        inner = Writer()
        inner.u24(CMD_NAME_TO_HASH["switch"])
        inner.write_short_size(len(args))
        inner.write(args)
        inner.write(body)
        inner.u8(0x00)  # block end marker
        data = inner.getvalue()
        w.write_block_size(0x60, len(data))
        w.write(data)

    def _compile_switch_body(self) -> bytes:
        w = Writer()
        while not self.tok.at_end():
            self.tok.skip_ws_nl()
            if self.tok.at_end():
                break
            if self.tok.peek() == "}":
                self.tok.advance()
                break
            self._compile_statement(w)
        return w.getvalue()

    def _compile_case(self, w: Writer):
        """Compile ``case VALUE: BODY``."""
        self.tok.read_until(" \t")  # 'case'
        self.tok.skip_ws()
        # case value
        cv = Writer()
        self._compile_value(cv)
        self.tok.skip_ws()
        self.tok.expect(":")
        self.tok.skip_ws()
        # case body (single value)
        bv = Writer()
        self._compile_value(bv)

        inner = Writer()
        inner.u8(ord("c"))
        inner.write(cv.getvalue())
        inner.write(bv.getvalue())
        data = inner.getvalue()
        w.write_block_size(0x50, len(data))
        w.write(data)

    def _compile_default(self, w: Writer):
        """Compile ``default: BODY``."""
        self.tok.read_until(":")
        self.tok.advance()  # ':'
        self.tok.skip_ws()
        bv = Writer()
        self._compile_value(bv)

        inner = Writer()
        inner.u8(ord("d"))
        inner.write(bv.getvalue())
        data = inner.getvalue()
        w.write_block_size(0x50, len(data))
        w.write(data)
