import os
import pdfplumber
import logging

logger = logging.getLogger(__name__)

def detect_file_type(filepath: str, char_threshold: int = 50) -> str:
    """
    Mendeteksi jenis file berdasarkan ekstensi dan konten karakter.
    
    Args:
        filepath: Path ke file input.
        char_threshold: Ambang batas rata-rata karakter per halaman.
        
    Returns:
        String jenis file: 'excel', 'pdf_digital', atau 'pdf_scan'.
    """
    _, ext = os.path.splitext(filepath.lower())
    
    if ext in ['.xlsx', '.xls']:
        return 'excel'
    elif ext != '.pdf':
        raise ValueError(f"Format file tidak didukung: {ext}")
    
    try:
        with pdfplumber.open(filepath) as pdf:
            if not pdf.pages:
                return 'pdf_scan'
                
            total_chars = 0
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    total_chars += len(text.strip())
                    
            avg_chars = total_chars / len(pdf.pages)
            
            if avg_chars >= char_threshold:
                logger.info(f"Terdeteksi sebagai PDF Digital (avg chars: {avg_chars:.2f})")
                return 'pdf_digital'
            else:
                logger.info(f"Terdeteksi sebagai PDF Scan (avg chars: {avg_chars:.2f})")
                return 'pdf_scan'
                
    except Exception as e:
        logger.error(f"Gagal membaca PDF saat deteksi: {e}")
        return 'pdf_scan'  # Fallback ke scan jika metadata rusak/gagal parse