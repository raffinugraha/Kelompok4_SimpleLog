# ============================================================
#  SimpleLog Compiler — Kelompok 4
#  Modul  : Semantic Analyzer
#  Tugas  : Teknik Kompilasi 2025
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from scanner import Scanner
from parser import (
    Parser, ASTNode, ProgramNode,
    DeclarationNode, AssignmentNode, IfNode, PrintNode,
    BinaryOpNode, UnaryOpNode, LiteralNode, IdentifierNode,
)


# ------------------------------------------------------------------
# 1. SYMBOL TABLE
# ------------------------------------------------------------------

@dataclass
class Symbol:
    """Satu entri di symbol table."""
    name       : str
    type_      : str        # saat ini selalu 'boolean'
    declared_at: int        # baris deklarasi
    initialized: bool = False


class SymbolTable:
    """
    Tabel simbol satu-scope (SimpleLog tidak punya fungsi/scope nested).
    Mendukung lookup, insert, dan dump untuk laporan.
    """

    def __init__(self):
        self._table: dict[str, Symbol] = {}

    def declare(self, name: str, type_: str, line: int) -> Optional[str]:
        """
        Daftarkan variabel baru.
        Kembalikan pesan error jika sudah dideklarasikan sebelumnya.
        """
        if name in self._table:
            prev = self._table[name]
            return (f"Variabel '{name}' sudah dideklarasikan "
                    f"di baris {prev.declared_at}")
        self._table[name] = Symbol(name=name, type_=type_, declared_at=line)
        return None

    def mark_initialized(self, name: str):
        if name in self._table:
            self._table[name].initialized = True

    def lookup(self, name: str) -> Optional[Symbol]:
        return self._table.get(name)

    def dump(self):
        """Cetak isi symbol table."""
        if not self._table:
            print("  (kosong)")
            return
        print(f"  {'Nama':<16} {'Tipe':<10} {'Baris':<8} {'Terinit'}")
        print(f"  {'─'*44}")
        for sym in self._table.values():
            init = 'ya' if sym.initialized else 'tidak'
            print(f"  {sym.name:<16} {sym.type_:<10} {sym.declared_at:<8} {init}")


# ------------------------------------------------------------------
# 2. KELAS ERROR SEMANTIK
# ------------------------------------------------------------------

class SemanticError(Exception):
    def __init__(self, message: str, line: int, col: int = 0):
        super().__init__(f"[Baris {line}] Error Semantik: {message}")
        self.line = line
        self.col  = col


# ------------------------------------------------------------------
# 3. SEMANTIC ANALYZER
# ------------------------------------------------------------------

class SemanticAnalyzer:
    """
    Melakukan dua hal utama:
      1. Mengisi symbol table dari setiap DeclarationNode.
      2. Memeriksa setiap IdentifierNode:
         - sudah dideklarasikan?
         - sudah diinisialisasi?
         - tipe cocok? (semua harus boolean di SimpleLog)

    Cara pakai:
        analyzer = SemanticAnalyzer()
        analyzer.analyze(ast)
        analyzer.symbol_table.dump()
    """

    def __init__(self):
        self.symbol_table = SymbolTable()
        self.errors: list[SemanticError] = []

    # ── entry point ───────────────────────────────────────────────

    def analyze(self, node: ASTNode) -> bool:
        """
        Jalankan analisis semantik pada AST.
        Kembalikan True jika tidak ada error.
        """
        self._visit(node)
        return len(self.errors) == 0

    # ── dispatcher ────────────────────────────────────────────────

    def _visit(self, node: ASTNode) -> Optional[str]:
        """
        Kunjungi satu node AST.
        Kembalikan tipe ekspresi ('boolean') atau None untuk statement.
        """
        method = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method, self._visit_unknown)
        return visitor(node)

    def _visit_unknown(self, node: ASTNode):
        print(f"  [peringatan] Node tidak dikenal: {type(node).__name__}")

    # ── visitor per node ──────────────────────────────────────────

    def _visit_ProgramNode(self, node: ProgramNode):
        for stmt in node.statements:
            self._visit(stmt)

    def _visit_DeclarationNode(self, node: DeclarationNode):
        # 1. Periksa nilai kanan dulu
        val_type = self._visit(node.value)

        # 2. Cek tipe nilai harus boolean
        if val_type and val_type != 'boolean':
            self._report(
                f"Tipe tidak cocok: variabel '{node.name}' "
                f"bertipe 'boolean' tapi nilai bertipe '{val_type}'",
                node.line
            )

        # 3. Daftarkan ke symbol table
        err = self.symbol_table.declare(node.name, 'boolean', node.line)
        if err:
            self._report(err, node.line)
        else:
            self.symbol_table.mark_initialized(node.name)

    def _visit_AssignmentNode(self, node: AssignmentNode):
        # 1. Variabel harus sudah dideklarasikan
        sym = self.symbol_table.lookup(node.name)
        if sym is None:
            self._report(
                f"Variabel '{node.name}' belum dideklarasikan",
                node.line
            )
            self._visit(node.value)
            return

        # 2. Periksa nilai kanan
        val_type = self._visit(node.value)

        # 3. Cek tipe cocok
        if val_type and val_type != sym.type_:
            self._report(
                f"Tipe tidak cocok pada assignment '{node.name}': "
                f"diharapkan '{sym.type_}', ditemukan '{val_type}'",
                node.line
            )

        self.symbol_table.mark_initialized(node.name)

    def _visit_IfNode(self, node: IfNode):
        # Kondisi harus bertipe boolean
        cond_type = self._visit(node.condition)
        if cond_type and cond_type != 'boolean':
            self._report(
                f"Kondisi 'if' harus bertipe 'boolean', "
                f"ditemukan '{cond_type}'",
                node.line
            )

        for stmt in node.then_branch:
            self._visit(stmt)

        if node.else_branch:
            for stmt in node.else_branch:
                self._visit(stmt)

    def _visit_PrintNode(self, node: PrintNode):
        self._visit(node.value)

    def _visit_BinaryOpNode(self, node: BinaryOpNode) -> str:
        left_type  = self._visit(node.left)
        right_type = self._visit(node.right)

        # AND / OR hanya berlaku untuk boolean
        for side, t in [('kiri', left_type), ('kanan', right_type)]:
            if t and t != 'boolean':
                self._report(
                    f"Operand {side} operator '{node.op}' "
                    f"harus 'boolean', ditemukan '{t}'",
                    node.line
                )
        return 'boolean'

    def _visit_UnaryOpNode(self, node: UnaryOpNode) -> str:
        operand_type = self._visit(node.operand)
        if operand_type and operand_type != 'boolean':
            self._report(
                f"Operand 'NOT' harus 'boolean', "
                f"ditemukan '{operand_type}'",
                node.line
            )
        return 'boolean'

    def _visit_LiteralNode(self, node: LiteralNode) -> str:
        return 'boolean'

    def _visit_IdentifierNode(self, node: IdentifierNode) -> str:
        sym = self.symbol_table.lookup(node.name)

        # Belum dideklarasikan sama sekali
        if sym is None:
            self._report(
                f"Variabel '{node.name}' belum dideklarasikan",
                node.line
            )
            return 'boolean'    # asumsikan boolean agar analisis lanjut

        # Dideklarasikan tapi belum diinisialisasi
        if not sym.initialized:
            self._report(
                f"Variabel '{node.name}' digunakan sebelum diinisialisasi",
                node.line
            )

        return sym.type_

    # ── helper ────────────────────────────────────────────────────

    def _report(self, message: str, line: int, col: int = 0):
        err = SemanticError(message, line, col)
        self.errors.append(err)
        print(err)


# ------------------------------------------------------------------
# 4. FUNGSI UTILITAS — LAPORAN LENGKAP
# ------------------------------------------------------------------

def print_semantic_report(analyzer: SemanticAnalyzer):
    print("\nSymbol Table:")
    analyzer.symbol_table.dump()

    print(f"\nTotal error semantik : {len(analyzer.errors)}")
    if not analyzer.errors:
        print("Analisis semantik berhasil.")


# ------------------------------------------------------------------
# 5. PROGRAM UTAMA — UJI COBA
# ------------------------------------------------------------------

if __name__ == '__main__':

    def run_test(title: str, source: str):
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
        print(f"\nSource:\n{source}")

        tokens   = Scanner(source).tokenize()
        parser   = Parser(tokens)
        ast      = parser.parse()

        if parser.errors:
            print(f"[Parser] {len(parser.errors)} error sintaks ditemukan, analisis dibatalkan.")
            return

        analyzer = SemanticAnalyzer()
        analyzer.analyze(ast)
        print_semantic_report(analyzer)

    # ── Test 1: program normal (tidak ada error) ──────────────────
    run_test("TEST 1 — Program Normal", """\
boolean a = true;
boolean b = false;
if (a AND NOT b) {
    print(a);
} else {
    print(b);
}
""")

    # ── Test 2: variabel tidak dideklarasikan ─────────────────────
    run_test("TEST 2 — Variabel Tidak Dideklarasikan", """\
boolean a = true;
if (a AND b) {
    print(a);
}
""")

    # ── Test 3: deklarasi ganda ───────────────────────────────────
    run_test("TEST 3 — Deklarasi Ganda", """\
boolean x = true;
boolean x = false;
print(x);
""")

    # ── Test 4: ekspresi kompleks benar ───────────────────────────
    run_test("TEST 4 — Ekspresi Kompleks", """\
boolean p = true;
boolean q = false;
boolean r = p OR q AND NOT p;
if ((p OR q) AND NOT r) {
    print(r);
} else {
    print(p);
}
""")

    # ── Test 5: assignment ke variabel yang belum dideklarasikan ──
    run_test("TEST 5 — Assignment Tanpa Deklarasi", """\
boolean a = true;
b = false;
print(a);
""")