"""
buat_visualisasi_bab4.py
========================
Menghasilkan grafik visualisasi untuk Bab 4 (format SVG untuk HTML/dokumen dan PNG untuk MS Word):
  1. docs/gambar_4_1_confusion_matrix.svg  (.png) - Heatmap Confusion Matrix 14 Sub-Kategori CoA
  2. docs/gambar_4_2_kurva_threshold.svg   (.png) - Kurva Confidence Threshold vs Macro-F1 & Coverage
  3. docs/gambar_4_3_perbandingan_model.svg(.png) - Grafik Batang Perbandingan SVM, RF, SBERT, FinBERT

Tidak memerlukan matplotlib/PIL (menggunakan SVG + encoder PNG murni dengan zlib/struct bawaan Python).
"""
import struct
import zlib
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
DOCS = BASE / "docs"
DOCS.mkdir(exist_ok=True)


# ---------------------------------------------------------------------
# MINI BITMAP FONT 5x7 & PNG ENCODER (murni stdlib)
# ---------------------------------------------------------------------
FONT_5X7 = {
    " ": [0,0,0,0,0,0,0],
    "0": [14,17,19,21,25,17,14], "1": [4,12,4,4,4,4,14], "2": [14,17,1,6,8,16,31],
    "3": [31,2,4,2,1,17,14], "4": [2,6,10,18,31,2,2], "5": [31,16,30,1,1,17,14],
    "6": [6,8,16,30,17,17,14], "7": [31,1,2,4,8,8,8], "8": [14,17,17,14,17,17,14],
    "9": [14,17,17,15,1,2,12], ".": [0,0,0,0,0,12,12], ",": [0,0,0,0,12,4,8],
    "%": [25,25,2,4,8,19,19], "-": [0,0,0,31,0,0,0], "_": [0,0,0,0,0,0,31],
    "(": [2,4,8,8,8,4,2], ")": [8,4,2,2,2,4,8], "+": [0,4,4,31,4,4,0],
    "/": [1,2,2,4,8,8,16], ":": [0,12,12,0,12,12,0], "=": [0,0,31,0,31,0,0],
    "A": [14,17,17,31,17,17,17], "B": [30,17,17,30,17,17,30], "C": [14,17,16,16,16,17,14],
    "D": [28,18,17,17,17,18,28], "E": [31,16,16,30,16,16,31], "F": [31,16,16,30,16,16,16],
    "G": [14,17,16,23,17,17,15], "H": [17,17,17,31,17,17,17], "I": [14,4,4,4,4,4,14],
    "J": [7,2,2,2,2,18,12], "K": [17,18,20,24,20,18,17], "L": [16,16,16,16,16,16,31],
    "M": [17,27,21,21,17,17,17], "N": [17,25,21,19,17,17,17], "O": [14,17,17,17,17,17,14],
    "P": [30,17,17,30,16,16,16], "Q": [14,17,17,17,21,18,13], "R": [30,17,17,30,20,18,17],
    "S": [15,16,16,14,1,1,30], "T": [31,4,4,4,4,4,4], "U": [17,17,17,17,17,17,14],
    "V": [17,17,17,17,17,10,4], "W": [17,17,17,21,21,27,17], "X": [17,17,10,4,10,17,17],
    "Y": [17,17,10,4,4,4,4], "Z": [31,1,2,4,8,16,31],
}


class Canvas:
    def __init__(self, w, h, bg=(255, 255, 255)):
        self.w, self.h = w, h
        self.img = np.full((h, w, 3), bg, dtype=np.uint8)

    def rect(self, x0, y0, x1, y1, color, border=None):
        x0, x1 = max(0, int(x0)), min(self.w, int(x1))
        y0, y1 = max(0, int(y0)), min(self.h, int(y1))
        if x1 > x0 and y1 > y0:
            self.img[y0:y1, x0:x1] = color
            if border:
                self.img[y0:min(self.h, y0+1), x0:x1] = border
                self.img[max(0, y1-1):y1, x0:x1] = border
                self.img[y0:y1, x0:min(self.w, x0+1)] = border
                self.img[y0:y1, max(0, x1-1):x1] = border

    def line(self, x0, y0, x1, y1, color, thick=2):
        steps = int(max(abs(x1 - x0), abs(y1 - y0), 1) * 2)
        xs = np.linspace(x0, x1, steps).astype(int)
        ys = np.linspace(y0, y1, steps).astype(int)
        for x, y in zip(xs, ys):
            self.rect(x - thick // 2, y - thick // 2, x + (thick + 1) // 2, y + (thick + 1) // 2, color)

    def text(self, x, y, s, color=(20, 20, 20), scale=1, align="left"):
        s = str(s).upper()
        total_w = len(s) * 6 * scale
        if align == "center":
            x -= total_w // 2
        elif align == "right":
            x -= total_w
        cx = int(x)
        cy = int(y)
        for ch in s:
            glyph = FONT_5X7.get(ch, FONT_5X7[" "])
            for r_idx, row_bits in enumerate(glyph):
                for c_idx in range(5):
                    if (row_bits >> (4 - c_idx)) & 1:
                        px = cx + c_idx * scale
                        py = cy + r_idx * scale
                        self.rect(px, py, px + scale, py + scale, color)
            cx += 6 * scale

    def save_png(self, path):
        raw = b"".join(b"\x00" + self.img[y].tobytes() for y in range(self.h))
        def chunk(tag, data):
            return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        ihdr = struct.pack("!IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0)
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
        Path(path).write_bytes(png)


# ---------------------------------------------------------------------
# 1. CONFUSION MATRIX (14x14)
# ---------------------------------------------------------------------
def buat_gambar_cm():
    df_cm = pd.read_csv(DATA / "confusion_matrix_coa.csv", index_col=0)
    labels = list(df_cm.index)
    singkat = [l[:12] for l in labels]
    mat = df_cm.values
    n = len(labels)
    vmax = max(1, mat.max())

    # SVG
    cell = 38
    left, top, right, bottom = 160, 70, 40, 40
    W, H = left + n * cell + right, top + n * cell + bottom
    svg = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' style='font-family:Arial,sans-serif;background:#fff'>",
           f"<text x='{W//2}' y='28' text-anchor='middle' font-size='15' font-weight='bold'>Confusion Matrix 5-Fold CV (TF-IDF + SVM Linear, 14 Sub-Kategori CoA)</text>"]
    for i in range(n):
        svg.append(f"<text x='{left - 8}' y='{top + i*cell + cell//2 + 4}' text-anchor='end' font-size='10'>{labels[i]}</text>")
        svg.append(f"<text x='{left + i*cell + cell//2}' y='{top - 8}' text-anchor='middle' font-size='9'>{i+1}</text>")
        for j in range(n):
            v = int(mat[i, j])
            if v == 0:
                bg, fg = "#f8f9fa", "#bbbbbb"
            elif i == j:
                intens = int(220 - 140 * (np.log1p(v) / np.log1p(vmax)))
                bg = f"rgb({intens-30},{intens+10},255)"
                fg = "#000000" if intens > 130 else "#ffffff"
            else:
                bg, fg = "#ffd6d6", "#900000"
            x, y = left + j * cell, top + i * cell
            svg.append(f"<rect x='{x}' y='{y}' width='{cell}' height='{cell}' fill='{bg}' stroke='#ccc'/>")
            svg.append(f"<text x='{x + cell//2}' y='{y + cell//2 + 4}' text-anchor='middle' font-size='11' fill='{fg}' font-weight='{'bold' if v>0 else 'normal'}'>{v}</text>")
    svg.append("</svg>")
    (DOCS / "gambar_4_1_confusion_matrix.svg").write_text("\n".join(svg), encoding="utf-8")

    # PNG
    c = Canvas(W, H)
    c.text(W // 2, 16, "CONFUSION MATRIX 5-FOLD CV (TF-IDF + SVM)", scale=2, align="center")
    for i in range(n):
        c.text(left - 8, top + i * cell + 14, f"{i+1}.{singkat[i]}", scale=1, align="right")
        c.text(left + i * cell + cell // 2, top - 14, str(i + 1), scale=1, align="center")
        for j in range(n):
            v = int(mat[i, j])
            if v == 0:
                col, tc = (248, 249, 250), (190, 190, 190)
            elif i == j:
                k = int(215 - 135 * (np.log1p(v) / np.log1p(vmax)))
                col = (max(30, k - 40), min(255, k), 250)
                tc = (10, 10, 10) if k > 125 else (255, 255, 255)
            else:
                col, tc = (255, 210, 210), (160, 0, 0)
            x, y = left + j * cell, top + i * cell
            c.rect(x, y, x + cell, y + cell, col, border=(205, 205, 205))
            c.text(x + cell // 2, y + 15, str(v), color=tc, scale=1, align="center")
    c.save_png(DOCS / "gambar_4_1_confusion_matrix.png")


# ---------------------------------------------------------------------
# 2. KURVA CONFIDENCE THRESHOLD
# ---------------------------------------------------------------------
def buat_gambar_threshold():
    df = pd.read_csv(DATA / "hasil_threshold_coa.csv")
    df = df[df["threshold"] <= 0.90].reset_index(drop=True)
    W, H = 720, 400
    L, T, R, B = 70, 50, 40, 60
    pw, ph = W - L - R, H - T - B

    def xy(t, val):
        x = L + (t - 0.50) / 0.40 * pw
        y = T + (1.0 - val) * ph
        return int(x), int(y)

    # SVG
    svg = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' style='font-family:Arial,sans-serif;background:#fff'>",
           f"<text x='{W//2}' y='26' text-anchor='middle' font-size='15' font-weight='bold'>Kurva Optimasi Confidence Threshold (Macro-F1 vs Auto-Classification Rate)</text>",
           f"<rect x='{L}' y='{T}' width='{pw}' height='{ph}' fill='none' stroke='#333'/>"]
    for v in [0.0, 0.2, 0.4, 0.6, 0.7, 0.8, 1.0]:
        _, y = xy(0.5, v)
        svg.append(f"<line x1='{L}' y1='{y}' x2='{L+pw}' y2='{y}' stroke='#e0e0e0' stroke-dasharray='3,3'/>")
        svg.append(f"<text x='{L-8}' y='{y+4}' text-anchor='end' font-size='11'>{int(v*100)}%</text>")
    for t in [0.50, 0.55, 0.60, 0.65, 0.70, 0.72, 0.75, 0.80, 0.85, 0.90]:
        x, _ = xy(t, 0)
        svg.append(f"<text x='{x}' y='{T+ph+20}' text-anchor='middle' font-size='11'>{t:.2f}</text>")

    pts_f1 = " ".join(f"{xy(r.threshold, r.f1_macro_auto)[0]},{xy(r.threshold, r.f1_macro_auto)[1]}" for _, r in df.iterrows())
    pts_cov = " ".join(f"{xy(r.threshold, r.auto_rate)[0]},{xy(r.threshold, r.auto_rate)[1]}" for _, r in df.iterrows())
    x_opt, y_opt = xy(0.72, 0.995)
    svg.append(f"<line x1='{x_opt}' y1='{T}' x2='{x_opt}' y2='{T+ph}' stroke='#d9534f' stroke-width='2' stroke-dasharray='5,4'/>")
    svg.append(f"<polyline fill='none' stroke='#1f77b4' stroke-width='2.5' points='{pts_f1}'/>")
    svg.append(f"<polyline fill='none' stroke='#2ca02c' stroke-width='2.5' points='{pts_cov}'/>")
    svg.append(f"<circle cx='{x_opt}' cy='{y_opt}' r='5' fill='#d9534f'/>")
    svg.append(f"<text x='{x_opt+8}' y='{T+25}' font-size='11' fill='#d9534f' font-weight='bold'>Optimal t* = 0.72 (F1=99.5%, Auto=82.8%)</text>")
    svg.append("</svg>")
    (DOCS / "gambar_4_2_kurva_threshold.svg").write_text("\n".join(svg), encoding="utf-8")

    # PNG
    c = Canvas(W, H)
    c.text(W // 2, 16, "OPTIMASI CONFIDENCE THRESHOLD (F1 VS COVERAGE)", scale=2, align="center")
    c.rect(L, T, L + pw, T + ph, (252, 252, 252), border=(80, 80, 80))
    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        _, y = xy(0.5, v)
        c.line(L, y, L + pw, y, (230, 230, 230), thick=1)
        c.text(L - 8, y - 3, f"{int(v*100)}%", scale=1, align="right")
    for t in [0.50, 0.60, 0.70, 0.72, 0.80, 0.90]:
        x, _ = xy(t, 0)
        c.text(x, T + ph + 10, f"{t:.2f}", scale=1, align="center")
    c.text(W // 2, H - 20, "CONFIDENCE THRESHOLD", scale=1, align="center")

    prev_f1, prev_cov = None, None
    for _, r in df.iterrows():
        p1 = xy(r.threshold, r.f1_macro_auto)
        p2 = xy(r.threshold, r.auto_rate)
        if prev_f1:
            c.line(prev_f1[0], prev_f1[1], p1[0], p1[1], (31, 119, 180), thick=3)
            c.line(prev_cov[0], prev_cov[1], p2[0], p2[1], (44, 160, 44), thick=3)
        prev_f1, prev_cov = p1, p2
    c.line(x_opt, T, x_opt, T + ph, (217, 83, 79), thick=2)
    c.text(x_opt - 5, T + 12, "OPT=0.72 (F1=99.5%, AUTO=82.8%)", color=(200, 40, 40), scale=1, align="right")
    c.text(L + 15, T + ph - 35, "BIRU: MACRO-F1 (AUTO)", color=(31, 119, 180), scale=1)
    c.text(L + 15, T + ph - 20, "HIJAU: AUTO-CLASSIFICATION RATE", color=(44, 160, 44), scale=1)
    c.save_png(DOCS / "gambar_4_3_tmp.png")
    (DOCS / "gambar_4_3_tmp.png").replace(DOCS / "gambar_4_2_kurva_threshold.png")


# ---------------------------------------------------------------------
# 3. PERBANDINGAN 4 MODEL KLASIFIKASI
# ---------------------------------------------------------------------
def buat_gambar_perbandingan():
    df = pd.read_csv(DATA / "hasil_banding_model_coa.csv")
    W, H = 720, 380
    L, T, R, B = 70, 55, 30, 65
    pw, ph = W - L - R, H - T - B

    c = Canvas(W, H)
    c.text(W // 2, 16, "PERBANDINGAN PERFORMA MODEL KLASIFIKASI (5-FOLD CV)", scale=2, align="center")
    c.rect(L, T, L + pw, T + ph, (252, 252, 252), border=(80, 80, 80))

    for v in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        y = int(T + (1.0 - v) * ph)
        c.line(L, y, L + pw, y, (230, 230, 230), thick=1)
        c.text(L - 8, y - 3, f"{v:.1f}", scale=1, align="right")

    metrik_cols = [("accuracy", (52, 152, 219), "ACC"),
                   ("precision_macro", (46, 204, 113), "PREC"),
                   ("recall_macro", (241, 196, 15), "REC"),
                   ("f1_macro", (231, 76, 60), "F1")]
    grup_w = pw // len(df)
    bar_w = 24

    svg = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}' style='font-family:Arial,sans-serif;background:#fff'>",
           f"<text x='{W//2}' y='28' text-anchor='middle' font-size='15' font-weight='bold'>Perbandingan Model Klasifikasi (5-Fold Stratified CV)</text>",
           f"<rect x='{L}' y='{T}' width='{pw}' height='{ph}' fill='none' stroke='#333'/>"]

    for idx, row in df.iterrows():
        gx = L + idx * grup_w + 22
        nama_pendek = row["model"].replace(" (TF-IDF)", "").replace(" + LogReg", "")
        c.text(gx + 2 * bar_w, T + ph + 14, nama_pendek, scale=1, align="center")
        svg.append(f"<text x='{gx + 2*bar_w}' y='{T+ph+22}' text-anchor='middle' font-size='12' font-weight='bold'>{row['model']}</text>")
        for m_i, (kol, col, lbl) in enumerate(metrik_cols):
            val = float(row[kol])
            bh = int(val * ph)
            bx0 = gx + m_i * (bar_w + 4)
            by0 = T + ph - bh
            c.rect(bx0, by0, bx0 + bar_w, T + ph, col, border=(60, 60, 60))
            c.text(bx0 + bar_w // 2, by0 - 10, f"{val:.2f}", scale=1, align="center")
            hex_c = "#%02x%02x%02x" % col
            svg.append(f"<rect x='{bx0}' y='{by0}' width='{bar_w}' height='{bh}' fill='{hex_c}' stroke='#333'/>")
            svg.append(f"<text x='{bx0 + bar_w//2}' y='{by0 - 5}' text-anchor='middle' font-size='10'>{val:.3f}</text>")

    # Legend
    for m_i, (_, col, lbl) in enumerate(metrik_cols):
        lx = L + 20 + m_i * 140
        c.rect(lx, H - 22, lx + 14, H - 12, col, border=(40, 40, 40))
        c.text(lx + 20, H - 20, lbl, scale=1)
    svg.append("</svg>")
    (DOCS / "gambar_4_3_perbandingan_model.svg").write_text("\n".join(svg), encoding="utf-8")
    c.save_png(DOCS / "gambar_4_3_perbandingan_model.png")


def main():
    buat_gambar_cm()
    buat_gambar_threshold()
    buat_gambar_perbandingan()
    print("Visualisasi selesai dibuat di folder docs/:")
    for f in sorted(DOCS.glob("gambar_4_*")):
        print("  -", f.name, f"({f.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

