class Tokenizer:
    """Character-level tokenizer for GCL script text."""

    __slots__ = ("text", "pos", "line")

    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.line = 1

    # -- basic navigation ---------------------------------------------------

    def at_end(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self, offset: int = 0) -> str | None:
        p = self.pos + offset
        return self.text[p] if p < len(self.text) else None

    def advance(self) -> str:
        c = self.text[self.pos]
        if c == "\n":
            self.line += 1
        self.pos += 1
        return c

    def skip_ws(self):
        """Skip spaces and tabs (NOT newlines)."""
        while self.pos < len(self.text) and self.text[self.pos] in " \t":
            self.pos += 1

    def skip_ws_nl(self):
        """Skip whitespace including newlines."""
        while self.pos < len(self.text) and self.text[self.pos] in " \t\n\r":
            if self.text[self.pos] == "\n":
                self.line += 1
            self.pos += 1

    def skip_line(self):
        while self.pos < len(self.text) and self.text[self.pos] != "\n":
            self.pos += 1
        if self.pos < len(self.text):
            self.line += 1
            self.pos += 1

    # -- token readers ------------------------------------------------------

    def expect(self, c: str):
        self.skip_ws()
        if self.at_end() or self.text[self.pos] != c:
            got = self.text[self.pos] if not self.at_end() else "EOF"
            raise SyntaxError(f"Expected '{c}', got '{got}' at line {self.line}")
        self.advance()

    def read_until(self, stop: str) -> str:
        start = self.pos
        while self.pos < len(self.text) and self.text[self.pos] not in stop:
            if self.text[self.pos] == "\n":
                self.line += 1
            self.pos += 1
        return self.text[start : self.pos]

    def read_word(self) -> str:
        """Read a contiguous word (stops at whitespace / special chars)."""
        start = self.pos
        while (
            self.pos < len(self.text) and self.text[self.pos] not in " \t\n\r(){}[],\\:"
        ):
            self.pos += 1
        return self.text[start : self.pos]

    def peek_word(self) -> str:
        """Peek at the next word without consuming."""
        saved_pos, saved_line = self.pos, self.line
        self.skip_ws()
        w = self.read_word()
        self.pos, self.line = saved_pos, saved_line
        return w

    def lookahead(self, s: str) -> bool:
        """Check if text at current position starts with *s*."""
        return self.text[self.pos : self.pos + len(s)] == s

    def read_string(self) -> str:
        """Read a double-quoted string literal; returns content."""
        self.expect('"')
        parts: list[str] = []
        while not self.at_end():
            c = self.text[self.pos]
            if c == '"':
                self.pos += 1
                return "".join(parts)
            if c == "\\":
                self.pos += 1
                if self.at_end():
                    break
                nc = self.text[self.pos]
                if nc == "n":
                    parts.append("\n")
                elif nc == "t":
                    parts.append("\t")
                elif nc == "\\":
                    parts.append("\\")
                elif nc == '"':
                    parts.append('"')
                elif nc == "x":
                    self.pos += 1
                    hx = self.text[self.pos : self.pos + 2]
                    parts.append(chr(int(hx, 16)))
                    self.pos += 1  # second hex digit consumed by advance below
                else:
                    parts.append("\\")
                    parts.append(nc)
                self.pos += 1
            else:
                parts.append(c)
                if c == "\n":
                    self.line += 1
                self.pos += 1
        raise SyntaxError(f"Unterminated string at line {self.line}")
