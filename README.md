# SIREKON — Sistem Rekonsiliasi Transaksi Keuangan Cerdas

Proyek Tugas Akhir Departemen Sistem Informasi ITS: **Sistem Rekonsiliasi Transaksi Keuangan Bank Berbasis Integrasi Table Recognition, NLP, dan Knowledge Base**.

## Tim Pengembang
- **Pool 1 — Table Recognition (`table_recognition/`)**: Ekstraksi tabel rekening koran format PDF digital & scan (Arya Wiraguna Dwiputra).
- **Pool 2 — Modul NLP (`src/` & `models/`)**: Klasifikasi teks keterangan mutasi ke 21 sub-kategori CoA menggunakan TF-IDF + SVM terkalibrasi, *confidence threshold* (`0.72`), dan *feedback learning* (Abrorus Shobah).
- **Pool 3 — Knowledge Base, Backend & WebApp (`src/knowledge_base/`, `src/api/`, `backend/`, `frontend/`)**: Mesin aturan akuntansi (*Forward Chaining*), pencocokan rekanan ERP, database Supabase, dan antarmuka React + Vite (Muhammad Ridho Utomo / Mario).

## Menjalankan Secara Lokal

### 1. Backend FastAPI
```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend WebApp (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
Untuk deploy ke **Vercel**, atur Root Directory ke `frontend` dan isi Environment Variable `VITE_API_BASE` dengan URL backend FastAPI produksi (default lokal: `http://localhost:8000/api`).
