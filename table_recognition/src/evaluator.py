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

def evaluate_end_to_end(predicted_records, gt_records):
    """Evaluasi akhir (End-to-End)."""
    tp = fp = fn = 0
    
    def make_key(rec):
        return (str(rec.get('waktu_transaksi', '')), 
                float(rec.get('debit', 0.0)), 
                float(rec.get('kredit', 0.0)))
                
    gt_keys = [make_key(r) for r in gt_records]
    pred_keys = [make_key(r) for r in predicted_records]
    
    for pk in pred_keys:
        if pk in gt_keys:
            tp += 1
            gt_keys.remove(pk)
        else:
            fp += 1
    fn = len(gt_keys)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    return {'precision': precision, 'recall': recall, 'f1': f1}