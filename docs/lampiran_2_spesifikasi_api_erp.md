# Lampiran 2: Spesifikasi API Endpoint yang Dibutuhkan Sistem SIREKON

## Ringkasan
Modul Knowledge Base pada sistem SIREKON membutuhkan akses ke **3 endpoint REST API** dari sistem ERP perusahaan untuk mengambil data secara real-time. Saat ini sistem menggunakan data mock (dummy) karena belum ada akses ke server.

## Kebutuhan Koneksi

| Item | Keterangan |
|------|-----------|
| Protokol | HTTPS (REST API) |
| Otentikasi | Bearer Token di header `Authorization` |
| Format | JSON |
| Frekuensi Akses | Setiap 5 menit (cache TTL) |

**Yang dibutuhkan:**
- Base URL API (contoh: `https://api.perusahaan.com/v1`)
- API Key / Token

---

## Endpoint 1: Chart of Accounts

**`GET /chart-of-accounts`**

Mengambil daftar seluruh kode akun resmi perusahaan.

**Contoh Response yang Diharapkan:**
```json
{
  "data": {
    "1.1.01.01": {
      "nama": "Cash on Hand:IDR",
      "tipe": "Asset",
      "level": "Detail"
    },
    "2.1.01.01": {
      "nama": "Trade Payable - 3rd Party",
      "tipe": "Liability",
      "level": "Detail"
    },
    "6.2.05.01": {
      "nama": "Utilities-Electricity",
      "tipe": "Expense",
      "level": "Detail"
    }
  }
}
```

---

## Endpoint 2: Master Rekanan (Vendor & Customer)

**`GET /partners`**

Mengambil daftar nama vendor dan customer yang terdaftar resmi di ERP.

**Contoh Response yang Diharapkan:**
```json
{
  "data": {
    "customers": [
      "AMERTHA JAYA",
      "PANCA BERSAUDARA",
      "MITRA ABADI JAYA"
    ],
    "vendors": [
      "CIOMAS ADISATWA",
      "BAREKA LINTAS INDO",
      "SENTOT PRABOWO"
    ]
  }
}
```

---

## Endpoint 3: Invoice Outstanding (Belum Lunas)

**`GET /invoices?status=UNPAID`**

Mengambil daftar faktur/tagihan yang belum lunas untuk pencocokan otomatis dengan transaksi bank.

**Contoh Response yang Diharapkan:**
```json
{
  "data": [
    {
      "invoice_no": "INV-2023-001",
      "partner_name": "CIOMAS ADISATWA",
      "partner_type": "VENDOR",
      "amount": 580075045.00,
      "due_date": "2023-07-31",
      "status": "UNPAID",
      "kode_akun": "2.1.01.01"
    }
  ]
}
```

**Field yang dibutuhkan per invoice:**
| Field | Tipe | Keterangan |
|-------|------|-----------|
| invoice_no | string | Nomor faktur |
| partner_name | string | Nama vendor/customer |
| partner_type | string | "VENDOR" atau "CUSTOMER" |
| amount | number | Nominal tagihan (dalam Rupiah) |
| due_date | string | Tanggal jatuh tempo (format: YYYY-MM-DD) |
| status | string | Status pembayaran |
| kode_akun | string | Kode akun CoA terkait |

---

## Alternatif (Jika API Belum Tersedia)

Jika server API belum siap, data berikut bisa diekspor dalam format **Excel (.xlsx) atau CSV**:

1. **Export CoA lengkap** — seluruh kode akun beserta nama dan tipe
2. **Export daftar vendor & customer** — nama-nama rekanan yang terdaftar di ERP
3. **Export invoice outstanding** — daftar tagihan yang belum lunas beserta nominal dan rekanan

Data dalam format file ini sudah cukup untuk tahap pengujian Tugas Akhir.
