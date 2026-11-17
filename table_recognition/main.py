"""SiRekon - modul table recognition.

Contoh:
  python main.py --input data/raw --recursive
Keluaran (folder output/):
  results.json   : daftar hasil per file (bank, status, masalah, bbox tabel, transaksi)
  transaksi.json : transaksi unik hasil dedup dari file berstatus OK (untuk modul rekonsiliasi)
  evaluasi.json  : (hanya dengan --evaluate) P/R/F1 per file, per bank, total terhadap GT
"""
import argparse
import json
import logging
import os

from src.deduplicator import deduplicate_records
from src.detector import detect_file_type
from src.evaluator import evaluate_semua
from src.pipeline_digital import process_pdf

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _kosong(filepath, status, masalah):
    return {"file": os.path.basename(filepath), "bank": None, "no_rekening": None,
            "status": status, "masalah": [masalah], "tabel_bbox": [], "transaksi": []}


def process_file(filepath: str) -> dict:
    """Proses satu file -> satu objek hasil (format results.json)."""
    try:
        tipe = detect_file_type(filepath)
    except ValueError as e:
        return _kosong(filepath, "FORMAT_TIDAK_DIDUKUNG", str(e))
    if tipe == "pdf_digital":
        logger.info("Pipeline digital: %s", filepath)
        return process_pdf(filepath)
    if tipe == "pdf_scan":
        logger.info("Pipeline scan (OCR): %s", filepath)
        try:   # impor ditunda: PDF digital tidak butuh OpenCV/Tesseract/Poppler
            from src.pipeline_scan import process_scan_pdf
        except ImportError as e:
            return _kosong(filepath, "BELUM_DIDUKUNG", f"pustaka OCR belum terpasang: {e}")
        return process_scan_pdf(filepath)
    return _kosong(filepath, "BELUM_DIDUKUNG", f"tipe {tipe} belum diimplementasi")


def kumpulkan_pdf(path, rekursif):
    if os.path.isfile(path):
        return [path]
    hasil = []
    for root, _, files in os.walk(path):
        hasil += [os.path.join(root, f) for f in sorted(files) if f.lower().endswith(".pdf")]
        if not rekursif:
            break
    return sorted(hasil)


def cetak_evaluasi(ev):
    print("\n=== EVALUASI END-TO-END (per transaksi) ===")
    print(f"{'file':<14}{'n_pred':>7}{'n_gt':>6}{'P':>8}{'R':>8}{'F1':>8}{'CER ket':>9}  cocok")
    for nama, r in ev["per_file"].items():
        print(f"{nama:<14}{r['n_prediksi']:>7}{r['n_gt']:>6}{r['precision']:>8.3f}{r['recall']:>8.3f}"
              f"{r['f1']:>8.3f}{r['cer_keterangan']:>9.4f}  {r['metode_cocok']}")
    for b, r in ev["per_bank"].items():
        print(f"[{b}] {r['n_file']} file  P={r['precision']:.3f} R={r['recall']:.3f} "
              f"F1={r['f1']:.3f} CER={r['cer_keterangan']:.4f}")
    t = ev["total"]
    if t["n_file"]:
        print(f"[TOTAL] {t['n_file']} file  P={t['precision']:.3f} R={t['recall']:.3f} "
              f"F1={t['f1']:.3f} CER={t['cer_keterangan']:.4f}")
    if "ocr_murni" in ev:
        print("\n=== PIPELINE SCAN: dua angka (A = OCR murni, B = setelah koreksi saldo) ===")
        for b, rb in ev["per_bank"].items():
            if b in ev["ocr_murni"]["per_bank"]:
                a = ev["ocr_murni"]["per_bank"][b]
                print(f"[{b}] A (murni)  P={a['precision']:.3f} R={a['recall']:.3f} F1={a['f1']:.3f} | "
                      f"B (koreksi) P={rb['precision']:.3f} R={rb['recall']:.3f} F1={rb['f1']:.3f}")
    if "sel_mentah" in ev:
        print("\n=== LEVEL-1: CER teks mentah per sel (tanpa parsing/koreksi) ===")
        kol = ("tanggal_waktu", "keterangan", "nominal", "saldo")
        print(f"{'file':<14}" + "".join(f"{k:>16}" for k in kol))
        tot_e = {k: 0 for k in kol}
        tot_c = {k: 0 for k in kol}
        for nama, r in ev["sel_mentah"].items():
            cat = "  (jumlah baris beda)" if r["baris_tidak_sama"] else ""
            print(f"{nama:<14}" + "".join(f"{r['cer'][k]:>16.4f}" for k in kol) + cat)
            for k in kol:
                tot_e[k] += r["kesalahan"][k]
                tot_c[k] += r["karakter"][k]
        print(f"{'[TOTAL]':<14}" + "".join(f"{(tot_e[k] / tot_c[k] if tot_c[k] else 0):>16.4f}" for k in kol))
    if ev["dilewati"]:
        print("Dilewati:", ", ".join(f"{k}({v})" for k, v in ev["dilewati"].items()))


def main():
    ap = argparse.ArgumentParser(description="SiRekon - Table Recognition Module")
    ap.add_argument("--input", required=True, help="Path ke file PDF atau folder")
    ap.add_argument("--recursive", action="store_true", help="Proses folder secara rekursif")
    ap.add_argument("--output", default="output", help="Folder keluaran (default: output)")
    ap.add_argument("--evaluate", action="store_true", help="Jalankan mode evaluasi")
    ap.add_argument("--gt", type=str, default=os.path.join("data", "ground_truth"),
                    help="Folder Ground Truth (default: data/ground_truth)")
    args = ap.parse_args()

    per_file = [process_file(p) for p in kumpulkan_pdf(args.input, args.recursive)]

    semua = []
    for h in per_file:
        if h["status"] == "OK":
            semua.extend(h["transaksi"])
        elif h["transaksi"]:
            logger.warning("%s berstatus %s, transaksinya tidak dimasukkan ke transaksi.json: %s",
                           h["file"], h["status"], "; ".join(h["masalah"]))
    unik, lap = deduplicate_records(semua, return_report=True)

    os.makedirs(args.output, exist_ok=True)
    with open(os.path.join(args.output, "results.json"), "w", encoding="utf-8") as f:
        json.dump(per_file, f, indent=2, ensure_ascii=False)
    with open(os.path.join(args.output, "transaksi.json"), "w", encoding="utf-8") as f:
        json.dump(unik, f, indent=2, ensure_ascii=False)

    for h in per_file:
        logger.info("%s | %s | %s | %d transaksi", h["file"], h["bank"], h["status"], len(h["transaksi"]))
    logger.info("Selesai: %d file, %d transaksi unik (%d duplikat dibuang). Hasil di: %s",
                len(per_file), lap["akhir"], lap["dibuang"], args.output)

    if args.evaluate:
        ev = evaluate_semua(per_file, args.gt)
        with open(os.path.join(args.output, "evaluasi.json"), "w", encoding="utf-8") as f:
            json.dump(ev, f, indent=2, ensure_ascii=False)
        cetak_evaluasi(ev)


if __name__ == "__main__":
    main()