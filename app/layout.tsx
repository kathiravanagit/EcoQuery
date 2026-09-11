import { Analytics } from '@vercel/analytics/next'
import { Geist, Geist_Mono } from 'next/font/google'
import type { Metadata, Viewport } from 'next'
import './globals.css'

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' })
const geistMono = Geist_Mono({ subsets: ['latin'], variable: '--font-mono' })

export const metadata: Metadata = {
  title: 'EcoQuery — Lower-impact AI, with receipts',
  description: 'Route AI inference intelligently, measure its footprint, and give your team an auditable path to lower-impact AI.',
  generator: 'EcoQuery',
  metadataBase: new URL('https://eco2query.vercel.app'),
  openGraph: { title: 'EcoQuery — Lower-impact AI, with receipts', description: 'The control plane for lower-impact AI.', type: 'website', url: 'https://eco2query.vercel.app' },
  icons: { icon: '/icon.svg' },
}

export const viewport: Viewport = { colorScheme: 'dark', themeColor: '#10221b', width: 'device-width', initialScale: 1, viewportFit: 'cover' }

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className="bg-background"><body className={`${geist.variable} ${geistMono.variable} antialiased`}>{children}{process.env.NODE_ENV === 'production' && <Analytics />}</body></html>
}
