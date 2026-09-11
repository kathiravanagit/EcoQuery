'use client'

import { useState } from 'react'
import { ArrowRight, Check, ChevronRight, CircleGauge, Leaf, Menu, Play, ShieldCheck, Sparkles, X, Zap } from 'lucide-react'

const trace = [
  { label: 'Intent classified', value: 'summarization', tone: 'green' },
  { label: 'Knowledge match', value: '96% confidence', tone: 'blue' },
  { label: 'Lowest-impact route', value: 'eu-west · 42 gCO₂e', tone: 'amber' },
]

export default function Page() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [demoRunning, setDemoRunning] = useState(false)

  return (
    <main className="min-h-screen overflow-hidden bg-background text-foreground">
      <header className="sticky top-0 z-50 border-b border-border/70 bg-background/90 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4 lg:px-8">
          <a href="#top" className="flex items-center gap-2 font-mono text-sm font-bold tracking-tight" aria-label="EcoQuery home">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Leaf className="size-4" /></span>
            <span>eco<span className="text-primary">query</span></span>
          </a>
          <nav className="hidden items-center gap-7 text-sm text-muted-foreground md:flex" aria-label="Main navigation">
            <a href="#how-it-works" className="transition-colors hover:text-foreground">How it works</a>
            <a href="#platform" className="transition-colors hover:text-foreground">Platform</a>
            <a href="#methodology" className="transition-colors hover:text-foreground">Methodology</a>
            <a href="#security" className="transition-colors hover:text-foreground">Security</a>
          </nav>
          <div className="hidden items-center gap-3 md:flex">
            <a href="#platform" className="rounded-lg px-4 py-2 text-sm text-muted-foreground hover:text-foreground">View demo</a>
            <a href="#contact" className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-transform hover:-translate-y-0.5">Get started <ArrowRight className="ml-1 inline size-4" /></a>
          </div>
          <button className="rounded-lg p-2 md:hidden" onClick={() => setMenuOpen(!menuOpen)} aria-label={menuOpen ? 'Close menu' : 'Open menu'} aria-expanded={menuOpen}>
            {menuOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
        {menuOpen && <nav className="border-t border-border px-5 py-4 md:hidden" aria-label="Mobile navigation"><div className="flex flex-col gap-4 text-sm"><a href="#how-it-works" onClick={() => setMenuOpen(false)}>How it works</a><a href="#platform" onClick={() => setMenuOpen(false)}>Platform</a><a href="#methodology" onClick={() => setMenuOpen(false)}>Methodology</a><a href="#contact" onClick={() => setMenuOpen(false)} className="font-semibold text-primary">Get started <ArrowRight className="ml-1 inline size-4" /></a></div></nav>}
      </header>

      <section id="top" className="mx-auto grid max-w-7xl gap-14 px-5 pb-24 pt-20 lg:grid-cols-[1.05fr_.95fr] lg:items-center lg:px-8 lg:pb-32 lg:pt-28">
        <div>
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3 py-1.5 font-mono text-xs text-primary"><Sparkles className="size-3.5" /> Sustainable inference, measured</div>
          <h1 className="max-w-3xl text-balance font-mono text-4xl font-bold tracking-[-0.06em] sm:text-5xl lg:text-7xl">The control plane for <span className="text-primary">lower-impact AI.</span></h1>
          <p className="mt-7 max-w-xl text-pretty text-base leading-7 text-muted-foreground sm:text-lg">EcoQuery routes every inference request to the right model and region, then shows your team what it cost in carbon, latency, and money.</p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row"><a href="#platform" className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/10 transition-transform hover:-translate-y-0.5">Explore the platform <ArrowRight className="size-4" /></a><a href="#how-it-works" className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-card px-5 py-3 text-sm font-semibold hover:bg-accent">See how it works <ChevronRight className="size-4" /></a></div>
          <div className="mt-10 flex flex-wrap gap-x-6 gap-y-3 text-xs text-muted-foreground"><span className="flex items-center gap-2"><Check className="size-3.5 text-primary" /> Provider-agnostic</span><span className="flex items-center gap-2"><Check className="size-3.5 text-primary" /> Auditable by default</span><span className="flex items-center gap-2"><Check className="size-3.5 text-primary" /> Built for teams</span></div>
        </div>
        <div id="platform" className="relative rounded-2xl border border-border bg-card p-3 shadow-2xl shadow-primary/5 sm:p-5"><div className="rounded-xl border border-border/80 bg-background"><div className="flex items-center justify-between border-b border-border px-4 py-3"><div className="flex items-center gap-2"><span className="size-2 rounded-full bg-primary" /><span className="font-mono text-xs text-muted-foreground">decision_trace.live</span></div><span className="rounded-full bg-primary/10 px-2 py-1 font-mono text-[10px] text-primary">LIVE DEMO</span></div><div className="p-5"><div className="mb-7 flex items-end justify-between"><div><p className="font-mono text-xs text-muted-foreground">REQUEST PREVIEW</p><p className="mt-2 text-lg font-semibold">Summarize the latest report</p></div><CircleGauge className="size-8 text-primary" /></div><div className="space-y-3">{trace.map((item, index) => <div key={item.label} className="flex items-center gap-3 rounded-xl border border-border bg-card p-3"><span className={`flex size-7 shrink-0 items-center justify-center rounded-full font-mono text-xs ${item.tone === 'green' ? 'bg-primary/15 text-primary' : item.tone === 'blue' ? 'bg-sky-500/15 text-sky-500' : 'bg-amber-500/15 text-amber-500'}`}>{index + 1}</span><div className="min-w-0 flex-1"><p className="text-xs text-muted-foreground">{item.label}</p><p className="truncate text-sm font-medium">{item.value}</p></div><Check className="size-4 text-primary" /></div>)}</div><button onClick={() => setDemoRunning(!demoRunning)} className="mt-5 flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-3 text-sm font-semibold text-primary-foreground hover:opacity-90"><Play className="size-4 fill-current" /> {demoRunning ? 'Routing complete · 42 gCO₂e' : 'Run a sample request'}</button></div></div></div>
      </section>

      <section id="how-it-works" className="border-y border-border bg-card/40"><div className="mx-auto max-w-7xl px-5 py-20 lg:px-8"><div className="max-w-2xl"><p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-primary">One layer, measurable impact</p><h2 className="mt-4 text-balance font-mono text-3xl font-bold tracking-[-0.04em] sm:text-4xl">Make every AI request count.</h2><p className="mt-4 leading-7 text-muted-foreground">From prompt to proof, EcoQuery gives your platform team the controls and evidence to improve inference without slowing delivery.</p></div><div className="mt-12 grid gap-4 md:grid-cols-3">{[{ icon: Zap, title: 'Route intelligently', copy: 'Select the best model and region based on intent, latency, cost, and grid intensity.' }, { icon: CircleGauge, title: 'Measure clearly', copy: 'Turn every request into a transparent record of energy, carbon, latency, and spend.' }, { icon: ShieldCheck, title: 'Prove progress', copy: 'Give engineering and sustainability teams a shared, exportable audit trail.' }].map(({ icon: Icon, title, copy }) => <article key={title} className="rounded-2xl border border-border bg-background p-6"><Icon className="size-5 text-primary" /><h3 className="mt-8 font-mono text-lg font-semibold">{title}</h3><p className="mt-3 text-sm leading-6 text-muted-foreground">{copy}</p></article>)}</div></div></section>

      <section id="methodology" className="mx-auto grid max-w-7xl gap-12 px-5 py-20 lg:grid-cols-[.8fr_1.2fr] lg:px-8"><div><p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-primary">Trust layer</p><h2 className="mt-4 text-balance font-mono text-3xl font-bold tracking-[-0.04em]">Metrics your sustainability team can stand behind.</h2><p className="mt-4 leading-7 text-muted-foreground">Every estimate is labeled, explainable, and tied to its inputs. No black-box green claims.</p></div><div className="grid gap-3 sm:grid-cols-2">{['Energy model assumptions', 'Grid-intensity source and refresh', 'Region and PUE factors', 'Estimated vs. measured output'].map((item) => <div key={item} className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 text-sm"><Check className="size-4 shrink-0 text-primary" />{item}</div>)}</div></section>

      <footer id="contact" className="border-t border-border bg-card/40"><div className="mx-auto flex max-w-7xl flex-col gap-5 px-5 py-10 sm:flex-row sm:items-center sm:justify-between lg:px-8"><div><a href="#top" className="font-mono text-sm font-bold">eco<span className="text-primary">query</span></a><p className="mt-2 text-xs text-muted-foreground">Lower-impact AI, with receipts.</p></div><div className="flex gap-5 text-xs text-muted-foreground"><a href="#security" className="hover:text-foreground">Security</a><a href="#methodology" className="hover:text-foreground">Methodology</a><a href="mailto:hello@ecoquery.dev" className="hover:text-foreground">Contact</a></div></div></footer>
    </main>
  )
}
