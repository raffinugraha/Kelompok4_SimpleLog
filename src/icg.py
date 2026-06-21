# ============================================================
#  SimpleLog Compiler — Kelompok 4
#  Modul  : ICG — Intermediate Code Generator (Three Address Code)
#  Tugas  : Teknik Kompilasi 2025
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from scanner import Scanner
from parser import (
    Parser, ASTNode, ProgramNode,
    DeclarationNode, AssignmentNode, IfNode, PrintNode,
    BinaryOpNode, UnaryOpNode, LiteralNode, IdentifierNode,
)
from semantic import SemanticAnalyzer


# ------------------------------------------------------------------
# 1. STRUKTUR INSTRUKSI TAC
# ------------------------------------------------------------------

@dataclass
class TACInstruction:
    """
    Satu instruksi Three Address Code.

    Format:
        result = arg1 op arg2    → BinaryOp
        result = op arg1         → UnaryOp  (NOT)
        result = arg1            → Copy / Assign
        if arg1 goto label       → CondJump
        goto label               → Jump
        label:                   → Label
        print arg1               → Print
    """
    op      : str             # operator atau instruksi
    arg1    : str  = ''       # operand pertama
    arg2    : str  = ''       # operand kedua (opsional)
    result  : str  = ''       # tempat hasil (opsional)

    def __str__(self) -> str:
        # Label
        if self.op == 'LABEL':
            return f"{self.result}:"

        # Jump tanpa syarat
        if self.op == 'GOTO':
            return f"    goto {self.result}"

        # Jump bersyarat
        if self.op == 'IF_GOTO':
            return f"    if {self.arg1} goto {self.result}"

        # Jump bersyarat TIDAK (ifFalse)
        if self.op == 'IFFALSE_GOTO':
            return f"    ifFalse {self.arg1} goto {self.result}"

        # Print
        if self.op == 'PRINT':
            return f"    print {self.arg1}"

        # Copy
        if self.op == 'COPY':
            return f"    {self.result} = {self.arg1}"

        # Unary (NOT)
        if self.op == 'NOT':
            return f"    {self.result} = NOT {self.arg1}"

        # Binary (AND, OR)
        return f"    {self.result} = {self.arg1} {self.op} {self.arg2}"


# ------------------------------------------------------------------
# 2. ICG — INTERMEDIATE CODE GENERATOR
# ------------------------------------------------------------------

class ICG:
    """
    Menghasilkan Three Address Code dari AST SimpleLog.

    Teknik:
      - Temporary variables  : t0, t1, t2, ...
      - Label                : L0, L1, L2, ...
      - Short-circuit eval   : AND/OR menggunakan jump bersyarat
        sehingga sisi kanan tidak dievaluasi jika tidak perlu.

    Cara pakai:
        icg    = ICG()
        code   = icg.generate(ast)
        icg.print_code()
    """

    def __init__(self):
        self.instructions : list[TACInstruction] = []
        self._temp_count  : int = 0
        self._label_count : int = 0

    # ── helper ────────────────────────────────────────────────────

    def _new_temp(self) -> str:
        """Buat nama temporary variable baru: t0, t1, ..."""
        name = f"t{self._temp_count}"
        self._temp_count += 1
        return name

    def _new_label(self) -> str:
        """Buat nama label baru: L0, L1, ..."""
        name = f"L{self._label_count}"
        self._label_count += 1
        return name

    def _emit(self, op: str, arg1='', arg2='', result=''):
        """Tambahkan satu instruksi TAC ke daftar."""
        self.instructions.append(TACInstruction(op=op, arg1=arg1,
                                                 arg2=arg2, result=result))

    # ── entry point ───────────────────────────────────────────────

    def generate(self, node: ASTNode) -> list[TACInstruction]:
        """Generate TAC dari root AST. Kembalikan daftar instruksi."""
        self._visit(node)
        return self.instructions

    # ── dispatcher ────────────────────────────────────────────────

    def _visit(self, node: ASTNode) -> str:
        """
        Kunjungi node dan kembalikan nama variabel/temp
        yang menyimpan hasilnya (untuk ekspresi).
        Statement mengembalikan string kosong.
        """
        method = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method, None)
        if visitor is None:
            raise NotImplementedError(f"ICG belum support: {type(node).__name__}")
        return visitor(node)

    # ── visitor statement ─────────────────────────────────────────

    def _visit_ProgramNode(self, node: ProgramNode) -> str:
        for stmt in node.statements:
            self._visit(stmt)
        return ''

    def _visit_DeclarationNode(self, node: DeclarationNode) -> str:
        """boolean x = <expr>  →  t0 = ...; x = t0"""
        src = self._visit(node.value)
        self._emit('COPY', arg1=src, result=node.name)
        return ''

    def _visit_AssignmentNode(self, node: AssignmentNode) -> str:
        """x = <expr>  →  t0 = ...; x = t0"""
        src = self._visit(node.value)
        self._emit('COPY', arg1=src, result=node.name)
        return ''

    def _visit_PrintNode(self, node: PrintNode) -> str:
        """print(<expr>)  →  print t0"""
        src = self._visit(node.value)
        self._emit('PRINT', arg1=src)
        return ''

    def _visit_IfNode(self, node: IfNode) -> str:
        """
        if (<cond>) { then } else { else }

        TAC yang dihasilkan:
            <kode evaluasi kondisi → t0>
            ifFalse t0 goto L_else
            <kode then>
            goto L_end
          L_else:
            <kode else>          (jika ada)
          L_end:
        """
        cond   = self._visit(node.condition)
        l_else = self._new_label()
        l_end  = self._new_label()

        # Lompat ke else jika kondisi FALSE
        self._emit('IFFALSE_GOTO', arg1=cond, result=l_else)

        # Blok then
        for stmt in node.then_branch:
            self._visit(stmt)

        # Lompat ke end (lewati else)
        self._emit('GOTO', result=l_end)

        # Label else
        self._emit('LABEL', result=l_else)

        # Blok else (jika ada)
        if node.else_branch:
            for stmt in node.else_branch:
                self._visit(stmt)

        # Label end
        self._emit('LABEL', result=l_end)
        return ''

    # ── visitor ekspresi ──────────────────────────────────────────

    def _visit_LiteralNode(self, node: LiteralNode) -> str:
        """true/false  →  t0 = true"""
        tmp = self._new_temp()
        val = 'true' if node.value else 'false'
        self._emit('COPY', arg1=val, result=tmp)
        return tmp

    def _visit_IdentifierNode(self, node: IdentifierNode) -> str:
        """Identifier langsung dikembalikan namanya (tidak perlu temp baru)."""
        return node.name

    def _visit_UnaryOpNode(self, node: UnaryOpNode) -> str:
        """NOT <operand>  →  t1 = NOT t0"""
        operand = self._visit(node.operand)
        tmp     = self._new_temp()
        self._emit('NOT', arg1=operand, result=tmp)
        return tmp

    def _visit_BinaryOpNode(self, node: BinaryOpNode) -> str:
        """
        Short-circuit evaluation:

        AND:
            eval left → tL
            ifFalse tL goto L_false
            eval right → tR
            ifFalse tR goto L_false
            result = true
            goto L_end
          L_false:
            result = false
          L_end:

        OR:
            eval left → tL
            if tL goto L_true
            eval right → tR
            if tR goto L_true
            result = false
            goto L_end
          L_true:
            result = true
          L_end:
        """
        result = self._new_temp()

        if node.op == 'AND':
            l_false = self._new_label()
            l_end   = self._new_label()

            tL = self._visit(node.left)
            self._emit('IFFALSE_GOTO', arg1=tL, result=l_false)

            tR = self._visit(node.right)
            self._emit('IFFALSE_GOTO', arg1=tR, result=l_false)

            self._emit('COPY', arg1='true',  result=result)
            self._emit('GOTO', result=l_end)

            self._emit('LABEL', result=l_false)
            self._emit('COPY',  arg1='false', result=result)

            self._emit('LABEL', result=l_end)

        elif node.op == 'OR':
            l_true = self._new_label()
            l_end  = self._new_label()

            tL = self._visit(node.left)
            self._emit('IF_GOTO', arg1=tL, result=l_true)

            tR = self._visit(node.right)
            self._emit('IF_GOTO', arg1=tR, result=l_true)

            self._emit('COPY', arg1='false', result=result)
            self._emit('GOTO', result=l_end)

            self._emit('LABEL', result=l_true)
            self._emit('COPY',  arg1='true',  result=result)

            self._emit('LABEL', result=l_end)

        return result


# ------------------------------------------------------------------
# 3. UTILITAS — CETAK TAC
# ------------------------------------------------------------------

def print_tac(instructions: list[TACInstruction]):
    print(f"\n{'─'*48}")
    print(f"  Three Address Code (TAC)")
    print(f"{'─'*48}")
    for i, instr in enumerate(instructions):
        line_num = f"{i:>3}:"
        print(f"{line_num}  {instr}")
    print(f"{'─'*48}")
    print(f"  Total instruksi: {len(instructions)}")


# ------------------------------------------------------------------
# 4. PROGRAM UTAMA — UJI COBA
# ------------------------------------------------------------------

if __name__ == '__main__':

    def run_test(title: str, source: str):
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
        print(f"\nSource:\n{source}")

        # Pipeline: Scanner → Parser → Semantic → ICG
        tokens   = Scanner(source).tokenize()
        parser   = Parser(tokens)
        ast      = parser.parse()

        if parser.errors:
            print("Parser error — ICG dibatalkan.")
            return

        analyzer = SemanticAnalyzer()
        ok       = analyzer.analyze(ast)

        if not ok:
            print("Semantic error — ICG dibatalkan.")
            return

        icg  = ICG()
        code = icg.generate(ast)
        print_tac(code)

    # ── Test 1: program dasar dari soal ──────────────────────────
    run_test("TEST 1 — Program Dasar", """\
boolean a = true;
boolean b = false;
if (a AND NOT b) {
    print(a);
} else {
    print(b);
}
""")

    # ── Test 2: OR dengan short-circuit ──────────────────────────
    run_test("TEST 2 — Short-circuit OR", """\
boolean x = false;
boolean y = true;
boolean z = x OR y;
print(z);
""")

    # ── Test 3: ekspresi kompleks ─────────────────────────────────
    run_test("TEST 3 — Ekspresi Kompleks", """\
boolean p = true;
boolean q = false;
boolean r = p OR q AND NOT p;
if ((p OR q) AND NOT r) {
    print(p);
} else {D
    print(r);
}
""")