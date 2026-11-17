import os
import argparse
import json
import logging
from src.detector import detect_file_type
from src.pipeline_digital import process_digital_pdf
from src.pipeline_scan import process_scan_pdf
from src.normalizer import normalize_data
from src.deduplicator import deduplicate_records

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_file(filepath: str) -> list:
    """Mengelola siklus penuh per file individu."""
    file_type = detect_file_type(filepath)
    
    if file_type == 'pdf_digital':
        logger.info(f"Memulai pipeline digital untuk: {filepath}")
        raw_data, _ = process_digital_pdf(filepath)
    elif file_type == 'pdf_scan':
        logger.info(f"Memulai pipeline scan untuk: {filepath}")
        raw_data, _ = process_scan_pdf(filepath)
    else:
        logger.warning(f"Melewati file yang belum didukung: {filepath}")
        return []
        
    normalized = normalize_data(raw_data, filepath)
    return normalized

def main():
    parser = argparse.ArgumentParser(description="SiRekon - Table Recognition Module")
    parser.add_argument('--input', type=str, required=True, help="Path ke file PDF atau folder")
    parser.add_argument('--recursive', action='store_true', help="Proses folder secara rekursif")
    parser.add_argument('--evaluate', action='store_true', help="Jalankan mode evaluasi")
    parser.add_argument('--gt', type=str, help="Path ke folder Ground Truth")
    
    args = parser.parse_args()
    
    all_records = []
    
    if os.path.isfile(args.input):
        all_records.extend(process_file(args.input))
    elif os.path.isdir(args.input):
        for root, _, files in os.walk(args.input):
            for file in files:
                if file.lower().endswith('.pdf'):
                    path = os.path.join(root, file)
                    all_records.extend(process_file(path))
            if not args.recursive:
                break
                
    # Tahap Post-Processing
    final_records = deduplicate_records(all_records)
    
    os.makedirs('output', exist_ok=True)
    out_path = os.path.join('output', 'results.json')
    
    with open(out_path, 'w') as f:
        json.dump(final_records, f, indent=2)
        
    logger.info(f"Ekstraksi selesai. Hasil disimpan di: {out_path}")
    
    if args.evaluate and args.gt:
        logger.info("TODO: Modul perbandingan evaluasi End-to-End dengan Ground Truth JSON.")

if __name__ == "__main__":
    main()