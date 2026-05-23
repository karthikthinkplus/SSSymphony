'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { sessionApi } from '@/lib/api'

const GRADES = [5, 6, 7, 8, 9, 10]
const GRADE_LABELS: Record<number, string> = {
  5: 'Grade 5', 6: 'Grade 6', 7: 'Grade 7',
  8: 'Grade 8', 9: 'Grade 9', 10: 'Grade 10',
}
const GRADE_TOPICS: Record<number, string> = {
  5: 'Numbers, Fractions & Basic Geometry',
  6: 'Integers, Algebra & Data Handling',
  7: 'Rational Numbers, Triangles & Mensuration',
  8: 'Squares, Cubes, Linear Equations',
  9: 'Polynomials, Coordinate Geometry & Statistics',
  10: 'Arithmetic Progressions, Trigonometry & Probability',
}

export default function HomePage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [school, setSchool] = useState('')
  const [grade, setGrade] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleStart = async () => {
    if (!name.trim()) { setError('Please enter your name'); return }
    if (!grade) { setError('Please select your grade'); return }
    setError('')
    setLoading(true)
    try {
      const res = await sessionApi.start({ name: name.trim(), school: school.trim(), grade })
      // Store session data
      localStorage.setItem('session_id', res.session_id)
      localStorage.setItem('student_name', name.trim())
      localStorage.setItem('selected_grade', String(grade))
      // Store first question for assessment page
      sessionStorage.setItem('first_question', JSON.stringify(res.first_question))
      router.push(`/assessment/${res.session_id}`)
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to start assessment. Is the server running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="noise-bg min-h-screen flex flex-col" style={{ background: 'var(--bg-primary)' }}>
      {/* Background orbs */}
      <div style={{
        position: 'fixed', inset: 0, pointerEvents: 'none', overflow: 'hidden', zIndex: 0,
      }}>
        <div style={{
          position: 'absolute', top: '-20%', left: '-10%', width: 600, height: 600,
          borderRadius: '50%', background: 'radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%)',
        }} />
        <div style={{
          position: 'absolute', bottom: '-10%', right: '-10%', width: 500, height: 500,
          borderRadius: '50%', background: 'radial-gradient(circle, rgba(139,92,246,0.10) 0%, transparent 70%)',
        }} />
        <div style={{
          position: 'absolute', top: '40%', left: '60%', width: 300, height: 300,
          borderRadius: '50%', background: 'radial-gradient(circle, rgba(6,182,212,0.07) 0%, transparent 70%)',
        }} />
      </div>

      <div style={{ position: 'relative', zIndex: 1, maxWidth: 900, margin: '0 auto', padding: '60px 24px', width: '100%' }}>
        {/* Hero */}
        <div className="animate-fade-in-up" style={{ textAlign: 'center', marginBottom: 64 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 8,
            padding: '8px 20px', borderRadius: 99,
            background: 'rgba(99,102,241,0.12)', border: '1px solid rgba(99,102,241,0.3)',
            marginBottom: 24, fontSize: 13, fontWeight: 600, color: 'var(--accent-primary)',
            letterSpacing: '0.5px',
          }}>
            <span>🎯</span> NCERT-Aligned · Grades 5–10 · AI-Powered
          </div>
          <h1 style={{ fontSize: 56, fontWeight: 800, lineHeight: 1.15, marginBottom: 20 }}>
            <span className="gradient-text">Symphony</span>
          </h1>
          <h2 style={{ fontSize: 28, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 16 }}>
            Adaptive Math Assessment Tool
          </h2>
          <p style={{ fontSize: 16, color: 'var(--text-muted)', maxWidth: 520, margin: '0 auto', lineHeight: 1.7 }}>
            A diagnostic engine that adapts to every response — pinpointing your exact strengths,
            gaps, and the root cause of every error across 5 learning dimensions.
          </p>
        </div>

        {/* Algorithm badges */}
        <div className="animate-fade-in-up stagger-1" style={{
          display: 'flex', gap: 12, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 64
        }}>
          {['CAT + IRT', 'CDM Diagnostics', 'Bayesian KT', 'Deep KT', 'Twin Question'].map(algo => (
            <span key={algo} style={{
              padding: '6px 16px', borderRadius: 99, fontSize: 12, fontWeight: 600,
              background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.2)',
              color: 'var(--text-secondary)',
            }}>{algo}</span>
          ))}
        </div>

        {/* Form card */}
        <div className="glass-card animate-fade-in-up stagger-2" style={{ padding: 48, marginBottom: 32 }}>
          <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>Start Your Assessment</h3>
          <p style={{ color: 'var(--text-muted)', fontSize: 14, marginBottom: 36 }}>
            Takes 15–25 minutes. The engine adapts in real-time to your responses.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 28 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                Your Name *
              </label>
              <input
                id="student-name"
                className="input-field"
                placeholder="e.g. Priya Sharma"
                value={name}
                onChange={e => setName(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleStart()}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                School (optional)
              </label>
              <input
                id="student-school"
                className="input-field"
                placeholder="e.g. Delhi Public School"
                value={school}
                onChange={e => setSchool(e.target.value)}
              />
            </div>
          </div>

          <div style={{ marginBottom: 36 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 14 }}>
              Select Your Grade *
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12 }}>
              {GRADES.map(g => (
                <button
                  key={g}
                  id={`grade-${g}`}
                  onClick={() => setGrade(g)}
                  style={{
                    padding: '20px 12px',
                    borderRadius: 14,
                    border: grade === g ? '2px solid var(--accent-primary)' : '1.5px solid var(--border)',
                    background: grade === g ? 'rgba(99,102,241,0.15)' : 'rgba(26,34,53,0.5)',
                    color: grade === g ? 'var(--text-primary)' : 'var(--text-muted)',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                    textAlign: 'center',
                  }}
                >
                  <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'Outfit, sans-serif', marginBottom: 2 }}>{g}</div>
                  <div style={{ fontSize: 11, fontWeight: 500 }}>Grade</div>
                  {grade === g && (
                    <div style={{
                      fontSize: 10, marginTop: 6, color: 'var(--accent-primary)',
                      lineHeight: 1.3, display: 'none',
                    }}>✓</div>
                  )}
                </button>
              ))}
            </div>
            {grade && (
              <div style={{
                marginTop: 12, padding: '10px 16px', borderRadius: 10,
                background: 'rgba(99,102,241,0.08)', border: '1px solid rgba(99,102,241,0.15)',
                fontSize: 13, color: 'var(--text-secondary)',
              }}>
                📚 {GRADE_TOPICS[grade]}
              </div>
            )}
          </div>

          {error && (
            <div style={{
              padding: '12px 16px', borderRadius: 10, marginBottom: 20,
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444', fontSize: 14,
            }}>⚠ {error}</div>
          )}

          <button
            id="start-assessment-btn"
            className="btn-primary"
            onClick={handleStart}
            disabled={loading}
            style={{ width: '100%', fontSize: 16, padding: '16px 32px' }}
          >
            {loading ? 'Starting Assessment…' : 'Begin Adaptive Assessment →'}
          </button>
        </div>

        {/* How it works */}
        <div className="animate-fade-in-up stagger-3" style={{
          display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 48
        }}>
          {[
            { icon: '🧠', title: 'Adapts in Real-Time', desc: 'Every answer adjusts the difficulty and topic selection using IRT and BKT algorithms.' },
            { icon: '🔍', title: 'Root Cause Diagnosis', desc: 'The CDM identifies whether errors are conceptual gaps, slips, or reading difficulties.' },
            { icon: '📊', title: 'Detailed Report', desc: 'Receive a 5-dimension skill profile with NCERT remediation recommendations.' },
          ].map((item, i) => (
            <div key={i} className="glass-card" style={{ padding: 24 }}>
              <div style={{ fontSize: 28, marginBottom: 12 }}>{item.icon}</div>
              <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>{item.title}</div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6 }}>{item.desc}</div>
            </div>
          ))}
        </div>

        {/* Admin link */}
        <div style={{ textAlign: 'center' }}>
          <a href="/admin" style={{ color: 'var(--text-muted)', fontSize: 13, textDecoration: 'none' }}>
            Teacher / Admin Panel →
          </a>
        </div>
      </div>
    </div>
  )
}
