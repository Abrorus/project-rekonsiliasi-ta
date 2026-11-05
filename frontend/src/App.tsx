import { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import {
  Upload, FileText, Brain, Database, CheckCircle2, AlertTriangle,
  XCircle, ArrowRight, Loader2, Clock, Zap, AlertCircle,
  Check, X, Pencil, ThumbsUp, ThumbsDown, Play, User, Search
} from 'lucide-react'

interface TransactionResult {
  id: string
  tanggal: string
  keterangan: string
  teks_bersih?: string
  kategori_nlp?: string
  jenis: 'DB' | 'CR' | string
  debit: number
  kredit: number
  saldo: number
  mutasi: number
  kode_akun: string
  nama_akun: string
  kandidat_kode_akun?: string
  kandidat_nama_akun?: string
  status: 'auto_match' | 'suggestion' | 'not_found' | 'confirmed' | 'rejected'
  metode: string
  conf: number
  confidence_tinggi: boolean
  threshold: number
  pool?: string
  nama_pihak?: string
  invoice_no?: string
  invoice_status?: string
}

interface CoaItem {
  kode: string
  nama: string
  label: string
  account_type?: string
}

interface Stats {
  total: number
  auto_match: number
  suggestion: number
  not_found: number
  manual: number
  confirmed: number
  rejected: number
  coverage: number
}

const API_BASE = 'http://localhost:8000/api'
const NLP_THRESHOLD = 0.72

function formatCurrency(val: number) {
  return new Intl.NumberFormat('id-ID').format(val)
}

function mapStatus(s: string): TransactionResult['status'] {
  if (s === 'auto_match' || s === 'auto') return 'auto_match'
  if (s === 'suggestion' || s === 'review') return 'suggestion'
  if (s === 'confirmed') return 'confirmed'
  if (s === 'rejected') return 'rejected'
  return 'not_found'
}

function mapRawToTransaction(r: Record<string, unknown>): TransactionResult {
  const jenis = String(r.jenis || 'DB').toUpperCase()
  const mutasi = Number(r.mutasi) || 0
  const debit = Number(r.debit) || (jenis === 'DB' ? mutasi : 0)
  const kredit = Number(r.kredit) || (jenis === 'CR' ? mutasi : 0)
  const saldo = Number(r.saldo) || 0
  const conf = Number(r.conf) || 0
  const threshold = Number(r.threshold) || NLP_THRESHOLD
  const confidence_tinggi =
    typeof r.confidence_tinggi === 'boolean' ? r.confidence_tinggi : conf >= threshold

  return {
    id: String(r.id || crypto.randomUUID()),
    tanggal: String(r.tanggal || r.tgl || '-'),
    keterangan: String(r.keterangan || r.ket || ''),
    teks_bersih: r.teks_bersih ? String(r.teks_bersih) : undefined,
    kategori_nlp: r.kategori_nlp ? String(r.kategori_nlp) : undefined,
    jenis,
    debit,
    kredit,
    saldo,
    mutasi: mutasi || debit || kredit,
    kode_akun: String(r.kode_akun || r.akun || 'NOT_FOUND'),
    nama_akun: String(r.nama_akun || r.nama || '-'),
    kandidat_kode_akun: r.kandidat_kode_akun ? String(r.kandidat_kode_akun) : undefined,
    kandidat_nama_akun: r.kandidat_nama_akun ? String(r.kandidat_nama_akun) : undefined,
    status: mapStatus(String(r.status || '')),
    metode: String(r.metode || '-'),
    conf,
    confidence_tinggi,
    threshold,
    pool: r.pool ? String(r.pool) : undefined,
    nama_pihak: r.nama_pihak as string | undefined,
    invoice_no: r.invoice_no as string | undefined,
    invoice_status: r.invoice_status as string | undefined,
  }
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; icon: typeof CheckCircle2; bg: string; text: string; border: string }> = {
    auto_match: { label: 'Auto Match', icon: CheckCircle2, bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
    suggestion: { label: 'Suggestion', icon: AlertTriangle, bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
    not_found: { label: 'Not Found', icon: XCircle, bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
    confirmed: { label: 'Dikonfirmasi', icon: ThumbsUp, bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
    rejected: { label: 'Dikoreksi', icon: ThumbsDown, bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200' },
  }
  const c = config[status] || config.not_found
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full border whitespace-nowrap ${c.bg} ${c.text} ${c.border}`}>
      <c.icon size={13} />
      {c.label}
    </span>
  )
}

function ConfidenceBadge({ conf, threshold = NLP_THRESHOLD }: { conf: number; threshold?: number }) {
  const isHigh = conf >= threshold
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-mono font-semibold rounded-md border ${
        isHigh
          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
          : 'bg-amber-50 text-amber-700 border-amber-200'
      }`}
      title={isHigh ? `Confidence >= ${threshold} (Valid)` : `Confidence < ${threshold} (Ragu-ragu / Perlu Review)`}
    >
      {conf.toFixed(2)} {isHigh ? '≥ 0.72' : '< 0.72'}
    </span>
  )
}

type StepKey = 'upload' | 'processing' | 'preview_nlp' | 'result'

function StepIndicator({ currentStep }: { currentStep: StepKey }) {
  const steps = [
    { key: 'upload' as const, label: '1. Upload PDF', icon: Upload },
    { key: 'preview_nlp' as const, label: '2. Ekstraksi Tabel & Skor NLP', icon: Brain },
    { key: 'result' as const, label: '3. Forward Chaining ERP (3 Status)', icon: Database },
  ]
  const currentIdx =
    currentStep === 'upload' ? 0 :
    currentStep === 'processing' || currentStep === 'preview_nlp' ? 1 :
    2

  return (
    <div className="flex items-center justify-center gap-2 py-3">
      {steps.map((s, i) => (
        <div key={s.key} className="flex items-center gap-2">
          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-300 ${
            i === currentIdx
              ? 'bg-blue-600 text-white shadow-md shadow-blue-200'
              : i < currentIdx
                ? 'bg-blue-100 text-blue-700'
                : 'bg-gray-100 text-gray-400'
          }`}>
            <s.icon size={14} />
            <span className="hidden md:inline">{s.label}</span>
          </div>
          {i < steps.length - 1 && (
            <ArrowRight size={14} className={i < currentIdx ? 'text-blue-400' : 'text-gray-300'} />
          )}
        </div>
      ))}
    </div>
  )
}

// ---- Modal Validasi Suggestion & Pencocokan Manual ERP (Not Found) ----
function ActionModal({
  isOpen,
  mode,
  transaction,
  coaList,
  onClose,
  onSubmit,
}: {
  isOpen: boolean
  mode: 'konfirmasi' | 'tolak'
  transaction: TransactionResult | null
  coaList: CoaItem[]
  onClose: () => void
  onSubmit: (kodeAkunBaru?: string, catatan?: string) => void
}) {
  const [kodeAkunBaru, setKodeAkunBaru] = useState('')
  const [searchCoa, setSearchCoa] = useState('')
  const [catatan, setCatatan] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isOpen && transaction) {
      const initialCode =
        transaction.kode_akun && transaction.kode_akun !== 'NOT_FOUND' && transaction.kode_akun !== 'UNKNOWN' && transaction.kode_akun !== 'PERLU_REVIEW'
          ? transaction.kode_akun
          : ''
      setKodeAkunBaru(mode === 'konfirmasi' ? initialCode : '')
      setSearchCoa('')
      setCatatan('')
    }
  }, [isOpen, transaction, mode])

  if (!isOpen || !transaction) return null

  const isNotFound = transaction.status === 'not_found'
  const isKonfirmasi = mode === 'konfirmasi'

  const filteredCoa = coaList.filter(item => {
    if (!searchCoa.trim()) return true
    const q = searchCoa.toLowerCase()
    return item.kode.toLowerCase().includes(q) || item.nama.toLowerCase().includes(q)
  })

  const handleSubmit = async () => {
    setLoading(true)
    await onSubmit(kodeAkunBaru || undefined, catatan || undefined)
    setLoading(false)
  }

  // Untuk transaksi Not Found atau mode Tolak/Koreksi, user wajib memilih kode akun ERP
  const requireAccountSelection = isNotFound || !isKonfirmasi

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`px-6 py-4 flex items-center gap-3 ${
          isNotFound
            ? 'bg-indigo-50 border-b border-indigo-100'
            : isKonfirmasi
              ? 'bg-emerald-50 border-b border-emerald-100'
              : 'bg-amber-50 border-b border-amber-100'
        }`}>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isNotFound
              ? 'bg-indigo-100 text-indigo-600'
              : isKonfirmasi
                ? 'bg-emerald-100 text-emerald-600'
                : 'bg-amber-100 text-amber-600'
          }`}>
            {isNotFound ? <Search size={20} /> : isKonfirmasi ? <Check size={20} /> : <Pencil size={20} />}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">
              {isNotFound
                ? 'Pencocokan Manual ke Sistem ERP (Not Found)'
                : isKonfirmasi
                  ? 'Validasi & Konfirmasi Suggestion KB'
                  : 'Koreksi Pemetaan Akun ERP'}
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {isNotFound
                ? 'Cari dan pasangkan output transaksi ini dengan akun Chart of Accounts (CoA) ERP perusahaan'
                : isKonfirmasi
                  ? 'Setujui kandidat akun hasil Forward Chaining KB atau sesuaikan dengan akun ERP'
                  : 'Pilih akun ERP yang tepat untuk memperbarui Knowledge Base (Feedback Loop)'}
            </p>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {/* Ringkasan Fakta Transaksi & Output NLP */}
          <div className="bg-slate-50 rounded-xl p-4 space-y-2 border border-slate-200/70">
            <div className="flex justify-between text-xs gap-4">
              <span className="text-gray-500 shrink-0">Keterangan Rekening Koran</span>
              <span className="font-mono font-medium text-gray-900 text-right">{transaction.keterangan}</span>
            </div>
            {transaction.teks_bersih && (
              <div className="flex justify-between text-xs gap-4">
                <span className="text-gray-500 shrink-0">Teks Bersih Kamus NLP</span>
                <span className="font-mono text-indigo-700 text-right">{transaction.teks_bersih}</span>
              </div>
            )}
            <div className="flex justify-between items-center text-xs">
              <span className="text-gray-500">Confidence Score NLP</span>
              <div className="flex items-center gap-2">
                {transaction.kategori_nlp && (
                  <span className="text-[11px] px-2 py-0.5 bg-purple-50 text-purple-700 rounded border border-purple-200 font-medium">
                    NLP: {transaction.kategori_nlp}
                  </span>
                )}
                <ConfidenceBadge conf={transaction.conf} threshold={transaction.threshold} />
              </div>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Nominal ({transaction.jenis === 'CR' ? 'Kredit / Masuk' : 'Debit / Keluar'})</span>
              <span className={`font-mono font-semibold ${transaction.jenis === 'CR' ? 'text-emerald-600' : 'text-red-600'}`}>
                Rp {formatCurrency(transaction.mutasi)}
              </span>
            </div>
            <div className="flex justify-between text-xs pt-1 border-t border-slate-200/70">
              <span className="text-gray-500">Hasil Forward Chaining KB</span>
              <span className="font-semibold text-gray-900 text-right">{transaction.nama_akun}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Metode Pelacakan</span>
              <span className="text-gray-600 text-right">{transaction.metode}</span>
            </div>
            {transaction.invoice_no && (
              <div className="flex justify-between text-xs pt-1 border-t border-slate-200/70">
                <span className="text-emerald-600 font-medium">Faktur ERP Terkait</span>
                <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  🧾 {transaction.invoice_no} (Lunas)
                </span>
              </div>
            )}
          </div>

          {/* Pencarian & Pemilihan Akun CoA Sistem ERP */}
          <div>
            <label className="block text-xs font-semibold text-gray-800 mb-1.5">
              {requireAccountSelection
                ? 'Pilih / Cari Akun dari Sistem ERP Perusahaan (Wajib)'
                : 'Akun CoA ERP Terpilih (Dapat diubah jika perlu)'}
            </label>

            {/* Search box ERP */}
            <div className="relative mb-2">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchCoa}
                onChange={(e) => setSearchCoa(e.target.value)}
                placeholder="Cari kode atau nama akun di ERP (misal: Listrik, Gaji, Sewa, Payable, 6.2...)"
                className="w-full pl-9 pr-3 py-2 text-xs border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
              />
            </div>

            {/* Daftar Akun ERP */}
            <div className="border border-gray-200 rounded-xl max-h-40 overflow-y-auto divide-y divide-gray-100 bg-white">
              {filteredCoa.length > 0 ? (
                filteredCoa.map((item) => {
                  const selected = kodeAkunBaru === item.kode
                  return (
                    <button
                      key={item.kode}
                      type="button"
                      onClick={() => setKodeAkunBaru(item.kode)}
                      className={`w-full px-3 py-2 text-left text-xs flex items-center justify-between transition-colors ${
                        selected
                          ? 'bg-blue-50 text-blue-800 font-semibold'
                          : 'hover:bg-gray-50 text-gray-700'
                      }`}
                    >
                      <div>
                        <span className="font-mono font-semibold text-blue-700 mr-2">{item.kode}</span>
                        <span>{item.nama}</span>
                      </div>
                      {selected && <Check size={14} className="text-blue-600 shrink-0" />}
                    </button>
                  )
                })
              ) : (
                <div className="p-3 text-center text-xs text-gray-400">
                  Tidak ada akun ERP yang cocok dengan kata kunci "{searchCoa}"
                </div>
              )}
            </div>

            {/* Input manual / kode terpilih */}
            <div className="mt-2 flex items-center gap-2">
              <span className="text-xs text-gray-500 shrink-0">Kode Akun ERP:</span>
              <input
                type="text"
                value={kodeAkunBaru}
                onChange={(e) => setKodeAkunBaru(e.target.value)}
                placeholder="Pilih dari daftar di atas atau ketik kode akun (cth: 6.2.05.01)"
                className="flex-1 px-3 py-1.5 text-xs font-mono border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Catatan Audit / Referensi Rekening Koran (opsional)</label>
            <textarea
              value={catatan}
              onChange={(e) => setCatatan(e.target.value)}
              placeholder="Catatan verifikasi manual..."
              rows={2}
              className="w-full px-3 py-2 text-xs border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-200/60 rounded-lg transition-all"
          >
            Batal
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || (requireAccountSelection && !kodeAkunBaru.trim())}
            className={`px-5 py-2 text-xs font-semibold text-white rounded-lg transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
              isNotFound
                ? 'bg-indigo-600 hover:bg-indigo-700'
                : isKonfirmasi
                  ? 'bg-emerald-600 hover:bg-emerald-700'
                  : 'bg-amber-600 hover:bg-amber-700'
            }`}
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {isNotFound
              ? 'Simpan Pencocokan ke ERP'
              : isKonfirmasi
                ? 'Validasi & Konfirmasi'
                : 'Simpan Koreksi'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}


// ---- Page 1: Upload PDF ----

function UploadPage({
  onProcess,
  onDemo,
  errorMsg,
}: {
  onProcess: (file: File) => void
  onDemo: () => void
  errorMsg: string | null
}) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileName, setFileName] = useState('')
  const [dragActive, setDragActive] = useState(false)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setFileName(file.name)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file)
      setFileName(file.name)
    }
  }

  return (
    <motion.div
      key="upload"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
      className="max-w-2xl mx-auto"
    >
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload PDF Rekening Koran</h2>
        <p className="text-gray-500 text-sm">
          Ekstraksi tabel standar (Tanggal, Keterangan, Debit, Kredit, Saldo), kalkulasi Confidence Score NLP (0,72), dan pencocokan Forward Chaining ke ERP
        </p>
      </div>

      {errorMsg && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3 shadow-sm"
        >
          <AlertCircle size={20} className="text-amber-600 shrink-0 mt-0.5" />
          <div className="text-sm text-amber-800">
            <p className="font-semibold">Perhatian</p>
            <p className="mt-0.5">{errorMsg}</p>
          </div>
        </motion.div>
      )}

      <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xl shadow-gray-100/50 p-8">
        <label
          className={`flex flex-col items-center justify-center w-full h-56 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-300 ${
            dragActive
              ? 'border-blue-500 bg-blue-50 scale-[1.02]'
              : fileName
                ? 'border-emerald-300 bg-emerald-50/50'
                : 'border-gray-200 hover:border-blue-400 hover:bg-blue-50/30'
          }`}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
        >
          <div className="flex flex-col items-center">
            {fileName ? (
              <motion.div
                initial={{ scale: 0.8 }}
                animate={{ scale: 1 }}
                className="flex flex-col items-center"
              >
                <div className="w-14 h-14 bg-emerald-100 rounded-2xl flex items-center justify-center mb-3 shadow-sm">
                  <FileText size={28} className="text-emerald-600" />
                </div>
                <p className="text-sm font-semibold text-emerald-700">{fileName}</p>
                <p className="text-xs text-emerald-500 mt-1">File siap diekstraksi oleh Modul Tabel & NLP</p>
              </motion.div>
            ) : (
              <>
                <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center mb-3">
                  <Upload size={28} className="text-gray-400" />
                </div>
                <p className="text-sm font-medium text-gray-700">
                  Drag & drop file PDF rekening koran di sini
                </p>
                <p className="text-xs text-gray-400 mt-1">atau klik untuk memilih file PDF</p>
              </>
            )}
          </div>
          <input type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
        </label>

        <div className="mt-6 space-y-3">
          <motion.button
            onClick={() => selectedFile && onProcess(selectedFile)}
            disabled={!selectedFile}
            whileHover={selectedFile ? { scale: 1.01 } : {}}
            whileTap={selectedFile ? { scale: 0.99 } : {}}
            className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-semibold rounded-xl hover:shadow-lg hover:shadow-blue-200/50 disabled:from-gray-200 disabled:to-gray-300 disabled:text-gray-400 disabled:shadow-none disabled:cursor-not-allowed transition-all duration-300 flex items-center justify-center gap-2"
          >
            <FileText size={18} />
            Ekstrak Tabel & Hitung Skor NLP
          </motion.button>

          <div className="relative flex items-center gap-3">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-gray-400 font-medium">atau</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          <motion.button
            onClick={onDemo}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.99 }}
            className="w-full py-3 bg-white border-2 border-dashed border-indigo-300 text-indigo-600 text-sm font-semibold rounded-xl hover:bg-indigo-50 hover:border-indigo-400 transition-all duration-300 flex items-center justify-center gap-2"
          >
            <Play size={16} />
            Coba Simulasi Data Rekening Koran (Demo Lengkap)
          </motion.button>
        </div>
      </div>

      {/* Pipeline Info */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { num: 1, icon: FileText, title: '1. Table Recognition (Arya)', desc: 'Ekstraksi kolom standar: Tanggal, Keterangan, Debit, Kredit, Saldo', color: 'blue' },
          { num: 2, icon: Brain, title: '2. Modul NLP (Abror)', desc: 'Normalisasi kamus CoA & evaluasi ambang Confidence Score 0,72', color: 'purple' },
          { num: 3, icon: Database, title: '3. Forward Chaining KB (Mario)', desc: 'Pencocokan ke sistem ERP menghasilkan Auto Match, Suggestion, & Not Found', color: 'emerald' },
        ].map((item, i) => (
          <motion.div
            key={item.num}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 * i, duration: 0.4 }}
            className="group bg-white rounded-xl border border-gray-200/80 p-5 hover:shadow-lg hover:shadow-gray-100/80 hover:-translate-y-0.5 transition-all duration-300"
          >
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-3 ${
              item.color === 'blue' ? 'bg-blue-100 text-blue-600' :
              item.color === 'purple' ? 'bg-purple-100 text-purple-600' :
              'bg-emerald-100 text-emerald-600'
            }`}>
              <item.icon size={20} />
            </div>
            <p className="text-sm font-semibold text-gray-900">{item.title}</p>
            <p className="text-xs text-gray-500 mt-1">{item.desc}</p>
          </motion.div>
        ))}
      </div>
    </motion.div>
  )
}

function ProcessingPage({ fileName, stageText }: { fileName: string; stageText?: string }) {
  return (
    <motion.div
      key="processing"
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3 }}
      className="max-w-md mx-auto text-center py-24"
    >
      <div className="relative w-20 h-20 mx-auto mb-8">
        <motion.div
          className="absolute inset-0 rounded-full border-4 border-blue-100"
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
        <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-600 animate-spin" />
        <div className="absolute inset-3 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-full flex items-center justify-center shadow-md">
          <Zap size={24} className="text-white" />
        </div>
      </div>
      <h2 className="text-xl font-bold text-gray-900 mb-2">{stageText || 'Memproses Dokumen Rekening Koran'}</h2>
      <p className="text-sm text-gray-500 mb-6 font-medium">{fileName}</p>
      <div className="flex items-center justify-center gap-6 text-xs text-gray-400">
        <span className="flex items-center gap-1 font-medium"><FileText size={14} /> Ekstraksi Tabel</span>
        <ArrowRight size={12} />
        <span className="flex items-center gap-1 font-medium"><Brain size={14} /> Skor NLP (0,72)</span>
        <ArrowRight size={12} />
        <span className="flex items-center gap-1 font-medium"><Database size={14} /> Forward Chaining KB</span>
      </div>
    </motion.div>
  )
}

// ---- Page 2: Preview Hasil Ekstraksi Tabel & Confidence Score NLP + Tombol "Lanjutkan" ----

function NlpPreviewPage({
  results,
  fileName,
  onUpdateKeterangan,
  onContinueToErp,
  isReprocessing,
}: {
  results: TransactionResult[]
  fileName: string
  onUpdateKeterangan: (id: string, newKet: string) => void
  onContinueToErp: () => void
  isReprocessing: boolean
}) {
  const navigate = useNavigate()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editValue, setEditValue] = useState('')

  useEffect(() => {
    if (results.length === 0) {
      navigate('/', { replace: true })
    }
  }, [results, navigate])

  const highConfCount = results.filter(r => r.conf >= NLP_THRESHOLD).length
  const lowConfCount = results.length - highConfCount

  const startEdit = (row: TransactionResult) => {
    setEditingId(row.id)
    setEditValue(row.keterangan)
  }

  const saveEdit = (id: string) => {
    if (editValue.trim()) {
      onUpdateKeterangan(id, editValue.trim())
    }
    setEditingId(null)
  }

  return (
    <motion.div
      key="preview_nlp"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      {/* Notification Banner + Tombol Lanjutkan */}
      <div className="mb-6 bg-gradient-to-r from-blue-600 to-indigo-700 rounded-2xl p-6 text-white shadow-xl shadow-blue-200/50 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/15 text-xs font-semibold backdrop-blur-sm">
            <Brain size={14} />
            Tahap 1 & 2 Selesai: Ekstraksi Tabel (Arya) & Confidence Score NLP (Abror)
          </div>
          <h2 className="text-xl font-bold pt-1">
            {results.length} Baris Transaksi Berhasil Diekstrak dari {fileName}
          </h2>
          <p className="text-xs text-blue-100 max-w-2xl">
            Terdapat <strong>{highConfCount} transaksi</strong> dengan Confidence Score <strong>≥ 0,72</strong> (JSON bersih sesuai kamus) dan{' '}
            <strong>{lowConfCount} transaksi</strong> dengan skor <strong>&lt; 0,72</strong>. Klik tombol <strong>Lanjutkan</strong> untuk menjalankan{' '}
            <strong>Forward Chaining (Modul KB Mario)</strong> ke database ERP perusahaan.
          </p>
        </div>

        <button
          onClick={onContinueToErp}
          disabled={isReprocessing}
          className="shrink-0 px-6 py-3.5 bg-white text-blue-700 hover:bg-blue-50 font-bold text-sm rounded-xl shadow-lg transition-all flex items-center gap-2 cursor-pointer disabled:opacity-60"
        >
          {isReprocessing ? (
            <>
              <Loader2 size={18} className="animate-spin" />
              Menjalankan Forward Chaining...
            </>
          ) : (
            <>
              <span>Lanjutkan ke Pencocokan ERP</span>
              <ArrowRight size={18} />
            </>
          )}
        </button>
      </div>

      {/* Ringkasan Threshold NLP 0.72 */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200/80 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-500 font-medium">Total Baris Tabel Standar</p>
            <p className="text-2xl font-bold text-gray-900 mt-0.5">{results.length}</p>
            <p className="text-[11px] text-gray-400 mt-0.5">Tanggal, Keterangan, Debit, Kredit, Saldo</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <FileText size={20} />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-emerald-200/80 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-emerald-700 font-semibold">Confidence NLP ≥ 0,72 (Valid)</p>
            <p className="text-2xl font-bold text-emerald-700 mt-0.5">{highConfCount}</p>
            <p className="text-[11px] text-gray-500 mt-0.5">Siap dicocokkan otomatis ke ERP (Auto Match / Not Found)</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <CheckCircle2 size={20} />
          </div>
        </div>

        <div className="bg-white rounded-xl border border-amber-200/80 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-amber-700 font-semibold">Confidence NLP &lt; 0,72 (Ragu-ragu)</p>
            <p className="text-2xl font-bold text-amber-700 mt-0.5">{lowConfCount}</p>
            <p className="text-[11px] text-gray-500 mt-0.5">Akan ditelusuri dengan Forward Chaining KB (Suggestion / Not Found)</p>
          </div>
          <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-600 flex items-center justify-center">
            <AlertTriangle size={20} />
          </div>
        </div>
      </div>

      {/* Tabel 5 Kolom Standar + Skor NLP */}
      <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xl shadow-gray-100/50 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">
              Tabel Hasil Ekstraksi Rekening Koran & Analisis Confidence Score NLP
            </h3>
            <p className="text-xs text-gray-400">
              Anda dapat meninjau atau memperbaiki teks deskripsi mengacu pada rekening koran asli sebelum melanjutkan ke Forward Chaining ERP
            </p>
          </div>
          <span className="text-xs font-medium text-indigo-600 bg-indigo-50 px-3 py-1 rounded-full">
            Ambang Batas (Threshold): 0,72
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50/80">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tanggal</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Keterangan</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Debit</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Kredit</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Saldo</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Prediksi Kategori NLP</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Confidence NLP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {results.map((row) => (
                <tr key={row.id} className={row.conf < NLP_THRESHOLD ? 'bg-amber-50/20 hover:bg-amber-50/40' : 'hover:bg-blue-50/20'}>
                  <td className="px-4 py-3 text-xs text-gray-600 whitespace-nowrap font-mono">{row.tanggal}</td>
                  <td className="px-4 py-3 max-w-[340px]">
                    {editingId === row.id ? (
                      <div className="flex items-center gap-1.5">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="w-full px-2.5 py-1 text-xs font-mono border border-blue-400 rounded-lg focus:outline-none"
                          autoFocus
                        />
                        <button
                          onClick={() => saveEdit(row.id)}
                          className="p-1 bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
                          title="Simpan"
                        >
                          <Check size={14} />
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="p-1 bg-gray-200 text-gray-600 rounded-md hover:bg-gray-300"
                          title="Batal"
                        >
                          <X size={14} />
                        </button>
                      </div>
                    ) : (
                      <div className="group flex items-start justify-between gap-2">
                        <div>
                          <div className="font-mono text-xs text-gray-900">{row.keterangan}</div>
                          {row.teks_bersih && (
                            <div className="text-[11px] text-gray-400 mt-0.5">
                              Kamus: <span className="font-mono text-gray-600">{row.teks_bersih}</span>
                            </div>
                          )}
                        </div>
                        <button
                          onClick={() => startEdit(row)}
                          className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-blue-600 rounded transition-opacity shrink-0"
                          title="Koreksi teks keterangan mengacu Rekening Koran asli"
                        >
                          <Pencil size={13} />
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs whitespace-nowrap text-red-600">
                    {row.debit > 0 ? formatCurrency(row.debit) : '-'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs whitespace-nowrap text-emerald-600">
                    {row.kredit > 0 ? formatCurrency(row.kredit) : '-'}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-xs whitespace-nowrap text-gray-700">
                    {row.saldo > 0 ? formatCurrency(row.saldo) : '-'}
                  </td>
                  <td className="px-4 py-3 text-xs">
                    <span className="px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200/70 font-medium text-[11px]">
                      {row.kategori_nlp || '-'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center whitespace-nowrap">
                    <ConfidenceBadge conf={row.conf} threshold={row.threshold} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  )
}

// ---- Page 3: Dashboard Hasil Pencocokan Forward Chaining ERP (3 Status: Auto Match, Suggestion, Not Found) ----

function ResultPage({
  results,
  fileName,
  liveStats,
  onConfirm,
  onReject,
  onRefreshStats,
  onBackToPreview,
}: {
  results: TransactionResult[]
  fileName: string
  liveStats: Stats | null
  onConfirm: (trx: TransactionResult) => void
  onReject: (trx: TransactionResult) => void
  onRefreshStats: () => void
  onBackToPreview: () => void
}) {
  const navigate = useNavigate()
  const [filterStatus, setFilterStatus] = useState<'all' | 'auto_match' | 'suggestion' | 'not_found' | 'confirmed' | 'rejected'>('all')

  useEffect(() => {
    if (results.length === 0) {
      navigate('/', { replace: true })
      return
    }
    onRefreshStats()
  }, [])

  const localStats = {
    auto_match: results.filter(r => r.status === 'auto_match').length,
    suggestion: results.filter(r => r.status === 'suggestion').length,
    not_found: results.filter(r => r.status === 'not_found').length,
    confirmed: results.filter(r => r.status === 'confirmed').length,
    rejected: results.filter(r => r.status === 'rejected').length,
  }

  const coverageRatio = results.length > 0
    ? (localStats.auto_match + localStats.confirmed) / results.length
    : (liveStats?.coverage || 0)

  const filteredResults = filterStatus === 'all'
    ? results
    : results.filter(r => r.status === filterStatus)

  const canAct = (status: string) => !['confirmed', 'rejected'].includes(status)

  return (
    <motion.div
      key="result"
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3 }}
    >
      {/* Header + Stats */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Dashboard Rekonsiliasi ERP (Forward Chaining KB)</h2>
          <p className="text-sm text-gray-500 mt-1 flex flex-wrap items-center gap-2">
            <FileText size={14} />
            <span>{fileName}</span>
            <span className="text-gray-300">|</span>
            <Clock size={14} />
            <span>{results.length} transaksi</span>
            <span className="text-gray-300">|</span>
            <span className="font-semibold text-emerald-600">
              Coverage Tervalidasi: {(coverageRatio * 100).toFixed(1)}%
            </span>
          </p>
        </div>
        <button
          onClick={onBackToPreview}
          className="self-start sm:self-auto px-3.5 py-2 text-xs font-medium text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-xl transition-colors"
        >
          ← Lihat Tabel Ekstraksi & Skor NLP
        </button>
      </div>

      {/* 3 Main Status Cards + 2 Feedback Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        {[
          {
            key: 'auto_match' as const,
            label: 'Auto Match',
            sub: 'NLP ≥ 0,72 & Cocok di ERP',
            count: localStats.auto_match,
            color: 'emerald',
            icon: CheckCircle2,
          },
          {
            key: 'suggestion' as const,
            label: 'Suggestion',
            sub: 'NLP < 0,72 & Cocok via KB',
            count: localStats.suggestion,
            color: 'amber',
            icon: AlertTriangle,
          },
          {
            key: 'not_found' as const,
            label: 'Not Found',
            sub: 'Belum Ditemukan di ERP',
            count: localStats.not_found,
            color: 'red',
            icon: XCircle,
          },
          {
            key: 'confirmed' as const,
            label: 'Dikonfirmasi',
            sub: 'Validasi Manual Selesai',
            count: localStats.confirmed,
            color: 'blue',
            icon: ThumbsUp,
          },
          {
            key: 'rejected' as const,
            label: 'Dikoreksi',
            sub: 'Feedback Loop KB',
            count: localStats.rejected,
            color: 'gray',
            icon: ThumbsDown,
          },
        ].map((s, i) => {
          const active = filterStatus === s.key
          return (
            <motion.button
              key={s.key}
              type="button"
              onClick={() => setFilterStatus(active ? 'all' : s.key)}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.05 * i }}
              className={`text-left bg-white rounded-xl border p-4 transition-all cursor-pointer ${
                active ? 'ring-2 ring-blue-500 shadow-md' : 'hover:shadow-sm'
              } ${
                s.color === 'emerald' ? 'border-emerald-200/80' :
                s.color === 'amber' ? 'border-amber-200/80' :
                s.color === 'red' ? 'border-red-200/80' :
                s.color === 'blue' ? 'border-blue-200/80' :
                'border-gray-200/80'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${
                  s.color === 'emerald' ? 'bg-emerald-100 text-emerald-600' :
                  s.color === 'amber' ? 'bg-amber-100 text-amber-600' :
                  s.color === 'red' ? 'bg-red-100 text-red-600' :
                  s.color === 'blue' ? 'bg-blue-100 text-blue-600' :
                  'bg-gray-100 text-gray-500'
                }`}>
                  <s.icon size={16} />
                </div>
                <span className="text-xl font-bold text-gray-900">{s.count}</span>
              </div>
              <p className="text-xs font-bold text-gray-800">{s.label}</p>
              <p className="text-[10px] text-gray-400 mt-0.5">{s.sub}</p>
            </motion.button>
          )
        })}
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xl shadow-gray-100/50 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-gray-900">Detail Transaksi & Pemetaan CoA ERP</h3>
            {filterStatus !== 'all' && (
              <button
                onClick={() => setFilterStatus('all')}
                className="text-xs px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-600 hover:bg-blue-100 font-medium"
              >
                Reset Filter ({filteredResults.length}/{results.length}) ✕
              </button>
            )}
          </div>
          <span className="text-xs text-gray-400">Menampilkan {filteredResults.length} dari {results.length} baris transaksi</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50/80">
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tanggal</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Keterangan</th>
                <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Debit</th>
                <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Kredit</th>
                <th className="px-3 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Saldo</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Skor NLP</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Akun CoA ERP</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-3 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Metode Forward Chaining</th>
                <th className="px-3 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredResults.map((row, i) => (
                <motion.tr
                  key={row.id || i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.02 * Math.min(i, 20) }}
                  className={`transition-colors ${
                    row.status === 'confirmed' ? 'bg-emerald-50/30' :
                    row.status === 'rejected' ? 'bg-gray-50/50' :
                    row.status === 'not_found' ? 'bg-red-50/10 hover:bg-red-50/30' :
                    row.status === 'suggestion' ? 'bg-amber-50/10 hover:bg-amber-50/30' :
                    'hover:bg-blue-50/30'
                  }`}
                >
                  <td className="px-3 py-3 text-gray-500 whitespace-nowrap text-xs font-mono">{row.tanggal}</td>
                  <td className="px-3 py-3 max-w-[260px]">
                    <span className="font-mono text-xs text-gray-800 line-clamp-2">{row.keterangan}</span>
                    <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
                      {row.nama_pihak && (
                        <span className="text-[10px] text-indigo-600 font-medium">{row.nama_pihak}</span>
                      )}
                      {row.invoice_no && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          🧾 {row.invoice_no} (Lunas)
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right font-mono text-xs whitespace-nowrap text-red-600">
                    {row.debit > 0 ? formatCurrency(row.debit) : '-'}
                  </td>
                  <td className="px-3 py-3 text-right font-mono text-xs whitespace-nowrap text-emerald-600">
                    {row.kredit > 0 ? formatCurrency(row.kredit) : '-'}
                  </td>
                  <td className="px-3 py-3 text-right font-mono text-xs whitespace-nowrap text-gray-600">
                    {row.saldo > 0 ? formatCurrency(row.saldo) : '-'}
                  </td>
                  <td className="px-3 py-3 text-center whitespace-nowrap">
                    <ConfidenceBadge conf={row.conf} threshold={row.threshold} />
                  </td>
                  <td className="px-3 py-3">
                    {row.status === 'not_found' ? (
                      <div>
                        <div className="text-xs font-semibold text-red-600">Belum Ada di ERP</div>
                        <div className="text-[11px] text-gray-400">
                          {row.kategori_nlp ? `Prediksi NLP: ${row.kategori_nlp}` : 'Perlu pencocokan manual'}
                        </div>
                      </div>
                    ) : (
                      <div>
                        <div className="text-xs font-semibold text-gray-900 font-mono">{row.kode_akun}</div>
                        <div className="text-[11px] text-gray-500">{row.nama_akun}</div>
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3 text-center">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-3 py-3 text-xs text-gray-500 max-w-[190px] truncate" title={row.metode}>
                    {row.metode}
                  </td>
                  <td className="px-3 py-3 text-center whitespace-nowrap">
                    {canAct(row.status) ? (
                      row.status === 'not_found' ? (
                        <button
                          onClick={() => onConfirm(row)}
                          title="Cari & Cocokkan Manual dengan Sistem ERP"
                          className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200 transition-all inline-flex items-center gap-1"
                        >
                          <Search size={13} />
                          <span>Cocokkan ERP</span>
                        </button>
                      ) : (
                        <div className="flex items-center justify-center gap-1">
                          <button
                            onClick={() => onConfirm(row)}
                            title="Validasi / Konfirmasi"
                            className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700 transition-all"
                          >
                            <Check size={16} />
                          </button>
                          <button
                            onClick={() => onReject(row)}
                            title="Koreksi Akun ERP"
                            className="p-1.5 rounded-lg text-amber-600 hover:bg-amber-50 hover:text-amber-700 transition-all"
                          >
                            <Pencil size={16} />
                          </button>
                        </div>
                      )
                    ) : (
                      <span className="text-xs font-medium text-gray-400">
                        {row.status === 'confirmed' ? 'Tervalidasi' : 'Dikoreksi'}
                      </span>
                    )}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </motion.div>
  )
}


// ---- Main App ----

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [fileName, setFileName] = useState('')
  const [results, setResults] = useState<TransactionResult[]>([])
  const [coaList, setCoaList] = useState<CoaItem[]>([])
  const [hasEditedKeterangan, setHasEditedKeterangan] = useState(false)
  const [isReprocessing, setIsReprocessing] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [liveStats, setLiveStats] = useState<Stats | null>(null)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<'konfirmasi' | 'tolak'>('konfirmasi')
  const [modalTransaction, setModalTransaction] = useState<TransactionResult | null>(null)

  const currentStep: StepKey =
    location.pathname === '/proses' ? 'processing' :
    location.pathname === '/preview-nlp' ? 'preview_nlp' :
    location.pathname === '/hasil' ? 'result' :
    'upload'

  useEffect(() => {
    // Muat daftar CoA ERP saat aplikasi dibuka agar siap dipakai untuk pencocokan manual
    fetch(`${API_BASE}/coa`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && Array.isArray(data.coa)) {
          setCoaList(data.coa)
        }
      })
      .catch(() => {})
  }, [])

  const fetchStats = async () => {
    try {
      const resp = await fetch(`${API_BASE}/stats`)
      if (resp.ok) {
        const data = await resp.json()
        setLiveStats(data)
      }
    } catch {
      // Gunakan hitungan lokal jika gagal
    }
  }

  const handleProcess = async (file: File) => {
    setErrorMsg(null)
    setFileName(file.name)
    setHasEditedKeterangan(false)
    navigate('/proses')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const resp = await fetch(`${API_BASE}/reconcile-pdf`, {
        method: 'POST',
        body: formData,
      })

      if (!resp.ok) {
        const errorText = await resp.text()
        throw new Error(errorText || `Server error: ${resp.status}`)
      }

      const json = await resp.json()
      const items = json.hasil || json.data || []
      if (items.length > 0) {
        const mapped: TransactionResult[] = items.map((r: Record<string, unknown>) => mapRawToTransaction(r))
        setResults(mapped)
        navigate('/preview-nlp', { replace: true })
      } else {
        setErrorMsg(json.message || 'Tidak ada baris transaksi yang berhasil diekstrak dari PDF ini.')
        navigate('/', { replace: true })
      }
    } catch (err: unknown) {
      console.error('Error saat rekonsiliasi PDF:', err)
      const message = err instanceof Error ? err.message : 'Pastikan backend FastAPI sudah berjalan di port 8000.'
      setErrorMsg(`Gagal memproses file: ${message}`)
      navigate('/', { replace: true })
    }
  }

  const handleDemo = async () => {
    setErrorMsg(null)
    setFileName('Rekening_Koran_BCA_2023.pdf (Simulasi)')
    setHasEditedKeterangan(false)
    navigate('/proses')

    try {
      const resp = await fetch(`${API_BASE}/demo-data`)
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`)

      const json = await resp.json()
      const items = json.hasil || json.data || []
      if (items.length > 0) {
        const mapped: TransactionResult[] = items.map((r: Record<string, unknown>) => mapRawToTransaction(r))
        setResults(mapped)
        navigate('/preview-nlp', { replace: true })
      } else {
        setErrorMsg('Tidak ada data demo dari server. Pastikan backend berjalan.')
        navigate('/', { replace: true })
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Pastikan backend FastAPI sudah berjalan di port 8000.'
      setErrorMsg(`Gagal mengambil data demo: ${message}`)
      navigate('/', { replace: true })
    }
  }

  const handleUpdateKeterangan = (id: string, newKet: string) => {
    setHasEditedKeterangan(true)
    setResults(prev =>
      prev.map(r => (r.id === id ? { ...r, keterangan: newKet } : r))
    )
  }

  const handleContinueToErp = async () => {
    if (hasEditedKeterangan) {
      setIsReprocessing(true)
      try {
        const payload = {
          transaksi: results.map(r => ({
            tanggal: r.tanggal,
            keterangan: r.keterangan,
            jenis: r.jenis,
            debit: r.debit,
            kredit: r.kredit,
            saldo: r.saldo,
            mutasi: r.mutasi,
            sumber_file: fileName,
          })),
        }
        const resp = await fetch(`${API_BASE}/rekonsiliasi`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        })
        if (resp.ok) {
          const json = await resp.json()
          const items = json.hasil || json.data || []
          if (items.length > 0) {
            setResults(items.map((r: Record<string, unknown>) => mapRawToTransaction(r)))
          }
        }
      } catch (e) {
        console.error('Gagal memproses ulang:', e)
      } finally {
        setIsReprocessing(false)
        setHasEditedKeterangan(false)
      }
    }
    navigate('/hasil')
  }

  // ---- Aksi konfirmasi / pencocokan manual / koreksi ----
  const openModal = (mode: 'konfirmasi' | 'tolak', trx: TransactionResult) => {
    setModalMode(mode)
    setModalTransaction(trx)
    setModalOpen(true)
  }

  const handleAction = async (kodeAkunBaru?: string, catatan?: string) => {
    if (!modalTransaction) return

    const endpoint = modalMode === 'konfirmasi' ? 'konfirmasi' : 'tolak'
    try {
      const resp = await fetch(`${API_BASE}/transaksi/${modalTransaction.id}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kode_akun_baru: kodeAkunBaru,
          catatan,
          dikonfirmasi_oleh: 'user',
        }),
      })

      if (resp.ok) {
        const data = await resp.json()
        setResults(prev => prev.map(r => {
          if (r.id === modalTransaction.id) {
            return {
              ...r,
              status: data.status as TransactionResult['status'],
              kode_akun: data.kode_akun || kodeAkunBaru || r.kode_akun,
              nama_akun: data.nama_akun || r.nama_akun,
            }
          }
          return r
        }))
        fetchStats()
      }
    } catch (err) {
      console.error('Gagal:', err)
    }

    setModalOpen(false)
  }

  const handleReset = () => {
    setFileName('')
    setResults([])
    setErrorMsg(null)
    setLiveStats(null)
    setHasEditedKeterangan(false)
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-gray-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 shrink-0 cursor-pointer" onClick={handleReset}>
            <div className="w-9 h-9 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-200/50">
              <Database size={18} className="text-white" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg font-bold text-gray-900 tracking-tight">SiRekon</h1>
              <p className="text-[11px] text-gray-400 -mt-0.5">Rekonsiliasi Bank (Table Recognition + NLP + Forward Chaining KB)</p>
            </div>
          </div>
          <StepIndicator currentStep={currentStep} />
          <div className="flex items-center gap-3 shrink-0">
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 bg-slate-100 border border-slate-200/80 rounded-full text-xs font-medium text-slate-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <User size={13} className="text-slate-500" />
              <span>Staf Keuangan</span>
            </div>
            {(currentStep === 'result' || currentStep === 'preview_nlp') && (
              <button
                onClick={handleReset}
                className="px-4 py-2 rounded-lg text-xs font-semibold text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-all duration-200"
              >
                Upload PDF Baru
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={
              <UploadPage
                onProcess={handleProcess}
                onDemo={handleDemo}
                errorMsg={errorMsg}
              />
            } />
            <Route path="/proses" element={
              <ProcessingPage fileName={fileName} />
            } />
            <Route path="/preview-nlp" element={
              <NlpPreviewPage
                results={results}
                fileName={fileName}
                onUpdateKeterangan={handleUpdateKeterangan}
                onContinueToErp={handleContinueToErp}
                isReprocessing={isReprocessing}
              />
            } />
            <Route path="/hasil" element={
              <ResultPage
                results={results}
                fileName={fileName}
                liveStats={liveStats}
                onConfirm={(trx) => openModal('konfirmasi', trx)}
                onReject={(trx) => openModal('tolak', trx)}
                onRefreshStats={fetchStats}
                onBackToPreview={() => navigate('/preview-nlp')}
              />
            } />
          </Routes>
        </AnimatePresence>
      </main>

      {/* Modal */}
      <AnimatePresence>
        {modalOpen && (
          <ActionModal
            isOpen={modalOpen}
            mode={modalMode}
            transaction={modalTransaction}
            coaList={coaList}
            onClose={() => setModalOpen(false)}
            onSubmit={handleAction}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

export default App
