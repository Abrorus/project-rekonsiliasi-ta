import logging

logger = logging.getLogger(__name__)

def calculate_iou(boxA, boxB):
    """Menghitung Intersection over Union (IoU) dari dua bounding box (x0, top, x1, bottom)."""
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    interArea = max(0, xB - xA) * max(0, yB - yA)
    if interArea == 0: return 0.0

    boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])

    iou = interArea / float(boxAArea + boxBArea - interArea)
    return iou

def levenshtein_distance(s1, s2):
    """Menghitung Levenshtein distance antara dua string."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def evaluate_td(predicted_bboxes, gt_bboxes, iou_threshold=0.5):
    """Evaluasi tahap Table Detection (TD)."""
    tp = fp = fn = 0
    matched_gt = set()
    
    for pred_box in predicted_bboxes:
        match_found = False
        for i, gt_box in enumerate(gt_bboxes):
            if i in matched_gt: continue
            if calculate_iou(pred_box, gt_box) >= iou_threshold:
                tp += 1
                matched_gt.add(i)
                match_found = True
                break
        if not match_found:
            fp += 1
            
    fn = len(gt_bboxes) - len(matched_gt)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {'precision': precision, 'recall': recall, 'f1': f1, 'tp': tp, 'fp': fp, 'fn': fn}

def evaluate_tsr(predicted_structure, gt_structure):
    """Evaluasi tahap Table Structure Recognition (TSR)."""
    col_acc = 1.0 if predicted_structure['num_cols'] == gt_structure['num_cols'] else 0.0
    row_acc = 1.0 if predicted_structure['num_rows'] == gt_structure['num_rows'] else 0.0
    return {'column_accuracy': col_acc, 'row_accuracy': row_acc}

def evaluate_extraction_digital(predicted_cells, gt_cells):
    """Evaluasi tahap Content Extraction (PDF Digital)."""
    exact_matches = 0
    total_cells = max(len(predicted_cells), len(gt_cells))
    if total_cells == 0: return {'exact_match_accuracy': 1.0, 'char_f1': 1.0}
    
    char_tp = char_fp = char_fn = 0
    
    for pred, gt in zip(predicted_cells, gt_cells):
        pred_str, gt_str = str(pred).strip(), str(gt).strip()
        if pred_str == gt_str:
            exact_matches += 1
            
        pred_chars, gt_chars = set(pred_str), set(gt_str)
        char_tp += len(pred_chars & gt_chars)
        char_fp += len(pred_chars - gt_chars)
        char_fn += len(gt_chars - pred_chars)
        
    exact_match_acc = exact_matches / total_cells
    
    char_precision = char_tp / (char_tp + char_fp) if (char_tp + char_fp) > 0 else 0
    char_recall = char_tp / (char_tp + char_fn) if (char_tp + char_fn) > 0 else 0
    char_f1 = 2 * (char_precision * char_recall) / (char_precision + char_recall) if (char_precision + char_recall) > 0 else 0
    
    return {'exact_match_accuracy': exact_match_acc, 'char_f1': char_f1}

def evaluate_extraction_scan(predicted_text, gt_text):
    """Evaluasi tahap Content Extraction (PDF Scan) dengan CER."""
    total_errors = levenshtein_distance(predicted_text, gt_text)
    total_chars = max(len(gt_text), 1)
    cer = total_errors / total_chars
    return {'cer': cer, 'total_chars': total_chars, 'total_errors': total_errors}

# ---------------------------------------------------------------------------
# Evaluasi end-to-end level 2 (konten ternormalisasi, per transaksi)
# ---------------------------------------------------------------------------
TOL = 0.005
_FIELD_ANGKA = ("debit", "kredit", "saldo")


def _norm_teks(s):
    return " ".join(str(s if s is not None else "").split())


def _sama_angka(a, b):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= TOL


def _bandingkan(pred, gt):
    """Daftar field yang berbeda antara satu record prediksi dan satu record GT."""
    beda = []
    if str(pred.get("waktu_transaksi")) != str(gt.get("waktu_transaksi")):
        beda.append("waktu_transaksi")
    for f in _FIELD_ANGKA:
        if not _sama_angka(pred.get(f), gt.get(f)):
            beda.append(f)
    return beda


def _kunci(rec):
    def r(v):
        return None if v is None else round(float(v), 2)
    return (str(rec.get("waktu_transaksi")), r(rec.get("debit")), r(rec.get("kredit")), r(rec.get("saldo")))


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"precision": p, "recall": r, "f1": f1}


def cocokkan_transaksi(pred, gt):
    """Pasangkan record prediksi dengan GT.

    - Jumlah sama  -> dipasangkan menurut urutan baris (row_index).
    - Jumlah beda  -> fallback ke kunci (waktu, debit, kredit, saldo) sebagai multiset,
      supaya satu baris yang hilang/berlebih tidak menggeser semua baris sesudahnya.
    Return (pasangan, pred_tak_terpasang, gt_tak_terpasang, metode); pasangan = [(i_pred, i_gt), ...].
    """
    if len(pred) == len(gt):
        return [(i, i) for i in range(len(gt))], [], [], "urutan"
    sisa = {}
    for j, g in enumerate(gt):
        sisa.setdefault(_kunci(g), []).append(j)
    pasangan, tak_pred = [], []
    for i, p in enumerate(pred):
        k = _kunci(p)
        if sisa.get(k):
            pasangan.append((i, sisa[k].pop(0)))
        else:
            tak_pred.append(i)
    terpakai = {j for _, j in pasangan}
    tak_gt = [j for j in range(len(gt)) if j not in terpakai]
    return pasangan, tak_pred, tak_gt, "kunci"


def evaluate_file(pred, gt, maks_salah=50):
    """Evaluasi satu file: P/R/F1 per transaksi + CER keterangan (pada pasangan yang cocok)."""
    pasangan, tak_pred, tak_gt, metode = cocokkan_transaksi(pred, gt)
    tp, salah = 0, []
    err = chars = 0
    for i, j in pasangan:
        beda = _bandingkan(pred[i], gt[j])
        if beda:
            salah.append({"baris_gt": j + 1, "field": beda,
                          "prediksi": {f: pred[i].get(f) for f in ["waktu_transaksi", *_FIELD_ANGKA]},
                          "gt": {f: gt[j].get(f) for f in ["waktu_transaksi", *_FIELD_ANGKA]}})
        else:
            tp += 1
        a, b = _norm_teks(pred[i].get("keterangan")), _norm_teks(gt[j].get("keterangan"))
        err += levenshtein_distance(a, b)
        chars += len(b)
    fp = len(pred) - tp
    fn = len(gt) - tp
    hasil = {"n_prediksi": len(pred), "n_gt": len(gt), "tp": tp, "fp": fp, "fn": fn,
             "metode_cocok": metode, **_prf(tp, fp, fn),
             "cer_keterangan": (err / chars) if chars else 0.0,
             "kesalahan_keterangan": err, "karakter_keterangan": chars,
             "baris_pred_tak_terpasang": [i + 1 for i in tak_pred],
             "baris_gt_tak_terpasang": [j + 1 for j in tak_gt],
             "salah": salah[:maks_salah]}
    return hasil


def evaluate_end_to_end(predicted_records, gt_records):
    """Kompatibel dengan versi lama: mengembalikan precision/recall/f1."""
    h = evaluate_file(predicted_records, gt_records)
    return {"precision": h["precision"], "recall": h["recall"], "f1": h["f1"]}


def muat_gt_content(gt_dir, nama):
    """data/ground_truth/<bank>/<nama>_content.json -> list transaksi, atau None bila tidak ada."""
    import json
    import os
    bank = nama.split("_")[0].lower()
    path = os.path.join(gt_dir, bank, f"{nama}_content.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("transactions", [])


def _norm_sel(s):
    """Teks sel dibandingkan tanpa spasi (OCR sering menghapus/menambah spasi di sekitar 'WIB', angka)."""
    return "".join(str(s or "").split())


_KOLOM_SEL = ("tanggal_waktu", "keterangan", "nominal", "saldo")


def evaluate_sel(pred_sel, gt_cells):
    """Evaluasi level-1: teks mentah per sel (CER per kolom), tanpa parsing/koreksi.

    pred_sel : daftar dict {tanggal, waktu, keterangan, nominal, saldo} (hasil['sel_mentah'])
    gt_cells : daftar dict {tanggal_waktu, keterangan, nominal, saldo} dari <nama>_cells.json
    Pasangan baris berdasarkan urutan; bila jumlah baris berbeda dilaporkan 'baris_tidak_sama'
    dan hanya sejumlah min(n_pred, n_gt) baris pertama yang dibandingkan.
    """
    n = min(len(pred_sel), len(gt_cells))
    err = {k: 0 for k in _KOLOM_SEL}
    chars = {k: 0 for k in _KOLOM_SEL}
    sel_benar = {k: 0 for k in _KOLOM_SEL}
    for i in range(n):
        p = dict(pred_sel[i])
        p["tanggal_waktu"] = f"{p.get('tanggal', '')} {p.get('waktu', '')}"
        for k in _KOLOM_SEL:
            a, b = _norm_sel(p.get(k)), _norm_sel(gt_cells[i].get(k))
            d = levenshtein_distance(a, b)
            err[k] += d
            chars[k] += len(b)
            sel_benar[k] += (d == 0)
    cer = {k: (err[k] / chars[k]) if chars[k] else 0.0 for k in _KOLOM_SEL}
    return {"n_baris_pred": len(pred_sel), "n_baris_gt": len(gt_cells),
            "baris_tidak_sama": len(pred_sel) != len(gt_cells), "n_dibandingkan": n,
            "cer": cer, "kesalahan": err, "karakter": chars,
            "akurasi_sel": {k: (sel_benar[k] / n) if n else 0.0 for k in _KOLOM_SEL}}


def muat_gt_cells(gt_dir, nama):
    """data/ground_truth/<bank>/<nama>_cells.json -> list sel, atau None bila tidak ada."""
    import json
    import os
    bank = nama.split("_")[0].lower()
    path = os.path.join(gt_dir, bank, f"{nama}_cells.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("cells", []) if isinstance(d, dict) else d


def evaluate_semua(hasil_per_file, gt_dir):
    """Evaluasi seluruh hasil pipeline (list per file dari results.json) terhadap GT.

    Mengembalikan {"per_file": {...}, "per_bank": {...}, "total": {...}, "dilewati": {...}}.
    File dilewati (tidak masuk rata-rata) bila: GT belum ada, GT masih kosong, atau
    pipeline belum mendukung bank tersebut. Pencocokan GT memakai awalan nama file
    (bca_01 -> folder bca), bukan bank hasil deteksi, agar salah deteksi bank terhitung.
    """
    import os
    per_file, dilewati, per_file_murni, per_sel = {}, {}, {}, {}
    for h in hasil_per_file:
        nama = os.path.splitext(h["file"])[0]
        try:
            gt = muat_gt_content(gt_dir, nama)
        except ValueError as e:  # json.JSONDecodeError turunan ValueError
            lok = f" (baris {e.lineno}, kolom {e.colno})" if hasattr(e, "lineno") else ""
            dilewati[nama] = f"GT_RUSAK{lok}: {e.msg if hasattr(e, 'msg') else e}"
            continue
        if gt is None:
            dilewati[nama] = "GT_BELUM_ADA"
        elif not gt:
            dilewati[nama] = "GT_KOSONG"
        elif h["status"] in ("BELUM_DIDUKUNG", "BANK_TIDAK_DIKENALI", "FORMAT_TIDAK_DIDUKUNG"):
            dilewati[nama] = h["status"]
        else:
            r = evaluate_file(h["transaksi"], gt)
            r["status_pipeline"] = h["status"]
            r["bank_terdeteksi"] = h["bank"]
            if "transaksi_ocr_murni" in h:      # pipeline scan: dua angka (A: tanpa koreksi, B: terkoreksi)
                per_file_murni[nama] = evaluate_file(h["transaksi_ocr_murni"], gt)
            per_file[nama] = r
        if h.get("sel_mentah") is not None and "transaksi_ocr_murni" in h:
            try:
                cells = muat_gt_cells(gt_dir, nama)
            except ValueError as e:
                dilewati[nama + "#sel"] = f"GT_SEL_RUSAK: {e}"
                cells = None
            if cells:
                per_sel[nama] = evaluate_sel(h["sel_mentah"], cells)

    def agregat(items):
        tp = sum(x["tp"] for x in items)
        fp = sum(x["fp"] for x in items)
        fn = sum(x["fn"] for x in items)
        err = sum(x["kesalahan_keterangan"] for x in items)
        ch = sum(x["karakter_keterangan"] for x in items)
        return {"n_file": len(items), "tp": tp, "fp": fp, "fn": fn, **_prf(tp, fp, fn),
                "cer_keterangan": (err / ch) if ch else 0.0}

    per_bank = {}
    for nama, r in per_file.items():
        per_bank.setdefault(nama.split("_")[0].lower(), []).append(r)
    hasil = {"per_file": per_file,
             "per_bank": {b: agregat(v) for b, v in sorted(per_bank.items())},
             "total": agregat(list(per_file.values())),
             "dilewati": dilewati}
    if per_file_murni:      # hanya file scan; angka A = OCR murni, angka B (per_file) = setelah koreksi saldo
        pb = {}
        for nama, r in per_file_murni.items():
            pb.setdefault(nama.split("_")[0].lower(), []).append(r)
        hasil["ocr_murni"] = {"per_file": per_file_murni,
                              "per_bank": {b: agregat(v) for b, v in sorted(pb.items())},
                              "total": agregat(list(per_file_murni.values()))}
    if per_sel:
        hasil["sel_mentah"] = per_sel
    return hasil