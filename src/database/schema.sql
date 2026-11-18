-- ============================================================
-- SIREKON Knowledge Base — Database Schema
-- Struktur: 4 Tree + Mapping Layer + Multitenant
-- Sesuai proposal TA: Tree + Map, Forward Chaining, Feedback Loop
-- ============================================================

-- 1. Tabel utama: Tree Nodes (self-referencing)
-- Menyimpan semua node dari 4 tree dalam satu tabel
-- Tree types: kategori, perusahaan, invoice, pola
CREATE TABLE IF NOT EXISTS tree_nodes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL,
    tree_type TEXT NOT NULL CHECK (tree_type IN ('kategori', 'perusahaan', 'invoice', 'pola')),
    parent_id UUID REFERENCES tree_nodes(id) ON DELETE SET NULL,
    kode TEXT,
    nama TEXT NOT NULL,
    deskripsi TEXT,
    level INTEGER NOT NULL DEFAULT 0,
    is_leaf BOOLEAN NOT NULL DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tree_nodes_client ON tree_nodes(client_id);
CREATE INDEX idx_tree_nodes_tree_type ON tree_nodes(client_id, tree_type);
CREATE INDEX idx_tree_nodes_parent ON tree_nodes(parent_id);
CREATE INDEX idx_tree_nodes_kode ON tree_nodes(client_id, kode);

-- 2. Mapping Layer (relasi cross-domain antar tree)
-- Menghubungkan node di tree berbeda, misal:
--   pola "BSNN" -> kategori "Bensin"
--   vendor "PT PLN" -> kategori "Biaya Utilitas"
CREATE TABLE IF NOT EXISTS mapping_layer (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL,
    source_node_id UUID NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES tree_nodes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    jumlah_konfirmasi_benar INTEGER NOT NULL DEFAULT 0,
    total_kemunculan INTEGER NOT NULL DEFAULT 0,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, source_node_id, target_node_id, relation_type)
);

CREATE INDEX idx_mapping_client ON mapping_layer(client_id);
CREATE INDEX idx_mapping_source ON mapping_layer(source_node_id);
CREATE INDEX idx_mapping_target ON mapping_layer(target_node_id);

-- 3. Account Mapping (kode transaksi bank -> kode akun ERP)
-- Tabel 3.1 di proposal: ADM->6-1100, PLN->6-2200, dll
CREATE TABLE IF NOT EXISTS account_mapping (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL,
    kode_transaksi_bank TEXT NOT NULL,
    kode_akun_erp TEXT NOT NULL,
    nama_akun TEXT,
    bank TEXT,
    deskripsi TEXT,
    jumlah_konfirmasi_benar INTEGER NOT NULL DEFAULT 0,
    total_kemunculan INTEGER NOT NULL DEFAULT 0,
    confidence NUMERIC(5,4) NOT NULL DEFAULT 0.0000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, kode_transaksi_bank, bank)
);

CREATE INDEX idx_account_mapping_client ON account_mapping(client_id);

-- 4. Transaksi (hasil rekonsiliasi yang sudah divalidasi)
-- Riwayat setiap transaksi yang diproses sistem
CREATE TABLE IF NOT EXISTS transaksi (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL,
    tanggal DATE NOT NULL,
    keterangan TEXT NOT NULL,
    keterangan_bersih TEXT,
    jenis TEXT NOT NULL CHECK (jenis IN ('DB', 'CR')),
    mutasi NUMERIC(15,2) NOT NULL,
    kode_akun_erp TEXT,
    nama_akun TEXT,
    kategori_node_id UUID REFERENCES tree_nodes(id),
    vendor_customer_node_id UUID REFERENCES tree_nodes(id),
    invoice_node_id UUID REFERENCES tree_nodes(id),
    nlp_confidence NUMERIC(5,4),
    kb_confidence NUMERIC(5,4),
    metode_matching TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'auto_match', 'suggestion', 'manual', 'confirmed', 'rejected')),
    dikonfirmasi_oleh TEXT,
    dikonfirmasi_pada TIMESTAMPTZ,
    sumber_file TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transaksi_client ON transaksi(client_id);
CREATE INDEX idx_transaksi_status ON transaksi(client_id, status);
CREATE INDEX idx_transaksi_tanggal ON transaksi(client_id, tanggal);

-- 5. Feedback Log (jejak setiap konfirmasi/tolak untuk audit)
CREATE TABLE IF NOT EXISTS feedback_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL,
    transaksi_id UUID NOT NULL REFERENCES transaksi(id) ON DELETE CASCADE,
    mapping_id UUID REFERENCES mapping_layer(id),
    account_mapping_id UUID REFERENCES account_mapping(id),
    aksi TEXT NOT NULL CHECK (aksi IN ('konfirmasi', 'tolak', 'manual_input')),
    kode_akun_lama TEXT,
    kode_akun_baru TEXT,
    catatan TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_feedback_client ON feedback_log(client_id);
CREATE INDEX idx_feedback_transaksi ON feedback_log(transaksi_id);

-- 6. Dokumen Upload (tracking file yang sudah diupload, cegah duplikat)
CREATE TABLE IF NOT EXISTS dokumen_upload (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    client_id UUID NOT NULL,
    nama_file TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    ukuran_byte BIGINT,
    jumlah_transaksi INTEGER DEFAULT 0,
    bank_terdeteksi TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, file_hash)
);

CREATE INDEX idx_dokumen_client ON dokumen_upload(client_id);
CREATE INDEX idx_dokumen_hash ON dokumen_upload(client_id, file_hash);

-- 7. Enable RLS on all tables
ALTER TABLE tree_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE mapping_layer ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_mapping ENABLE ROW LEVEL SECURITY;
ALTER TABLE transaksi ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE dokumen_upload ENABLE ROW LEVEL SECURITY;
