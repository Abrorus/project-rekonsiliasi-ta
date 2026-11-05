"""
buat_docx_bab4.py
=================
Mengonversi docs/BAB4_draft.md dan docs/BAB5_draft.md (beserta gambar visualisasi) ke dalam:
  1. docs/Buku_TA_Bab1_sd_Bab4_Draft.docx (salinan dokumen proposal asli + Bab 4 & Bab 5 dengan style Heading1/2/3 & tabel ITS)
  2. docs/BAB4_Siap_Copas_Word.html       (berisi Bab 4 & Bab 5 lengkap dengan grafik inline, siap Ctrl+A -> Ctrl+C -> Ctrl+V ke Word)

Jalankan:  venv\\Scripts\\python.exe src\\buat_docx_bab4.py
"""
import base64
import re
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DOCS = BASE / "docs"
MD_BAB4 = DOCS / "BAB4_draft.md"
MD_BAB5 = DOCS / "BAB5_draft.md"
SRC_DOCX = Path(r"C:/Users/Abrorus/.gemini/antigravity/brain/f42f9d1b-8f51-4619-9092-15de10e66259/.user_uploaded/media_1793533457852_867bc864.docx")
OUT_DOCX = DOCS / "Buku_TA_Bab1_sd_Bab4_Draft.docx"
OUT_HTML = DOCS / "BAB4_Siap_Copas_Word.html"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", W_NS)


def w(tag):
    return f"{{{W_NS}}}{tag}"


def tambah_runs(p, teks):
    pola = re.compile(r"(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)")
    pos = 0
    for m in pola.finditer(teks):
        if m.start() > pos:
            _run(p, teks[pos:m.start()])
        seg = m.group(0)
        if seg.startswith("**"):
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
    if italic:
        ET.SubElement(rPr, w("i"))
    t = ET.SubElement(r, w("t"))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = teks


def buat_paragraf(teks, style=None, page_break=False, center=False):
    p = ET.Element(w("p"))
    pPr = ET.SubElement(p, w("pPr"))
    if style:
        ps = ET.SubElement(pPr, w("pStyle"))
        ps.set(w("val"), style)
    else:
        jc = ET.SubElement(pPr, w("jc"))
        jc.set(w("val"), "center" if center else "both")
    if page_break:
        r = ET.SubElement(p, w("r"))
        br = ET.SubElement(r, w("br"))
        br.set(w("type"), "page")
    tambah_runs(p, teks)
    return p


def buat_tabel(rows):
    tbl = ET.Element(w("tbl"))
    tblPr = ET.SubElement(tbl, w("tblPr"))
    tblW = ET.SubElement(tblPr, w("tblW"))
    tblW.set(w("w"), "5000")
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
            p = ET.SubElement(tc, w("p"))
            if idx == 0:
                tambah_runs(p, f"**{cell}**")
            else:
                tambah_runs(p, cell)
    return tbl


def parse_markdown(md_teks):
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
                elemen.append(buat_paragraf(f"**[{cap} — sisipkan file docs/{fname}]**", center=True))
            i += 1
        elif line.startswith("# "):
            judul = re.sub(r"\s*\(DRAFT.*\)", "", line[2:].strip())
            judul = re.sub(r"^BAB\s+\d+\s+", "", judul)
            elemen.append(buat_paragraf(judul, style="Heading1", page_break=True))
            i += 1
        elif line.startswith("## "):
            judul = re.sub(r"^\d+\.\d+\s+", "", line[3:].strip())
            elemen.append(buat_paragraf(judul, style="Heading2"))
            i += 1
        elif line.startswith("### "):
            judul = re.sub(r"^\d+\.\d+\.\d+\s+", "", line[4:].strip())
            elemen.append(buat_paragraf(judul, style="Heading3"))
            i += 1
        elif line.startswith("> "):
            elemen.append(buat_paragraf(line[2:].strip()))
            i += 1
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^[-:]+$", c) for c in raw):
                    rows.append(raw)
                i += 1
            if rows:
                elemen.append(buat_tabel(rows))
        else:
            elemen.append(buat_paragraf(line))
            i += 1
    return elemen


def buat_html(md_teks):
    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>BAB 4 & BAB 5 - Siap Copy Paste ke Word</title>",
        "<style>body{font-family:'Times New Roman',serif;font-size:12pt;line-height:1.5;max-width:820px;margin:2em auto;text-align:justify}",
        "h1,h2,h3{font-family:'Times New Roman',serif;text-align:left} table{border-collapse:collapse;width:100%;margin:12pt 0;font-size:11pt}",
        "th,td{border:1px solid #000;padding:4px 8px;text-align:left} th{background:#f2f2f2;font-weight:bold}",
        "figure{text-align:center;margin:16pt 0} figcaption{font-size:11pt;font-weight:bold;margin-top:6pt}</style></head><body>"
    ]
    lines = md_teks.splitlines()
    i = 0

    def fmt(s):
        s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", s)
        s = re.sub(r"`([^`]+)`", r"<i>\1</i>", s)
        return s

    while i < len(lines):
        line = lines[i].strip()
        if not line:
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
            html.append(f"<p><i>{fmt(line[2:])}</i></p>")
            i += 1
        elif line.startswith("|"):
            html.append("<table>")
            first = True
            while i < len(lines) and lines[i].strip().startswith("|"):
                raw = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.match(r"^[-:]+$", c) for c in raw):
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
    md_gabung = MD_BAB4.read_text(encoding="utf-8") + "\n\n" + MD_BAB5.read_text(encoding="utf-8")
    buat_html(md_gabung)
    print(f"HTML (Bab 4 + Bab 5 + Gambar) tersimpan: {OUT_HTML}")

    if not SRC_DOCX.exists():
        return

    elemen = parse_markdown(md_gabung)
    shutil.copyfile(SRC_DOCX, OUT_DOCX)

    with zipfile.ZipFile(SRC_DOCX, "r") as zin:
        xml_bytes = zin.read("word/document.xml")
        semua_item = {name: zin.read(name) for name in zin.namelist() if name != "word/document.xml"}

    root = ET.fromstring(xml_bytes)
    body = root.find(w("body"))

    idx_insert = len(body) - 1
    for idx, child in enumerate(list(body)):
        teks = "".join(t.text or "" for t in child.findall(f".//{w('t')}")).strip().upper()
        if "DAFTAR PUSTAKA" in teks and idx > 40:
            idx_insert = idx
            break

    for offset, el in enumerate(elemen):
        body.insert(idx_insert + offset, el)

    with zipfile.ZipFile(OUT_DOCX, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, content in semua_item.items():
            zout.writestr(name, content)
        zout.writestr("word/document.xml", ET.tostring(root, encoding="utf-8", xml_declaration=True))

    print(f"DOCX (Bab 1 s.d. Bab 5) tersimpan      : {OUT_DOCX}")


if __name__ == "__main__":
    main()
