import os
import re
import logging
from typing import Dict, List, Optional, Any

# Konfigurasi Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger.warning("Package 'requests' belum terinstal. Mode live API akan nonaktif.")

try:
    from knowledge_base.kategori_keuangan import KATEGORI
    from knowledge_base.rekanan_resolver import MASTER_CUSTOMERS, MASTER_VENDORS
except ImportError:
    try:
        from src.knowledge_base.kategori_keuangan import KATEGORI
        from src.knowledge_base.rekanan_resolver import MASTER_CUSTOMERS, MASTER_VENDORS
    except ImportError:
        from kategori_keuangan import KATEGORI
        from rekanan_resolver import MASTER_CUSTOMERS, MASTER_VENDORS

# ==============================================================================
# ADAPTER REST API PERUSAHAAN (ERP & ACCOUNTING INTEGRATION LAYER)
# ==============================================================================

class PerusahaanAPIClient:
    """
    Klien Adapter untuk berkomunikasi dengan REST API sistem ERP/Akuntansi perusahaan.
    
    Dilengkapi dengan 'Mock Mode' bawaan sehingga Modul Knowledge Base tetap dapat
    diuji dan didemokan meskipun server API perusahaan belum rilis / offline.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        use_mock: bool = True,
        timeout: int = 5
    ):
        """
        Inisialisasi klien API.
        
        - base_url: URL induk endpoint perusahaan (misal: 'https://api.perusahaan.com/v1')
        - api_key: Token otentikasi Bearer / Header
        - use_mock: Set True jika belum ada API live, set False jika ingin menembak server asli
        - timeout: Batas waktu request dalam detik (default 5 detik)
        """
        self.base_url = base_url or os.getenv("PERUSAHAAN_API_URL", "https://api.avolut.com/v1")
        self.api_key = api_key or os.getenv("PERUSAHAAN_API_KEY", "mock-token-xyz")
        self.use_mock = use_mock
        self.timeout = timeout

        if self.use_mock:
            logger.info("PerusahaanAPIClient aktif dalam mode: SANDBOX / MOCK DATA.")
        else:
            logger.info(f"PerusahaanAPIClient aktif dalam mode: LIVE API ({self.base_url}).")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    # --------------------------------------------------------------------------
    # 1. CHART OF ACCOUNTS (CoA) PERUSAHAAN
    # --------------------------------------------------------------------------
    def get_chart_of_accounts(self) -> Dict[str, Dict[str, str]]:
        """Mengambil struktur akun resmi dari buku besar perusahaan."""
        if not self.use_mock and REQUESTS_AVAILABLE:
            try:
                url = f"{self.base_url}/chart-of-accounts"
                resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.json().get("data", {})
                logger.warning(f"Gagal mengambil CoA dari server (Status {resp.status_code}), fallback ke Mock.")
            except Exception as e:
                logger.warning(f"Koneksi live API gagal ({e}), otomatis beralih ke Mock.")

        # Fallback Mock: Menggunakan kamus kategori lokal
        return KATEGORI

    # --------------------------------------------------------------------------
    # 2. MASTER PARTNER (VENDOR & CUSTOMER)
    # --------------------------------------------------------------------------
    def get_partners(self) -> Dict[str, List[str]]:
        """Mengambil daftar rekanan bisnis resmi perusahaan."""
        if not self.use_mock and REQUESTS_AVAILABLE:
            try:
                url = f"{self.base_url}/partners"
                resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.json().get("data", {})
                logger.warning(f"Gagal mengambil Partner dari server, fallback ke Mock.")
            except Exception as e:
                logger.warning(f"Koneksi live API gagal ({e}), otomatis beralih ke Mock.")

        # Fallback Mock: Menggunakan daftar rekanan yang sudah teridentifikasi
        return {
            "customers": sorted(list(MASTER_CUSTOMERS)),
            "vendors": sorted(list(MASTER_VENDORS))
        }

    # --------------------------------------------------------------------------
    # 3. TAGIHAN / INVOICE MATCHING (REKONSILIASI FAKTUR)
    # --------------------------------------------------------------------------
    def get_unpaid_invoices(self) -> List[Dict[str, Any]]:
        """Mengambil daftar invoice yang belum lunas (outstanding)."""
        if not self.use_mock and REQUESTS_AVAILABLE:
            try:
                url = f"{self.base_url}/invoices?status=UNPAID"
                resp = requests.get(url, headers=self._get_headers(), timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.json().get("data", [])
                logger.warning(f"Gagal mengambil Invoice dari server, fallback ke Mock.")
            except Exception as e:
                logger.warning(f"Koneksi live API gagal ({e}), otomatis beralih ke Mock.")

        # Fallback Mock: Sampel invoice realistis berdasarkan riwayat BCA 2023
        return [
            {
                "invoice_no": "INV-2023-001",
                "partner_name": "CIOMAS ADISATWA",
                "partner_type": "VENDOR",
                "amount": 580075045.0,
                "due_date": "2023-07-31",
                "status": "UNPAID",
                "kode_akun": "6-5000"
            },
            {
                "invoice_no": "INV-2023-002",
                "partner_name": "AMERTHA JAYA",
                "partner_type": "CUSTOMER",
                "amount": 595075045.0,
                "due_date": "2023-07-30",
                "status": "UNPAID",
                "kode_akun": "4-2000"
            },
            {
                "invoice_no": "INV-2023-003",
                "partner_name": "BAREKA LINTAS INDO",
                "partner_type": "VENDOR",
                "amount": 138500000.0,
                "due_date": "2023-07-28",
                "status": "UNPAID",
                "kode_akun": "6-5000"
            }
        ]

    def match_invoice(
        self,
        keterangan: str,
        nominal: Optional[float] = None,
        nama_rekanan: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fungsi Matching: Mencocokkan transaksi bank dengan daftar invoice perusahaan.
        
        Kriteria Pencocokan:
        1. Mencari nomor invoice langsung dari teks keterangan (misal 'INV-2023-001').
        2. ATAU mencocokkan kombinasi Nama Rekanan + Kesesuaian Nominal Tagihan.
        """
        invoices = self.get_unpaid_invoices()
        k_upper = str(keterangan).upper()

        # Strategi 1: Exact Match Nomor Invoice di teks mutasi
        for inv in invoices:
            inv_no = inv["invoice_no"].upper()
            if inv_no in k_upper:
                return {
                    "matched": True,
                    "kriteria": "Nomor Invoice Teridentifikasi",
                    "invoice_no": inv["invoice_no"],
                    "partner_name": inv["partner_name"],
                    "kode_akun": inv["kode_akun"],
                    "status_rekonsiliasi": "RECONCILED",
                    "selisih_nominal": abs(float(nominal or 0) - float(inv["amount"])) if nominal else 0.0
                }

        # Strategi 2: Match berdasarkan Nama Partner + Nominal Persis
        if nominal and nama_rekanan:
            for inv in invoices:
                if inv["partner_name"].upper() in nama_rekanan.upper():
                    if abs(float(nominal) - float(inv["amount"])) < 1.0: # Selisih 0 rupiah
                        return {
                            "matched": True,
                            "kriteria": "Nama Rekanan & Nominal Tepat",
                            "invoice_no": inv["invoice_no"],
                            "partner_name": inv["partner_name"],
                            "kode_akun": inv["kode_akun"],
                            "status_rekonsiliasi": "RECONCILED",
                            "selisih_nominal": 0.0
                        }

        return None

if __name__ == "__main__":
    print("=== PENGUJIAN ADAPTER REST API PERUSAHAAN ===")
    client = PerusahaanAPIClient(use_mock=True)

    print("\n1. Mengambil Master Rekanan:")
    partners = client.get_partners()
    print(f"Total Customer Terdaftar : {len(partners['customers'])} (Contoh: {partners['customers'][:3]})")
    print(f"Total Vendor Terdaftar   : {len(partners['vendors'])} (Contoh: {partners['vendors'][:3]})")

    print("\n2. Uji Pencocokan Invoice (Matching Engine):")
    # Contoh mutasi BCA: "TRSF E-BANKING INV-2023-001 CIOMAS ADISATWA", nominal: 580075045.0
    hasil_match = client.match_invoice(
        keterangan="TRSF E-BANKING INV-2023-001 CIOMAS ADISATWA",
        nominal=580075045.0,
        nama_rekanan="CIOMAS ADISATWA"
    )

    if hasil_match:
        print("-> HASIL MATCHING BERHASIL:")
        print(f"   Nomor Faktur : {hasil_match['invoice_no']}")
        print(f"   Rekanan      : {hasil_match['partner_name']}")
        print(f"   Kode Akun    : {hasil_match['kode_akun']}")
        print(f"   Status Rekon : {hasil_match['status_rekonsiliasi']}")
        print(f"   Kriteria     : {hasil_match['kriteria']}")
    else:
        print("-> Tidak ditemukan invoice yang cocok.")
