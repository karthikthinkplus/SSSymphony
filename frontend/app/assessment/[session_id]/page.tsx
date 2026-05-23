'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter, useParams } from 'next/navigation'
import { sessionApi, QuestionOut } from '@/lib/api'

const OPTIONS = ['A', 'B', 'C', 'D'] as const

function getOptionText(q: QuestionOut, opt: string): string {
  const map: Record<string, string> = { A: q.option_a, B: q.option_b, C: q.option_c, D: q.option_d }
  return map[opt] || ''
}

export default function AssessmentPage() {
  const router = useRouter()
  const params = useParams()
  const sessionId = params?.session_id as string

  const [question, setQuestion] = useState<QuestionOut | null>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [questionCount, setQuestionCount] = useState(0)
  const [maxQ] = useState(30)
  const [complete, setComplete] = useState(false)
  const [error, setError] = useState('')
  const startTimeRef = useRef<number>(Date.now())

  useEffect(() => {
    // Load the first question from session storage or redirect
    const storedGrade = localStorage.getItem('selected_grade')
    if (!storedGrade || !sessionId) {
      router.push('/')
      return
    }
    // Fetch session status to get current state
    sessionApi.getStatus(sessionId).then(status => {
      if (status.status === 'completed') {
        setComplete(true)
        setTimeout(() => router.push(`/report/${sessionId}`), 1500)
        return
      }
    }).catch(() => router.push('/'))

    // The first question is delivered via the start response, stored in sessionStorage by the landing page
    const firstQ = sessionStorage.getItem('first_question')
    if (firstQ) {
      setQuestion(JSON.parse(firstQ))
      setQuestionCount(1)
      sessionStorage.removeItem('first_question')
    }
  }, [sessionId])

  const handleSubmit = async () => {
    if (!selected || !question || submitting) return
    setSubmitting(true)

    const responseTimeMs = Date.now() - startTimeRef.current
    try {
      const res = await sessionApi.respond({
        session_id: sessionId,
        question_id: question.question_id,
        selected_option: selected,
        response_time_ms: responseTimeMs,
      })

      if (res.session_complete || !res.next_question) {
        setComplete(true)
        setTimeout(() => router.push(`/report/${sessionId}`), 2000)
      } else {
        setQuestion(res.next_question)
        setQuestionCount(prev => prev + 1)
        setSelected(null)
        startTimeRef.current = Date.now()
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Failed to submit response')
    } finally {
      setSubmitting(false)
    }
  }

  if (complete) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: 64, marginBottom: 24 }}>🎉</div>
          <h2 style={{ fontSize: 28, fontWeight: 700, marginBottom: 12 }}>Assessment Complete!</h2>
          <p style={{ color: 'var(--text-muted)' }}>Generating your diagnostic report…</p>
          <div style={{ marginTop: 24, width: 48, height: 48, border: '4px solid var(--accent-primary)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '24px auto 0' }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  if (!question) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 48, height: 48, border: '4px solid var(--accent-primary)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 16px' }} />
          <p style={{ color: 'var(--text-muted)' }}>Loading assessment…</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  const progress = Math.min((questionCount / maxQ) * 100, 100)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', padding: '0' }}>
      {/* Fixed top bar */}
      <div style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        background: 'rgba(10,14,26,0.9)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--border)', padding: '14px 32px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 18, fontWeight: 800, fontFamily: 'Outfit', color: 'var(--accent-primary)' }}>Adapti+ Learn</span>
          <span style={{ color: 'var(--border)', fontSize: 18 }}>|</span>
          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
            {question.topic_area} → {question.skill_name}
          </span>
          {question.is_twin_probe && (
            <span style={{
              padding: '3px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600,
              background: 'rgba(6,182,212,0.15)', color: '#06b6d4',
              border: '1px solid rgba(6,182,212,0.3)',
            }}>DIAGNOSTIC PROBE</span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{
            padding: '4px 14px', borderRadius: 99, fontSize: 12, fontWeight: 600,
            background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
            color: 'var(--accent-primary)',
            textTransform: 'capitalize',
          }}>{question.difficulty_band}</div>
          <span style={{ fontSize: 13, color: 'var(--text-muted)', fontWeight: 600 }}>
            Q {questionCount} of ~{maxQ}
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div style={{ position: 'fixed', top: 0, left: 0, right: 0, height: 3, zIndex: 101 }}>
        <div style={{
          height: '100%', width: `${progress}%`,
          background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
          transition: 'width 0.5s ease',
        }} />
      </div>

      {/* Main content */}
      <div style={{ paddingTop: 100, minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ maxWidth: 720, width: '100%', padding: '0 24px 60px' }}>
          {/* Grade + topic breadcrumb */}
          <div className="animate-fade-in" style={{ marginBottom: 24, display: 'flex', gap: 8, alignItems: 'center' }}>
            <span style={{
              padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 600,
              background: 'rgba(99,102,241,0.1)', color: 'var(--accent-primary)',
              border: '1px solid rgba(99,102,241,0.2)',
            }}>Grade {question.grade_level}</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>›</span>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{question.topic_area}</span>
            <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>›</span>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontWeight: 500 }}>{question.skill_name}</span>
          </div>

          {/* Question card */}
          <div className="glass-card animate-fade-in-up" style={{ padding: 40, marginBottom: 24 }}>
            {question.word_problem_flag && !question.is_twin_probe && (
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 16,
                padding: '4px 12px', borderRadius: 99, fontSize: 11, fontWeight: 600,
                background: 'rgba(245,158,11,0.1)', color: '#f59e0b',
                border: '1px solid rgba(245,158,11,0.25)',
              }}>📖 Word Problem</div>
            )}
            <p style={{
              fontSize: 18, lineHeight: 1.75, color: 'var(--text-primary)',
              fontWeight: 400, letterSpacing: '0.1px',
            }}>
              {question.question_text}
            </p>
          </div>

          {/* Options */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 28 }}>
            {OPTIONS.map(opt => {
              const text = getOptionText(question, opt)
              if (!text) return null
              return (
                <button
                  key={opt}
                  id={`option-${opt}`}
                  className={`option-btn ${selected === opt ? 'selected' : ''}`}
                  onClick={() => setSelected(opt)}
                >
                  <span className="option-letter">{opt}</span>
                  <span style={{ flex: 1, lineHeight: 1.5 }}>{text}</span>
                </button>
              )
            })}
          </div>

          {error && (
            <div style={{
              padding: '12px 16px', borderRadius: 10, marginBottom: 16,
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444', fontSize: 14,
            }}>⚠ {error}</div>
          )}

          {/* Submit */}
          <button
            id="submit-answer-btn"
            className="btn-primary"
            onClick={handleSubmit}
            disabled={!selected || submitting}
            style={{ width: '100%', fontSize: 16, padding: '16px' }}
          >
            {submitting ? 'Processing…' : selected ? 'Confirm Answer →' : 'Select an answer to continue'}
          </button>

          <p style={{ textAlign: 'center', marginTop: 16, fontSize: 12, color: 'var(--text-muted)' }}>
            No right/wrong feedback shown during assessment · The engine adapts after each response
          </p>
        </div>
      </div>
    </div>
  )
}
