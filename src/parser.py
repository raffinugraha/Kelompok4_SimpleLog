# ============================================================
#  SimpleLog Compiler — Kelompok 4
#  Modul  : Parser + AST Builder
#  Tugas  : Teknik Kompilasi 2025
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from scanner import Scanner, Token, TokenType


# ------------------------------------------------------------------
# 1. NODE-NODE AST
# ------------------------------------------------------------------

# ── Base ──────────────────────────────────────────────────────────

@dataclass
class ASTNode:
    """Kelas dasar semua node AST."""
    line: int = 0
    col:  int = 0


# ── Program ───────────────────────────────────────────────────────

@dataclass
class ProgramNode(ASTNode):
    """Root node — seluruh program."""
    statements: list = field(default_factory=list)


# ── Statement nodes ───────────────────────────────────────────────

@dataclass
class DeclarationNode(ASTNode):
    """boolean <name> = <expr> ;"""
    name:  str     = ''
    value: ASTNode = None


@dataclass
class AssignmentNode(ASTNode):
    """<name> = <expr> ;"""
    name:  str     = ''
    value: ASTNode = None


@dataclass
class IfNode(ASTNode):
    """if (<cond>) { ... } [else { ... }]"""
    condition:   ASTNode         = None
    then_branch: list            = field(default_factory=list)
    else_branch: Optional[list]  = None


@dataclass
class PrintNode(ASTNode):
    """print(<expr>) ;"""
    value: ASTNode = None


# ── Expression nodes ──────────────────────────────────────────────

@dataclass
class BinaryOpNode(ASTNode):
    """<left> AND/OR <right>"""
    op:    str     = ''
    left:  ASTNode = None
    right: ASTNode = None


@dataclass
class UnaryOpNode(ASTNode):
    """NOT <operand>"""
    op:      str     = ''
    operand: ASTNode = None


@dataclass
class LiteralNode(ASTNode):
    """true / false"""
    value: bool = False


@dataclass
class IdentifierNode(ASTNode):
    """nama variabel"""
    name: str = ''


# ------------------------------------------------------------------
# 2. KELAS ERROR SINTAKS
# ------------------------------------------------------------------

class SyntaxError_(Exception):
    """Error sintaks dengan info baris & kolom."""
    def __init__(self, message: str, line: int, col: int):
        super().__init__(f"[Baris {line}, Kolom {col}] Error Sintaks: {message}")
        self.line = line
        self.col  = col


# ------------------------------------------------------------------
# 3. KELAS PARSER
# ------------------------------------------------------------------

class Parser:
    """
    Recursive-descent parser untuk SimpleLog.

    Grammar yang diimplementasikan:
        program      → statement*
        statement    → declaration | assignment | if_stmt | print_stmt
        declaration  → 'boolean' IDENTIFIER '=' bool_expr ';'
        assignment   → IDENTIFIER '=' bool_expr ';'
        if_stmt      → 'if' '(' bool_expr ')' '{' statement* '}'
                       [ 'else' '{' statement* '}' ]
        print_stmt   → 'print' '(' bool_expr ')' ';'
        bool_expr    → bool_term ( 'OR' bool_term )*
        bool_term    → bool_factor ( 'AND' bool_factor )*
        bool_factor  → 'NOT' bool_factor | '(' bool_expr ')' | bool_literal | IDENTIFIER
        bool_literal → 'true' | 'false'
    """

    def __init__(self, tokens: list[Token]):
        # Buang token COMMENT agar tidak mengganggu parsing
        self.tokens  = [t for t in tokens if t.type != TokenType.COMMENT]
        self.pos     = 0
        self.errors  = []

    # ── helper ────────────────────────────────────────────────────

    def _current(self) -> Token:
        return self.tokens[self.pos]

    def _peek(self, offset: int = 1) -> Token:
        idx = self.pos + offset
        return self.tokens[idx] if idx < len(self.tokens) else self.tokens[-1]

    def _advance(self) -> Token:
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def _check(self, *types: TokenType) -> bool:
        return self._current().type in types

    def _match(self, *types: TokenType) -> bool:
        if self._check(*types):
            self._advance()
            return True
        return False

    def _expect(self, ttype: TokenType, msg: str) -> Token:
        """Ambil token dengan tipe tertentu; lempar error jika tidak cocok."""
        if self._check(ttype):
            return self._advance()
        tok = self._current()
        raise SyntaxError_(
            f"{msg} — ditemukan '{tok.value}' ({tok.type.name})",
            tok.line, tok.column
        )

    def _sync(self):
        """
        Panic-mode recovery: lewati token sampai ketemu
        titik awal statement baru agar parsing bisa lanjut.
        """
        while not self._check(TokenType.EOF):
            if self._current().type in (
                TokenType.BOOLEAN, TokenType.IF,
                TokenType.PRINT, TokenType.RBRACE
            ):
                return
            self._advance()

    # ── parse utama ───────────────────────────────────────────────

    def parse(self) -> ProgramNode:
        """Entry point — kembalikan ProgramNode."""
        stmts = []
        while not self._check(TokenType.EOF):
            try:
                stmts.append(self._parse_statement())
            except SyntaxError_ as e:
                self.errors.append(e)
                print(e)
                self._sync()

        return ProgramNode(statements=stmts)

    # ── statement ─────────────────────────────────────────────────

    def _parse_statement(self) -> ASTNode:
        tok = self._current()

        if tok.type == TokenType.BOOLEAN:
            return self._parse_declaration()

        if tok.type == TokenType.IDENTIFIER:
            return self._parse_assignment()

        if tok.type == TokenType.IF:
            return self._parse_if()

        if tok.type == TokenType.PRINT:
            return self._parse_print()

        # Token tidak terduga
        self._advance()
        raise SyntaxError_(
            f"Pernyataan tidak valid dimulai dengan '{tok.value}'",
            tok.line, tok.column
        )

    def _parse_declaration(self) -> DeclarationNode:
        """boolean IDENTIFIER = bool_expr ;"""
        tok = self._advance()                                   # konsumsi 'boolean'
        name_tok = self._expect(TokenType.IDENTIFIER,
                                "Nama variabel diperlukan setelah 'boolean'")
        self._expect(TokenType.ASSIGN,
                     f"'=' diperlukan setelah nama variabel '{name_tok.value}'")
        value = self._parse_bool_expr()
        self._expect(TokenType.SEMICOLON,
                     "';' diperlukan di akhir deklarasi")
        return DeclarationNode(name=name_tok.value, value=value,
                               line=tok.line, col=tok.column)

    def _parse_assignment(self) -> AssignmentNode:
        """IDENTIFIER = bool_expr ;"""
        name_tok = self._advance()                              # konsumsi identifier
        self._expect(TokenType.ASSIGN,
                     f"'=' diperlukan setelah '{name_tok.value}'")
        value = self._parse_bool_expr()
        self._expect(TokenType.SEMICOLON,
                     "';' diperlukan di akhir assignment")
        return AssignmentNode(name=name_tok.value, value=value,
                              line=name_tok.line, col=name_tok.column)

    def _parse_if(self) -> IfNode:
        """if ( bool_expr ) { statement* } [ else { statement* } ]"""
        tok = self._advance()                                   # konsumsi 'if'
        self._expect(TokenType.LPAREN,  "'(' diperlukan setelah 'if'")
        condition = self._parse_bool_expr()
        self._expect(TokenType.RPAREN,  "')' penutup kondisi if")
        self._expect(TokenType.LBRACE,  "'{' pembuka blok if")
        then_branch = self._parse_block()
        self._expect(TokenType.RBRACE,  "'}' penutup blok if")

        else_branch = None
        if self._match(TokenType.ELSE):
            self._expect(TokenType.LBRACE, "'{' pembuka blok else")
            else_branch = self._parse_block()
            self._expect(TokenType.RBRACE, "'}' penutup blok else")

        return IfNode(condition=condition,
                      then_branch=then_branch,
                      else_branch=else_branch,
                      line=tok.line, col=tok.column)

    def _parse_print(self) -> PrintNode:
        """print ( bool_expr ) ;"""
        tok = self._advance()                                   # konsumsi 'print'
        self._expect(TokenType.LPAREN, "'(' diperlukan setelah 'print'")
        value = self._parse_bool_expr()
        self._expect(TokenType.RPAREN, "')' penutup print")
        self._expect(TokenType.SEMICOLON, "';' diperlukan di akhir print")
        return PrintNode(value=value, line=tok.line, col=tok.column)

    def _parse_block(self) -> list[ASTNode]:
        """Baca daftar statement di dalam { }."""
        stmts = []
        while not self._check(TokenType.RBRACE, TokenType.EOF):
            try:
                stmts.append(self._parse_statement())
            except SyntaxError_ as e:
                self.errors.append(e)
                print(e)
                self._sync()
        return stmts

    # ── ekspresi boolean (sesuai hierarki prioritas) ──────────────

    def _parse_bool_expr(self) -> ASTNode:
        """bool_expr → bool_term ( OR bool_term )*"""
        left = self._parse_bool_term()
        while self._check(TokenType.OR):
            op_tok = self._advance()                            # konsumsi 'OR'
            right  = self._parse_bool_term()
            left   = BinaryOpNode(op='OR', left=left, right=right,
                                  line=op_tok.line, col=op_tok.column)
        return left

    def _parse_bool_term(self) -> ASTNode:
        """bool_term → bool_factor ( AND bool_factor )*"""
        left = self._parse_bool_factor()
        while self._check(TokenType.AND):
            op_tok = self._advance()                            # konsumsi 'AND'
            right  = self._parse_bool_factor()
            left   = BinaryOpNode(op='AND', left=left, right=right,
                                  line=op_tok.line, col=op_tok.column)
        return left

    def _parse_bool_factor(self) -> ASTNode:
        """bool_factor → NOT bool_factor | ( bool_expr ) | true | false | IDENTIFIER"""
        tok = self._current()

        # NOT <factor>
        if tok.type == TokenType.NOT:
            self._advance()
            operand = self._parse_bool_factor()
            return UnaryOpNode(op='NOT', operand=operand,
                               line=tok.line, col=tok.column)

        # ( bool_expr )
        if tok.type == TokenType.LPAREN:
            self._advance()
            expr = self._parse_bool_expr()
            self._expect(TokenType.RPAREN, "')' penutup ekspresi")
            return expr

        # true
        if tok.type == TokenType.TRUE:
            self._advance()
            return LiteralNode(value=True, line=tok.line, col=tok.column)

        # false
        if tok.type == TokenType.FALSE:
            self._advance()
            return LiteralNode(value=False, line=tok.line, col=tok.column)

        # identifier
        if tok.type == TokenType.IDENTIFIER:
            self._advance()
            return IdentifierNode(name=tok.value, line=tok.line, col=tok.column)

        # tidak ada yang cocok
        self._advance()
        raise SyntaxError_(
            f"Ekspresi boolean tidak valid: '{tok.value}'",
            tok.line, tok.column
        )


# ------------------------------------------------------------------
# 4. FUNGSI UTILITAS — CETAK AST
# ------------------------------------------------------------------

def print_ast(node: ASTNode, indent: int = 0):
    """Cetak AST secara rekursif dengan indentasi."""
    prefix = "  " * indent

    if isinstance(node, ProgramNode):
        print(f"{prefix}Program")
        for stmt in node.statements:
            print_ast(stmt, indent + 1)

    elif isinstance(node, DeclarationNode):
        print(f"{prefix}Deklarasi: boolean {node.name}")
        print_ast(node.value, indent + 1)

    elif isinstance(node, AssignmentNode):
        print(f"{prefix}Assignment: {node.name} =")
        print_ast(node.value, indent + 1)

    elif isinstance(node, IfNode):
        print(f"{prefix}If")
        print(f"{prefix}  [kondisi]")
        print_ast(node.condition, indent + 2)
        print(f"{prefix}  [then]")
        for s in node.then_branch:
            print_ast(s, indent + 2)
        if node.else_branch is not None:
            print(f"{prefix}  [else]")
            for s in node.else_branch:
                print_ast(s, indent + 2)

    elif isinstance(node, PrintNode):
        print(f"{prefix}Print")
        print_ast(node.value, indent + 1)

    elif isinstance(node, BinaryOpNode):
        print(f"{prefix}BinaryOp: {node.op}")
        print_ast(node.left,  indent + 1)
        print_ast(node.right, indent + 1)

    elif isinstance(node, UnaryOpNode):
        print(f"{prefix}UnaryOp: {node.op}")
        print_ast(node.operand, indent + 1)

    elif isinstance(node, LiteralNode):
        print(f"{prefix}Literal: {str(node.value).lower()}")

    elif isinstance(node, IdentifierNode):
        print(f"{prefix}Identifier: {node.name}")

    else:
        print(f"{prefix}Unknown: {node}")


# ------------------------------------------------------------------
# 5. PROGRAM UTAMA — UJI COBA
# ------------------------------------------------------------------

if __name__ == '__main__':
    # ── Test 1: program normal ────────────────────────────────────
    source1 = """\
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
    print("  TEST 1 — Program Normal")
    print("=" * 60)
    tokens = Scanner(source1).tokenize()
    parser = Parser(tokens)
    ast    = parser.parse()
    print("\nAST:")
    print_ast(ast)
    if not parser.errors:
        print("\nParsing berhasil. Tidak ada error sintaks.")

    # ── Test 2: ekspresi kompleks ─────────────────────────────────
    source2 = """\
boolean x = true;
boolean y = false;
boolean z = x OR y AND NOT x;
if ((x OR y) AND NOT z) {
    print(x);
}
"""

    print("\n" + "=" * 60)
    print("  TEST 2 — Ekspresi Kompleks")
    print("=" * 60)
    tokens2 = Scanner(source2).tokenize()
    parser2 = Parser(tokens2)
    ast2    = parser2.parse()
    print("\nAST:")
    print_ast(ast2)
    if not parser2.errors:
        print("\nParsing berhasil. Tidak ada error sintaks.")

    # ── Test 3: error sintaks ─────────────────────────────────────
    source3 = """\
boolean a = true
boolean b = false;
if a AND b {
    print(a);
}
"""

    print("\n" + "=" * 60)
    print("  TEST 3 — Error Sintaks")
    print("=" * 60)
    tokens3 = Scanner(source3).tokenize()
    parser3 = Parser(tokens3)
    ast3    = parser3.parse()
    print(f"\nDitemukan {len(parser3.errors)} error sintaks.")