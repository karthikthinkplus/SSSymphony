'use client'

import { useState, useRef } from 'react'
import { adminApi } from '@/lib/api'

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [importing, setImporting] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')
  const fileRef = useRef<HTMLInputElement>(null)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f && (f.name.endsWith('.xlsx') || f.name.endsWith('.xls'))) {
      setFile(f); setResult(null); setError('')
    } else {
      setError('Please drop an Excel file (.xlsx or .xls)')
    }
  }

  const handleImport = async () => {
    if (!file) return
    setImporting(true)
    setResult(null)
    setError('')
    try {
      const res = await adminApi.importExcel(file)
      setResult(res)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Import failed. Check server logs.')
    } finally {
      setImporting(false)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: 'Outfit', marginBottom: 6 }}>Import Question Bank</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>
          Upload the 5-sheet SME Excel workbook to populate the database
        </p>
      </div>

      {/* Schema reminder */}
      <div className="glass-card" style={{ padding: 24, marginBottom: 28 }}>
        <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 16 }}>Expected Excel Format (5 Sheets)</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
          {[
            { name: '1_Skills', desc: 'Skill nodes + prerequisites' },
            { name: '2_Questions', desc: 'Question bank (MCQ/Word)' },
            { name: '3_Q_Matrix', desc: 'Binary skill × question grid' },
            { name: '4_AnswerTraps', desc: 'Distractor diagnostics' },
            { name: '5_Dimensions', desc: '5 learning dimension tags' },
          ].map(s => (
            <div key={s.name} style={{
              padding: '14px 16px', borderRadius: 10,
              background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)',
              textAlign: 'center',
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent-primary)', marginBottom: 6 }}>{s.name}</div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        style={{
          border: `2px dashed ${dragging ? 'var(--accent-primary)' : file ? '#10b981' : 'var(--border-light)'}`,
          borderRadius: 20,
          padding: '60px 40px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragging ? 'rgba(99,102,241,0.06)' : file ? 'rgba(16,185,129,0.04)' : 'rgba(26,34,53,0.4)',
          transition: 'all 0.3s ease',
          marginBottom: 24,
        }}
      >
        <input ref={fileRef} type="file" accept=".xlsx,.xls" style={{ display: 'none' }}
          onChange={e => { const f = e.target.files?.[0]; if (f) { setFile(f); setResult(null); setError('') } }} />
        <div style={{ fontSize: 48, marginBottom: 16 }}>{file ? '✅' : '📥'}</div>
        {file ? (
          <>
            <p style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>{file.name}</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{(file.size / 1024).toFixed(1)} KB · Click to change</p>
          </>
        ) : (
          <>
            <p style={{ fontSize: 16, fontWeight: 600, marginBottom: 6 }}>Drag & drop your Excel file here</p>
            <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>or click to browse · .xlsx / .xls accepted</p>
          </>
        )}
      </div>

      {error && (
        <div style={{
          padding: '14px 18px', borderRadius: 10, marginBottom: 20,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#ef4444', fontSize: 14,
        }}>{error}</div>
      )}

      <button
        id="import-btn"
        className="btn-primary"
        onClick={handleImport}
        disabled={!file || importing}
        style={{ width: '100%', marginBottom: 28 }}
      >
        {importing ? 'Importing…' : file ? `Import ${file.name} →` : 'Select a file to continue'}
      </button>

      {/* Result */}
      {result && (
        <div className="glass-card" style={{ padding: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
            <span style={{ fontSize: 28 }}>{result.success ? '✅' : '❌'}</span>
            <h3 style={{ fontSize: 18, fontWeight: 700 }}>
              {result.success ? 'Import Successful!' : 'Import Failed — Validation Errors'}
            </h3>
          </div>

          {result.success && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
              {[
                { label: 'Skills', value: result.skills_imported },
                { label: 'Questions', value: result.questions_imported },
                { label: 'Q-Matrix Rows', value: result.q_matrix_rows },
                { label: 'Traps', value: result.traps_imported },
                { label: 'Dimensions', value: result.dimensions_imported },
              ].map(item => (
                <div key={item.label} style={{
                  padding: '16px', textAlign: 'center', borderRadius: 10,
                  background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
                }}>
                  <div style={{ fontSize: 24, fontWeight: 800, color: '#10b981' }}>{item.value}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{item.label}</div>
                </div>
              ))}
            </div>
          )}

          {result.errors?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ fontSize: 14, fontWeight: 700, color: '#ef4444', marginBottom: 8 }}>Errors:</h4>
              {result.errors.map((e: string, i: number) => (
                <div key={i} style={{
                  padding: '8px 12px', marginBottom: 4, borderRadius: 6,
                  background: 'rgba(239,68,68,0.08)', fontSize: 13, color: '#ef4444',
                }}>• {e}</div>
              ))}
            </div>
          )}

          {result.warnings?.length > 0 && (
            <div>
              <h4 style={{ fontSize: 14, fontWeight: 700, color: '#f59e0b', marginBottom: 8 }}>Warnings:</h4>
              {result.warnings.map((w: string, i: number) => (
                <div key={i} style={{
                  padding: '8px 12px', marginBottom: 4, borderRadius: 6,
                  background: 'rgba(245,158,11,0.08)', fontSize: 13, color: '#f59e0b',
                }}>• {w}</div>
              ))}
            </div>
          )}

          {result.success && (
            <a href="/admin/questions">
              <button className="btn-secondary" style={{ marginTop: 16 }}>Browse Question Bank →</button>
            </a>
          )}
        </div>
      )}
    </div>
  )
}
