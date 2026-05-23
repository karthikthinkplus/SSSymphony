'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  Tooltip, Cell,
} from 'recharts'
import { sessionApi, ReportData } from '@/lib/api'

const COLORS_RADAR = '#6366f1'
const TRAP_COLOR_MAP: Record<string, string> = {
  Concept_Error: '#ef4444',
  Calculation_Error: '#f59e0b',
  Careless_Slip: '#06b6d4',
  Sign_Error: '#8b5cf6',
  Procedural_Error: '#10b981',
  Reading_Error: '#f97316',
}

function MasteryBar({ p, status }: { p: number; status: string }) {
  const colorClass = status === 'Mastered' ? 'success' : status === 'Gap' ? 'danger' : 'warning'
  const pct = Math.round(p * 100)
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
      <div style={{ flex: 1 }}>
        <div className="progress-bar">
          <div className={`progress-fill ${colorClass}`} style={{ width: `${pct}%` }} />
        </div>
      </div>
      <span style={{ minWidth: 36, fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', textAlign: 'right' }}>
        {pct}%
      </span>
      <span className={`skill-badge ${status.toLowerCase()}`}>{status}</span>
    </div>
  )
}

export default function ReportPage() {
  const params = useParams()
  const router = useRouter()
  const sessionId = params?.session_id as string
  const [report, setReport] = useState<ReportData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionId) return
    sessionApi.getReport(sessionId)
      .then(setReport)
      .catch(() => setError('Could not load report. Please try again.'))
      .finally(() => setLoading(false))
  }, [sessionId])

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ width: 56, height: 56, border: '4px solid var(--accent-primary)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite', margin: '0 auto 20px' }} />
          <p style={{ color: 'var(--text-muted)', fontSize: 15 }}>Generating your diagnostic report…</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ color: '#ef4444', marginBottom: 16 }}>{error || 'Report not found'}</p>
          <button className="btn-secondary" onClick={() => router.push('/')}>← Back to Home</button>
        </div>
      </div>
    )
  }

  const radarData = [
    { subject: 'Reading', value: report.dimension_scores.reading },
    { subject: 'Understanding', value: report.dimension_scores.understanding },
    { subject: 'Application', value: report.dimension_scores.application },
    { subject: 'Calculation', value: report.dimension_scores.calculation },
    { subject: 'Retention', value: report.dimension_scores.retention },
  ]

  const trapData = Object.entries(report.error_taxonomy).map(([name, count]) => ({ name: name.replace('_', ' '), count, fill: TRAP_COLOR_MAP[name] || '#6366f1' }))

  const scoreColor = report.accuracy_pct >= 75 ? '#10b981' : report.accuracy_pct >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ background: 'var(--bg-primary)', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.1) 50%, rgba(6,182,212,0.08) 100%)',
        borderBottom: '1px solid var(--border)', padding: '48px 0 40px',
      }}>
        <div style={{ maxWidth: 1000, margin: '0 auto', padding: '0 32px' }}>
          <div style={{ marginBottom: 8 }}>
            <button className="btn-secondary" onClick={() => router.push('/')} style={{ padding: '8px 16px', fontSize: 13 }}>
              ← New Assessment
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 24, marginTop: 24 }}>
            <div>
              <h1 style={{ fontSize: 38, fontWeight: 800, marginBottom: 8 }}>
                {report.student_name}'s <span className="gradient-text">Diagnostic Report</span>
              </h1>
              {report.school && <p style={{ color: 'var(--text-muted)', fontSize: 15 }}>{report.school} · Grade {report.selected_grade}</p>}
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 64, fontWeight: 900, fontFamily: 'Outfit', color: scoreColor, lineHeight: 1 }}>
                {report.accuracy_pct}%
              </div>
              <div style={{ fontSize: 14, color: 'var(--text-muted)', marginTop: 4 }}>Overall Accuracy</div>
              <div style={{
                marginTop: 8, padding: '6px 16px', borderRadius: 99, display: 'inline-block',
                background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)',
                fontSize: 13, color: 'var(--accent-primary)', fontWeight: 600,
              }}>
                Performing at Grade {report.grade_equivalent_level} Level
              </div>
            </div>
          </div>

          {/* Quick stats */}
          <div style={{ display: 'flex', gap: 16, marginTop: 28, flexWrap: 'wrap' }}>
            {[
              { label: 'Questions', value: report.total_questions },
              { label: 'Correct', value: report.correct_answers },
              { label: 'Grade Equiv.', value: `Gr ${report.grade_equivalent_level}` },
              { label: 'Skills Assessed', value: report.skill_mastery.length },
              ...(report.reading_gap_detected ? [{ label: 'Reading Gap', value: `${report.reading_gap_pct}%`, warn: true }] : []),
            ].map((s, i) => (
              <div key={i} style={{
                padding: '12px 20px', borderRadius: 12,
                background: (s as any).warn ? 'rgba(239,68,68,0.1)' : 'rgba(99,102,241,0.08)',
                border: `1px solid ${(s as any).warn ? 'rgba(239,68,68,0.3)' : 'rgba(99,102,241,0.2)'}`,
              }}>
                <div style={{ fontSize: 22, fontWeight: 800, fontFamily: 'Outfit', color: (s as any).warn ? '#ef4444' : 'var(--text-primary)' }}>{s.value}</div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '40px 32px' }}>

        {/* Narrative card */}
        <div className="glass-card animate-fade-in-up" style={{ padding: 32, marginBottom: 28, borderLeft: '3px solid var(--accent-primary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <span style={{ fontSize: 20 }}>🧠</span>
            <h2 style={{ fontSize: 17, fontWeight: 700 }}>AI Diagnostic Summary</h2>
          </div>
          <p style={{ color: 'var(--text-secondary)', lineHeight: 1.8, fontSize: 15 }}>{report.narrative}</p>
        </div>

        {/* Radar + Error taxonomy */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 28 }}>
          {/* Radar */}
          <div className="glass-card" style={{ padding: 28 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 4 }}>5-Dimension Profile</h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>Scores across learning dimensions</p>
            <ResponsiveContainer width="100%" height={260}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(99,102,241,0.15)" />
                <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <Radar
                  name="Score"
                  dataKey="value"
                  stroke="#6366f1"
                  fill="#6366f1"
                  fillOpacity={0.25}
                  strokeWidth={2}
                />
              </RadarChart>
            </ResponsiveContainer>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 12 }}>
              {radarData.map(d => (
                <div key={d.subject} style={{ textAlign: 'center', padding: '8px', borderRadius: 8, background: 'rgba(99,102,241,0.05)' }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--accent-primary)' }}>{d.value}%</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{d.subject}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Error taxonomy */}
          <div className="glass-card" style={{ padding: 28 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 4 }}>Error Taxonomy</h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>Breakdown of incorrect responses</p>
            {trapData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={trapData} layout="vertical" margin={{ left: 0, right: 16 }}>
                  <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} />
                  <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 11 }} width={120} />
                  <Tooltip
                    contentStyle={{ background: '#1a2235', border: '1px solid var(--border)', borderRadius: 8, color: '#f1f5f9' }}
                  />
                  <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                    {trapData.map((entry, index) => <Cell key={index} fill={entry.fill} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
                <p>No errors recorded yet</p>
              </div>
            )}
          </div>
        </div>

        {/* Skill mastery */}
        <div className="glass-card animate-fade-in-up" style={{ padding: 28, marginBottom: 28 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 4 }}>Skill Mastery Breakdown</h2>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 24 }}>BKT probability of mastery per skill encountered</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            {report.skill_mastery.map(skill => (
              <div key={skill.skill_id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <div>
                    <span style={{ fontSize: 14, fontWeight: 600 }}>{skill.skill_name}</span>
                    <span style={{ marginLeft: 10, fontSize: 12, color: 'var(--text-muted)' }}>
                      Grade {skill.grade_level} · {skill.topic_area}
                    </span>
                  </div>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{skill.attempts} attempt{skill.attempts !== 1 ? 's' : ''}</span>
                </div>
                <MasteryBar p={skill.p_mastery} status={skill.status} />
              </div>
            ))}
            {report.skill_mastery.length === 0 && (
              <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>No skills assessed yet.</p>
            )}
          </div>
        </div>

        {/* Reading gap alert */}
        {report.reading_gap_detected && (
          <div className="animate-fade-in-up" style={{
            padding: 24, borderRadius: 16, marginBottom: 28,
            background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.3)',
          }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <span style={{ fontSize: 24 }}>📖</span>
              <div>
                <h3 style={{ fontSize: 16, fontWeight: 700, color: '#f59e0b', marginBottom: 6 }}>Reading Comprehension Gap Detected</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 14, lineHeight: 1.7 }}>
                  {report.reading_gap_pct.toFixed(0)}% of word problem failures were resolved when presented as pure equations.
                  This suggests a language comprehension barrier rather than a mathematical concept gap.
                  <strong style={{ color: '#f59e0b' }}> Strong in math, struggles with English word problems.</strong>
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Foundational gap chain */}
        {report.foundational_gap_chain.length > 0 && (
          <div className="glass-card animate-fade-in-up" style={{ padding: 28, marginBottom: 28 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 4 }}>Root Cause Chain</h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 24 }}>Knowledge graph traversal during your assessment</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {report.foundational_gap_chain.map((item, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{
                    padding: '8px 16px', borderRadius: 10,
                    background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
                    fontSize: 13,
                  }}>
                    <div style={{ fontWeight: 600 }}>{item.from_skill}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Grade {item.from_grade}</div>
                  </div>
                  <div style={{ color: 'var(--accent-primary)', fontSize: 20 }}>→</div>
                  <div style={{
                    padding: '8px 16px', borderRadius: 10,
                    background: 'rgba(99,102,241,0.1)', border: '1px solid rgba(99,102,241,0.2)',
                    fontSize: 13,
                  }}>
                    <div style={{ fontWeight: 600 }}>{item.to_skill}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Grade {item.to_grade}</div>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 4 }}>
                    ({item.reason})
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recommended focus areas */}
        {report.recommended_skills.length > 0 && (
          <div className="glass-card animate-fade-in-up" style={{ padding: 28 }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, marginBottom: 4 }}>Recommended Focus Areas</h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>Top skills to strengthen next</p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {report.recommended_skills.map((skill, i) => (
                <div key={skill.skill_id} style={{
                  display: 'flex', alignItems: 'center', gap: 16,
                  padding: '16px 20px', borderRadius: 12,
                  background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)',
                }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: 'white',
                    fontSize: 14, fontWeight: 700, flexShrink: 0,
                  }}>{i + 1}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>{skill.skill_name}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                      Grade {skill.grade_level} · {skill.ncert_ref}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ marginTop: 40, textAlign: 'center' }}>
          <button className="btn-primary" onClick={() => router.push('/')} style={{ marginRight: 12 }}>
            Take Another Assessment
          </button>
          <a href="/admin" style={{ textDecoration: 'none' }}>
            <button className="btn-secondary">Teacher Dashboard →</button>
          </a>
        </div>
      </div>
    </div>
  )
}
