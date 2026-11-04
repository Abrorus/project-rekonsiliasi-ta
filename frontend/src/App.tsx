import { useState, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'motion/react'
import {
  Upload, FileText, Brain, Database, CheckCircle2, AlertTriangle,
  XCircle, ArrowRight, Loader2, BarChart3, Clock, Zap, AlertCircle,
  Check, X, Pencil, ThumbsUp, ThumbsDown, Play, User
} from 'lucide-react'

interface TransactionResult {
  id: string
  tanggal: string
  keterangan: string
  jenis: 'DB' | 'CR' | string
  mutasi: number
  kode_akun: string
  nama_akun: string
  status: 'auto_match' | 'suggestion' | 'manual' | 'confirmed' | 'rejected'
  metode: string
  nama_pihak?: string
  invoice_no?: string
  invoice_status?: string
}

interface Stats {
  total: number
  auto_match: number
  suggestion: number
  manual: number
  confirmed: number
  rejected: number
  coverage: number
}

const API_BASE = 'http://localhost:8000/api'

function formatCurrency(val: number) {
  return new Intl.NumberFormat('id-ID').format(val)
}

function mapStatus(s: string): TransactionResult['status'] {
  if (s === 'auto_match' || s === 'auto') return 'auto_match'
  if (s === 'suggestion' || s === 'review') return 'suggestion'
  if (s === 'confirmed') return 'confirmed'
  if (s === 'rejected') return 'rejected'
  return 'manual'
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; icon: typeof CheckCircle2; bg: string; text: string; border: string }> = {
    auto_match: { label: 'Auto Match', icon: CheckCircle2, bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
    suggestion: { label: 'Suggestion', icon: AlertTriangle, bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
    manual: { label: 'Manual', icon: XCircle, bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
    confirmed: { label: 'Dikonfirmasi', icon: ThumbsUp, bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200' },
    rejected: { label: 'Ditolak', icon: ThumbsDown, bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200' },
  }
  const c = config[status] || config.manual
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-full border ${c.bg} ${c.text} ${c.border}`}>
      <c.icon size={13} />
      {c.label}
    </span>
  )
}

type StepKey = 'upload' | 'processing' | 'result'

function StepIndicator({ currentStep }: { currentStep: StepKey }) {
  const steps = [
    { key: 'upload' as const, label: 'Upload PDF', icon: Upload },
    { key: 'processing' as const, label: 'Proses Rekonsiliasi', icon: Loader2 },
    { key: 'result' as const, label: 'Hasil Rekonsiliasi', icon: BarChart3 },
  ]
  const currentIdx = steps.findIndex(s => s.key === currentStep)

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
            <s.icon size={14} className={i === currentIdx && s.key === 'processing' ? 'animate-spin' : ''} />
            <span className="hidden sm:inline">{s.label}</span>
          </div>
          {i < steps.length - 1 && (
            <ArrowRight size={14} className={i < currentIdx ? 'text-blue-400' : 'text-gray-300'} />
          )}
        </div>
      ))}
    </div>
  )
}

// ---- Modal Konfirmasi/Tolak ----
function ActionModal({
  isOpen,
  mode,
  transaction,
  onClose,
  onSubmit,
}: {
  isOpen: boolean
  mode: 'konfirmasi' | 'tolak'
  transaction: TransactionResult | null
  onClose: () => void
  onSubmit: (kodeAkunBaru?: string, catatan?: string) => void
}) {
  const [kodeAkunBaru, setKodeAkunBaru] = useState('')
  const [catatan, setCatatan] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setKodeAkunBaru('')
      setCatatan('')
    }
  }, [isOpen])

  if (!isOpen || !transaction) return null

  const handleSubmit = async () => {
    setLoading(true)
    await onSubmit(kodeAkunBaru || undefined, catatan || undefined)
    setLoading(false)
  }

  const isKonfirmasi = mode === 'konfirmasi'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.95 }}
        className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={`px-6 py-4 flex items-center gap-3 ${
          isKonfirmasi ? 'bg-emerald-50 border-b border-emerald-100' : 'bg-red-50 border-b border-red-100'
        }`}>
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            isKonfirmasi ? 'bg-emerald-100 text-emerald-600' : 'bg-red-100 text-red-600'
          }`}>
            {isKonfirmasi ? <Check size={20} /> : <X size={20} />}
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">
              {isKonfirmasi ? 'Konfirmasi Rekomendasi' : 'Tolak Rekomendasi'}
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {isKonfirmasi ? 'Setujui pemetaan akun ini' : 'Tolak dan masukkan akun yang benar'}
            </p>
          </div>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          <div className="bg-gray-50 rounded-xl p-4 space-y-2">
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Keterangan</span>
              <span className="font-mono text-gray-800 text-right max-w-[250px] truncate">{transaction.keterangan}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Rekomendasi KB</span>
              <span className="font-semibold text-gray-900">{transaction.kode_akun}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Nama Akun</span>
              <span className="text-gray-700">{transaction.nama_akun}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-gray-500">Metode</span>
              <span className="text-gray-600">{transaction.metode}</span>
            </div>
            {transaction.invoice_no && (
              <div className="flex justify-between text-xs pt-1 border-t border-gray-200/60">
                <span className="text-emerald-600 font-medium">Faktur ERP Terkait</span>
                <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                  🧾 {transaction.invoice_no} (Lunas)
                </span>
              </div>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">
              {isKonfirmasi ? 'Kode Akun Koreksi (opsional)' : 'Kode Akun yang Benar'}
            </label>
            <input
              type="text"
              value={kodeAkunBaru}
              onChange={(e) => setKodeAkunBaru(e.target.value)}
              placeholder="Contoh: 6.2.05.01"
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
            />
            {isKonfirmasi && (
              <p className="text-[11px] text-gray-400 mt-1">Kosongkan jika rekomendasi sudah benar</p>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1.5">Catatan (opsional)</label>
            <textarea
              value={catatan}
              onChange={(e) => setCatatan(e.target.value)}
              placeholder="Alasan konfirmasi/tolak..."
              rows={2}
              className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-100 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-200/60 rounded-lg transition-all"
          >
            Batal
          </button>
          <button
            onClick={handleSubmit}
            disabled={loading || (!isKonfirmasi && !kodeAkunBaru)}
            className={`px-5 py-2 text-sm font-semibold text-white rounded-lg transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
              isKonfirmasi
                ? 'bg-emerald-600 hover:bg-emerald-700'
                : 'bg-red-600 hover:bg-red-700'
            }`}
          >
            {loading && <Loader2 size={14} className="animate-spin" />}
            {isKonfirmasi ? 'Konfirmasi' : 'Tolak & Simpan'}
          </button>
        </div>
      </motion.div>
    </div>
  )
}


// ---- Page Components ----

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
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Mutasi Rekening Bank</h2>
        <p className="text-gray-500">Masukkan file PDF mutasi rekening untuk diekstraksi dan direkonsiliasi otomatis</p>
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
                <p className="text-xs text-emerald-500 mt-1">File siap diproses oleh pipeline rekonsiliasi</p>
              </motion.div>
            ) : (
              <>
                <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center mb-3">
                  <Upload size={28} className="text-gray-400" />
                </div>
                <p className="text-sm font-medium text-gray-700">
                  Drag & drop file PDF mutasi di sini
                </p>
                <p className="text-xs text-gray-400 mt-1">atau klik untuk memilih file rekening koran PDF</p>
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
            Mulai Rekonsiliasi
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
            Coba Data Demo (tanpa upload PDF)
          </motion.button>
        </div>
      </div>

      {/* Pipeline Info */}
      <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { num: 1, icon: FileText, title: 'Modul Tabel', desc: 'Ekstraksi PDF mutasi bank ke tabular', color: 'blue' },
          { num: 2, icon: Brain, title: 'Modul NLP', desc: 'Normalisasi teks & klasifikasi ML SVM', color: 'purple' },
          { num: 3, icon: Database, title: 'Knowledge Base', desc: 'Decision Tree, Rekanan & mapping CoA', color: 'emerald' },
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

function ProcessingPage({ fileName }: { fileName: string }) {
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
      <h2 className="text-xl font-bold text-gray-900 mb-2">Memproses Rekonsiliasi</h2>
      <p className="text-sm text-gray-500 mb-6 font-medium">{fileName}</p>
      <div className="flex items-center justify-center gap-6 text-xs text-gray-400">
        <span className="flex items-center gap-1 font-medium"><FileText size={14} /> Ekstraksi Tabel</span>
        <ArrowRight size={12} />
        <span className="flex items-center gap-1 font-medium"><Brain size={14} /> Model NLP</span>
        <ArrowRight size={12} />
        <span className="flex items-center gap-1 font-medium"><Database size={14} /> Knowledge Base</span>
      </div>
    </motion.div>
  )
}

function ResultPage({
  results,
  fileName,
  liveStats,
  onConfirm,
  onReject,
  onRefreshStats,
}: {
  results: TransactionResult[]
  fileName: string
  liveStats: Stats | null
  onConfirm: (trx: TransactionResult) => void
  onReject: (trx: TransactionResult) => void
  onRefreshStats: () => void
}) {
  const navigate = useNavigate()

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
    manual: results.filter(r => r.status === 'manual').length,
    confirmed: results.filter(r => r.status === 'confirmed').length,
    rejected: results.filter(r => r.status === 'rejected').length,
  }

  const displayStats = liveStats || {
    total: results.length,
    ...localStats,
    coverage: results.length > 0
      ? (localStats.auto_match + localStats.confirmed) / results.length
      : 0,
  }

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
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Hasil Rekonsiliasi</h2>
          <p className="text-sm text-gray-500 mt-1 flex items-center gap-2">
            <FileText size={14} />
            {fileName}
            <span className="text-gray-300">|</span>
            <Clock size={14} />
            {results.length} transaksi diproses
            {displayStats.coverage > 0 && (
              <>
                <span className="text-gray-300">|</span>
                <span className="font-semibold text-emerald-600">Coverage: {(displayStats.coverage * 100).toFixed(1)}%</span>
              </>
            )}
          </p>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6">
        {[
          { label: 'Auto Match', count: displayStats.auto_match, color: 'emerald', icon: CheckCircle2 },
          { label: 'Suggestion', count: displayStats.suggestion, color: 'amber', icon: AlertTriangle },
          { label: 'Manual', count: displayStats.manual, color: 'red', icon: XCircle },
          { label: 'Dikonfirmasi', count: displayStats.confirmed, color: 'blue', icon: ThumbsUp },
          { label: 'Ditolak', count: displayStats.rejected, color: 'gray', icon: ThumbsDown },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 * i }}
            className={`bg-white rounded-xl border p-4 ${
              s.color === 'emerald' ? 'border-emerald-200/60' :
              s.color === 'amber' ? 'border-amber-200/60' :
              s.color === 'red' ? 'border-red-200/60' :
              s.color === 'blue' ? 'border-blue-200/60' :
              'border-gray-200/60'
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
            <p className="text-xs font-medium text-gray-500">{s.label}</p>
          </motion.div>
        ))}
      </div>

      {/* Table */}
      <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xl shadow-gray-100/50 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-900">Detail Transaksi & Pemetaan CoA</h3>
          <span className="text-xs text-gray-400">{results.length} baris transaksi</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50/80">
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tanggal</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Keterangan</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Mutasi</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Akun CoA</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Metode</th>
                <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {results.map((row, i) => (
                <motion.tr
                  key={row.id || i}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: 0.02 * Math.min(i, 20) }}
                  className={`transition-colors ${
                    row.status === 'confirmed' ? 'bg-emerald-50/30' :
                    row.status === 'rejected' ? 'bg-gray-50/50' :
                    'hover:bg-blue-50/30'
                  }`}
                >
                  <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-xs">{row.tanggal}</td>
                  <td className="px-4 py-3 max-w-[280px]">
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
                  <td className={`px-4 py-3 text-right font-mono text-xs whitespace-nowrap ${
                    row.jenis === 'CR' ? 'text-emerald-600' : 'text-red-600'
                  }`}>
                    {row.jenis === 'CR' ? '+' : '-'}{formatCurrency(row.mutasi)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-xs font-semibold text-gray-900">{row.kode_akun}</div>
                    <div className="text-[11px] text-gray-500">{row.nama_akun}</div>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 max-w-[200px] truncate">{row.metode}</td>
                  <td className="px-4 py-3 text-center">
                    {canAct(row.status) ? (
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={() => onConfirm(row)}
                          title="Konfirmasi"
                          className="p-1.5 rounded-lg text-emerald-600 hover:bg-emerald-50 hover:text-emerald-700 transition-all"
                        >
                          <Check size={16} />
                        </button>
                        <button
                          onClick={() => onReject(row)}
                          title="Tolak & Koreksi"
                          className="p-1.5 rounded-lg text-red-500 hover:bg-red-50 hover:text-red-600 transition-all"
                        >
                          <Pencil size={16} />
                        </button>
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">
                        {row.status === 'confirmed' ? 'OK' : 'Ditolak'}
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
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [liveStats, setLiveStats] = useState<Stats | null>(null)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [modalMode, setModalMode] = useState<'konfirmasi' | 'tolak'>('konfirmasi')
  const [modalTransaction, setModalTransaction] = useState<TransactionResult | null>(null)

  const currentStep: StepKey =
    location.pathname === '/proses' ? 'processing' :
    location.pathname === '/hasil' ? 'result' :
    'upload'

  const fetchStats = async () => {
    try {
      const resp = await fetch(`${API_BASE}/stats`)
      if (resp.ok) {
        const data = await resp.json()
        setLiveStats(data)
      }
    } catch {
      // Stats gagal load, pakai hitungan lokal
    }
  }

  const handleProcess = async (file: File) => {
    setErrorMsg(null)
    setFileName(file.name)
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
        const mapped: TransactionResult[] = items.map((r: Record<string, unknown>) => ({
          id: r.id || crypto.randomUUID(),
          tanggal: r.tanggal || r.tgl || '',
          keterangan: r.keterangan || r.ket || '',
          jenis: r.jenis || '',
          mutasi: Number(r.mutasi) || 0,
          kode_akun: r.kode_akun || r.akun || '',
          nama_akun: r.nama_akun || r.nama || '',
          status: mapStatus(String(r.status || '')),
          metode: r.metode || '',
          nama_pihak: r.nama_pihak as string | undefined,
          invoice_no: r.invoice_no as string | undefined,
          invoice_status: r.invoice_status as string | undefined,
        }))
        setResults(mapped)
        navigate('/hasil', { replace: true })
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
    setFileName('demo-data.pdf (simulasi)')
    navigate('/proses')

    try {
      const resp = await fetch(`${API_BASE}/demo-data`)
      if (!resp.ok) throw new Error(`Server error: ${resp.status}`)

      const json = await resp.json()
      const items = json.hasil || json.data || []
      if (items.length > 0) {
        const mapped: TransactionResult[] = items.map((r: Record<string, unknown>) => ({
          id: r.id || crypto.randomUUID(),
          tanggal: r.tanggal || r.tgl || '',
          keterangan: r.keterangan || r.ket || '',
          jenis: r.jenis || '',
          mutasi: Number(r.mutasi) || 0,
          kode_akun: r.kode_akun || r.akun || '',
          nama_akun: r.nama_akun || r.nama || '',
          status: mapStatus(String(r.status || '')),
          metode: r.metode || '',
          nama_pihak: r.nama_pihak as string | undefined,
          invoice_no: r.invoice_no as string | undefined,
          invoice_status: r.invoice_status as string | undefined,
        }))
        setResults(mapped)
        navigate('/hasil', { replace: true })
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

  // ---- Aksi konfirmasi/tolak ----
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
              kode_akun: data.kode_akun || r.kode_akun,
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
    navigate('/')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-white/80 backdrop-blur-xl border-b border-gray-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-9 h-9 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-200/50">
              <Database size={18} className="text-white" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg font-bold text-gray-900 tracking-tight">SiRekon</h1>
              <p className="text-[11px] text-gray-400 -mt-0.5">Sistem Rekonsiliasi Transaksi Bank (NLP + Knowledge Base)</p>
            </div>
          </div>
          <StepIndicator currentStep={currentStep} />
          <div className="flex items-center gap-3 shrink-0">
            <div className="hidden sm:flex items-center gap-1.5 px-3 py-1 bg-slate-100 border border-slate-200/80 rounded-full text-xs font-medium text-slate-700">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <User size={13} className="text-slate-500" />
              <span>User</span>
            </div>
            {currentStep === 'result' && (
              <button
                onClick={handleReset}
                className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-all duration-200"
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
            <Route path="/hasil" element={
              <ResultPage
                results={results}
                fileName={fileName}
                liveStats={liveStats}
                onConfirm={(trx) => openModal('konfirmasi', trx)}
                onReject={(trx) => openModal('tolak', trx)}
                onRefreshStats={fetchStats}
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
            onClose={() => setModalOpen(false)}
            onSubmit={handleAction}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

export default App
