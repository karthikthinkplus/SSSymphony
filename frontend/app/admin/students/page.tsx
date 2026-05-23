'use client'

import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/api'

export default function StudentsPage() {
  const [students, setStudents] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [grade, setGrade] = useState<number | ''>('')
  const [loading, setLoading] = useState(true)
  const [selectedStudent, setSelectedStudent] = useState<string | null>(null)
  const [report, setReport] = useState<any>(null)
  const [reportLoading, setReportLoading] = useState(false)

  const fetchStudents = async () => {
    setLoading(true)
    try {
      const res = await adminApi.getStudents({
        search: search || undefined,
        grade: grade ? Number(grade) : undefined,
      })
      setStudents(res.students || [])
      setTotal(res.total || 0)
    } catch { } finally { setLoading(false) }
  }

  useEffect(() => { fetchStudents() }, [search, grade])

  const viewReport = async (sid: string) => {
    setSelectedStudent(sid)
    setReportLoading(true)
    try {
      const r = await adminApi.getStudentReport(sid)
      setReport(r)
    } catch (e: any) {
      setReport({ error: e?.response?.data?.detail || 'No completed sessions' })
    } finally { setReportLoading(false) }
  }

  return (
    <div>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: 'Outfit', marginBottom: 6 }}>Students</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>All registered students and their assessment history</p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 24, alignItems: 'center' }}>
        <input
          className="input-field"
          placeholder="Search by name…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ maxWidth: 260 }}
        />
        <select
          className="input-field"
          value={grade}
          onChange={e => setGrade(e.target.value ? Number(e.target.value) : '')}
          style={{ maxWidth: 160 }}
        >
          <option value="">All Grades</option>
          {[5,6,7,8,9,10].map(g => <option key={g} value={g}>Grade {g}</option>)}
        </select>
        <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{total} student{total !== 1 ? 's' : ''}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selectedStudent ? '1fr 420px' : '1fr', gap: 24 }}>
        {/* Table */}
        <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading…</div>
          ) : students.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>👥</div>
              <p>No students yet. Share the student assessment link to get started.</p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Grade</th>
                  <th>School</th>
                  <th>Sessions</th>
                  <th>Last Score</th>
                  <th>Last Assessment</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {students.map((s: any) => (
                  <tr key={s.student_id} style={{ cursor: 'pointer' }} onClick={() => viewReport(s.student_id)}>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{s.name}</td>
                    <td>Grade {s.class_grade}</td>
                    <td>{s.school || '—'}</td>
                    <td>{s.sessions_count}</td>
                    <td>
                      {s.overall_score != null ? (
                        <span style={{
                          fontWeight: 700,
                          color: s.overall_score >= 75 ? '#10b981' : s.overall_score >= 50 ? '#f59e0b' : '#ef4444',
                        }}>{s.overall_score}%</span>
                      ) : '—'}
                    </td>
                    <td style={{ fontSize: 12 }}>
                      {s.last_session_date ? new Date(s.last_session_date).toLocaleDateString('en-IN') : '—'}
                    </td>
                    <td>
                      <button className="btn-secondary" style={{ padding: '6px 14px', fontSize: 12 }}
                        onClick={e => { e.stopPropagation(); viewReport(s.student_id) }}>
                        View Report
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Report panel */}
        {selectedStudent && (
          <div className="glass-card" style={{ padding: 24, maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ fontSize: 16, fontWeight: 700 }}>Diagnostic Report</h3>
              <button onClick={() => { setSelectedStudent(null); setReport(null) }}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}>✕</button>
            </div>
            {reportLoading ? (
              <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading report…</div>
            ) : report?.error ? (
              <p style={{ color: '#ef4444', fontSize: 14 }}>{report.error}</p>
            ) : report ? (
              <div>
                <div style={{ marginBottom: 16 }}>
                  <h4 style={{ fontSize: 18, fontWeight: 800 }}>{report.student_name}</h4>
                  <p style={{ fontSize: 13, color: 'var(--text-muted)' }}>{report.school} · Grade {report.selected_grade}</p>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
                  {[
                    { l: 'Accuracy', v: `${report.accuracy_pct}%` },
                    { l: 'Grade Level', v: `Grade ${report.grade_equivalent_level}` },
                    { l: 'Questions', v: report.total_questions },
                    { l: 'Correct', v: report.correct_answers },
                  ].map(item => (
                    <div key={item.l} style={{ padding: '12px 16px', borderRadius: 10, background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)' }}>
                      <div style={{ fontSize: 20, fontWeight: 800 }}>{item.v}</div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{item.l}</div>
                    </div>
                  ))}
                </div>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.7, marginBottom: 16 }}>
                  {report.narrative}
                </p>
                <a
                  href={`/report/${report.session_id}`}
                  target="_blank"
                  style={{ color: 'var(--accent-primary)', fontSize: 13, textDecoration: 'none', fontWeight: 600 }}
                >
                  Full Report →
                </a>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}
