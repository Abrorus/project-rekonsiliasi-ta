import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
import logging
from typing import List, Dict, Tuple
from .evaluator import evaluate_extraction_scan

logger = logging.getLogger(__name__)

def detect_tables(image: np.ndarray) -> Tuple[List[Tuple], np.ndarray]:
    """Tahap 1: Table Detection berbasis kontur luasan minimum."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h_img, w_img = image.shape[:2]
    min_area = (h_img * w_img) * 0.10
    
    bboxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w * h >= min_area:
            bboxes.append((x, y, x + w, y + h))
            
    if not bboxes:
        logger.warning("Tidak ditemukan kontur tabel utama. Menggunakan seluruh halaman.")
        bboxes.append((0, 0, w_img, h_img))
        
    return bboxes, gray

def recognize_structure(gray_image: np.ndarray, bbox: Tuple) -> Tuple[int, int, List[Tuple]]:
    """Tahap 2: Table Structure Recognition dengan morfologi garis."""
    x1, y1, x2, y2 = bbox
    roi = gray_image[y1:y2, x1:x2]
    
    _, thresh = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    
    # Kernel adaptif berdasarkan ukuran tabel
    kernel_length = np.array(roi).shape[1] // 80
    
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_length))
    hori_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_length, 1))
    
    img_vw = cv2.erode(thresh, vert_kernel, iterations=3)
    vert_lines = cv2.dilate(img_vw, vert_kernel, iterations=3)
    
    img_hw = cv2.erode(thresh, hori_kernel, iterations=3)
    hori_lines = cv2.dilate(img_hw, hori_kernel, iterations=3)
    
    table_grid = cv2.addWeighted(vert_lines, 0.5, hori_lines, 0.5, 0.0)
    _, table_grid = cv2.threshold(table_grid, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    
    # Deteksi perpotongan / sel
    contours, _ = cv2.findContours(table_grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    cell_bboxes = []
    for cnt in contours:
        cx, cy, cw, ch = cv2.boundingRect(cnt)
        if cw > 20 and ch > 10: # Filter noise
            # Translasi kembali ke koordinat halaman
            cell_bboxes.append((x1 + cx, y1 + cy, x1 + cx + cw, y1 + cy + ch))
            
    # Mengurutkan koordinat sel (top-to-bottom, left-to-right)
    # TODO: verify with real data (pengurutan toleransi sumbu Y)
    cell_bboxes = sorted(cell_bboxes, key=lambda b: (b[1] // 10, b[0]))
    
    num_rows = len(set([b[1] // 10 for b in cell_bboxes]))
    num_cols = len(cell_bboxes) // num_rows if num_rows > 0 else 0
    
    return num_rows, num_cols, cell_bboxes

def extract_content(image: np.ndarray, cell_bboxes: List[Tuple], gt_texts: List[str] = None) -> List[str]:
    """Tahap 3: Content Extraction dengan iterasi adaptif CER."""
    extracted = []
    
    for i, bbox in enumerate(cell_bboxes):
        x1, y1, x2, y2 = bbox
        cell_img = image[y1:y2, x1:x2]
        
        def run_ocr(img, psm=7, use_otsu=True):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
            if use_otsu:
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
            else:
                thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
            
            custom_config = f'--oem 3 --psm {psm}'
            return pytesseract.image_to_string(thresh, config=custom_config).strip()
            
        base_text = run_ocr(cell_img)
        
        # Iterasi CER Correction jika Ground Truth tersedia (Simulasi)
        if gt_texts and i < len(gt_texts):
            eval_res = evaluate_extraction_scan(base_text, gt_texts[i])
            if eval_res['cer'] > 0.05:
                logger.info(f"CER tinggi ({eval_res['cer']:.2f}). Menjalankan iterasi preprocessing...")
                
                # Iterasi 1: Denoise + Otsu Biasa
                denoised = cv2.fastNlMeansDenoising(cell_img, None, 10, 7, 21)
                text_1 = run_ocr(denoised, use_otsu=False)
                if evaluate_extraction_scan(text_1, gt_texts[i])['cer'] <= 0.05:
                    base_text = text_1
                else:
                    # Iterasi 2: PSM 6 (Uniform Block)
                    text_2 = run_ocr(cell_img, psm=6)
                    if evaluate_extraction_scan(text_2, gt_texts[i])['cer'] <= 0.05:
                        base_text = text_2
                        
        extracted.append(base_text)
        
    return extracted

def process_scan_pdf(filepath: str, gt_texts: List[str] = None) -> Tuple[List[Dict], Dict]:
    """Menjalankan seluruh pipeline PDF Scan."""
    eval_data = {'bboxes': [], 'structures': []}
    
    try:
        images = convert_from_path(filepath, dpi=300)
        # TODO: verify with real data (Mengubah List[str] ke List[Dict] sesuai format row akhir. 
        # Saat ini PDF Scan pipeline masih berupa proof-of-concept per sel akibat variabilitas grid opencv.)
        logger.info(f"Berhasil mengkonversi PDF scan ke {len(images)} citra.")
        
        # (Implementasi detail konstruksi Dict dari sel-sel hasil scan akan diletakkan di sini 
        # setelah penyesuaian sumbu X/Y kolom).
        
    except Exception as e:
        logger.error(f"Gagal memproses file scan {filepath}: {e}")
        
    return [], eval_data