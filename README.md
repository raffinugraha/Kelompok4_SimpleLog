# SimpleLog Compiler — Kelompok 4

Kompiler sederhana untuk bahasa **SimpleLog**, dibangun untuk tugas Proyek Akhir mata kuliah Teknik Kompilasi. SimpleLog adalah bahasa yang berfokus pada operasi logika boolean dengan operator `AND`, `OR`, `NOT`, dan struktur kendali `if-else`.

```
boolean a = true;
boolean b = false;
if (a AND NOT b) {
    print(a);
} else {
    print(b);
}
```
## Struktur Proyek

```
Kelompok4_SimpleLog/
│   ├── src/
│   ├── scanner.py              # Analisis leksikal (kode sumber -> token)
│   ├── parser.py                # Analisis sintaks (token -> AST)
│   ├── semantic.py               # Analisis semantik (symbol table & validasi tipe)
│   ├── icg.py                    # Pembuatan kode antara (AST -> Three Address Code)
│   ├── optimizer.py               # Optimasi (constant folding & dead codeelimination)
│   ├──compiler.py                # Error handling + integrasi seluruh pipeline + CLI
├── tests/
│   ├── test1_valid.sl
│   ├── test2_lexical_error.sl
│   ├── test3_syntax_error.sl
│   ├── test4_semantic_error.sl
│   └── test5_complex.sl
├── docs/
│   └── LAPORAN PROJEK UAS TK KEL 4.pdf
└── README.md
```

## Spesifikasi Bahasa SimpleLog

- **Tipe data:** `boolean` (nilai `true` / `false`)
- **Operator logika:** `AND`, `OR`, `NOT` — prioritas: `NOT` > `AND` > `OR`
- **Struktur kendali:** `if (...) { ... } else { ... }`
- **Pernyataan:** deklarasi (`boolean x = ...;`), assignment (`x = ...;`), `print(...)`
- **Komentar:** satu baris menggunakan `--`

Grammar BNF lengkap tersedia di laporan (`docs/LAPORAN PROJEK UAS TK KEL 4.pdf`, Bab 2).

## Cara Menjalankan

### Persyaratan
- Python 3.10 atau lebih baru (tidak ada dependency eksternal, cukup Python standar)

### Instalasi
```bash
git clone [URL_REPOSITORY_INI]
cd KEL_4
```

### Mode Demo (4 skenario uji bawaan, tanpa perlu file)
```bash
python compiler.py --demo
```

### Mode File (kompilasi file SimpleLog sendiri)
```bash
python compiler.py ../tests/test1_valid.sl --all
```

### Opsi CLI

| Flag | Fungsi |
|---|---|
| (tanpa flag) | Kompilasi biasa, hanya tampilkan status & error |
| `--tokens` | Tampilkan daftar token hasil scanning |
| `--ast` | Tampilkan Abstract Syntax Tree |
| `--tac` | Tampilkan Three Address Code sebelum optimasi |
| `--optimize` | Jalankan optimasi & tampilkan TAC sesudahnya |
| `--all` | Tampilkan semua output di atas sekaligus |
| `--demo` | Jalankan 4 skenario uji bawaan (tanpa perlu file) |

## Pipeline Kompilasi

```
Source Code (.sl)
      |
      v
[1] Scanner     -> daftar Token
      |
      v
[2] Parser      -> Abstract Syntax Tree (AST)
      |
      v
[3] Semantic    -> Symbol Table + validasi tipe
    Analyzer
      |
      v
[4] ICG         -> Three Address Code (TAC)
      |
      v
[5] Optimizer   -> TAC yang sudah disederhanakan
      |
      v
Output akhir + Laporan Error (jika ada)
```

Setiap tahap berhenti otomatis jika ditemukan error, agar tidak melanjutkan proses dengan data yang tidak valid. Error dari setiap fase (leksikal, sintaks, semantik) dikumpulkan oleh `ErrorReporter` dan ditampilkan dengan format konsisten, lengkap dengan nomor baris, kolom, dan potongan kode sumber terkait.

## Test Case

| File | Tujuan | Hasil yang Diharapkan |
|---|---|---|
| `test1_valid.sl` | Program valid dasar sesuai contoh soal | Berhasil — 34 token, 18 instruksi TAC awal, 13 setelah optimasi |
| `test2_lexical_error.sl` | Karakter tidak dikenal (`@`) | Gagal — 1 error leksikal |
| `test3_syntax_error.sl` | Titik koma & kurung `if` hilang | Gagal — 3 error sintaks (multi-error recovery) |
| `test4_semantic_error.sl` | Deklarasi ganda & variabel tak terdefinisi | Gagal — 3 error semantik |
| `test5_complex.sl` | Ekspresi `AND`/`OR`/`NOT` bersarang | Berhasil — 48 token, 41 instruksi TAC awal |

Jalankan seluruh test sekaligus (dari dalam folder `src/`):
```bash
for f in ../tests/*.sl; do python compiler.py "$f"; done
```
> Di PowerShell (Windows), gunakan:
> ```powershell
> Get-ChildItem ..\tests\*.sl | ForEach-Object { python compiler.py $_.FullName }
> ```

## Teknik yang Diimplementasikan

- **Scanning:** pembacaan karakter per karakter dengan pelacakan baris & kolom
- **Parsing:** recursive descent parsing, dengan panic-mode recovery untuk melaporkan multi-error sintaks
- **Analisis semantik:** pola visitor, symbol table dengan pengecekan deklarasi ganda, variabel tak terdefinisi, dan inisialisasi
- **ICG:** Three Address Code dengan short-circuit evaluation untuk `AND`/`OR` (menggunakan lompatan bersyarat, bukan operator langsung)
- **Optimasi:** constant folding (dengan reset nilai konstanta pada setiap `LABEL` untuk menjaga korektnas lintas cabang kontrol) dan dead code elimination (unreachable code, NOP, temporary tak terpakai), dijalankan secara iteratif

## Laporan Lengkap

Dokumentasi detail (latar belakang, desain grammar BNF, arsitektur, implementasi, dan hasil pengujian) tersedia di `docs/LAPORAN PROJEK UAS TK KEL 4.pdf`.

## Batasan

- Hanya mendukung tipe data `boolean` (tidak ada integer, string, atau float)
- Tidak mendukung perulangan (`while`/`for`)
- Tidak mendukung deklarasi fungsi/prosedur
- Code generator ke bahasa target (Python/JavaScript) tidak diimplementasikan (bersifat opsional pada ketentuan tugas)
