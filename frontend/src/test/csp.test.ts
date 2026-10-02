import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

/**
 * Guards the CSP in vercel.json against the resources index.html actually loads.
 *
 * Both regressions this catches shipped silently: an inline service-worker
 * registration (blocked by script-src 'self', so the worker never registered)
 * and a Google Fonts <link> (origin absent from style-src, so the stylesheet
 * never loaded). Neither is visible without opening DevTools.
 */

/** Works whether vitest runs from `frontend/` or the repo root. */
function findFrontendRoot(): string {
  const candidates = [process.cwd(), resolve(process.cwd(), 'frontend')]
  const root = candidates.find(
    (dir) =>
      existsSync(resolve(dir, 'index.html')) && existsSync(resolve(dir, 'vercel.json')),
  )
  if (!root) throw new Error(`frontend root not found from ${process.cwd()}`)
  return root
}

const frontendRoot = findFrontendRoot()
const indexHtml = readFileSync(resolve(frontendRoot, 'index.html'), 'utf8')
const vercel = JSON.parse(readFileSync(resolve(frontendRoot, 'vercel.json'), 'utf8')) as {
  headers: Array<{ source: string; headers: Array<{ key: string; value: string }> }>
}

type Directives = Record<string, string[]>

function parseCsp(value: string): Directives {
  return value.split(';').reduce<Directives>((acc, part) => {
    const [name, ...sources] = part.trim().split(/\s+/).filter(Boolean)
    if (name) acc[name] = sources
    return acc
  }, {})
}

const cspHeader = vercel.headers
  .flatMap((rule) => rule.headers)
  .find((h) => h.key === 'Content-Security-Policy')?.value

const directives: Directives = cspHeader ? parseCsp(cspHeader) : {}

/** Same-origin paths need no allowance; only cross-origin URLs are checked. */
function originOf(url: string): string | null {
  if (url.startsWith('/')) return null
  const match = /^https?:\/\/[^/]+/.exec(url)
  return match ? match[0] : null
}

/** Everything index.html pulls in as an actual subresource, not a hint or meta tag. */
function loadedOrigins(): Array<{ directive: string; origin: string }> {
  const found: Array<{ directive: string; origin: string }> = []
  const push = (directive: string, url: string | undefined): void => {
    if (!url) return
    const origin = originOf(url)
    if (origin) found.push({ directive, origin })
  }

  for (const m of indexHtml.matchAll(/<script\b[^>]*\bsrc\s*=\s*["']([^"']+)["']/gi)) {
    push('script-src', m[1])
  }
  for (const m of indexHtml.matchAll(/<link\b[^>]*rel\s*=\s*["']stylesheet["'][^>]*>/gi)) {
    push('style-src', /\bhref\s*=\s*["']([^"']+)["']/i.exec(m[0])?.[1])
  }
  for (const m of indexHtml.matchAll(/<img\b[^>]*\bsrc\s*=\s*["']([^"']+)["']/gi)) {
    push('img-src', m[1])
  }
  return found
}

describe('Content Security Policy', () => {
  it('defines an app-wide CSP that does not allow inline scripts', () => {
    expect(cspHeader, 'vercel.json must set Content-Security-Policy').toBeTruthy()
    expect(directives['script-src']).toContain("'self'")
    expect(directives['script-src']).not.toContain("'unsafe-inline'")
    expect(directives['object-src']).toContain("'none'")
    expect(directives['frame-ancestors']).toContain("'none'")
  })

  it('has no executable inline <script> in index.html', () => {
    const scripts = [...indexHtml.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)]
    const inline = scripts.filter(([, attrs]) => !/\bsrc\s*=/.test(attrs))
    const executable = inline.filter(
      ([, attrs]) => !/type\s*=\s*["']application\/(ld\+)?json["']/i.test(attrs),
    )
    expect(executable.map(([, attrs]) => attrs.trim())).toEqual([])
  })

  it('keeps every cross-origin subresource inside its CSP directive', () => {
    const unallowed = loadedOrigins().filter(
      ({ directive, origin }) => !(directives[directive] ?? []).includes(origin),
    )
    expect(unallowed).toEqual([])
  })
})
