'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'

const NAV = [
  { href: '/admin/dashboard', label: 'Dashboard', icon: '📊' },
  { href: '/admin/students', label: 'Students', icon: '👥' },
  { href: '/admin/cohort', label: 'Cohort Analytics', icon: '📈' },
  { href: '/admin/questions', label: 'Question Bank', icon: '📚' },
  { href: '/admin/import', label: 'Import Excel', icon: '📥' },
]

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [role, setRole] = useState('')

  useEffect(() => {
    if (pathname === '/admin') return  // login page
    const token = localStorage.getItem('admin_token')
    if (!token) { router.push('/admin'); return }
    setRole(localStorage.getItem('admin_role') || 'teacher')
  }, [pathname])

  if (pathname === '/admin') return <>{children}</>

  const handleLogout = () => {
    localStorage.removeItem('admin_token')
    localStorage.removeItem('admin_role')
    router.push('/admin')
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* Sidebar */}
      <div className="admin-sidebar">
        <div style={{ padding: '28px 24px 20px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ fontSize: 20, fontWeight: 800, fontFamily: 'Outfit', marginBottom: 4 }}>
            <span className="gradient-text">Adapti+ Learn</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Admin Portal
          </div>
        </div>

        <nav style={{ padding: '12px 12px', flex: 1 }}>
          {NAV.map(item => {
            const active = pathname.startsWith(item.href)
            return (
              <a
                key={item.href}
                href={item.href}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '11px 14px', borderRadius: 10, marginBottom: 2,
                  textDecoration: 'none', fontSize: 14, fontWeight: active ? 600 : 500,
                  background: active ? 'rgba(99,102,241,0.15)' : 'transparent',
                  color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                  borderLeft: active ? '3px solid var(--accent-primary)' : '3px solid transparent',
                  transition: 'all 0.2s',
                }}
              >
                <span style={{ fontSize: 16 }}>{item.icon}</span>
                {item.label}
              </a>
            )
          })}
        </nav>

        <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)' }}>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 10 }}>
            Logged in as <strong style={{ color: 'var(--text-secondary)' }}>{role}</strong>
          </div>
          <button
            onClick={handleLogout}
            className="btn-secondary"
            style={{ width: '100%', padding: '8px 16px', fontSize: 13 }}
          >
            Sign Out
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="admin-content" style={{ flex: 1 }}>
        {children}
      </div>
    </div>
  )
}
