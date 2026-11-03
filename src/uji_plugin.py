"""Uji logika plugin_server tanpa membuka socket (validasi + klasifikasi)."""
import plugin_server as s

batch = [{"keterangan": "BIAYA ADM", "jenis": "DB"}, {"keterangan": "pulsa kantor jan", "jenis": "db"},
         {"keterangan": "TRSF E-BANKING PANCA BERSAUDARA", "jenis": "CR"}]
assert all(s._valid(i) for i in batch)
assert not s._valid({"jenis": "XX", "keterangan": "a"}) and not s._valid({"jenis": "CR"})
for i in batch:
    h = s._klasifikasi(i)
    print(h["jenis"], h["keterangan"], "->", h["label"], h["confidence"], h["status"])
print("threshold:", s.THRESHOLD, "| html OK:", "<textarea" in s.HALAMAN)
