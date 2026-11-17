"""Hitung dan validasi saldo (terutama BCA: saldo tidak tercetak di tiap baris)."""

TOL = 0.005


def hitung_saldo(records, saldo_awal):
    """Isi saldo yang kosong dengan rantai saldo_awal + kredit - debit.

    Saldo yang tercetak dipakai sebagai checkpoint: dibandingkan dengan hitungan
    dan rantai di-resync ke nilai tercetak. Return (records_baru, selisih) dengan
    selisih = [(indeks_0, tercetak, hitungan), ...].
    """
    out, selisih, prev = [], [], round(float(saldo_awal), 2)
    for i, rec in enumerate(records):
        rec = dict(rec)
        hit = round(prev + (rec["kredit"] or 0.0) - (rec["debit"] or 0.0), 2)
        if rec.get("saldo") is None:
            rec["saldo"] = hit
        else:
            if abs(rec["saldo"] - hit) > TOL:
                selisih.append((i, rec["saldo"], hit))
            hit = rec["saldo"]
        prev = hit
        out.append(rec)
    return out, selisih


def validasi_ringkasan(records, saldo_akhir=None, total_debit=None, total_kredit=None,
                       n_debit=None, n_kredit=None):
    """Cocokkan hasil dengan ringkasan di footer. Return daftar pesan masalah."""
    masalah = []
    if saldo_akhir is not None and records:
        if abs(records[-1]["saldo"] - saldo_akhir) > TOL:
            masalah.append(f"saldo akhir {records[-1]['saldo']:.2f} != footer {saldo_akhir:.2f}")
    if total_debit is not None:
        s = round(sum(r["debit"] for r in records), 2)
        if abs(s - total_debit) > TOL:
            masalah.append(f"total debit {s:.2f} != footer {total_debit:.2f}")
    if total_kredit is not None:
        s = round(sum(r["kredit"] for r in records), 2)
        if abs(s - total_kredit) > TOL:
            masalah.append(f"total kredit {s:.2f} != footer {total_kredit:.2f}")
    if n_debit is not None:
        n = sum(1 for r in records if r["debit"] > 0)
        if n != n_debit:
            masalah.append(f"jumlah debit {n} != footer {n_debit}")
    if n_kredit is not None:
        n = sum(1 for r in records if r["kredit"] > 0)
        if n != n_kredit:
            masalah.append(f"jumlah kredit {n} != footer {n_kredit}")
    return masalah


def periksa_file(records, saldo_awal, saldo_akhir=None, total_debit=None, total_kredit=None,
                 n_debit=None, n_kredit=None):
    """hitung_saldo + validasi_ringkasan. Return (records, laporan)."""
    recs, selisih = hitung_saldo(records, saldo_awal)
    masalah = [f"baris {i + 1}: saldo tercetak {p:.2f} != hitungan {h:.2f}" for i, p, h in selisih]
    masalah += validasi_ringkasan(recs, saldo_akhir, total_debit, total_kredit, n_debit, n_kredit)
    return recs, {"status": "OK" if not masalah else "PERLU_REVIEW",
                  "masalah": masalah, "selisih_saldo": selisih}


# ---------------------------------------------------------------------------
# Koreksi OCR berbasis aritmetika saldo (pipeline scan BNI/Mandiri)
# ---------------------------------------------------------------------------

def _lev(a, b):
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _digits(x):
    return "" if x is None else str(int(round(abs(x) * 100)))


def _dekat(a, b):
    return a is not None and b is not None and abs(a - b) <= TOL


def koreksi_rantai(rows, saldo_awal=None, saldo_akhir=None):
    """Perbaiki nominal/saldo hasil OCR memakai identitas saldo[i] = saldo[i-1] + nominal[i].

    rows : daftar dict dengan 'nominal' (float bertanda, atau None) dan 'saldo' (float atau None).
    Untuk setiap baris yang tidak konsisten ada dua kandidat:
      A) nominal salah  -> nominal := saldo - saldo_sebelumnya
      B) saldo salah    -> saldo   := saldo_sebelumnya + nominal
    Kandidat dipilih yang membuat BARIS BERIKUTNYA konsisten (untuk baris terakhir: cocok dengan
    saldo_akhir header bila ada). Bila keduanya/tidak satupun konsisten, dipilih yang digit-nya paling
    mirip hasil OCR dan baris ditandai tidak pasti.

    Return (rows_baru, koreksi). koreksi = daftar dict {indeks, jenis, dari, ke, pasti}.
    """
    out = [dict(r) for r in rows]
    koreksi = []
    n = len(out)
    prev = saldo_awal
    if prev is None and out and out[0]["saldo"] is not None and out[0]["nominal"] is not None:
        prev = round(out[0]["saldo"] - out[0]["nominal"], 2)   # asumsi baris pertama konsisten

    def konsisten_setelah(i, saldo_i):
        """Apakah baris i+1 konsisten bila saldo baris i = saldo_i? (None bila tidak bisa dinilai)"""
        if i + 1 < n:
            nx = out[i + 1]
            if nx["nominal"] is None or nx["saldo"] is None:
                return None
            return _dekat(saldo_i + nx["nominal"], nx["saldo"])
        if saldo_akhir is not None:
            return _dekat(saldo_i, saldo_akhir)
        return None

    for i, r in enumerate(out):
        nom, sal = r["nominal"], r["saldo"]
        if prev is None:
            prev = sal
            continue
        if nom is not None and sal is not None and _dekat(prev + nom, sal):
            prev = sal
            continue
        # --- baris tidak konsisten / ada nilai hilang ---
        cand = []
        if sal is not None:
            a = round(sal - prev, 2)
            cand.append(("nominal", a, sal, _lev(_digits(nom), _digits(a))))
        if nom is not None:
            b = round(prev + nom, 2)
            cand.append(("saldo", nom, b, _lev(_digits(sal), _digits(b))))
        if not cand:
            continue
        nilai = []
        for jenis, nom_c, sal_c, jarak in cand:
            nilai.append((jenis, nom_c, sal_c, jarak, konsisten_setelah(i, sal_c)))
        baik = [c for c in nilai if c[4] is True]
        pasti = len(baik) == 1
        pilih_dari = baik if baik else nilai
        jenis, nom_c, sal_c, jarak, _ = min(pilih_dari, key=lambda c: c[3])
        if jenis == "nominal":
            koreksi.append(dict(indeks=i, jenis="nominal", dari=nom, ke=nom_c, pasti=pasti))
        else:
            koreksi.append(dict(indeks=i, jenis="saldo", dari=sal, ke=sal_c, pasti=pasti))
        r["nominal"], r["saldo"] = nom_c, sal_c
        prev = sal_c
    return out, koreksi


def koreksi_dp(rows, saldo_awal=None, saldo_akhir=None, beam=60, desimal=0):
    """Koreksi global berbasis pemrograman dinamis (menggantikan keputusan baris-per-baris).

    rows : daftar dict {'nominal': [(nilai, suara), ...], 'saldo': [(nilai, suara), ...]} berisi
           hipotesis hasil OCR (nilai float; nominal bertanda). Urutan = urutan baris di dokumen.
    Mencari rangkaian (nominal_i, saldo_i) yang memenuhi saldo_i = saldo_{i-1} + nominal_i dengan
    total biaya terkecil. Biaya: nilai teramati = 0..(selisih suara); nilai turunan = 1.5 + jarak
    Levenshtein digit ke hipotesis terdekat. saldo_awal/saldo_akhir (dari header) dipakai sebagai
    titik ujung; saldo_akhir hanya berupa penalti (karena angka header pun hasil OCR).

    Return (rows_baru, koreksi): rows_baru = [{'nominal','saldo'}], koreksi = [{indeks, jenis, dari,
    ke, pasti}] untuk nilai terpilih yang berbeda dari hipotesis utama OCR.
    """
    DER, PEN_AKHIR = 1.5, 2.0

    def biaya_obs(obs):
        if not obs:
            return {}
        mx = max(v for _, v in obs)
        d = {}
        for val, v in obs:
            val = round(val, 2)
            d[val] = min(d.get(val, 99), float(mx - v))
        return d

    def biaya(val, obs_map, obs_digits):
        val = round(val, 2)
        if val in obs_map:
            return obs_map[val]
        dv = _digits(val)
        return DER + (min(_lev(dv, o) for o in obs_digits) if obs_digits else 3)

    N = len(rows)
    nm = [biaya_obs(r["nominal"]) for r in rows]
    sm = [biaya_obs(r["saldo"]) for r in rows]
    nd = [[_digits(v) for v in m] for m in nm]
    sd = [[_digits(v) for v in m] for m in sm]
    skala = 10 ** desimal

    def tetangga(m, dua_tanda):
        """Hipotesis tambahan: satu kali edit digit (ganti/sisip/hapus) dari hipotesis UTAMA."""
        if not m:
            return []
        utama = min(m, key=m.get)
        ds = str(int(round(abs(utama) * skala)))
        hasil = set()
        for k in range(len(ds) + 1):
            for d in "0123456789":
                if k < len(ds) and d != ds[k]:
                    hasil.add(ds[:k] + d + ds[k + 1:])
                hasil.add(ds[:k] + d + ds[k:])
            if k < len(ds):
                hasil.add(ds[:k] + ds[k + 1:])
        nilai = set()
        for x in hasil:
            if x and not x.startswith("0") or x == "0":
                v = int(x) / skala
                nilai.add(round(v, 2))
                if dua_tanda:
                    nilai.add(round(-v, 2))
        return [v for v in nilai if v not in m]
    nx = [tetangga(m, True) for m in nm]
    sx = [tetangga(m, False) for m in sm]

    if saldo_awal is not None:
        states = {round(saldo_awal, 2): (0.0, None, None)}
    else:
        states = {}
        if N:
            for s, cs in sm[0].items():
                for n, cn in nm[0].items():
                    key = round(s - n, 2)
                    c = 1.0 + cs + cn
                    if key not in states or states[key][0] > c:
                        states[key] = (c, None, None)
            for s, cs in sm[0].items():     # nominal baris-0 tak terbaca: biarkan bebas
                states.setdefault(round(s, 2), (3.0, None, None))
    hist = []   # per baris: dict saldo -> (biaya, saldo_sebelumnya, nominal)
    for i in range(N):
        baru = {}
        for p, (cp, _, _) in states.items():
            for n in list(nm[i]) + nx[i]:
                cn = biaya(n, nm[i], nd[i])
                s = round(p + n, 2)
                c = cp + cn + biaya(s, sm[i], sd[i])
                if s not in baru or baru[s][0] > c:
                    baru[s] = (c, p, n)
            for s in list(sm[i]) + sx[i]:
                cs = biaya(s, sm[i], sd[i])
                n = round(s - p, 2)
                if abs(n) < TOL:
                    continue
                c = cp + cs + biaya(n, nm[i], nd[i])
                if s not in baru or baru[s][0] > c:
                    baru[s] = (c, p, n)
        if not baru:    # tidak ada hipotesis sama sekali: lanjutkan saldo apa adanya
            baru = {p: (cp + 10.0, p, 0.0) for p, (cp, _, _) in states.items()}
        top = sorted(baru.items(), key=lambda kv: kv[1][0])[:beam]
        states = dict(top)
        hist.append(states)
    if not N:
        return [], []
    akhir = {}
    for s, (c, p, n) in hist[-1].items():
        pen = 0.0
        if saldo_akhir is not None and abs(s - saldo_akhir) > TOL:
            pen = PEN_AKHIR
        akhir[s] = c + pen
    s = min(akhir, key=akhir.get)
    hasil = [None] * N
    for i in range(N - 1, -1, -1):
        c, p, n = hist[i][s]
        hasil[i] = {"nominal": n, "saldo": s}
        s = p
    koreksi = []
    for i, (r, h) in enumerate(zip(rows, hasil)):
        for jenis in ("nominal", "saldo"):
            obs = r[jenis]
            utama = round(max(obs, key=lambda t: t[1])[0], 2) if obs else None
            if utama is None or abs(utama - h[jenis]) > TOL:
                dekat = (_lev(_digits(utama), _digits(h[jenis])) <= 2) if utama is not None else False
                koreksi.append({"indeks": i, "jenis": jenis, "dari": utama, "ke": h[jenis], "pasti": dekat})
    return hasil, koreksi