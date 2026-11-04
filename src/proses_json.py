"""
proses_json.py
==============
Kontrak input/output Pool 2 (modul NLP) untuk integrasi dengan Pool 1 (input) dan Pool 3 (output).

INPUT  (dari Pool 1): JSON list transaksi, kolom minimal: tanggal, keterangan, debit, kredit, saldo
       (boleh tambah kolom lain, akan diteruskan apa adanya). jenis: kredit > 0 -> CR, selain itu DB.

OUTPUT (ke Pool 3): JSON
  {
    "threshold": 0.72,
    "ringkasan": {"total": N, "otomatis": a, "perlu_review": b},
    "transaksi": [ {...kolom asli..., "label", "nama_akun", "confidence",
                    "status": "OTOMATIS" | "PERLU_REVIEW_MANUAL",
                    "sumber_label": "model" | "manual"} ]
  }
  - status OTOMATIS           : confidence >= threshold, siap diproses Pool 3 (matching ERP).
  - status PERLU_REVIEW_MANUAL: confidence < threshold, harus dicek manual dulu.

KOREKSI MANUAL (opsional, hasil review di UI Pool 3): JSON {"<index transaksi>": "LABEL", ...}
  Setelah dikoreksi, status menjadi OTOMATIS dengan sumber_label "manual" -> inilah "JSON bersih".

Pemakaian (dari folder src):
  python proses_json.py input.json output.json
  python proses_json.py output.json bersih.json --koreksi koreksi.json   # terapkan hasil review manual
"""
import json
import sys

from kategori_keuangan import LABEL_COA
from routing import klasifikasi_transaksi, load_model


def _angka(x):
    try:
        return float(str(x).replace(",", "") or 0)
    except ValueError:
        return 0.0


def proses(transaksi, model, threshold):
    hasil = []
    for i, t in enumerate(transaksi):
        jenis = "CR" if _angka(t.get("kredit")) > 0 else "DB"
        h = klasifikasi_transaksi(str(t.get("keterangan", "")), jenis, model, threshold)
        hasil.append({**t, "index": i, "jenis": jenis, "label": h["label"], "nama_akun": h["nama_akun"],
                      "confidence": h["confidence"], "sumber_label": "model",
                      "status": "OTOMATIS" if h["status"] == "OTOMATIS" else "PERLU_REVIEW_MANUAL"})
    return _bungkus(hasil, threshold)


def _bungkus(hasil, threshold):
    n_auto = sum(h["status"] == "OTOMATIS" for h in hasil)
    return {"threshold": threshold,
            "ringkasan": {"total": len(hasil), "otomatis": n_auto, "perlu_review": len(hasil) - n_auto},
            "transaksi": hasil}


def terapkan_koreksi(paket, koreksi):
    for h in paket["transaksi"]:
        lab = koreksi.get(str(h["index"]))
        if lab:
            if lab not in LABEL_COA:
                raise ValueError(f"label tidak dikenal: {lab}")
            h.update(label=lab, nama_akun=LABEL_COA[lab]["nama"], status="OTOMATIS", sumber_label="manual")
    return _bungkus(paket["transaksi"], paket["threshold"])


def main():
    argv = sys.argv[1:]
    file_koreksi = None
    if "--koreksi" in argv:
        i = argv.index("--koreksi")
        file_koreksi = argv[i + 1] if i + 1 < len(argv) else None
        argv = argv[:i] + argv[i + 2:]
    if len(argv) != 2 or ("--koreksi" in sys.argv and not file_koreksi):
        sys.exit(__doc__)
    src, dst = argv
    data = json.load(open(src, encoding="utf-8"))
    if file_koreksi:
        koreksi = json.load(open(file_koreksi, encoding="utf-8-sig"))
        paket = terapkan_koreksi(data, koreksi)
    else:
        model, threshold = load_model()
        paket = proses(data, model, threshold)
    json.dump(paket, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    r = paket["ringkasan"]
    print(f"{dst}: total={r['total']} otomatis={r['otomatis']} perlu_review={r['perlu_review']}")


if __name__ == "__main__":
    main()
