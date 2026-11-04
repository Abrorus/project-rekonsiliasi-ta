import pandas as pd
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def deduplicate_records(records: List[Dict]) -> List[Dict]:
    """
    Menghapus duplikasi berdasarkan primary keys gabungan:
    (source_file, waktu_transaksi, debit, kredit).
    """
    if not records:
        return []
        
    df = pd.DataFrame(records)
    initial_count = len(df)
    
    # Drop duplikat dengan mempertahankan entri pertama
    df = df.drop_duplicates(subset=['source_file', 'waktu_transaksi', 'debit', 'kredit'], keep='first')
    
    final_count = len(df)
    removed_count = initial_count - final_count
    
    if removed_count > 0:
        logger.info(f"Deduplikasi selesai. Menghapus {removed_count} record duplikat. Sisa: {final_count}")
    else:
        logger.info(f"Tidak ada duplikat ditemukan. Total record: {final_count}")
        
    return df.to_dict('records')