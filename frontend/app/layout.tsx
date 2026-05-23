import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Symphony — Adaptive Math Assessment',
  description: 'AI-powered adaptive mathematics assessment for Indian school students (Grades 5–10), aligned to NCERT curriculum.',
  keywords: 'adaptive learning, mathematics, NCERT, IRT, cognitive diagnostic, India, school assessment',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  )
}
