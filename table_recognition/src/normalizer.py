import pandas as pd
import dateparser
import re
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

HEADER_MAPPING = {
    'waktu_transaksi': ['tanggal', 'date', 'tgl', 'tanggal transaksi', 'tgl transaksi'],
    'keterangan': ['keterangan', 'description', 'uraian', 'deskripsi'],
    'debit': ['debet', 'debit', 'db'],
    'kredit': ['kredit', 'credit', 'cr'],
    'saldo': ['saldo', 'balance', 'saldo akhir'],
    'mutasi': ['mutasi'],           # Kasus khusus BCA
    'nominal': ['nominal'],         # Kasus khusus BNI
    'tipe': ['tipe', 'type', 'c/d'] # Kasus khusus BNI
}

def standardize_headers(row: Dict) -> Dict:
    """Memetakan header mentah ke skema standar, menampung UNKNOWN_HEADER."""
    standardized = {}
    for raw_header, val in row.items():
        raw_clean = str(raw_header).lower().strip()
        matched = False
        for std_col, variants in HEADER_MAPPING.items():
            if raw_clean in variants:
                standardized[std_col] = val
                matched = True
                break
        if not matched:
            logger.debug(f"UNKNOWN_HEADER terdeteksi: {raw_header}")
            standardized[raw_header] = val
    return standardized

def parse_date(date_str: str, source_file: str) -> str:
    """Normalisasi tanggal. Menarik tahun dari file jika formatnya DD/MM."""
    if not date_str: return ""
    
    parsed = dateparser.parse(date_str, languages=['id', 'en'])
    if not parsed:
        try:
            parsed = pd.to_datetime(date_str)
        except:
            return date_str
            
    # Penanganan BCA: DD/MM (Tanpa Tahun)
    if len(date_str.split('/')) == 2 or len(date_str.split('-')) == 2:
        file_year_match = re.search(r'20\d{2}', source_file)
        if file_year_match:
            parsed = parsed.replace(year=int(file_year_match.group()))
            
    return parsed.strftime('%Y-%m-%d')

def parse_amount(amount_str: str) -> float:
    """Membersihkan format IDR (titik ribuan, koma desimal) ke float."""
    if not amount_str or str(amount_str).strip() == '': return 0.0
    
    cleaned = re.sub(r'[^\d,-]', '', str(amount_str))
    # Ubah format Indonesia (1.000.000,00) menjadi standar komputasi (1000000.00)
    cleaned = cleaned.replace('.', '').replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def normalize_data(raw_data: List[Dict], source_file: str) -> List[Dict]:
    """Mengeksekusi normalisasi pada seluruh row transaksi."""
    normalized_records = []
    
    for row in raw_data:
        std_row = standardize_headers(row)
        
        # Penanganan Kasus Khusus BCA: Kolom Mutasi (DB/CR)
        if 'mutasi' in std_row and std_row['mutasi']:
            mutasi_val = str(std_row['mutasi']).strip().upper()
            amt = parse_amount(mutasi_val.replace('DB', '').replace('CR', ''))
            if 'DB' in mutasi_val:
                std_row['debit'], std_row['kredit'] = amt, 0.0
            elif 'CR' in mutasi_val:
                std_row['debit'], std_row['kredit'] = 0.0, amt
                
        # Penanganan Kasus Khusus BNI: Nominal + Tipe
        if 'nominal' in std_row and 'tipe' in std_row:
            amt = parse_amount(std_row['nominal'])
            tipe_val = str(std_row['tipe']).strip().upper()
            if tipe_val == 'D':
                std_row['debit'], std_row['kredit'] = amt, 0.0
            elif tipe_val == 'C':
                std_row['debit'], std_row['kredit'] = 0.0, amt

        waktu = parse_date(std_row.get('waktu_transaksi', ''), source_file)
        
        record = {
            'source_file': os.path.basename(source_file),
            'waktu_transaksi': waktu,
            'keterangan': std_row.get('keterangan', ''),
            'debit': parse_amount(std_row.get('debit', 0.0)),
            'kredit': parse_amount(std_row.get('kredit', 0.0)),
            'saldo': parse_amount(std_row.get('saldo', 0.0))
        }
        
        if record['waktu_transaksi'] or record['keterangan']:
            normalized_records.append(record)
            
    return normalized_records