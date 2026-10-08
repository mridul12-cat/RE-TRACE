import React from 'react'

export const metadata = {
  title: 'RE:TRACE — Verifiable Circular Economy & Climate Tracking',
  description: 'Digital Product Passports, AI Visual Observation, Deterministic Mass-Balance & Local EVM Blockchain Anchor',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-slate-950 text-slate-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}
