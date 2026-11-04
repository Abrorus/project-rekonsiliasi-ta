import pdfplumber
import logging
from typing import List, Dict, Tuple, Any

logger = logging.getLogger(__name__)

HEADER_KEYWORDS = [
    'tanggal', 'date', 'tgl', 'keterangan', 'description', 'uraian', 
    'deskripsi', 'debet', 'debit', 'kredit', 'credit', 'mutasi', 
    'saldo', 'balance', 'nominal', 'tipe'
]

def detect_tables(page: pdfplumber.page.Page) -> Tuple[List[Any], List[Tuple]]:
    """
    Tahap 1: Table Detection (TD).
    Auto-detect strategi garis (BCA, Mandiri, BRI, BSI) lalu fallback ke text (BNI).
    """
    tables_lines = page.find_tables(table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"})
    if tables_lines:
        return tables_lines, [t.bbox for t in tables_lines]
        
    tables_text = page.find_tables(table_settings={"vertical_strategy": "text", "horizontal_strategy": "text"})
    if tables_text:
        logger.info("Tabel eksplisit tidak ditemukan, menggunakan fallback 'text' strategy (indikasi format BNI)")
        return tables_text, [t.bbox for t in tables_text]
        
    return [], []

def recognize_structure(table_obj: Any) -> Tuple[int, int, int]:
    """
    Tahap 2: Table Structure Recognition (TSR).
    Mengenali jumlah baris, kolom, dan mendeteksi lokasi header secara dinamis.
    """
    raw_data = table_obj.extract()
    num_rows = len(raw_data)
    num_cols = len(raw_data[0]) if num_rows > 0 else 0
    
    header_idx = -1
    for i, row in enumerate(raw_data):
        if not row: continue
        matches = sum(1 for cell in row if cell and str(cell).lower().strip() in HEADER_KEYWORDS)
        if matches >= 2:
            header_idx = i
            break
            
    return num_rows, num_cols, header_idx

def extract_content(table_obj: Any, header_idx: int) -> List[Dict]:
    """
    Tahap 3: Content Extraction.
    Mengekstrak baris demi baris, melewati baris kosong.
    """
    raw_data = table_obj.extract()
    if header_idx == -1 or header_idx >= len(raw_data):
        return []
        
    headers = [str(h).strip().replace('\n', ' ') if h else f"UNKNOWN_HEADER_{i}" for i, h in enumerate(raw_data[header_idx])]
    extracted_data = []
    
    for row in raw_data[header_idx + 1:]:
        if not any(row): continue  # Skip baris kosong
        
        # Filter dasar untuk membuang page footer / header berulang
        # TODO: verify with real data (Pastikan baris benar-benar transaksi berdasarkan kolom nominal/tanggal)
        row_dict = {}
        for i, cell in enumerate(row):
            if i < len(headers):
                val = str(cell).replace('\n', ' ').strip() if cell else ""
                row_dict[headers[i]] = val
        
        # Validasi ringan: Jika seluruh kunci kosong, skip
        if any(row_dict.values()):
            extracted_data.append(row_dict)
            
    return extracted_data

def process_digital_pdf(filepath: str) -> Tuple[List[Dict], Dict]:
    """Menjalankan seluruh pipeline PDF Digital."""
    all_extracted_data = []
    eval_data = {'bboxes': [], 'structures': []}
    
    try:
        with pdfplumber.open(filepath) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables, bboxes = detect_tables(page)
                eval_data['bboxes'].extend(bboxes)
                
                for tbl in tables:
                    num_rows, num_cols, header_idx = recognize_structure(tbl)
                    eval_data['structures'].append({'num_rows': num_rows, 'num_cols': num_cols})
                    
                    if header_idx != -1:
                        content = extract_content(tbl, header_idx)
                        all_extracted_data.extend(content)
                        
    except Exception as e:
        logger.error(f"Gagal memproses file {filepath} pada pipeline digital: {e}")
        
    return all_extracted_data, eval_data