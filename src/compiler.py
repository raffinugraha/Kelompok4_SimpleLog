# ============================================================
#  SimpleLog Compiler — Kelompok 4
#  Modul  : Error Handling + Main Compiler (CLI)
#  Tugas  : Teknik Kompilasi 2025
#
#  Cara pakai:
#      python compiler.py program.sl
#      python compiler.py program.sl --tokens
#      python compiler.py program.sl --ast
#      python compiler.py program.sl --tac
#      python compiler.py program.sl --optimize
#      python compiler.py program.sl --all
# ============================================================

from __future__ import annotations
import sys
import argparse
from dataclasses import dataclass
from enum import Enum, auto

from scanner  import Scanner,  LexicalError
from parser   import Parser,   SyntaxError_, print_ast
from semantic import SemanticAnalyzer, SemanticError
from icg      import ICG,      print_tac
from optimizer import Optimizer


# ------------------------------------------------------------------
# 1. KATEGORI & SEVERITY ERROR
# ------------------------------------------------------------------

class ErrorPhase(Enum):
    LEXICAL  = "Leksikal"
    SYNTAX   = "Sintaks"
    SEMANTIC = "Semantik"
    INTERNAL = "Internal"


class Severity(Enum):
    ERROR   = auto()
    WARNING = auto()


# ------------------------------------------------------------------
# 2. KELAS ERROR TERPADU
# ------------------------------------------------------------------

@dataclass
class CompilerError:
    """Satu error yang dinormalisasi dari fase mana pun."""
    phase    : ErrorPhase
    severity : Severity
    message  : str
    line     : int
    col      : int = 0

    def __str__(self) -> str:
        loc      = f"baris {self.line}" + (f", kolom {self.col}" if self.col else "")
        sev      = "ERROR" if self.severity == Severity.ERROR else "PERINGATAN"
        return (f"  [{sev}] [{self.phase.value}] {loc}\n"
                f"  └─ {self.message}")


# ------------------------------------------------------------------
# 3. ERROR REPORTER — PENGUMPUL & PENCETAK ERROR
# ------------------------------------------------------------------

class ErrorReporter:
    """
    Mengumpulkan semua error dari semua fase kompilasi,
    lalu mencetak laporan yang rapi dan informatif.
    """

    def __init__(self, source: str):
        self.source  = source.splitlines()
        self.errors  : list[CompilerError] = []

    # ── tambah error ──────────────────────────────────────────────

    def add(self, phase: ErrorPhase, message: str,
            line: int, col: int = 0,
            severity: Severity = Severity.ERROR):
        self.errors.append(CompilerError(
            phase=phase, severity=severity,
            message=message, line=line, col=col
        ))

    def add_lexical (self, e: LexicalError):
        self.add(ErrorPhase.LEXICAL,  str(e.args[0]).split(": ", 1)[-1],
                 e.line, e.column)

    def add_syntax  (self, e: SyntaxError_):
        # Ambil pesan setelah "Error Sintaks: "
        msg = str(e).split("Error Sintaks: ", 1)[-1]
        self.add(ErrorPhase.SYNTAX,   msg, e.line, e.col)

    def add_semantic(self, e: SemanticError):
        msg = str(e).split("Error Semantik: ", 1)[-1]
        self.add(ErrorPhase.SEMANTIC, msg, e.line, e.col)

    # ── properti ──────────────────────────────────────────────────

    @property
    def has_errors(self) -> bool:
        return any(e.severity == Severity.ERROR for e in self.errors)

    @property
    def count(self) -> int:
        return len(self.errors)

    # ── cetak laporan ─────────────────────────────────────────────

    def print_report(self):
        if not self.errors:
            _print_ok("Tidak ada error ditemukan.")
            return

        # Kelompokkan per fase
        phases = [ErrorPhase.LEXICAL, ErrorPhase.SYNTAX, ErrorPhase.SEMANTIC]
        for phase in phases:
            phase_errs = [e for e in self.errors if e.phase == phase]
            if not phase_errs:
                continue

            _print_section(f"Error {phase.value} ({len(phase_errs)})")
            for err in phase_errs:
                print(err)
                self._print_source_context(err.line, err.col)
                print()

        # Ringkasan
        n_err  = sum(1 for e in self.errors if e.severity == Severity.ERROR)
        n_warn = sum(1 for e in self.errors if e.severity == Severity.WARNING)
        print(f"  {'─'*48}")
        parts = []
        if n_err:  parts.append(f"{n_err} error")
        if n_warn: parts.append(f"{n_warn} peringatan")
        print(f"  Ringkasan: {', '.join(parts)} ditemukan.")

    def _print_source_context(self, line: int, col: int):
        """Tampilkan baris source code tempat error terjadi + penunjuk kolom."""
        if line < 1 or line > len(self.source):
            return
        src_line = self.source[line - 1]
        print(f"      {line:>4} │ {src_line}")
        if col > 0:
            pointer = " " * (col - 1) + "^"
            print(f"           │ {pointer}")


# ------------------------------------------------------------------
# 4. COMPILER — ORKESTRASI SEMUA FASE
# ------------------------------------------------------------------

class SimpleLogCompiler:
    """
    Pipeline lengkap kompiler SimpleLog:
      Scanner → Parser → Semantic → ICG → Optimizer

    Tiap fase berhenti jika fase sebelumnya menghasilkan error
    (tidak ada gunanya melanjutkan ke fase berikutnya).
    """

    def __init__(self, source: str):
        self.source   = source
        self.reporter = ErrorReporter(source)

        # Hasil tiap fase (None = belum dijalankan / gagal)
        self.tokens   = None
        self.ast      = None
        self.symbol_table = None
        self.tac      = None
        self.tac_opt  = None
        self.optimizer_stats = None

    # ── jalankan pipeline ─────────────────────────────────────────

    def compile(self, optimize: bool = True) -> bool:
        """
        Jalankan seluruh pipeline.
        Kembalikan True jika berhasil tanpa error.
        """
        return (
            self._phase_scan()
            and self._phase_parse()
            and self._phase_semantic()
            and self._phase_icg()
            and (not optimize or self._phase_optimize())
        )

    def _phase_scan(self) -> bool:
        _print_phase("1/5  Scanning...")
        scanner     = Scanner(self.source)
        self.tokens = scanner.tokenize()

        for err in scanner.errors:
            self.reporter.add_lexical(err)

        if self.reporter.has_errors:
            _print_fail("Scanning gagal.")
            return False

        _print_ok(f"Scanning selesai — {len(self.tokens)} token.")
        return True

    def _phase_parse(self) -> bool:
        _print_phase("2/5  Parsing...")
        parser   = Parser(self.tokens)
        self.ast = parser.parse()

        for err in parser.errors:
            self.reporter.add_syntax(err)

        if self.reporter.has_errors:
            _print_fail("Parsing gagal.")
            return False

        _print_ok("Parsing selesai — AST berhasil dibangun.")
        return True

    def _phase_semantic(self) -> bool:
        _print_phase("3/5  Analisis semantik...")
        analyzer          = SemanticAnalyzer()
        analyzer.analyze(self.ast)
        self.symbol_table = analyzer.symbol_table

        for err in analyzer.errors:
            self.reporter.add_semantic(err)

        if self.reporter.has_errors:
            _print_fail("Analisis semantik gagal.")
            return False

        n_sym = len(analyzer.symbol_table._table)
        _print_ok(f"Semantik selesai — {n_sym} variabel terdaftar.")
        return True

    def _phase_icg(self) -> bool:
        _print_phase("4/5  Generasi kode antara (TAC)...")
        icg      = ICG()
        self.tac = icg.generate(self.ast)
        _print_ok(f"ICG selesai — {len(self.tac)} instruksi TAC.")
        return True

    def _phase_optimize(self) -> bool:
        _print_phase("5/5  Optimasi...")
        opt          = Optimizer()
        self.tac_opt = opt.optimize(self.tac)
        self.optimizer_stats = opt

        saved = len(self.tac) - len(self.tac_opt)
        pct   = (saved / len(self.tac) * 100) if self.tac else 0
        _print_ok(
            f"Optimasi selesai — {len(self.tac_opt)} instruksi "
            f"(hemat {saved} / {pct:.0f}%)."
        )
        return True

    # ── tampilkan hasil ───────────────────────────────────────────

    def print_tokens(self):
        if not self.tokens:
            return
        _print_section("Daftar Token")
        print(f"  {'No':<4} {'Tipe':<18} {'Nilai':<16} {'Baris':<7} Kolom")
        print(f"  {'─'*56}")
        for i, tok in enumerate(self.tokens, 1):
            print(f"  {i:<4} {tok.type.name:<18} {tok.value!r:<16}"
                  f" {tok.line:<7} {tok.column}")

    def print_ast(self):
        if not self.ast:
            return
        _print_section("Abstract Syntax Tree (AST)")
        print_ast(self.ast, indent=1)

    def print_tac(self, optimized: bool = False):
        code  = self.tac_opt if (optimized and self.tac_opt) else self.tac
        label = "TAC (setelah optimasi)" if optimized else "TAC (sebelum optimasi)"
        if not code:
            return
        _print_section(label)
        print_tac(code)

    def print_symbol_table(self):
        if not self.symbol_table:
            return
        _print_section("Symbol Table")
        self.symbol_table.dump()


# ------------------------------------------------------------------
# 5. HELPER PRINT
# ------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
DIM    = "\033[2m"


def _print_phase(msg: str):
    print(f"\n{CYAN}{BOLD}▶ {msg}{RESET}")

def _print_ok(msg: str):
    print(f"  {GREEN}✓{RESET} {msg}")

def _print_fail(msg: str):
    print(f"  {RED}✗{RESET} {msg}")

def _print_section(title: str):
    print(f"\n{BOLD}{'─'*52}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─'*52}{RESET}")


# ------------------------------------------------------------------
# 6. CLI — ANTARMUKA BARIS PERINTAH
# ------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog        = "compiler.py",
        description = "SimpleLog Compiler — Kelompok 4 Teknik Kompilasi 2025",
    )
    ap.add_argument("file",
                    nargs   = "?",
                    help    = "File source SimpleLog (.sl) yang akan dikompilasi")
    ap.add_argument("--tokens",   action="store_true",
                    help="Tampilkan daftar token hasil scanning")
    ap.add_argument("--ast",      action="store_true",
                    help="Tampilkan Abstract Syntax Tree")
    ap.add_argument("--tac",      action="store_true",
                    help="Tampilkan TAC sebelum optimasi")
    ap.add_argument("--optimize", action="store_true",
                    help="Jalankan optimasi dan tampilkan TAC sesudahnya")
    ap.add_argument("--all",      action="store_true",
                    help="Tampilkan semua output (tokens, ast, tac, optimize)")
    ap.add_argument("--demo",     action="store_true",
                    help="Jalankan demo dengan kode bawaan (tanpa file)")
    return ap


def main():
    ap   = build_arg_parser()
    args = ap.parse_args()

    # ── mode demo (tanpa file) ────────────────────────────────────
    if args.demo or not args.file:
        _run_demo()
        return

    # ── baca file ─────────────────────────────────────────────────
    try:
        with open(args.file, encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"{RED}Error: File '{args.file}' tidak ditemukan.{RESET}")
        sys.exit(1)

    show_all = args.all
    do_opt   = args.optimize or show_all

    print(f"\n{BOLD}SimpleLog Compiler — Kelompok 4{RESET}")
    print(f"{DIM}File: {args.file}{RESET}")
    print("─" * 52)

    compiler = SimpleLogCompiler(source)
    ok       = compiler.compile(optimize=do_opt)

    # ── tampilkan output sesuai flag ──────────────────────────────
    if args.tokens or show_all:
        compiler.print_tokens()

    if args.ast or show_all:
        compiler.print_ast()

    if args.tac or show_all:
        compiler.print_tac(optimized=False)

    if do_opt:
        compiler.print_tac(optimized=True)
        if compiler.optimizer_stats:
            compiler.optimizer_stats.print_report()

    if show_all:
        compiler.print_symbol_table()

    # ── laporan error ─────────────────────────────────────────────
    _print_section("Laporan Error")
    compiler.reporter.print_report()

    print()
    if ok:
        print(f"{GREEN}{BOLD}Kompilasi BERHASIL.{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}Kompilasi GAGAL.{RESET}\n")
        sys.exit(1)


# ------------------------------------------------------------------
# 7. MODE DEMO — UJI COBA SEMUA JENIS ERROR
# ------------------------------------------------------------------

def _run_demo():
    cases = [
        ("BERHASIL — Program Normal", """\
-- program SimpleLog kelompok 4
boolean a = true;
boolean b = false;
if (a AND NOT b) {
    print(a);
} else {
    print(b);
}
"""),
        ("ERROR LEKSIKAL — Karakter tidak dikenal", """\
boolean a = true;
boolean b = @false;
print(a);
"""),
        ("ERROR SINTAKS — Titik koma hilang & if tanpa kurung", """\
boolean a = true
boolean b = false;
if a AND b {
    print(a);
}
"""),
        ("ERROR SEMANTIK — Variabel belum dideklarasi & deklarasi ganda", """\
boolean a = true;
boolean a = false;
if (a AND z) {
    print(z);
}
"""),
    ]

    for title, source in cases:
        print(f"\n{'═'*56}")
        print(f"  {BOLD}{title}{RESET}")
        print(f"{'═'*56}")
        print(f"\n{DIM}Source:{RESET}\n{source}")

        compiler = SimpleLogCompiler(source)
        ok       = compiler.compile(optimize=True)

        if ok:
            compiler.print_tokens()
            compiler.print_ast()
            compiler.print_tac(optimized=True)
            if compiler.optimizer_stats:
                compiler.optimizer_stats.print_report()
            compiler.print_symbol_table()

        _print_section("Laporan Error")
        compiler.reporter.print_report()

        status = f"{GREEN}{BOLD}BERHASIL{RESET}" if ok else f"{RED}{BOLD}GAGAL{RESET}"
        print(f"\n  Status kompilasi: {status}\n")


if __name__ == '__main__':
    main()