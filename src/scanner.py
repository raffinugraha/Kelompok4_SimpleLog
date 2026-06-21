# ============================================================
#  SimpleLog Compiler — Kelompok 4
#  Modul  : Scanner (Lexical Analyzer)
#  Tugas  : Teknik Kompilasi 2025
# ============================================================

from enum import Enum, auto
from dataclasses import dataclass


# ------------------------------------------------------------------
# 1. DEFINISI TOKEN
# ------------------------------------------------------------------

class TokenType(Enum):
    # Tipe data & literal
    BOOLEAN     = auto()   # keyword 'boolean'
    TRUE        = auto()   # keyword 'true'
    FALSE       = auto()   # keyword 'false'

    # Operator logika
    AND         = auto()   # keyword 'AND'
    OR          = auto()   # keyword 'OR'
    NOT         = auto()   # keyword 'NOT'

    # Pernyataan
    IF          = auto()   # keyword 'if'
    ELSE        = auto()   # keyword 'else'
    PRINT       = auto()   # keyword 'print'

    # Simbol
    ASSIGN      = auto()   # =
    SEMICOLON   = auto()   # ;
    LPAREN      = auto()   # (
    RPAREN      = auto()   # )
    LBRACE      = auto()   # {
    RBRACE      = auto()   # }

    # Identifier & lainnya
    IDENTIFIER  = auto()   # nama variabel
    COMMENT     = auto()   # -- komentar
    EOF         = auto()   # akhir file


# Pemetaan keyword → TokenType
KEYWORDS = {
    'boolean' : TokenType.BOOLEAN,
    'true'    : TokenType.TRUE,
    'false'   : TokenType.FALSE,
    'AND'     : TokenType.AND,
    'OR'      : TokenType.OR,
    'NOT'     : TokenType.NOT,
    'if'      : TokenType.IF,
    'else'    : TokenType.ELSE,
    'print'   : TokenType.PRINT,
}

# Pemetaan simbol tunggal → TokenType
SYMBOLS = {
    '=' : TokenType.ASSIGN,
    ';' : TokenType.SEMICOLON,
    '(' : TokenType.LPAREN,
    ')' : TokenType.RPAREN,
    '{' : TokenType.LBRACE,
    '}' : TokenType.RBRACE,
}


# ------------------------------------------------------------------
# 2. KELAS TOKEN
# ------------------------------------------------------------------

@dataclass
class Token:
    type    : TokenType
    value   : str
    line    : int
    column  : int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, line={self.line}, col={self.column})"


# ------------------------------------------------------------------
# 3. KELAS ERROR LEKSIKAL
# ------------------------------------------------------------------

class LexicalError(Exception):
    def __init__(self, message, line, column):
        super().__init__(f"[Baris {line}, Kolom {column}] Error Leksikal: {message}")
        self.line   = line
        self.column = column


# ------------------------------------------------------------------
# 4. KELAS SCANNER
# ------------------------------------------------------------------

class Scanner:
    """
    Mengubah source code SimpleLog menjadi daftar token.

    Cara pakai:
        scanner = Scanner(source_code)
        tokens  = scanner.tokenize()
    """

    def __init__(self, source: str):
        self.source  = source
        self.pos     = 0          # posisi karakter saat ini
        self.line    = 1          # baris saat ini
        self.column  = 1          # kolom saat ini
        self.tokens  = []
        self.errors  = []

    # ── helper ────────────────────────────────────────────────────

    def _current(self) -> str:
        """Karakter di posisi sekarang, atau '' jika sudah habis."""
        return self.source[self.pos] if self.pos < len(self.source) else ''

    def _peek(self, offset=1) -> str:
        """Intip karakter ke depan tanpa memajukan posisi."""
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ''

    def _advance(self) -> str:
        """Ambil karakter sekarang dan majukan posisi."""
        ch = self.source[self.pos]
        self.pos    += 1
        self.column += 1
        if ch == '\n':
            self.line  += 1
            self.column = 1
        return ch

    def _add_token(self, ttype: TokenType, value: str, line: int, col: int):
        self.tokens.append(Token(ttype, value, line, col))

    # ── metode utama ───────────────────────────────────────────────

    def tokenize(self) -> list[Token]:
        """
        Jalankan scanner dan kembalikan daftar token.
        Token EOF selalu ditambahkan di akhir.
        """
        while self.pos < len(self.source):
            self._scan_token()

        self._add_token(TokenType.EOF, '', self.line, self.column)
        return self.tokens

    def _scan_token(self):
        """Baca satu token dari posisi sekarang."""
        line = self.line
        col  = self.column
        ch   = self._current()

        # 1. Lewati whitespace
        if ch in ' \t\r\n':
            self._advance()
            return

        # 2. Komentar -- (dua tanda minus)
        if ch == '-' and self._peek() == '-':
            self._scan_comment(line, col)
            return

        # 3. Simbol tunggal
        if ch in SYMBOLS:
            self._advance()
            self._add_token(SYMBOLS[ch], ch, line, col)
            return

        # 4. Identifier atau keyword
        if ch.isalpha() or ch == '_':
            self._scan_identifier(line, col)
            return

        # 5. Karakter tidak dikenal → error leksikal
        self._advance()
        err = LexicalError(f"Karakter tidak dikenal: '{ch}'", line, col)
        self.errors.append(err)
        print(err)   # tampilkan error tapi lanjutkan scanning

    def _scan_comment(self, line: int, col: int):
        """Baca komentar dari -- hingga akhir baris."""
        value = ''
        while self._current() and self._current() != '\n':
            value += self._advance()
        self._add_token(TokenType.COMMENT, value, line, col)

    def _scan_identifier(self, line: int, col: int):
        """Baca identifier dan tentukan apakah keyword atau nama variabel."""
        value = ''
        while self._current().isalnum() or self._current() == '_':
            value += self._advance()

        ttype = KEYWORDS.get(value, TokenType.IDENTIFIER)
        self._add_token(ttype, value, line, col)


# ------------------------------------------------------------------
# 5. FUNGSI UTILITAS — TAMPILKAN TOKEN
# ------------------------------------------------------------------

def print_tokens(tokens: list[Token]):
    """Cetak daftar token dalam format tabel."""
    print(f"\n{'─'*60}")
    print(f"{'No':<4} {'Tipe':<18} {'Nilai':<16} {'Baris':<7} {'Kolom'}")
    print(f"{'─'*60}")
    for i, tok in enumerate(tokens, 1):
        print(f"{i:<4} {tok.type.name:<18} {tok.value!r:<16} {tok.line:<7} {tok.column}")
    print(f"{'─'*60}")
    print(f"Total: {len(tokens)} token\n")


# ------------------------------------------------------------------
# 6. PROGRAM UTAMA — UJI COBA
# ------------------------------------------------------------------

if __name__ == '__main__':
    # Contoh kode SimpleLog sesuai soal
    source_code = """\
-- contoh program SimpleLog
boolean a = true;
boolean b = false;
if (a AND NOT b) {
    print(a);
} else {
    print(b);
}
"""

    print("=" * 60)
    print("  SimpleLog Scanner — Kelompok 4")
    print("=" * 60)
    print("\nSource code:")
    print(source_code)

    scanner = Scanner(source_code)
    tokens  = scanner.tokenize()

    print_tokens(tokens)

    if scanner.errors:
        print(f"Ditemukan {len(scanner.errors)} error leksikal.")
    else:
        print("Scanning berhasil. Tidak ada error leksikal.")