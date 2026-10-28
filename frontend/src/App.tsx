import { useState } from 'react'

type Step = 'upload' | 'processing' | 'result'

function App() {
  const [step, setStep] = useState<Step>('upload')
  const [fileName, setFileName] = useState<string>('')

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setFileName(file.name)
    }
  }

  const handleProcess = () => {
    if (!fileName) return
    setStep('processing')
    // Simulasi proses (nanti diganti API call)
    setTimeout(() => setStep('result'), 2000)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">SiRekon</h1>
            <p className="text-sm text-gray-500">Sistem Rekonsiliasi Transaksi Keuangan</p>
          </div>
          <nav className="flex gap-6 text-sm">
            <button
              onClick={() => setStep('upload')}
              className={`px-3 py-1.5 rounded-md transition ${step === 'upload' ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:text-gray-900'}`}
            >
              Upload
            </button>
            <button
              onClick={() => setStep('result')}
              className={`px-3 py-1.5 rounded-md transition ${step === 'result' ? 'bg-blue-50 text-blue-700 font-medium' : 'text-gray-600 hover:text-gray-900'}`}
            >
              Hasil Rekonsiliasi
            </button>
          </nav>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Step: Upload */}
        {step === 'upload' && (
          <div className="max-w-xl mx-auto">
            <div className="bg-white rounded-lg border border-gray-200 p-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-2">Upload Mutasi Bank</h2>
              <p className="text-sm text-gray-500 mb-6">
                Upload file PDF mutasi bank untuk diproses oleh sistem rekonsiliasi.
              </p>

              <label className="flex flex-col items-center justify-center w-full h-48 border-2 border-dashed border-gray-300 rounded-lg cursor-pointer hover:border-blue-400 hover:bg-blue-50/50 transition">
                <div className="flex flex-col items-center py-6">
                  <svg className="w-10 h-10 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                  </svg>
                  {fileName ? (
                    <p className="text-sm font-medium text-blue-600">{fileName}</p>
                  ) : (
                    <>
                      <p className="text-sm text-gray-600">Klik untuk pilih file atau drag & drop</p>
                      <p className="text-xs text-gray-400 mt-1">PDF (maks. 10MB)</p>
                    </>
                  )}
                </div>
                <input type="file" accept=".pdf" className="hidden" onChange={handleFileChange} />
              </label>

              <button
                onClick={handleProcess}
                disabled={!fileName}
                className="mt-6 w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition"
              >
                Proses Rekonsiliasi
              </button>
            </div>

            {/* Pipeline info */}
            <div className="mt-6 grid grid-cols-3 gap-3">
              <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
                <div className="text-2xl mb-1">1</div>
                <p className="text-xs font-medium text-gray-900">Table Recognition</p>
                <p className="text-xs text-gray-500">Extract PDF</p>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
                <div className="text-2xl mb-1">2</div>
                <p className="text-xs font-medium text-gray-900">NLP Processing</p>
                <p className="text-xs text-gray-500">Klasifikasi teks</p>
              </div>
              <div className="bg-white rounded-lg border border-gray-200 p-4 text-center">
                <div className="text-2xl mb-1">3</div>
                <p className="text-xs font-medium text-gray-900">Knowledge Base</p>
                <p className="text-xs text-gray-500">Matching CoA</p>
              </div>
            </div>
          </div>
        )}

        {/* Step: Processing */}
        {step === 'processing' && (
          <div className="max-w-xl mx-auto text-center py-20">
            <div className="animate-spin w-12 h-12 border-4 border-blue-200 border-t-blue-600 rounded-full mx-auto mb-6" />
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Memproses {fileName}</h2>
            <p className="text-sm text-gray-500">Table Recognition → NLP → Knowledge Base</p>
          </div>
        )}

        {/* Step: Result */}
        {step === 'result' && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Hasil Rekonsiliasi</h2>
                <p className="text-sm text-gray-500">{fileName || 'mutasi_bca_2023.pdf'}</p>
              </div>
              <div className="flex gap-3">
                <span className="px-3 py-1 bg-green-100 text-green-700 text-xs font-medium rounded-full">Auto-matched: 285</span>
                <span className="px-3 py-1 bg-yellow-100 text-yellow-700 text-xs font-medium rounded-full">Perlu Review: 42</span>
                <span className="px-3 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-full">Manual: 10</span>
              </div>
            </div>

            {/* Tabel hasil (dummy) */}
            <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 border-b border-gray-200">
                  <tr>
                    <th className="px-4 py-3 font-medium text-gray-600">Tanggal</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Keterangan</th>
                    <th className="px-4 py-3 font-medium text-gray-600 text-right">Mutasi</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Akun CoA</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Status</th>
                    <th className="px-4 py-3 font-medium text-gray-600">Metode</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {[
                    { tgl: '02/01/2023', ket: 'TRSF E-BANKING CIOMAS ADISATWA', mutasi: '-580,075,045', akun: '2.1.01.01', nama: 'Trade Payable', status: 'auto', metode: 'KB (Master Vendor)' },
                    { tgl: '02/01/2023', ket: 'SWITCHING DR 008 PANCA BERSAUDARA', mutasi: '+50,000,000', akun: '1.1.02.98', nama: 'Cross Account Bank', status: 'auto', metode: 'KB (Switching)' },
                    { tgl: '03/01/2023', ket: 'BYR VIA E-BANKING PENERIMAAN NEGARA', mutasi: '-14,978,282', akun: 'PERLU_REVIEW', nama: 'Pajak', status: 'review', metode: 'KB (Pajak)' },
                    { tgl: '05/01/2023', ket: 'REF TXN 99823 ANOMALI', mutasi: '-100,000', akun: '-', nama: '-', status: 'manual', metode: 'Manual Review' },
                  ].map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-600">{row.tgl}</td>
                      <td className="px-4 py-3 text-gray-900 font-mono text-xs">{row.ket}</td>
                      <td className={`px-4 py-3 text-right font-mono text-xs ${row.mutasi.startsWith('+') ? 'text-green-600' : 'text-red-600'}`}>{row.mutasi}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs font-medium text-gray-900">{row.akun}</span>
                        <br />
                        <span className="text-xs text-gray-500">{row.nama}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                          row.status === 'auto' ? 'bg-green-100 text-green-700' :
                          row.status === 'review' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-red-100 text-red-700'
                        }`}>
                          {row.status === 'auto' ? 'Auto' : row.status === 'review' ? 'Review' : 'Manual'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">{row.metode}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Iframe ERP placeholder */}
            <div className="mt-8 bg-white rounded-lg border border-gray-200 p-4">
              <h3 className="text-sm font-medium text-gray-900 mb-3">Data ERP Mitra</h3>
              <div className="w-full h-64 bg-gray-100 rounded border border-dashed border-gray-300 flex items-center justify-center">
                <p className="text-sm text-gray-400">iframe ERP mitra akan ditampilkan di sini</p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
