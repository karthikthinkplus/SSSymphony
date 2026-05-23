'use client'

import { useEffect, useState } from 'react'
import { adminApi } from '@/lib/api'

export default function QuestionsPage() {
  const [questions, setQuestions] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [grade, setGrade] = useState<number | ''>('')
  const [difficulty, setDifficulty] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<any | null>(null)

  const fetchQuestions = async () => {
    setLoading(true)
    try {
      const res = await adminApi.getQuestions({
        grade: grade ? Number(grade) : undefined,
        difficulty: difficulty || undefined,
        search: search || undefined,
        limit: 100,
      })
      setQuestions(res.questions || [])
      setTotal(res.total || 0)
    } catch { } finally { setLoading(false) }
  }

  useEffect(() => { fetchQuestions() }, [grade, difficulty, search])

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: 'Outfit', marginBottom: 6 }}>Question Bank</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>{total} questions · Browse and filter the NCERT question bank</p>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        <input className="input-field" placeholder="Search question text…" value={search}
          onChange={e => setSearch(e.target.value)} style={{ maxWidth: 300 }} />
        <select className="input-field" value={grade} onChange={e => setGrade(e.target.value ? Number(e.target.value) : '')} style={{ maxWidth: 150 }}>
          <option value="">All Grades</option>
          {[5,6,7,8,9,10].map(g => <option key={g} value={g}>Grade {g}</option>)}
        </select>
        <select className="input-field" value={difficulty} onChange={e => setDifficulty(e.target.value)} style={{ maxWidth: 150 }}>
          <option value="">All Difficulties</option>
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>
        <a href="/admin/import">
          <button className="btn-primary" style={{ padding: '10px 20px', fontSize: 14 }}>📥 Import Excel</button>
        </a>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 380px' : '1fr', gap: 20 }}>
        <div className="glass-card" style={{ padding: 0, overflow: 'hidden' }}>
          {loading ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-muted)' }}>Loading questions…</div>
          ) : questions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>📭</div>
              <p>No questions found. <a href="/admin/import" style={{ color: 'var(--accent-primary)' }}>Import your XLSX file →</a></p>
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Question</th>
                  <th>Skill</th>
                  <th>Grade</th>
                  <th>Difficulty</th>
                  <th>Type</th>
                  <th>Traps</th>
                </tr>
              </thead>
              <tbody>
                {questions.map((q: any) => (
                  <tr key={q.question_id} onClick={() => setSelected(q)} style={{ cursor: 'pointer' }}>
                    <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{q.question_id.substring(0, 20)}…</td>
                    <td style={{ maxWidth: 240 }}>{q.question_text}</td>
                    <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{q.skill_name}</td>
                    <td>Gr {q.grade_level}</td>
                    <td>
                      <span style={{
                        padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600,
                        background: q.difficulty_band === 'easy' ? 'rgba(16,185,129,0.1)' : q.difficulty_band === 'hard' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                        color: q.difficulty_band === 'easy' ? '#10b981' : q.difficulty_band === 'hard' ? '#ef4444' : '#f59e0b',
                      }}>{q.difficulty_band}</span>
                    </td>
                    <td>{q.word_problem_flag ? '📖 Word' : '✏️ Equation'}</td>
                    <td>{q.has_traps ? '✅' : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {selected && (
          <div className="glass-card" style={{ padding: 24, maxHeight: '80vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700 }}>Question Detail</h3>
              <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 18 }}>✕</button>
            </div>
            <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
              <span style={{ padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600, background: 'rgba(99,102,241,0.1)', color: 'var(--accent-primary)' }}>
                Grade {selected.grade_level}
              </span>
              <span style={{ padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600, background: 'rgba(245,158,11,0.1)', color: '#f59e0b' }}>
                {selected.difficulty_band}
              </span>
              {selected.word_problem_flag && (
                <span style={{ padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600, background: 'rgba(6,182,212,0.1)', color: '#06b6d4' }}>
                  Word Problem
                </span>
              )}
              {selected.has_twin && (
                <span style={{ padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600, background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>
                  Has Twin
                </span>
              )}
            </div>
            <p style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 20, color: 'var(--text-primary)' }}>{selected.question_text}</p>
            <div style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--text-muted)', marginBottom: 16, wordBreak: 'break-all' }}>
              ID: {selected.question_id}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
              <strong>Skill:</strong> {selected.skill_name}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
              <strong>Correct Answer:</strong> Option {selected.correct_option}
            </div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              <strong>Traps Configured:</strong> {selected.has_traps ? 'Yes' : 'No'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
