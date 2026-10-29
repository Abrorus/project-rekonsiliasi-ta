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
    
    parsed = dateparser.parse(date_str, languages=['id', 'en'], settings={'DATE_ORDER': 'DMY'})
    if not parsed:
        try:
            parsed = pd.to_datetime(date_str, dayfirst=True)
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

def normalize_data(raw_records: List[Dict], source_file: str) -> List[Dict]:
    """Penyelarasan seluruh field baris transaksi ke format Canonical SiRekon."""
    normalized_list = []
    filename = os.path.basename(source_file)
    
    for row in raw_records:
        std = standardize_headers(row)
        
        # Penanganan Kasus BNI: nominal tunggal + tipe C/D
        debit = parse_amount(std.get('debit', '0'))
        kredit = parse_amount(std.get('kredit', '0'))
        
        if 'nominal' in std and 'tipe' in std:
            val = parse_amount(std['nominal'])
            t = str(std['tipe']).upper()
            if 'C' in t or 'CR' in t:
                kredit = val
            elif 'D' in t or 'DB' in t:
                debit = val
                
        # Kasus mutasi tunggal (BCA)
        if 'mutasi' in std:
            val = str(std['mutasi'])
            if 'DB' in val.upper():
                debit = parse_amount(val)
            elif 'CR' in val.upper():
                kredit = parse_amount(val)
                
        normalized_record = {
            "source_file": filename,
            "waktu_transaksi": parse_date(str(std.get('waktu_transaksi', '')), filename),
            "keterangan": str(std.get('keterangan', '')).strip(),
            "debit": debit,
            "kredit": kredit,
            "saldo": parse_amount(std.get('saldo', '0'))
        }
        
        # Jangan masukkan baris kosong/header tersisa
        if normalized_record['keterangan'] != '' or normalized_record['debit'] > 0 or normalized_record['kredit'] > 0:
            normalized_list.append(normalized_record)
            
    return normalized_list
