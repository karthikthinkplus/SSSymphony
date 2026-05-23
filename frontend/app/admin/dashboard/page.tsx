'use client'

import { useEffect, useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
  ResponsiveContainer, PieChart, Pie, Legend,
} from 'recharts'
import { adminApi } from '@/lib/api'

const TRAP_COLORS: Record<string, string> = {
  Concept_Error: '#ef4444', Calculation_Error: '#f59e0b',
  Careless_Slip: '#06b6d4', Sign_Error: '#8b5cf6',
  Procedural_Error: '#10b981', Reading_Error: '#f97316',
}

function StatCard({ label, value, icon, sub }: { label: string; value: string | number; icon: string; sub?: string }) {
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div style={{ fontSize: 28 }}>{icon}</div>
        <div style={{ fontSize: 28, fontWeight: 800, fontFamily: 'Outfit', color: 'var(--text-primary)' }}>{value}</div>
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

export default function DashboardPage() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    adminApi.getDashboard()
      .then(setData)
      .catch(() => setError('Could not load dashboard. Is the server running?'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
      <div style={{ width: 40, height: 40, border: '4px solid var(--accent-primary)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )

  if (error) return (
    <div style={{ textAlign: 'center', padding: 60, color: '#ef4444' }}>
      <div style={{ fontSize: 32, marginBottom: 12 }}>⚠</div>
      <p>{error}</p>
    </div>
  )

  const gradeData = Object.entries(data?.avg_score_by_grade || {}).map(([g, v]) => ({ grade: `Gr ${g}`, score: v }))
  const trapData = Object.entries(data?.trap_type_distribution || {}).map(([name, count]) => ({
    name: name.replace('_', ' '), count, fill: TRAP_COLORS[name] || '#6366f1',
  }))

  return (
    <div>
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, fontFamily: 'Outfit', marginBottom: 6 }}>Dashboard</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Overview of all assessment activity</p>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 32 }}>
        <StatCard icon="👤" label="Total Students" value={data?.total_students ?? 0} />
        <StatCard icon="📝" label="Total Sessions" value={data?.total_sessions ?? 0} />
        <StatCard icon="📅" label="This Week" value={data?.sessions_this_week ?? 0} sub="Assessments completed" />
        <StatCard icon="📚" label="Grades Covered" value="5–10" sub="NCERT curriculum" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 32 }}>
        {/* Grade performance */}
        <div className="glass-card" style={{ padding: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Average Score by Grade</h2>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>Accuracy % across completed sessions</p>
          {gradeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={gradeData}>
                <XAxis dataKey="grade" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis tick={{ fill: '#64748b', fontSize: 11 }} domain={[0, 100]} />
                <Tooltip contentStyle={{ background: '#1a2235', border: '1px solid #2d3748', borderRadius: 8, color: '#f1f5f9' }} />
                <Bar dataKey="score" fill="#6366f1" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '60px 0' }}>No completed sessions yet</p>}
        </div>

        {/* Error taxonomy */}
        <div className="glass-card" style={{ padding: 28 }}>
          <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Error Distribution</h2>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>Trap types across all assessments</p>
          {trapData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={trapData} layout="vertical" margin={{ left: 0, right: 16 }}>
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} />
                <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 11 }} width={120} />
                <Tooltip contentStyle={{ background: '#1a2235', border: '1px solid #2d3748', borderRadius: 8, color: '#f1f5f9' }} />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {trapData.map((e, i) => <Cell key={i} fill={e.fill} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '60px 0' }}>No error data yet</p>}
        </div>
      </div>

      {/* Top failing skills */}
      <div className="glass-card" style={{ padding: 28 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Top Skills with Knowledge Gaps</h2>
        <p style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 20 }}>Skills where most students have BKT P(L) ≤ 0.30</p>
        {(data?.top_failing_skills || []).length > 0 ? (
          <table className="data-table">
            <thead>
              <tr>
                <th>Skill</th>
                <th>Grade</th>
                <th>Students with Gap</th>
              </tr>
            </thead>
            <tbody>
              {(data?.top_failing_skills || []).map((s: any, i: number) => (
                <tr key={i}>
                  <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{s.skill_name}</td>
                  <td>Grade {s.grade_level}</td>
                  <td>
                    <span style={{
                      padding: '3px 10px', borderRadius: 99, fontSize: 12, fontWeight: 700,
                      background: 'rgba(239,68,68,0.15)', color: '#ef4444',
                    }}>{s.gap_count}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px 0' }}>
            No gap data yet — run some assessments first
          </p>
        )}
      </div>
    </div>
  )
}
