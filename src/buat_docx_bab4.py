"""
buat_docx_bab4.py
=================
Mengonversi dokumen Proposal menjadi Buku Tugas Akhir Final (Bab 1 s.d. Bab 5) dengan format XML
yang 100% mengikuti template ITS pada Bab 2 dan Bab 3:
  - Heading1 memakai numId=21 ilvl=0 -> otomatis muncul "BAB 4 HASIL DAN PEMBAHASAN" & "BAB 5 KESIMPULAN DAN SARAN"
  - Heading2 memakai numId=21 ilvl=1 -> otomatis muncul "4.1", "4.2", ..., "5.1", "5.2"
  - Heading3 memakai numId=21 ilvl=2 -> otomatis muncul "4.5.1"
  - DAFTAR PUSTAKA & LAMPIRAN diberi numId=0 ilvl=0 -> tidak bernomor bab
  - Paragraf isi memakai indentasi alinea firstLine=720 left=284 seperti Bab 3
  - Gambar grafik PNG ditanamkan langsung ke dalam word/media/ dan word/_rels/document.xml.rels

Jalankan:  venv\\Scripts\\python.exe src\\buat_docx_bab4.py
"""
import base64
import re
import struct
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOCS = BASE / "docs"
MD_ABSTRAK = DOCS / "ABSTRAK_final.md"
MD_BAB4 = DOCS / "BAB4_draft.md"
MD_BAB5 = DOCS / "BAB5_draft.md"
SRC_DOCX = Path(r"C:/Users/Abrorus/.gemini/antigravity/brain/f42f9d1b-8f51-4619-9092-15de10e66259/.user_uploaded/media_1793533457852_867bc864.docx")
OUT_DOCX = DOCS / "Buku_TA_Bab1_sd_Bab4_Draft.docx"
OUT_FINAL_DOCX = DOCS / "Buku_TA_Final_Bab1_sd_Bab5.docx"
OUT_HTML = DOCS / "BAB4_Siap_Copas_Word.html"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WP_NS = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_PKG_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

ET.register_namespace("w", W_NS)
ET.register_namespace("wp", WP_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("pic", PIC_NS)
ET.register_namespace("r", R_NS)

ABSTRAK_ID_FINAL = (
    "Proses rekonsiliasi keuangan berperan penting dalam menjaga konsistensi laporan kas perusahaan. "
    "Namun, perusahaan mitra (software house) masih menghadapi kendala pencocokan mutasi rekening koran "
    "lintas bank secara manual yang tidak efisien dan rentan terhadap kelalaian (human error). Teks "
    "keterangan transaksi perbankan umumnya bersifat pendek, tidak terstruktur, minim konteks, dan memuat "
    "banyak singkatan tidak baku, sehingga pendekatan rule-based konvensional tidak adaptif. Penelitian ini "
    "mengembangkan modul Natural Language Processing (NLP) sebagai bagian dari sistem rekonsiliasi keuangan "
    "cerdas SIREKON (Pool 2). Modul ini mengombinasikan tahapan text preprocessing (normalisasi, tokenisasi, "
    "kamus sinonim perbankan, dan stopword removal), ekstraksi fitur gabungan TF-IDF word n-gram (1-2) serta "
    "character n-gram (3-5), dan algoritme Support Vector Machine (SVM) terkalibrasi untuk memetakan transaksi "
    "ke dalam sub-kategori Chart of Accounts (CoA) pada arus cash in (kredit) dan cash out (debit). Untuk "
    "menangani transaksi ambigu, diterapkan mekanisme confidence threshold yang mengalihkan prediksi "
    "berkepercayaan rendah ke modul Knowledge Base (Pool 3) guna divalidasi menggunakan aturan forward chaining "
    "berbasis data ERP. Hasil pengujian 5-fold Stratified Cross-Validation pada data transaksi riil menunjukkan "
    "bahwa kombinasi TF-IDF dan SVM Linear mencapai akurasi 95,5% dan Macro-F1 0,895, mengungguli Random Forest "
    "(Macro-F1 0,776), SBERT (0,780), dan FinBERT (0,771; signifikan secara statistik dengan p = 0,0168). Pada "
    "nilai ambang optimal 0,72, modul NLP mengklasifikasikan 82,80% transaksi secara otomatis dengan tingkat "
    "akurasi 99,57% serta menyaring 93,3% kesalahan prediksi ke Pool 3. Integrasi hibrida antara Pool 2 dan "
    "Pool 3 menghasilkan Overall System Coverage sebesar 94,62% dengan akurasi gabungan 98,11%, sehingga hanya "
    "menyisakan 5,38% transaksi yang memerlukan konfirmasi manual staf keuangan."
)

ABSTRAK_EN_FINAL = (
    "The financial reconciliation process plays a vital role in maintaining consistent corporate cash statements. "
    "However, the partner software house faces operational challenges with manual, inefficient, and error-prone "
    "matching of heterogeneous bank statements. Banking transaction narrations are typically short, unstructured, "
    "lack context, and contain non-standard abbreviations, rendering conventional rule-based approaches non-adaptive. "
    "This study develops a Natural Language Processing (NLP) module within the intelligent financial reconciliation "
    "system SIREKON (Pool 2). The module combines text preprocessing (normalization, tokenization, banking synonym "
    "dictionary, and stopword removal), hybrid TF-IDF feature extraction using word n-grams (1-2) and character "
    "n-grams (3-5), and a calibrated Support Vector Machine (SVM) classifier to map transaction narrations into "
    "Chart of Accounts (CoA) sub-categories across cash in (credit) and cash out (debit) flows. To handle ambiguous "
    "transactions, a confidence threshold mechanism routes low-confidence predictions to the Knowledge Base module "
    "(Pool 3) for cross-validation using ERP-based forward chaining rules. Evaluation using 5-fold Stratified "
    "Cross-Validation on real transaction data demonstrates that the TF-IDF and Linear SVM combination achieves "
    "95.5% accuracy and a Macro-F1 score of 0.895, outperforming Random Forest (Macro-F1 0.776), SBERT (0.780), "
    "and FinBERT (0.771; statistically significant at p = 0.0168). At the optimal threshold of 0.72, the NLP module "
    "automatically classifies 82.80% of transactions with 99.57% accuracy while successfully filtering 93.3% of "
    "misclassifications to Pool 3. The hybrid integration of Pool 2 and Pool 3 achieves an Overall System Coverage "
    "of 94.62% with a combined accuracy of 98.11%, leaving only 5.38% of transactions requiring manual review by "
    "finance staff."
)


def w(tag):
    return f"{{{W_NS}}}{tag}"


def bersihkan_latex(teks):
    """Ubah notasi LaTeX sederhana ($\\alpha = 0,05$, dll.) menjadi karakter Unicode bersih untuk Word."""
    teks = teks.replace(r"\alpha", "α").replace(r"\tau^*", "τ*").replace(r"\tau", "τ")
    teks = re.sub(r"\$([^$]+)\$", r"\1", teks)
    return teks


def get_p_text(p):
    return "".join(t.text or "" for t in p.findall(f".//{w('t')}")).strip()


def set_p_text_keep_first_rpr(p, new_text):
    runs = p.findall(w("r"))
    first_rpr = None
    if runs:
        rpr = runs[0].find(w("rPr"))
        if rpr is not None:
            first_rpr = ET.fromstring(ET.tostring(rpr))
    for r in list(runs):
        p.remove(r)
    new_r = ET.SubElement(p, w("r"))
    if first_rpr is not None:
        new_r.append(first_rpr)
    t = ET.SubElement(new_r, w("t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = new_text


def set_num_pr(pPr, num_id, ilvl):
    old = pPr.find(w("numPr"))
    if old is not None:
        pPr.remove(old)
    numPr = ET.SubElement(pPr, w("numPr"))
    ilvl_el = ET.SubElement(numPr, w("ilvl"))
    ilvl_el.set(w("val"), str(ilvl))
    numId_el = ET.SubElement(numPr, w("numId"))
    numId_el.set(w("val"), str(num_id))


def ubah_proposal_jadi_buku_ta(body):
    judul_ta = "SIREKON: PENGEMBANGAN MODUL UNTUK KLASIFIKASI TEKS BERITA TRANSAKSI TRANSFER PADA SISTEM REKONSILIASI KEUANGAN"
    for p in body.findall(f".//{w('p')}"):
        teks = get_p_text(p)
        pPr = p.find(w("pPr"))
        # Pastikan Heading1 non-bab (LEMBAR PENGESAHAN, ABSTRAK, DAFTAR ISI, DAFTAR PUSTAKA, LAMPIRAN) diberi numId=0
        if pPr is not None:
            ps = pPr.find(w("pStyle"))
            if ps is not None and ps.attrib.get(w("val")) == "Heading1":
                if teks.upper() in ("LEMBAR PENGESAHAN", "ABSTRAK", "ABSTRACT", "DAFTAR ISI",
                                    "DAFTAR GAMBAR", "DAFTAR TABEL", "DAFTAR SIMBOL",
                                    "DAFTAR PUSTAKA", "LAMPIRAN", ""):
                    set_num_pr(pPr, 0, 0)

        if not teks:
            continue
        if teks == "PROPOSAL TUGAS AKHIR":
            set_p_text_keep_first_rpr(p, "TUGAS AKHIR")
        elif "JUDUL PROPOSAL TUGAS AKHIR DITULIS SINGKAT" in teks:
            set_p_text_keep_first_rpr(p, judul_ta)
        elif teks == "NRP. 5026231245":
            set_p_text_keep_first_rpr(p, "NRP. 5026231145")
        elif "Disetujui oleh Tim Penguji Proposal Tugas Akhir" in teks:
            set_p_text_keep_first_rpr(p, "Disetujui oleh Tim Penguji Tugas Akhir :")
        elif teks == "Juni, 2026":
            set_p_text_keep_first_rpr(p, "November, 2026")
        elif teks.startswith("Proses rekonsiliasi keuangan penting untuk menjaga konsistensi"):
            set_p_text_keep_first_rpr(p, ABSTRAK_ID_FINAL)
        elif teks.startswith("The financial reconciliation process is crucial for maintaining"):
            set_p_text_keep_first_rpr(p, ABSTRAK_EN_FINAL)
        elif "Dalam penyusunan proposal tugas akhir ini" in teks:
            set_p_text_keep_first_rpr(p, teks.replace("Dalam penyusunan proposal tugas akhir ini", "Dalam penyusunan tugas akhir ini"))
        elif "mengusulkan pengembangan modul Natural Language Processing" in teks:
            set_p_text_keep_first_rpr(p, teks.replace("mengusulkan pengembangan", "mengembangkan").replace("Modul NLP akan menerapkan", "Modul NLP menerapkan"))

    # Hapus Subbab 3.3 Rencana Jadwal Pelaksanaan Penelitian + Tabel 3.1 di Bab 3
    children = list(body)
    hapus_mulai = None
    hapus_sampai = None
    for idx, el in enumerate(children):
        t = "".join(x.text or "" for x in el.findall(f".//{w('t')}")).strip()
        if idx > 200 and t == "Rencana Jadwal Pelaksanaan Penelitian":
            hapus_mulai = idx
        elif hapus_mulai is not None and t.upper() == "DAFTAR PUSTAKA":
            hapus_sampai = idx
            break
    if hapus_mulai is not None and hapus_sampai is not None:
        for el in children[hapus_mulai:hapus_sampai]:
            body.remove(el)


def tambah_runs(p, teks):
    teks = bersihkan_latex(teks)
    pola = re.compile(r"(\*\*\*[^*]+\*\*\*|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")
    pos = 0
    for m in pola.finditer(teks):
        if m.start() > pos:
            _run(p, teks[pos:m.start()])
        seg = m.group(0)
        if seg.startswith("***"):
            _run(p, seg[3:-3], bold=True, italic=True)
        elif seg.startswith("**"):
            _run(p, seg[2:-2], bold=True)
        elif seg.startswith("*"):
            _run(p, seg[1:-1], italic=True)
        else:
            _run(p, seg[1:-1], italic=True)
        pos = m.end()
    if pos < len(teks):
        _run(p, teks[pos:])


def _run(p, teks, bold=False, italic=False):
    if not teks:
        return
    r = ET.SubElement(p, w("r"))
    rPr = ET.SubElement(r, w("rPr"))
    if bold:
        ET.SubElement(rPr, w("b"))
        ET.SubElement(rPr, w("bCs"))
    if italic:
        ET.SubElement(rPr, w("i"))
        ET.SubElement(rPr, w("iCs"))
    t = ET.SubElement(r, w("t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = teks


def buat_heading_bab(judul):
    """Persis menyamai XML BAB 2 TINJAUAN PUSTAKA & BAB 3 METODOLOGI (numId=21, ilvl=0)."""
    p = ET.Element(w("p"))
    pPr = ET.SubElement(p, w("pPr"))
    ps = ET.SubElement(pPr, w("pStyle"))
    ps.set(w("val"), "Heading1")
    set_num_pr(pPr, 21, 0)
    ind = ET.SubElement(pPr, w("ind"))
    ind.set(w("left"), "0")
    ind.set(w("firstLine"), "708")
    # Page break sebelum judul Bab baru
    r_br = ET.SubElement(p, w("r"))
    br = ET.SubElement(r_br, w("br"))
    br.set(w("type"), "page")
    tambah_runs(p, judul)
    return p


def buat_heading_subbab(judul, level=2):
    """Persis menyamai XML Subbab 3.1/3.2 (level=2 -> ilvl=1) dan 3.2.1 (level=3 -> ilvl=2)."""
    p = ET.Element(w("p"))
    pPr = ET.SubElement(p, w("pPr"))
    ps = ET.SubElement(pPr, w("pStyle"))
    ps.set(w("val"), f"Heading{level}")
    set_num_pr(pPr, 21, level - 1)
    sp = ET.SubElement(pPr, w("spacing"))
    sp.set(w("before"), "240")
    sp.set(w("after"), "120")
    ind = ET.SubElement(pPr, w("ind"))
    ind.set(w("left"), "1004")
    if level == 2:
        ind.set(w("hanging"), "720")
    else:
        rPr = ET.SubElement(pPr, w("rPr"))
        ET.SubElement(rPr, w("b"))
        ET.SubElement(rPr, w("bCs"))
    tambah_runs(p, judul)
    return p


def buat_paragraf_isi(teks, judul_tabel=False, butir_list=False, center=False):
    """Persis menyamai XML paragraf isi di Bab 3 (ind left=284, firstLine=720)."""
    p = ET.Element(w("p"))
    pPr = ET.SubElement(p, w("pPr"))
    sp = ET.SubElement(pPr, w("spacing"))
    if judul_tabel:
        sp.set(w("before"), "180")
        sp.set(w("after"), "60")
        ind = ET.SubElement(pPr, w("ind"))
        ind.set(w("left"), "284")
        tambah_runs(p, f"**{teks}**")
        return p
    elif center:
        sp.set(w("before"), "80")
        sp.set(w("after"), "160")
        jc = ET.SubElement(pPr, w("jc"))
        jc.set(w("val"), "center")
        tambah_runs(p, teks)
        return p
    elif butir_list:
        sp.set(w("before"), "80")
        sp.set(w("after"), "80")
        ind = ET.SubElement(pPr, w("ind"))
        ind.set(w("left"), "644")
        ind.set(w("hanging"), "360")
        tambah_runs(p, teks)
        return p
    else:
        sp.set(w("before"), "120")
        sp.set(w("after"), "120")
        ind = ET.SubElement(pPr, w("ind"))
        ind.set(w("left"), "284")
        ind.set(w("firstLine"), "720")
        tambah_runs(p, teks)
        return p


def buat_paragraf_gambar(r_id, img_path, doc_pr_id):
    """Membuat elemen w:p yang berisi w:drawing inline untuk gambar PNG."""
    data = Path(img_path).read_bytes()
    w_px, h_px = struct.unpack("!II", data[16:24])
    # Lebar gambar di halaman Word ~ 14.5 cm = 5220000 EMU
    cx = 5220000
    cy = int(cx * (h_px / max(1, w_px)))

    xml_str = (
        f'<w:p xmlns:w="{W_NS}" xmlns:wp="{WP_NS}" xmlns:a="{A_NS}" xmlns:pic="{PIC_NS}" xmlns:r="{R_NS}">'
        f'<w:pPr><w:spacing w:before="160" w:after="60"/><w:jc w:val="center"/></w:pPr>'
        f'<w:r><w:rPr><w:noProof/></w:rPr>'
        f'<w:drawing><wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{doc_pr_id}" name="Picture {doc_pr_id}"/>'
        f'<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        f'<a:graphic><a:graphicData uri="{PIC_NS}">'
        f'<pic:pic>'
        f'<pic:nvPicPr><pic:cNvPr id="0" name="img_{doc_pr_id}.png"/><pic:cNvPicPr><a:picLocks noChangeAspect="1"/></pic:cNvPicPr></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{r_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        f'</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    )
    return ET.fromstring(xml_str)


def buat_tabel(rows):
    tbl = ET.Element(w("tbl"))
    tblPr = ET.SubElement(tbl, w("tblPr"))
    tblInd = ET.SubElement(tblPr, w("tblInd"))
    tblInd.set(w("w"), "284")
    tblInd.set(w("type"), "dxa")
    tblW = ET.SubElement(tblPr, w("tblW"))
    tblW.set(w("w"), "4800")
    tblW.set(w("type"), "pct")
    borders = ET.SubElement(tblPr, w("tblBorders"))
    for b in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        el = ET.SubElement(borders, w(b))
        el.set(w("val"), "single")
        el.set(w("sz"), "4")
        el.set(w("space"), "0")
        el.set(w("color"), "000000")
    for idx, row in enumerate(rows):
        tr = ET.SubElement(tbl, w("tr"))
        for cell in row:
            tc = ET.SubElement(tr, w("tc"))
            tcPr = ET.SubElement(tc, w("tcPr"))
            if idx == 0:
                shd = ET.SubElement(tcPr, w("shd"))
                shd.set(w("val"), "clear")
                shd.set(w("color"), "auto")
                shd.set(w("fill"), "EDEDED")
            p = ET.SubElement(tc, w("p"))
            pPr = ET.SubElement(p, w("pPr"))
            sp = ET.SubElement(pPr, w("spacing"))
            sp.set(w("before"), "40")
            sp.set(w("after"), "40")
            if idx == 0:
                tambah_runs(p, f"**{cell}**")
            else:
                tambah_runs(p, cell)
    return tbl


def parse_markdown(md_teks, daftar_gambar):
    """Mengubah teks Markdown Bab 4 & Bab 5 menjadi daftar elemen XML Word."""
    elemen = []
    lines = md_teks.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.startswith("!["):
            m = re.match(r"!\[([^\]]+)\]\(([^)]+)\)", line)
            if m:
                cap, fname = m.group(1), m.group(2).replace(".svg", ".png")
                img_path = DOCS / fname
                if img_path.exists():
                    idx_img = len(daftar_gambar) + 1
                    r_id = f"rIdBab4Img{idx_img}"
                    media_name = f"media/bab4_img{idx_img}.png"
                    daftar_gambar.append((r_id, media_name, img_path))
                    elemen.append(buat_paragraf_gambar(r_id, img_path, 900 + idx_img))
                    elemen.append(buat_paragraf_isi(cap, center=True))
            i += 1
        elif line.startswith("# "):
            judul = re.sub(r"\s*\(DRAFT.*\)", "", line[2:].strip())
            judul = re.sub(r"^BAB\s+\d+\s+", "", judul)
            elemen.append(buat_heading_bab(judul))
            i += 1
        elif line.startswith("## "):
            judul = re.sub(r"^\d+\.\d+\s+", "", line[3:].strip())
            elemen.append(buat_heading_subbab(judul, level=2))
            i += 1
        elif line.startswith("### "):
            judul = re.sub(r"^\d+\.\d+\.\d+\s+", "", line[4:].strip())
            elemen.append(buat_heading_subbab(judul, level=3))
            i += 1
        elif line.startswith("> "):
            # Catatan internal draf dilewati pada dokumen Word resmi
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^[-:\s]+$", c) for c in raw):
                    rows.append(raw)
                i += 1
            if rows:
                elemen.append(buat_tabel(rows))
        elif re.match(r"^Tabel\s+4\.\d+\s+", line):
            elemen.append(buat_paragraf_isi(line, judul_tabel=True))
            i += 1
        elif re.match(r"^\d+\.\s+", line):
            elemen.append(buat_paragraf_isi(line, butir_list=True))
            i += 1
        else:
            elemen.append(buat_paragraf_isi(line))
            i += 1
    return elemen


def buat_html(md_teks):
    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>Abstrak, Bab 4 & Bab 5 - Siap Copy Paste ke Word</title>",
        "<style>body{font-family:'Times New Roman',serif;font-size:12pt;line-height:1.5;max-width:820px;margin:2em auto;text-align:justify}",
        "h1,h2,h3{font-family:'Times New Roman',serif;text-align:left} table{border-collapse:collapse;width:100%;margin:12pt 0;font-size:11pt}",
        "th,td{border:1px solid #000;padding:4px 8px;text-align:left} th{background:#f2f2f2;font-weight:bold}",
        "figure{text-align:center;margin:16pt 0} figcaption{font-size:11pt;font-weight:bold;margin-top:6pt}</style></head><body>"
    ]
    lines = md_teks.splitlines()
    i = 0

    def fmt(s):
        s = bersihkan_latex(s)
        s = re.sub(r"\*\*\*([^*]+)\*\*\*", r"<b><i>\1</i></b>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", s)
        s = re.sub(r"`([^`]+)`", r"<i>\1</i>", s)
        return s

    while i < len(lines):
        line = lines[i].strip()
        if not line or line == "---":
            i += 1
            continue
        if line.startswith("!["):
            m = re.match(r"!\[([^\]]+)\]\(([^)]+)\)", line)
            if m:
                cap, fname = m.group(1), m.group(2)
                png_path = DOCS / fname.replace(".svg", ".png")
                svg_path = DOCS / fname
                if png_path.exists():
                    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
                    html.append(f"<figure><img src='data:image/png;base64,{b64}' style='max-width:100%;border:1px solid #ccc'/><figcaption>{cap}</figcaption></figure>")
                elif svg_path.exists():
                    html.append(f"<figure>{svg_path.read_text(encoding='utf-8')}<figcaption>{cap}</figcaption></figure>")
            i += 1
        elif line.startswith("# "):
            html.append(f"<h1>{fmt(line[2:])}</h1>")
            i += 1
        elif line.startswith("## "):
            html.append(f"<h2>{fmt(line[3:])}</h2>")
            i += 1
        elif line.startswith("### "):
            html.append(f"<h3>{fmt(line[4:])}</h3>")
            i += 1
        elif line.startswith("> "):
            i += 1
        elif line.startswith("|"):
            html.append("<table>")
            first = True
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^[-:\s]+$", c) for c in raw):
                    tag = "th" if first else "td"
                    html.append("<tr>" + "".join(f"<{tag}>{fmt(c)}</{tag}>" for c in raw) + "</tr>")
                    first = False
                i += 1
            html.append("</table>")
        else:
            html.append(f"<p>{fmt(line)}</p>")
            i += 1
    html.append("</body></html>")
    OUT_HTML.write_text("\n".join(html), encoding="utf-8")


def main():
    md_bab45 = MD_BAB4.read_text(encoding="utf-8") + "\n\n" + MD_BAB5.read_text(encoding="utf-8")
    md_html = (MD_ABSTRAK.read_text(encoding="utf-8") + "\n\n" if MD_ABSTRAK.exists() else "") + md_bab45
    buat_html(md_html)
    print(f"HTML (Abstrak + Bab 4 + Bab 5 + Gambar) tersimpan: {OUT_HTML}")

    if not SRC_DOCX.exists():
        return

    daftar_gambar = []
    elemen = parse_markdown(md_bab45, daftar_gambar)

    with zipfile.ZipFile(SRC_DOCX, "r") as zin:
        xml_bytes = zin.read("word/document.xml")
        rels_bytes = zin.read("word/_rels/document.xml.rels")
        semua_item = {name: zin.read(name) for name in zin.namelist()
                      if name not in ("word/document.xml", "word/_rels/document.xml.rels")}

    root = ET.fromstring(xml_bytes)
    body = root.find(w("body"))

    ubah_proposal_jadi_buku_ta(body)

    idx_insert = len(body) - 1
    for idx, child in enumerate(list(body)):
        teks = "".join(t.text or "" for t in child.findall(f".//{w('t')}")).strip().upper()
        if teks == "DAFTAR PUSTAKA" and idx > 200:
            idx_insert = idx
            break

    for offset, el in enumerate(elemen):
        body.insert(idx_insert + offset, el)

    # Tambahkan relationship gambar baru ke word/_rels/document.xml.rels
    ET.register_namespace("", REL_PKG_NS)
    rels_root = ET.fromstring(rels_bytes)
    for r_id, media_name, img_path in daftar_gambar:
        rel_el = ET.SubElement(rels_root, f"{{{REL_PKG_NS}}}Relationship")
        rel_el.set("Id", r_id)
        rel_el.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
        rel_el.set("Target", media_name)
        semua_item[f"word/{media_name}"] = Path(img_path).read_bytes()

    xml_out = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    rels_out = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

    for target_docx in [OUT_FINAL_DOCX, OUT_DOCX]:
        try:
            with zipfile.ZipFile(target_docx, "w", zipfile.ZIP_DEFLATED) as zout:
                for name, content in semua_item.items():
                    zout.writestr(name, content)
                zout.writestr("word/document.xml", xml_out)
                zout.writestr("word/_rels/document.xml.rels", rels_out)
            print(f"DOCX Buku TA Final tersimpan                     : {target_docx}")
        except PermissionError:
            alt = target_docx.with_name(target_docx.stem + "_Terbaru.docx")
            with zipfile.ZipFile(alt, "w", zipfile.ZIP_DEFLATED) as zout:
                for name, content in semua_item.items():
                    zout.writestr(name, content)
                zout.writestr("word/document.xml", xml_out)
                zout.writestr("word/_rels/document.xml.rels", rels_out)
            print(f"File sedang dibuka di Word, disimpan ke          : {alt}")


if __name__ == "__main__":
    main()
