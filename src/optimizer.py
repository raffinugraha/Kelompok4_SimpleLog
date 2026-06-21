# ============================================================
#  SimpleLog Compiler — Kelompok 4
#  Modul  : Optimizer (TAC Optimization)
#  Teknik : 1. Constant Folding
#            2. Dead Code Elimination
#  Tugas  : Teknik Kompilasi 2025
# ============================================================

from __future__ import annotations
from dataclasses import dataclass, field
from scanner import Scanner
from parser import Parser
from semantic import SemanticAnalyzer
from icg import ICG, TACInstruction, print_tac


# ------------------------------------------------------------------
# 1. CONSTANT FOLDING
# ------------------------------------------------------------------

class ConstantFolder:
    """
    Teknik optimasi 1: Constant Folding.

    Mengevaluasi ekspresi yang SEMUA operandnya sudah diketahui
    nilainya pada saat kompilasi (konstanta), lalu mengganti
    instruksi tersebut dengan hasil langsung.

    Contoh sebelum:
        t0 = true
        t1 = false
        t2 = NOT t1          →  t2 = true
        t3 = t0 AND t2       →  t3 = true

    Contoh sesudah:
        t0 = true
        t1 = false
        t2 = true
        t3 = true
    """

    BOOL_VALS = {'true', 'false'}

    def optimize(self, instructions: list[TACInstruction]) -> list[TACInstruction]:
        """
        Jalankan constant folding.
        Kembalikan daftar instruksi baru yang sudah dioptimasi.
        """
        # known: peta nama variabel/temp → nilai konstanta ('true'/'false')
        known   : dict[str, str]          = {}
        result  : list[TACInstruction]    = []
        folded  : int                     = 0

        for instr in instructions:
            # PENTING: LABEL adalah titik temu (merge point) dari beberapa
            # jalur kontrol alir yang berbeda (misal: jalur 'then' dan jalur
            # setelah 'goto'). Nilai konstanta yang diketahui sebelum label
            # belum tentu masih berlaku setelah label, karena jalur lain
            # yang masuk ke label ini bisa membawa nilai berbeda.
            # Maka tabel 'known' WAJIB dikosongkan di setiap label agar
            # folding tidak salah mengasumsikan nilai dari jalur tertentu.
            if instr.op == 'LABEL':
                known.clear()
                result.append(instr)
                continue

            new_instr = self._fold(instr, known)
            result.append(new_instr)

            # Catat berapa instruksi yang berhasil di-fold
            if new_instr is not instr:
                folded += 1

            # Perbarui tabel nilai yang diketahui
            if new_instr.op == 'COPY' and new_instr.arg1 in self.BOOL_VALS:
                known[new_instr.result] = new_instr.arg1
            elif new_instr.result and new_instr.result not in known:
                # Hasil tak diketahui — hapus dari tabel supaya aman
                known.pop(new_instr.result, None)
        self.folded_count = folded
        return result

    def _fold(self, instr: TACInstruction,
              known: dict[str, str]) -> TACInstruction:
        """Coba fold satu instruksi. Kembalikan instruksi asli jika tidak bisa."""

        # ── NOT <arg1> ──────────────────────────────────────────
        if instr.op == 'NOT':
            val = known.get(instr.arg1)
            if val in self.BOOL_VALS:
                folded_val = 'false' if val == 'true' else 'true'
                return TACInstruction(op='COPY', arg1=folded_val,
                                      result=instr.result)

        # ── <arg1> AND <arg2> ────────────────────────────────────
        # Short-circuit: salah satu false → hasil false
        # Keduanya true → hasil true
        if instr.op == 'AND':
            v1 = known.get(instr.arg1)
            v2 = known.get(instr.arg2)
            if v1 == 'false' or v2 == 'false':
                return TACInstruction(op='COPY', arg1='false',
                                      result=instr.result)
            if v1 == 'true' and v2 == 'true':
                return TACInstruction(op='COPY', arg1='true',
                                      result=instr.result)

        # ── <arg1> OR <arg2> ─────────────────────────────────────
        if instr.op == 'OR':
            v1 = known.get(instr.arg1)
            v2 = known.get(instr.arg2)
            if v1 == 'true' or v2 == 'true':
                return TACInstruction(op='COPY', arg1='true',
                                      result=instr.result)
            if v1 == 'false' and v2 == 'false':
                return TACInstruction(op='COPY', arg1='false',
                                      result=instr.result)

        # ── COPY dari variabel yang nilainya sudah diketahui ─────
        if instr.op == 'COPY' and instr.arg1 in known:
            val = known[instr.arg1]
            if val in self.BOOL_VALS:
                return TACInstruction(op='COPY', arg1=val,
                                      result=instr.result)

        # ── IFFALSE dengan kondisi yang sudah diketahui ──────────
        if instr.op == 'IFFALSE_GOTO':
            val = known.get(instr.arg1)
            if val == 'true':
                # Kondisi selalu true → jump TIDAK pernah diambil → hapus
                return TACInstruction(op='NOP', result='')
            if val == 'false':
                # Kondisi selalu false → jump SELALU diambil → jadi GOTO
                return TACInstruction(op='GOTO', result=instr.result)

        # ── IF_GOTO dengan kondisi yang sudah diketahui ──────────
        if instr.op == 'IF_GOTO':
            val = known.get(instr.arg1)
            if val == 'false':
                return TACInstruction(op='NOP', result='')
            if val == 'true':
                return TACInstruction(op='GOTO', result=instr.result)

        return instr   # tidak bisa di-fold


# ------------------------------------------------------------------
# 2. DEAD CODE ELIMINATION
# ------------------------------------------------------------------

class DeadCodeEliminator:
    """
    Teknik optimasi 2: Dead Code Elimination.

    Menghapus instruksi yang tidak akan pernah dieksekusi atau
    tidak berkontribusi pada hasil program:

    (a) Unreachable code — instruksi setelah GOTO/JUMP tanpa label
        perantara tidak akan pernah dicapai.

    (b) NOP — instruksi kosong sisa constant folding.

    (c) Unused temporaries — instruksi COPY ke temp (tN) yang
        hasilnya tidak pernah dibaca oleh instruksi lain.

    Contoh sebelum:
          goto L1
          t0 = true      ← tidak pernah dicapai (dead)
        L1:
          NOP            ← sisa folding

    Contoh sesudah:
          goto L1
        L1:
    """

    def optimize(self, instructions: list[TACInstruction]) -> list[TACInstruction]:
        step1 = self._remove_unreachable(instructions)
        step2 = self._remove_nop(step1)
        step3 = self._remove_unused_temps(step2)
        self.removed_count = len(instructions) - len(step3)
        return step3

    # ── (a) Unreachable code ──────────────────────────────────────

    def _remove_unreachable(self,
                            instructions: list[TACInstruction]
                            ) -> list[TACInstruction]:
        """
        Setelah GOTO atau IFFALSE_GOTO tanpa kondisi (alias GOTO),
        instruksi berikutnya tidak bisa dicapai kecuali ada LABEL.
        """
        result      : list[TACInstruction] = []
        unreachable : bool                 = False

        for instr in instructions:
            if instr.op == 'LABEL':
                unreachable = False   # label = titik masuk baru

            if not unreachable:
                result.append(instr)

            # Setelah GOTO tanpa syarat, semua instruksi berikutnya
            # sampai label berikutnya adalah dead code
            if instr.op == 'GOTO':
                unreachable = True

        return result

    # ── (b) Hapus NOP ────────────────────────────────────────────

    def _remove_nop(self,
                    instructions: list[TACInstruction]
                    ) -> list[TACInstruction]:
        return [i for i in instructions if i.op != 'NOP']

    # ── (c) Unused temporaries ────────────────────────────────────

    def _remove_unused_temps(self,
                              instructions: list[TACInstruction]
                              ) -> list[TACInstruction]:
        """
        Hitung berapa kali tiap variabel temp (tN) dibaca.
        Hapus instruksi COPY/NOT/AND/OR yang hasilnya tidak pernah dibaca.
        Variabel program (bukan temp) tidak disentuh.
        """
        # Hitung penggunaan (sebagai arg, bukan result)
        use_count: dict[str, int] = {}
        for instr in instructions:
            for arg in (instr.arg1, instr.arg2):
                if arg:
                    use_count[arg] = use_count.get(arg, 0) + 1

        # Hapus instruksi yang result-nya temp dan tidak pernah dipakai
        result = []
        for instr in instructions:
            r = instr.result
            is_temp    = r.startswith('t') and r[1:].isdigit()
            is_write   = instr.op in ('COPY', 'NOT', 'AND', 'OR')
            is_unused  = use_count.get(r, 0) == 0

            if is_temp and is_write and is_unused:
                continue   # buang
            result.append(instr)

        return result


# ------------------------------------------------------------------
# 3. OPTIMIZER — ORKESTRASI DUA TEKNIK
# ------------------------------------------------------------------

class Optimizer:
    """
    Menjalankan kedua teknik optimasi secara berurutan:
      1. Constant Folding
      2. Dead Code Elimination

    Proses diulang (iterative) sampai tidak ada perubahan lagi,
    karena satu pass folding bisa mengekspos dead code baru,
    dan sebaliknya.
    """

    def __init__(self):
        self.folder      = ConstantFolder()
        self.eliminator  = DeadCodeEliminator()
        self.passes      = 0
        self.total_folded   = 0
        self.total_removed  = 0

    def optimize(self,
                 instructions: list[TACInstruction]
                 ) -> list[TACInstruction]:
        current = instructions

        while True:
            self.passes += 1
            prev_len = len(current)

            # Pass 1: Constant Folding
            after_fold = self.folder.optimize(current)
            self.total_folded += self.folder.folded_count

            # Pass 2: Dead Code Elimination
            after_dce = self.eliminator.optimize(after_fold)
            self.total_removed += self.eliminator.removed_count

            # Berhenti jika sudah tidak ada perubahan
            if len(after_dce) == prev_len:
                current = after_dce
                break

            current = after_dce

        return current

    def print_report(self):
        print(f"\n  Laporan Optimasi:")
        print(f"  {'─'*36}")
        print(f"  Pass dijalankan        : {self.passes}")
        print(f"  Instruksi di-fold      : {self.total_folded}")
        print(f"  Instruksi dihapus (DCE): {self.total_removed}")


# ------------------------------------------------------------------
# 4. PROGRAM UTAMA — UJI COBA
# ------------------------------------------------------------------

if __name__ == '__main__':

    def run_test(title: str, source: str):
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)
        print(f"\nSource:\n{source}")

        # Pipeline lengkap
        tokens   = Scanner(source).tokenize()
        parser   = Parser(tokens)
        ast      = parser.parse()

        if parser.errors:
            print("Parser error — dibatalkan."); return

        analyzer = SemanticAnalyzer()
        if not analyzer.analyze(ast):
            print("Semantic error — dibatalkan."); return

        icg  = ICG()
        tac  = icg.generate(ast)

        print_tac(tac)
        print(f"\n  [sebelum optimasi: {len(tac)} instruksi]")

        opt      = Optimizer()
        tac_opt  = opt.optimize(tac)

        print_tac(tac_opt)
        print(f"\n  [sesudah optimasi: {len(tac_opt)} instruksi]")
        opt.print_report()

        saved = len(tac) - len(tac_opt)
        pct   = (saved / len(tac) * 100) if tac else 0
        print(f"  Penghematan            : {saved} instruksi ({pct:.0f}%)")

    # ── Test 1: constant folding murni ───────────────────────────
    run_test("TEST 1 — Constant Folding", """\
boolean a = true;
boolean b = false;
boolean c = NOT b;
boolean d = a AND c;
print(d);
""")

    # ── Test 2: dead code dari if (kondisi selalu true) ──────────
    run_test("TEST 2 — Dead Code Elimination", """\
boolean a = true;
boolean b = false;
if (a AND NOT b) {
    print(a);
} else {
    print(b);
}
""")

    # ── Test 3: ekspresi kompleks, dua teknik bersama ────────────
    run_test("TEST 3 — Folding + DCE Bersamaan", """\
boolean p = true;
boolean q = false;
boolean r = p OR q AND NOT p;
if ((p OR q) AND NOT r) {
    print(p);
} else {
    print(r);
}
""")