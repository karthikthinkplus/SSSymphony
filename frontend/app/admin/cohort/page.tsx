'use client'

import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer,
} from 'recharts'
import { adminApi } from '@/lib/api'

const TRAP_COLORS: Record<string, string> = {
  Concept_Error: '#ef4444', Calculation_Error: '#f59e0b',
  Careless_Slip: '#06b6d4', Sign_Error: '#8b5cf6',
  Procedural_Error: '#10b981', Reading_Error: '#f97316',
}

export default function CohortPage() {
  const [grade, setGrade] = useState(8)
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const fetchCohort = async (g: number) => {
    setLoading(true)
    try { setData(await adminApi.getCohort(g)) }
    catch { setData(null) }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchCohort(grade) }, [grade])

  const failureData = (data?.skill_failure_rates || []).map((s: any) => ({
    name: s.skill_name.length > 22 ? s.skill_name.substring(0, 22) + '…' : s.skill_name,
    rate: s.failure_rate,
  }))

  const trapData = Object.entries(data?.trap_type_counts || {}).map(([name, count]) => ({
    name: name.replace('_', ' '), count, fill: TRAP_COLORS[name] || '#6366f1',
  }))

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, fontFamily: 'Outfit', marginBottom: 6 }}>Cohort Analytics</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Grade-level performance, error patterns, and prerequisite gaps</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[5,6,7,8,9,10].map(g => (
            <button key={g} onClick={() => setGrade(g)} style={{
              padding: '8px 16px', borderRadius: 10, fontSize: 14, fontWeight: 600, cursor: 'pointer',
              background: grade === g ? 'rgba(99,102,241,0.2)' : 'transparent',
              border: grade === g ? '1.5px solid var(--accent-primary)' : '1.5px solid var(--border)',
              color: grade === g ? 'var(--text-primary)' : 'var(--text-muted)', transition: 'all 0.2s',
            }}>Grade {g}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>Loading Grade {grade} data…</div>
      ) : !data ? (
        <div style={{ textAlign: 'center', padding: 80, color: 'var(--text-muted)' }}>No data for Grade {grade}</div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 28 }}>
            {[
              { icon: '👥', label: 'Students', value: data.student_count },
              { icon: '⚡', label: 'Avg θ (Ability)', value: data.avg_theta?.toFixed(2) ?? '—' },
              { icon: '📚', label: 'Skills Tracked', value: data.skill_failure_rates?.length ?? 0 },
            ].map(s => (
              <div key={s.label} className="stat-card" style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>{s.icon}</div>
                <div style={{ fontSize: 28, fontWeight: 800, fontFamily: 'Outfit' }}>{s.value}</div>
                <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{s.label}</div>
              </div>
            ))}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
            <div className="glass-card" style={{ padding: 28 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Skill Failure Rates</h2>
              {failureData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={failureData} layout="vertical">
                    <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} domain={[0, 100]} tickFormatter={(v: any) => `${v}%`} />
                    <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 11 }} width={140} />
                    <Tooltip contentStyle={{ background: '#1a2235', border: '1px solid #2d3748', borderRadius: 8, color: '#f1f5f9' }} formatter={(v: any) => [`${v}%`, 'Failure Rate']} />
                    <Bar dataKey="rate" fill="#ef4444" radius={[0, 6, 6, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '80px 0' }}>No data yet</p>}
            </div>

            <div className="glass-card" style={{ padding: 28 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Error Type Distribution</h2>
              {trapData.length > 0 ? (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={trapData}>
                    <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} />
                    <YAxis tick={{ fill: '#64748b', fontSize: 11 }} />
                    <Tooltip contentStyle={{ background: '#1a2235', border: '1px solid #2d3748', borderRadius: 8, color: '#f1f5f9' }} />
                    <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                      {trapData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '80px 0' }}>No error data yet</p>}
            </div>
          </div>

          {(data.prerequisite_gaps || []).length > 0 && (
            <div className="glass-card" style={{ padding: 28 }}>
              <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Prerequisite Gap Tracker</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {data.prerequisite_gaps.map((g: any, i: number) => (
                  <div key={i} style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    padding: '14px 20px', borderRadius: 10,
                    background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.15)',
                  }}>
                    <div>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{g.skill_name}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 10 }}>Grade {g.grade_level}</span>
                    </div>
                    <span style={{
                      padding: '4px 12px', borderRadius: 99, fontSize: 12, fontWeight: 700,
                      background: 'rgba(239,68,68,0.15)', color: '#ef4444',
                    }}>{g.occurrence_count} students</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
