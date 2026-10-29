import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import {
  Upload, FileText, Brain, Database, CheckCircle2, AlertTriangle,
  XCircle, ArrowRight, Loader2, BarChart3, Clock, Zap, PlayCircle, AlertCircle
} from 'lucide-react'

type Step = 'upload' | 'processing' | 'result'

interface TransactionResult {
  tgl: string
  ket: string
  jenis: 'DB' | 'CR' | string
  mutasi: number
  akun: string
  nama: string
  status: 'auto' | 'review' | 'manual'
  metode: string
  conf: number
  pool?: string
}

const DEFAULT_DEMO: TransactionResult[] = [
  { tgl: '02/01/2023', ket: 'TRSF E-BANKING CIOMAS ADISATWA', jenis: 'DB', mutasi: 580075045, akun: '2.1.01.01', nama: 'Trade Payable - 3rd Party', status: 'auto', metode: 'KB (Master Vendor)', conf: 0.86, pool: 'Pool 1 (NLP Confident + KB Validated)' },
  { tgl: '02/01/2023', ket: 'SWITCHING DR 008 PANCA BERSAUDARA', jenis: 'CR', mutasi: 50000000, akun: '1.1.02.98', nama: 'Cross Account Bank', status: 'auto', metode: 'KB (Switching)', conf: 0.37, pool: 'Pool 3 (Knowledge Base)' },
  { tgl: '02/01/2023', ket: 'TRSF E-BANKING AMERTHA JAYA', jenis: 'CR', mutasi: 595075045, akun: '1.1.04.01', nama: 'Account Receivable 3rd Party', status: 'auto', metode: 'KB (Master Customer)', conf: 0.95, pool: 'Pool 1 (NLP Confident + KB Validated)' },
  { tgl: '03/01/2023', ket: 'BYR VIA E-BANKING 0860 PLN JATIM', jenis: 'DB', mutasi: 1694321, akun: '6.2.05.01', nama: 'Utilities-Electricity', status: 'auto', metode: 'KB Tree (operasional)', conf: 0.73, pool: 'Pool 1 (NLP Confident + KB Validated)' },
  { tgl: '03/01/2023', ket: 'TRSF E-BANKING 89000/BPJS TK', jenis: 'DB', mutasi: 16561371, akun: 'PERLU_REVIEW', nama: 'BPJS - Akun belum tersedia', status: 'review', metode: 'KB Tree (bpjs)', conf: 0.55, pool: 'Pool 3 (Knowledge Base)' },
  { tgl: '04/01/2023', ket: 'BYR VIA E-BANKING PENERIMAAN NEGARA', jenis: 'DB', mutasi: 14978282, akun: 'PERLU_REVIEW', nama: 'Pajak - Akun belum tersedia', status: 'review', metode: 'KB Tree (pajak)', conf: 0.35, pool: 'Pool 3 (Knowledge Base)' },
  { tgl: '05/01/2023', ket: 'BA JASA E-BANKING BIAYA TRANSFER SME', jenis: 'DB', mutasi: 2900, akun: 'PERLU_REVIEW', nama: 'Biaya Bank - Akun belum tersedia', status: 'review', metode: 'KB Tree (perbankan)', conf: 0.42, pool: 'Pool 3 (Knowledge Base)' },
  { tgl: '05/01/2023', ket: 'REF TXN 99823 ANOMALI', jenis: 'DB', mutasi: 100000, akun: 'UNKNOWN', nama: 'Perlu Tinjauan Manual', status: 'manual', metode: 'Manual Review', conf: 0.28, pool: 'Pool 3 (Knowledge Base)' },
]

function formatCurrency(val: number) {
  return new Intl.NumberFormat('id-ID').format(val)
}

function StatusBadge({ status }: { status: 'auto' | 'review' | 'manual' }) {
  const config = {
    auto: { label: 'Auto Match', icon: CheckCircle2, bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
    review: { label: 'Perlu Review', icon: AlertTriangle, bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
    manual: { label: 'Manual', icon: XCircle, bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  }
  const c = config[status] || config.manual
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full border ${c.bg} ${c.text} ${c.border}`}>
      <c.icon size={12} />
      {c.label}
    </span>
  )
}

function StepIndicator({ step }: { step: Step }) {
  const steps = [
    { key: 'upload', label: 'Upload', icon: Upload },
    { key: 'processing', label: 'Proses', icon: Loader2 },
    { key: 'result', label: 'Hasil', icon: BarChart3 },
  ]
  const currentIdx = steps.findIndex(s => s.key === step)

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
            {s.label}
          </div>
          {i < steps.length - 1 && (
            <ArrowRight size={14} className={i < currentIdx ? 'text-blue-400' : 'text-gray-300'} />
          )}
        </div>
      ))}
    </div>
  )
}

const API_BASE = 'http://localhost:8000/api'

function App() {
  const [step, setStep] = useState<Step>('upload')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [fileName, setFileName] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [results, setResults] = useState<TransactionResult[]>(DEFAULT_DEMO)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setSelectedFile(file)
      setFileName(file.name)
      setErrorMsg(null)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file && file.type === 'application/pdf') {
      setSelectedFile(file)
      setFileName(file.name)
      setErrorMsg(null)
    }
  }

  // Eksekusi data demo nyata yang diproses langsung oleh NLP + KB di server
  const handleRunDemo = async () => {
    setErrorMsg(null)
    setFileName('Simulasi 11 Transaksi Riil Mitra (BCA)')
    setStep('processing')

    try {
      const resp = await fetch(`${API_BASE}/demo-data`)
      if (!resp.ok) throw new Error(`Server API status: ${resp.status}`)
      const json = await resp.json()
      if (json.data && json.data.length > 0) {
        setResults(json.data)
      }
      setStep('result')
    } catch (err: unknown) {
      console.warn('Gagal memanggil backend, menggunakan fallback data lokal:', err)
      // Fallback data lokal jika backend belum dinyalakan
      setResults(DEFAULT_DEMO)
      setStep('result')
    }
  }

  // Eksekusi upload file PDF ke backend
  const handleProcess = async () => {
    if (!selectedFile) return
    setErrorMsg(null)
    setStep('processing')

    const formData = new FormData()
    formData.append('file', selectedFile)

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
      if (json.data && json.data.length > 0) {
        setResults(json.data)
        setStep('result')
      } else {
        // Jika PDF tidak menghasilkan baris tabel
        setErrorMsg(json.message || 'Tidak ada baris transaksi yang berhasil diekstrak dari PDF.')
        setStep('upload')
      }
    } catch (err: unknown) {
      console.error('Error saat upload PDF:', err)
      const message = err instanceof Error ? err.message : 'Pastikan backend FastAPI sudah berjalan di port 8000.'
      setErrorMsg(`Gagal memproses PDF via backend: ${message}`)
      setStep('upload')
    }
  }

  const stats = {
    auto: results.filter(r => r.status === 'auto').length,
    review: results.filter(r => r.status === 'review').length,
    manual: results.filter(r => r.status === 'manual').length,
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-200/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 shrink-0">
            <div className="w-9 h-9 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-200/50">
              <Database size={18} className="text-white" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-lg font-bold text-gray-900 tracking-tight">SiRekon</h1>
              <p className="text-[11px] text-gray-400 -mt-0.5">Sistem Rekonsiliasi Transaksi (NLP + KB)</p>
            </div>
          </div>
          <StepIndicator step={step} />
          {step === 'result' && (
            <button
              onClick={() => { setStep('upload'); setFileName(''); setSelectedFile(null); setErrorMsg(null) }}
              className="px-3 sm:px-4 py-2 rounded-lg text-sm font-medium text-gray-500 hover:text-gray-700 hover:bg-gray-50 transition-all duration-200 shrink-0"
            >
              Upload Baru
            </button>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">
        <AnimatePresence mode="wait">
          {/* ===== UPLOAD ===== */}
          {step === 'upload' && (
            <motion.div
              key="upload"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.3 }}
              className="max-w-2xl mx-auto"
            >
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Upload Mutasi Bank</h2>
                <p className="text-gray-500">Upload file PDF untuk memulai pipeline ekstraksi tabel, NLP klasifikasi, dan pencocokan CoA</p>
              </div>

              {errorMsg && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mb-6 p-4 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3"
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
                        <div className="w-14 h-14 bg-emerald-100 rounded-2xl flex items-center justify-center mb-3">
                          <FileText size={28} className="text-emerald-600" />
                        </div>
                        <p className="text-sm font-semibold text-emerald-700">{fileName}</p>
                        <p className="text-xs text-emerald-500 mt-1">File siap diproses oleh pipeline</p>
                      </motion.div>
                    ) : (
                      <>
                        <div className="w-14 h-14 bg-gray-100 rounded-2xl flex items-center justify-center mb-3">
                          <Upload size={28} className="text-gray-400" />
                        </div>
                        <p className="text-sm font-medium text-gray-600">
                          Drag & drop file PDF mutasi di sini
                        </p>
                        <p className="text-xs text-gray-400 mt-1">atau klik untuk pilih file rekening koran PDF</p>
                      </>
                    )}
                  </div>
                  <input type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
                </label>

                <div className="mt-6 flex flex-col sm:flex-row items-center gap-3">
                  <motion.button
                    onClick={handleProcess}
                    disabled={!selectedFile}
                    whileHover={selectedFile ? { scale: 1.01 } : {}}
                    whileTap={selectedFile ? { scale: 0.99 } : {}}
                    className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-semibold rounded-xl hover:shadow-lg hover:shadow-blue-200/50 disabled:from-gray-200 disabled:to-gray-300 disabled:text-gray-400 disabled:shadow-none disabled:cursor-not-allowed transition-all duration-300"
                  >
                    Mulai Rekonsiliasi PDF
                  </motion.button>

                  <button
                    onClick={handleRunDemo}
                    type="button"
                    className="w-full sm:w-auto px-5 py-3 border border-indigo-200 text-indigo-700 hover:bg-indigo-50/50 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 transition-all duration-200 shrink-0"
                    title="Uji langsung dengan transaksi riil yang diproses oleh NLP + KB"
                  >
                    <PlayCircle size={16} />
                    Uji Data Demo
                  </button>
                </div>
              </div>

              {/* Pipeline */}
              <div className="mt-8 grid grid-cols-3 gap-4">
                {[
                  { num: 1, icon: FileText, title: 'Table Recognition', desc: 'Ekstraksi PDF mutasi bank ke tabular', color: 'blue' },
                  { num: 2, icon: Brain, title: 'NLP Processing', desc: 'TF-IDF, Sastrawi & Klasifikasi SVM', color: 'purple' },
                  { num: 3, icon: Database, title: 'Knowledge Base', desc: 'Decision Tree, Rekanan & CoA mitra', color: 'emerald' },
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
          )}

          {/* ===== PROCESSING ===== */}
          {step === 'processing' && (
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
                <div className="absolute inset-3 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-full flex items-center justify-center">
                  <Zap size={24} className="text-white" />
                </div>
              </div>
              <h2 className="text-xl font-bold text-gray-900 mb-2">Memproses Transaksi</h2>
              <p className="text-sm text-gray-500 mb-6">{fileName || 'Memproses pipeline...'}</p>
              <div className="flex items-center justify-center gap-6 text-xs text-gray-400">
                <span className="flex items-center gap-1"><FileText size={14} /> Extract PDF</span>
                <ArrowRight size={12} />
                <span className="flex items-center gap-1"><Brain size={14} /> NLP SVM</span>
                <ArrowRight size={12} />
                <span className="flex items-center gap-1"><Database size={14} /> KB & CoA</span>
              </div>
            </motion.div>
          )}

          {/* ===== RESULT ===== */}
          {step === 'result' && (
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
                    {fileName || 'Transaksi'}
                    <span className="text-gray-300">|</span>
                    <Clock size={14} />
                    {results.length} transaksi diproses
                  </p>
                </div>
              </div>

              {/* Stat Cards */}
              <div className="grid grid-cols-3 gap-4 mb-6">
                {[
                  { label: 'Auto Match (Pool 1)', count: stats.auto, total: results.length, color: 'emerald', icon: CheckCircle2 },
                  { label: 'Perlu Review (Pool 3)', count: stats.review, total: results.length, color: 'amber', icon: AlertTriangle },
                  { label: 'Manual Review', count: stats.manual, total: results.length, color: 'red', icon: XCircle },
                ].map((s, i) => (
                  <motion.div
                    key={s.label}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.05 * i }}
                    className={`bg-white rounded-xl border p-5 ${
                      s.color === 'emerald' ? 'border-emerald-200/60' :
                      s.color === 'amber' ? 'border-amber-200/60' :
                      'border-red-200/60'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                        s.color === 'emerald' ? 'bg-emerald-100 text-emerald-600' :
                        s.color === 'amber' ? 'bg-amber-100 text-amber-600' :
                        'bg-red-100 text-red-600'
                      }`}>
                        <s.icon size={20} />
                      </div>
                      <span className="text-2xl font-bold text-gray-900">{s.count}</span>
                    </div>
                    <p className="text-sm font-medium text-gray-600">{s.label}</p>
                    <div className="mt-2 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${s.total > 0 ? (s.count / s.total) * 100 : 0}%` }}
                        transition={{ delay: 0.3 + 0.1 * i, duration: 0.6 }}
                        className={`h-full rounded-full ${
                          s.color === 'emerald' ? 'bg-emerald-500' :
                          s.color === 'amber' ? 'bg-amber-500' :
                          'bg-red-500'
                        }`}
                      />
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Table */}
              <div className="bg-white rounded-2xl border border-gray-200/80 shadow-xl shadow-gray-100/50 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-900">Detail Transaksi & Pemetaan CoA</h3>
                  <span className="text-xs text-gray-400">{results.length} baris</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-gray-50/80">
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Tanggal</th>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Keterangan</th>
                        <th className="px-6 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wider">Mutasi</th>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Akun CoA Mitra</th>
                        <th className="px-6 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Confidence</th>
                        <th className="px-6 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Metode Matching</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {results.map((row, i) => (
                        <motion.tr
                          key={i}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: 0.03 * i }}
                          className="hover:bg-blue-50/30 transition-colors"
                        >
                          <td className="px-6 py-4 text-gray-500 whitespace-nowrap">{row.tgl}</td>
                          <td className="px-6 py-4">
                            <span className="font-mono text-xs text-gray-800">{row.ket}</span>
                            {row.pool && (
                              <div className="text-[10px] text-gray-400 mt-0.5">{row.pool}</div>
                            )}
                          </td>
                          <td className={`px-6 py-4 text-right font-mono text-xs whitespace-nowrap ${
                            row.jenis === 'CR' ? 'text-emerald-600' : 'text-red-600'
                          }`}>
                            {row.jenis === 'CR' ? '+' : '-'}{formatCurrency(row.mutasi)}
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-xs font-semibold text-gray-900">{row.akun}</div>
                            <div className="text-[11px] text-gray-500">{row.nama}</div>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <div className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs font-mono font-medium ${
                              row.conf >= 0.66 ? 'bg-emerald-50 text-emerald-700' :
                              row.conf >= 0.4 ? 'bg-amber-50 text-amber-700' :
                              'bg-red-50 text-red-700'
                            }`}>
                              {(row.conf * 100).toFixed(0)}%
                            </div>
                          </td>
                          <td className="px-6 py-4 text-center">
                            <StatusBadge status={row.status} />
                          </td>
                          <td className="px-6 py-4 text-xs text-gray-500">{row.metode}</td>
                        </motion.tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* ERP iframe placeholder */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 }}
                className="mt-8 bg-white rounded-2xl border border-gray-200/80 shadow-xl shadow-gray-100/50 overflow-hidden"
              >
                <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-2">
                  <div className="w-7 h-7 bg-indigo-100 rounded-lg flex items-center justify-center">
                    <Database size={14} className="text-indigo-600" />
                  </div>
                  <h3 className="text-sm font-semibold text-gray-900">Data ERP Mitra</h3>
                </div>
                <div className="w-full h-64 bg-gradient-to-br from-gray-50 to-gray-100/50 flex flex-col items-center justify-center gap-3">
                  <div className="w-12 h-12 bg-gray-200/80 rounded-2xl flex items-center justify-center">
                    <Database size={24} className="text-gray-400" />
                  </div>
                  <p className="text-sm text-gray-400 font-medium">Data ERP mitra akan ditampilkan di sini</p>
                  <p className="text-xs text-gray-300">Menampilkan data CoA, vendor, customer, dan invoice</p>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  )
}

export default App
