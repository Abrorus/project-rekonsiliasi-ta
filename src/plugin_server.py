"""
plugin_server.py
================
Modul NLP SIREKON (Pool 2) sebagai plugin web + REST API, hanya memakai pustaka standar Python
untuk server (tanpa dependensi tambahan).

Endpoint:
  GET  /                -> antarmuka web sederhana (uji satu transaksi / tempel banyak baris)
  GET  /health          -> {"status": "ok", "threshold": ..., "labels": [...]}
  POST /classify        -> body {"keterangan": "...", "jenis": "CR|DB"}
  POST /classify/batch  -> body {"transaksi": [{"keterangan": "...", "jenis": "CR|DB"}, ...]}

Respons memuat label, nama_akun, confidence, status (OTOMATIS | RUJUK_POOL3).
Transaksi berstatus RUJUK_POOL3 diteruskan Pool 3 (knowledge base) oleh sistem pemanggil.

Jalankan (dari folder src):  python plugin_server.py [port]      # default 8000
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from routing import klasifikasi_transaksi, load_model

MODEL, THRESHOLD = load_model()

HALAMAN = """<!doctype html><meta charset=utf-8><title>SIREKON - Modul NLP</title>
<style>body{font-family:sans-serif;max-width:900px;margin:2em auto}textarea{width:100%;height:9em}
table{border-collapse:collapse;width:100%;margin-top:1em}td,th{border:1px solid #ccc;padding:4px 8px;text-align:left}
.RUJUK_POOL3{background:#fff3cd}.OTOMATIS{background:#d4edda}</style>
<h2>SIREKON - Klasifikasi Keterangan Transaksi</h2>
<p>Satu transaksi per baris, format: <code>CR|DB, keterangan</code></p>
<textarea id=in>CR, TRSF E-BANKING PANCA BERSAUDARA
DB, BPJS KS Jakarta Feb25
DB, BIAYA ADM
DB, beli kopi untuk tamu</textarea><br>
<button onclick=go()>Klasifikasi</button> <span id=info></span>
<table id=out></table>
<script>
async function go(){
 const t=document.getElementById('in').value.split('\\n').filter(x=>x.trim()).map(l=>{
  const i=l.indexOf(','); return {jenis:l.slice(0,i).trim().toUpperCase(), keterangan:l.slice(i+1).trim()}});
 const r=await (await fetch('/classify/batch',{method:'POST',body:JSON.stringify({transaksi:t})})).json();
 document.getElementById('info').textContent='threshold = '+r.threshold;
 document.getElementById('out').innerHTML='<tr><th>Jenis<th>Keterangan<th>Akun<th>Confidence<th>Status</tr>'+
  r.hasil.map(h=>`<tr class=${h.status}><td>${h.jenis}<td>${h.keterangan}<td>${h.nama_akun}<td>${h.confidence}<td>${h.status}`).join('');
}
</script>"""


def _valid(item):
    return (isinstance(item, dict) and str(item.get("jenis", "")).upper() in ("CR", "DB")
            and str(item.get("keterangan", "")).strip() != "")


def _klasifikasi(item):
    return klasifikasi_transaksi(str(item["keterangan"]), str(item["jenis"]).upper(), MODEL, THRESHOLD)


class Handler(BaseHTTPRequestHandler):
    def _kirim(self, kode, obj, tipe="application/json"):
        data = obj.encode() if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(kode)
        self.send_header("Content-Type", tipe + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self._kirim(200, HALAMAN, "text/html")
        elif self.path == "/health":
            self._kirim(200, {"status": "ok", "threshold": THRESHOLD, "labels": list(MODEL.classes_)})
        else:
            self._kirim(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError:
            return self._kirim(400, {"error": "body bukan JSON valid"})
        if self.path == "/classify":
            if not _valid(body):
                return self._kirim(422, {"error": "wajib: keterangan (teks) dan jenis (CR|DB)"})
            return self._kirim(200, _klasifikasi(body))
        if self.path == "/classify/batch":
            items = body.get("transaksi")
            if not isinstance(items, list) or not all(_valid(i) for i in items):
                return self._kirim(422, {"error": "transaksi: list of {keterangan, jenis(CR|DB)}"})
            hasil = [_klasifikasi(i) for i in items]
            return self._kirim(200, {"threshold": THRESHOLD, "hasil": hasil,
                                     "auto": sum(h["status"] == "OTOMATIS" for h in hasil),
                                     "rujuk_pool3": sum(h["status"] == "RUJUK_POOL3" for h in hasil)})
        self._kirim(404, {"error": "not found"})


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"SIREKON NLP plugin di http://127.0.0.1:{port}  (threshold={THRESHOLD})")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()

