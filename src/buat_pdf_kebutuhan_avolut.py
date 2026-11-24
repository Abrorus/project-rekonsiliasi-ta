"""
buat_pdf_kebutuhan_avolut.py
============================
Membuat dokumen PDF (dan HTML) ringkas & to-the-point yang menggabungkan kebutuhan:
  - Modul NLP (Pool 2 - Abror)
  - Modul Knowledge Base (Pool 3 - Mario)
untuk dikirimkan kepada Pak Depta (Avolut).

Output:
  - docs/Kebutuhan_Data_Avolut_NLP_dan_KB.pdf
  - docs/Kebutuhan_Data_Avolut_NLP_dan_KB.html
"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOCS = BASE / "docs"
DOCS.mkdir(exist_ok=True)
OUT_PDF = DOCS / "Kebutuhan_Data_Avolut_NLP_dan_KB.pdf"
OUT_HTML = DOCS / "Kebutuhan_Data_Avolut_NLP_dan_KB.html"


# ---------------------------------------------------------------------
# MINIMAL NATIVE PDF WRITER (A4, Helvetica & Helvetica-Bold, Tabel Rapi)
# ---------------------------------------------------------------------
class PDFPage:
    def __init__(self, w=595.28, h=841.89):
        self.w = w
        self.h = h
        self.cmds = []

    def _esc(self, s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def rect(self, x, y_top, w, h_box, fill_rgb=None, stroke_rgb=(0, 0, 0), line_w=0.6):
        y = self.h - y_top - h_box
        ops = [f"{line_w:.2f} w"]
        if fill_rgb:
            ops.append(f"{fill_rgb[0]:.3f} {fill_rgb[1]:.3f} {fill_rgb[2]:.3f} rg")
        if stroke_rgb:
            ops.append(f"{stroke_rgb[0]:.3f} {stroke_rgb[1]:.3f} {stroke_rgb[2]:.3f} RG")
        mode = "B" if (fill_rgb and stroke_rgb) else ("f" if fill_rgb else "S")
        ops.append(f"{x:.2f} {y:.2f} {w:.2f} {h_box:.2f} re {mode}")
        self.cmds.append(" ".join(ops))

    def text(self, x, y_top, s, font="F1", size=10, rgb=(0, 0, 0)):
        y = self.h - y_top
        self.cmds.append(
            f"BT /{font} {size} Tf {rgb[0]:.3f} {rgb[1]:.3f} {rgb[2]:.3f} rg "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm ({self._esc(s)}) Tj ET"
        )

    def stream(self):
        return "\n".join(self.cmds).encode("latin-1", errors="replace")


def wrap_text(teks, max_chars):
    words = teks.split()
    lines, cur = [], ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


def draw_table(page, y_top, col_widths, headers, rows, x_left=45):
    row_pad_y = 5
    line_h = 12
    # Header
    h_lines = [wrap_text(h, max(8, int(w / 5.2))) for h, w in zip(headers, col_widths)]
    max_hl = max(len(x) for x in h_lines)
    box_h = max_hl * line_h + 2 * row_pad_y
    cx = x_left
    for h_wr, cw in zip(h_lines, col_widths):
        page.rect(cx, y_top, cw, box_h, fill_rgb=(0.91, 0.93, 0.96), stroke_rgb=(0.2, 0.2, 0.2), line_w=0.6)
        for idx, ln in enumerate(h_wr):
            page.text(cx + 5, y_top + row_pad_y + (idx + 0.82) * line_h, ln, font="F2", size=9.2)
        cx += cw
    y_top += box_h

    # Rows
    for r in rows:
        c_lines = []
        for cell, cw in zip(r, col_widths):
            # Estimasi karakter per baris (font 9pt ~ 4.7 pt/char)
            max_c = max(6, int((cw - 10) / 4.65))
            c_lines.append(wrap_text(cell, max_c))
        max_l = max(len(x) for x in c_lines)
        rh = max_l * line_h + 2 * row_pad_y
        cx = x_left
        for idx_col, (lines_col, cw) in enumerate(zip(c_lines, col_widths)):
            page.rect(cx, y_top, cw, rh, fill_rgb=None, stroke_rgb=(0.35, 0.35, 0.35), line_w=0.5)
            fnt = "F2" if idx_col == 1 else "F1"
            for idx_l, ln in enumerate(lines_col):
                page.text(cx + 5, y_top + row_pad_y + (idx_l + 0.82) * line_h, ln, font=fnt, size=8.8)
            cx += cw
        y_top += rh
    return y_top


def save_pdf(pages, out_path):
    objs = []

    def add_obj(data_bytes):
        objs.append(data_bytes)
        return len(objs)

    f1_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    f2_id = add_obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")

    page_ids = []
    content_ids = []
    for p in pages:
        st = p.stream()
        cid = add_obj(f"<< /Length {len(st)} >>\nstream\n".encode("ascii") + st + b"\nendstream")
        content_ids.append(cid)
        page_ids.append(None)

    pages_tree_id = len(objs) + len(pages) + 1
    for i, p in enumerate(pages):
        pid = add_obj(
            f"<< /Type /Page /Parent {pages_tree_id} 0 R /MediaBox [0 0 {p.w:.2f} {p.h:.2f}] "
            f"/Resources << /Font << /F1 {f1_id} 0 R /F2 {f2_id} 0 R >> >> "
            f"/Contents {content_ids[i]} 0 R >>".encode("ascii")
        )
        page_ids[i] = pid

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    add_obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii"))
    catalog_id = add_obj(f"<< /Type /Catalog /Pages {pages_tree_id} 0 R >>".encode("ascii"))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for idx, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")

    xref_pos = len(out)
    out.extend(f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(objs)+1} /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    Path(out_path).write_bytes(out)


def buat_dokumen():
    p1 = PDFPage()
    y = 42

    # Judul Header
    p1.text(45, y, "DAFTAR KEBUTUHAN DATA & KONFIRMASI MITRA (AVOLUT)", font="F2", size=13.5, rgb=(0.1, 0.2, 0.45))
    y += 16
    p1.text(45, y, "Proyek Tugas Akhir Sistem Rekonsiliasi Keuangan (SIREKON) - Modul NLP & Knowledge Base", font="F2", size=10, rgb=(0.25, 0.25, 0.25))
    y += 8
    p1.rect(45, y, 505, 1.2, fill_rgb=(0.1, 0.2, 0.45), stroke_rgb=None)
    y += 14

    intro = (
        "Saat ini pengembangan Modul NLP (klasifikasi teks mutasi) dan Modul Knowledge Base (pencocokan ERP) "
        "sudah berjalan dengan baik. Agar sistem dan pengujian akhir berjalan optimal, kami memohon bantuan "
        "konfirmasi serta dukungan data dari pihak mitra untuk 4 poin berikut:"
    )
    for ln in wrap_text(intro, 98):
        p1.text(45, y, ln, font="F1", size=9.5)
        y += 13
    y += 6

    # BAGIAN 1: COA (Gabungan NLP & KB)
    p1.text(45, y, "1. Konfirmasi Kode Akun (CoA) untuk 5 Kategori Transaksi & Singkatan Mutasi (NLP & KB)", font="F2", size=10.5, rgb=(0.1, 0.2, 0.45))
    y += 14
    sub1 = (
        "Berdasarkan pencocokan mutasi BCA (2023) & Mandiri dengan file CoA (313 akun), terdapat 5 jenis transaksi "
        "rutin yang belum memiliki kode akun spesifik di CoA:"
    )
    for ln in wrap_text(sub1, 98):
        p1.text(45, y, ln, font="F1", size=9.2)
        y += 12
    y += 4

    rows_coa = [
        ["1", "Biaya Admin Bank (admin bulanan, biaya transfer, SKN/RTGS)", '"BIAYA ADM", "BIAYA TRANSFER"', "Belum ada akun biaya bank di CoA"],
        ["2", "Biaya Tolakan (retur / gagal transfer)", "Transaksi tolakan / pengembalian", "Belum ada akun tolakan di CoA"],
        ["3", "Bunga Bank / Jasa Giro (pendapatan bunga)", '"BUNGA", "JASA GIRO", "CR BUNGA"', "Belum ada akun pendapatan bunga (Revenue di 4.1.01.xx hanya produk)"],
        ["4", "Setoran Pajak (PPh/PPN disetor ke negara)", '"BYR VIA E-BANKING PENERIMAAN NEGARA"', "Ada Prepaid Tax (1.1.08.xx) & Withholding Tax (2.1.04.xx), belum ada akun setoran pajak"],
        ["5", "BPJS (TK & Kesehatan)", '"TRSF E-BANKING 89000/BPJS TK", "BPJS KS"', "Belum ada akun spesifik BPJS. Apakah masuk ke Employee Benefit (6.2.02.01)?"],
    ]
    y = draw_table(p1, y, [22, 145, 143, 195], ["No", "Jenis Transaksi", "Contoh di Mutasi Bank", "Status di CoA Saat Ini"], rows_coa)
    y += 12

    bullets_1 = [
        "- Mohon konfirmasi: apakah 5 kategori di atas perlu dibuatkan kode akun baru, atau dimasukkan ke akun CoA yang sudah ada (mohon info nomor akunnya)?",
        "- Konfirmasi istilah di mutasi Mandiri: apakah 'LN interco to3PL' / 'Rturn LN' adalah Pinjaman (Loan), serta 'gkar' (DARI ARTA SEJAHTERA) dan 'KE GNC' masuk ke kategori apa?",
    ]
    for b in bullets_1:
        for ln in wrap_text(b, 96):
            p1.text(50, y, ln, font="F1", size=9.0)
            y += 12
    y += 8

    # BAGIAN 2: Validasi 20% Sampel NLP
    p1.text(45, y, "2. Validasi Sampel Transaksi untuk Pengujian Akurasi NLP (Modul NLP)", font="F2", size=10.5, rgb=(0.1, 0.2, 0.45))
    y += 13
    rows_val = [
        ["1", "sampel_validasi_20persen.xlsx (121 baris transaksi acak)", "Mohon bantuan mengisi kolom 'label_validator' di sheet 'Sampel' memakai pilihan kode di sheet 'Daftar Label' (syarat uji reliabilitas Cohen's Kappa)."],
        ["2", "review_catatan_unik.xlsx (opsional / bahan diskusi)", "Daftar keterangan transaksi Mandiri yang sudah kami beri label usulan, untuk dikonfirmasi jika ada yang kurang tepat."],
    ]
    y = draw_table(p1, y, [22, 185, 298], ["No", "File Lampiran", "Kebutuhan Validasi"], rows_val)
    y += 14

    # BAGIAN 3: Akses Data ERP (Modul KB)
    p1.text(45, y, "3. Akses Data ERP: API Sandbox atau Export Data (Modul Knowledge Base)", font="F2", size=10.5, rgb=(0.1, 0.2, 0.45))
    y += 13
    sub3 = "Modul KB telah menyiapkan koneksi ke ERP untuk mencocokkan transaksi dengan rekanan & invoice secara otomatis (saat ini masih memakai data dummy):"
    for ln in wrap_text(sub3, 98):
        p1.text(45, y, ln, font="F1", size=9.2)
        y += 12
    y += 4

    rows_erp = [
        ["1", "Daftar Vendor & Customer Terdaftar", "Mencocokkan nama pada mutasi bank dengan rekanan resmi perusahaan"],
        ["2", "Daftar Invoice Outstanding (Belum Lunas)", "Rekonsiliasi otomatis: mencocokkan nominal mutasi dengan tagihan terbuka"],
        ["3", "CoA Terbaru (jika ada update)", "Memastikan pemetaan kode akun selalu mutakhir"],
    ]
    y = draw_table(p1, y, [22, 185, 298], ["No", "Data yang Dibutuhkan", "Fungsi di Sistem"], rows_erp)
    y += 11
    p1.text(50, y, "- Yang dibutuhkan: Base URL API ERP (atau URL sandbox/testing) beserta API Key/Token, atau file export CSV/Excel.", font="F1", size=9.0)
    y += 18

    # BAGIAN 4: Sampel Mutasi Bank Lain
    p1.text(45, y, "4. Ketersediaan Sampel Mutasi Bank Lain: BNI, BRI, BSI (Modul NLP)", font="F2", size=10.5, rgb=(0.1, 0.2, 0.45))
    y += 13
    sub4 = (
        "- Sesuai ruang lingkup proposal (5 bank: BCA, Mandiri, BNI, BRI, BSI), apakah terdapat sampel/dummy mutasi "
        "untuk BNI, BRI, atau BSI? Apabila tidak tersedia, kami izin menggunakan data simulasi berformat standar bank tersebut."
    )
    for ln in wrap_text(sub4, 96):
        p1.text(50, y, ln, font="F1", size=9.0)
        y += 12

    save_pdf([p1], OUT_PDF)

    # Buat juga HTML bersih
    html = """<!doctype html><html><head><meta charset='utf-8'>
<title>Kebutuhan Data & Konfirmasi Mitra (Avolut) - Modul NLP & KB</title>
<style>
  body { font-family: Arial, sans-serif; font-size: 10.5pt; line-height: 1.45; color: #222; max-width: 780px; margin: 24px auto; }
  h1 { font-size: 14pt; color: #1a3373; margin-bottom: 2px; }
  .sub { font-size: 10pt; font-weight: bold; color: #444; border-bottom: 2px solid #1a3373; padding-bottom: 6px; margin-bottom: 12px; }
  h2 { font-size: 11pt; color: #1a3373; margin: 14px 0 6px 0; }
  p, ul { margin: 5px 0; }
  table { border-collapse: collapse; width: 100%; margin: 6px 0 8px 0; font-size: 9.5pt; }
  th, td { border: 1px solid #444; padding: 5px 8px; text-align: left; vertical-align: top; }
  th { background: #e8edf5; font-weight: bold; }
</style></head><body>
<h1>DAFTAR KEBUTUHAN DATA & KONFIRMASI MITRA (AVOLUT)</h1>
<div class='sub'>Proyek Tugas Akhir Sistem Rekonsiliasi Keuangan (SIREKON) — Modul NLP & Knowledge Base</div>
<p>Saat ini pengembangan <b>Modul NLP</b> (klasifikasi teks mutasi) dan <b>Modul Knowledge Base</b> (pencocokan data ERP) sudah berjalan dengan baik. Agar sistem dan pengujian akhir berjalan optimal, kami memohon bantuan konfirmasi serta dukungan data dari pihak mitra untuk 4 poin berikut:</p>

<h2>1. Konfirmasi Kode Akun (CoA) untuk 5 Kategori Transaksi & Singkatan Mutasi (NLP & KB)</h2>
<p>Berdasarkan pencocokan mutasi BCA (2023) & Mandiri dengan file CoA (313 akun), terdapat 5 jenis transaksi rutin yang belum memiliki kode akun spesifik di CoA:</p>
<table>
  <tr><th style='width:28px'>No</th><th style='width:210px'>Jenis Transaksi</th><th style='width:190px'>Contoh di Mutasi Bank</th><th>Status di CoA Saat Ini</th></tr>
  <tr><td>1</td><td><b>Biaya Admin Bank</b> (admin bulanan, biaya transfer, SKN/RTGS)</td><td>"BIAYA ADM", "BIAYA TRANSFER"</td><td>Belum ada akun biaya bank di CoA</td></tr>
  <tr><td>2</td><td><b>Biaya Tolakan</b> (retur / gagal transfer)</td><td>Transaksi tolakan / pengembalian</td><td>Belum ada akun tolakan di CoA</td></tr>
  <tr><td>3</td><td><b>Bunga Bank / Jasa Giro</b> (pendapatan bunga)</td><td>"BUNGA", "JASA GIRO", "CR BUNGA"</td><td>Belum ada akun pendapatan bunga (Revenue di 4.1.01.xx hanya untuk produk)</td></tr>
  <tr><td>4</td><td><b>Setoran Pajak</b> (PPh/PPN disetor ke negara)</td><td>"BYR VIA E-BANKING PENERIMAAN NEGARA"</td><td>Ada Prepaid Tax (1.1.08.xx) & Withholding Tax (2.1.04.xx), belum ada akun pajak yang disetor ke negara</td></tr>
  <tr><td>5</td><td><b>BPJS</b> (TK & Kesehatan)</td><td>"TRSF E-BANKING 89000/BPJS TK", "BPJS KS"</td><td>Belum ada akun spesifik BPJS. Apakah bisa masuk ke Employee Benefit (6.2.02.01)?</td></tr>
</table>
<ul>
  <li><b>Yang dibutuhkan:</b> Apakah 5 kategori di atas perlu dibuatkan kode akun baru di CoA, atau dimasukkan ke akun yang sudah ada (mohon info kode & nama akunnya)?</li>
  <li><b>Konfirmasi singkatan mutasi Mandiri:</b> Apakah keterangan <code>LN interco to3PL</code> / <code>Rturn LN</code> merupakan Pinjaman (Loan), serta transaksi <code>gkar</code> (DARI ARTA SEJAHTERA) dan <code>KE GNC</code> masuk ke kategori akun apa?</li>
</ul>

<h2>2. Validasi Sampel Transaksi untuk Pengujian Akurasi (Modul NLP)</h2>
<table>
  <tr><th style='width:28px'>No</th><th style='width:230px'>File Lampiran</th><th>Kebutuhan Validasi</th></tr>
  <tr><td>1</td><td><b>sampel_validasi_20persen.xlsx</b> (121 baris transaksi acak)</td><td>Mohon bantuan mengisi kolom <code>label_validator</code> pada sheet <b>Sampel</b> menggunakan kode kategori di sheet <b>Daftar Label</b> (sebagai syarat validasi <i>domain expert</i> pada buku TA).</td></tr>
  <tr><td>2</td><td><b>review_catatan_unik.xlsx</b> (opsional / bahan diskusi)</td><td>Daftar keterangan unik Mandiri yang sudah kami beri label usulan, untuk dikonfirmasi apabila ada yang kurang sesuai.</td></tr>
</table>

<h2>3. Akses Data ERP: API Sandbox atau Export Data (Modul Knowledge Base)</h2>
<p>Modul KB telah menyiapkan koneksi ke ERP untuk mencocokkan transaksi dengan rekanan & invoice secara otomatis (saat ini masih memakai data dummy):</p>
<table>
  <tr><th style='width:28px'>No</th><th style='width:230px'>Data yang Dibutuhkan</th><th>Fungsi di Sistem</th></tr>
  <tr><td>1</td><td><b>Daftar Vendor & Customer Terdaftar</b></td><td>Mencocokkan nama pada mutasi bank dengan rekanan resmi perusahaan</td></tr>
  <tr><td>2</td><td><b>Daftar Invoice Outstanding</b> (belum lunas)</td><td>Rekonsiliasi otomatis: mencocokkan nominal mutasi dengan tagihan terbuka</td></tr>
  <tr><td>3</td><td><b>CoA Terbaru</b> (jika ada update)</td><td>Memastikan mapping kode akun selalu up-to-date</td></tr>
</table>
<ul>
  <li><b>Yang dibutuhkan:</b> Base URL API ERP (atau URL sandbox/testing) beserta API Key/Token otentikasi, atau export data CSV/Excel.</li>
</ul>

<h2>4. Ketersediaan Sampel Mutasi Bank Lain: BNI, BRI, BSI (Modul NLP)</h2>
<ul>
  <li>Sesuai ruang lingkup proposal (5 bank: BCA, Mandiri, BNI, BRI, BSI), apakah di Avolut terdapat sampel/dummy mutasi untuk <b>BNI, BRI, atau BSI</b>? Apabila tidak tersedia, kami izin menggunakan data simulasi berformat standar bank tersebut.</li>
</ul>
</body></html>"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"PDF berhasil dibuat : {OUT_PDF} ({OUT_PDF.stat().st_size} bytes)")
    print(f"HTML berhasil dibuat: {OUT_HTML}")


if __name__ == "__main__":
    buat_dokumen()
