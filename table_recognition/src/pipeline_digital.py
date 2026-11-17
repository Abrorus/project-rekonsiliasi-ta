"""PDF digital -> hasil terstruktur (record standar + laporan validasi)."""
import os

from .balance import periksa_file
from .bank_identifier import kenali_bank
from .extractors import EXTRACTORS, baca_header_halaman
from .normalizer import normalize_data


def _angka(s):
    return None if s is None else float(str(s).replace(",", ""))


def process_pdf(path):
    """Proses satu PDF digital. Tidak melempar untuk masalah data; status dilaporkan."""
    nama = os.path.basename(path)
    hasil = {"file": nama, "bank": None, "no_rekening": None, "status": "GAGAL",
             "masalah": [], "tabel_bbox": [], "transaksi": []}
    bank = kenali_bank(baca_header_halaman(path))
    hasil["bank"] = bank
    if bank is None:
        hasil["status"] = "BANK_TIDAK_DIKENALI"
        return hasil
    if bank not in EXTRACTORS:
        hasil["status"] = "BELUM_DIDUKUNG"
        hasil["masalah"].append(f"extractor {bank} belum ada")
        return hasil
    rows, meta, bbox = EXTRACTORS[bank](path)
    hasil["no_rekening"] = meta.get("no_rekening")
    hasil["tabel_bbox"] = bbox
    try:
        recs = normalize_data(rows, bank, dict(meta, source_file=nama))
    except ValueError as e:
        hasil["masalah"].append(str(e))
        return hasil
    recs, lap = periksa_file(
        recs, _angka(meta.get("saldo_awal")), _angka(meta.get("saldo_akhir")),
        _angka(meta.get("mutasi_db")), _angka(meta.get("mutasi_cr")),
        meta.get("n_db"), meta.get("n_cr"))
    hasil.update(status=lap["status"], masalah=lap["masalah"], transaksi=recs)
    return hasil