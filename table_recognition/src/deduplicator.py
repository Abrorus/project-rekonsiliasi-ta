"""Deduplikasi transaksi lintas file (mis. periode rekening koran yang tumpang tindih).

Kunci: (bank, no_rekening, waktu_transaksi, debit, kredit, saldo).
- source_file BUKAN bagian kunci: duplikat justru muncul antar file.
- saldo ikut kunci: membedakan dua transaksi BCA di hari yang sama dengan nominal sama
  (BCA hanya punya tanggal, tanpa jam).
- Record dengan no_rekening kosong tidak pernah digabung (identitas rekening tidak pasti).
"""
import logging
from itertools import count

logger = logging.getLogger(__name__)


def _angka(v):
    return None if v is None else round(float(v), 2)


def kunci_dedup(rec, unik):
    if rec.get("no_rekening") in (None, ""):
        return ("TANPA_REKENING", unik)
    return (rec.get("bank"), rec["no_rekening"], rec.get("waktu_transaksi"),
            _angka(rec.get("debit")), _angka(rec.get("kredit")), _angka(rec.get("saldo")))


def deduplicate_records(records, return_report=False):
    """Hapus duplikat, pertahankan kemunculan pertama.

    return_report=True -> (records_unik, laporan) dengan
    laporan = {"awal", "akhir", "dibuang", "rincian": [{"dibuang_dari", "sama_dengan", "waktu_transaksi"}]}
    """
    seen, hasil, rincian, urut = {}, [], [], count()
    for rec in records:
        k = kunci_dedup(rec, next(urut))
        if k in seen:
            rincian.append({"dibuang_dari": rec.get("source_file"), "sama_dengan": seen[k],
                            "waktu_transaksi": rec.get("waktu_transaksi")})
            continue
        seen[k] = rec.get("source_file")
        hasil.append(rec)
    lap = {"awal": len(records), "akhir": len(hasil), "dibuang": len(rincian), "rincian": rincian}
    logger.info("Deduplikasi: %d -> %d record (%d duplikat dibuang)", lap["awal"], lap["akhir"], lap["dibuang"])
    return (hasil, lap) if return_report else hasil