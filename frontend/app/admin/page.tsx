'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { adminApi } from '@/lib/api'

export default function AdminLoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleLogin = async () => {
    if (!username || !password) { setError('Enter username and password'); return }
    setLoading(true)
    setError('')
    try {
      const res = await adminApi.login(username, password)
      localStorage.setItem('admin_token', res.access_token)
      localStorage.setItem('admin_role', res.role)
      router.push('/admin/dashboard')
    } catch {
      setError('Invalid credentials. Default: admin / admin123')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg-primary)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div style={{ width: '100%', maxWidth: 420, padding: '0 24px' }}>
        <div style={{ textAlign: 'center', marginBottom: 40 }}>
          <span style={{ fontSize: 40, display: 'block', marginBottom: 12 }}>🎓</span>
          <h1 style={{ fontSize: 28, fontWeight: 800, fontFamily: 'Outfit' }}>
            <span className="gradient-text">Adapti+ Learn</span> Admin
          </h1>
          <p style={{ color: 'var(--text-muted)', marginTop: 6, fontSize: 14 }}>Teacher & Administrator Portal</p>
        </div>

        <div className="glass-card" style={{ padding: 36 }}>
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
              Username
            </label>
            <input
              id="admin-username"
              className="input-field"
              placeholder="admin"
              value={username}
              onChange={e => setUsername(e.target.value)}
            />
          </div>
          <div style={{ marginBottom: 28 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
              Password
            </label>
            <input
              id="admin-password"
              className="input-field"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleLogin()}
            />
          </div>

          {error && (
            <div style={{
              padding: '10px 14px', borderRadius: 8, marginBottom: 20,
              background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
              color: '#ef4444', fontSize: 13,
            }}>{error}</div>
          )}

          <button
            id="admin-login-btn"
            className="btn-primary"
            onClick={handleLogin}
            disabled={loading}
            style={{ width: '100%' }}
          >
            {loading ? 'Signing in…' : 'Sign In →'}
          </button>

          <p style={{ marginTop: 20, textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
            Default credentials: <code style={{ color: 'var(--accent-primary)' }}>admin / admin123</code>
          </p>
        </div>

        <div style={{ textAlign: 'center', marginTop: 20 }}>
          <a href="/" style={{ color: 'var(--text-muted)', fontSize: 13, textDecoration: 'none' }}>← Student Assessment</a>
        </div>
      </div>
    </div>
  )
}
