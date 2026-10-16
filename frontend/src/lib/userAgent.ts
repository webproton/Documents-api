// Order matters: Edge and Opera also contain "Chrome", Chrome contains "Safari"
const BROWSERS: [RegExp, string][] = [
  [/Edg\//, 'Edge'],
  [/OPR\/|Opera/, 'Opera'],
  [/Firefox\//, 'Firefox'],
  [/Chrome\//, 'Chrome'],
  [/Safari\//, 'Safari'],
]

const SYSTEMS: [RegExp, string][] = [
  [/iPhone|iPad/, 'iOS'],
  [/Android/, 'Android'],
  [/Windows/, 'Windows'],
  [/Mac OS X|Macintosh/, 'macOS'],
  [/Linux/, 'Linux'],
]

const match = (ua: string, rules: [RegExp, string][]) =>
  rules.find(([pattern]) => pattern.test(ua))?.[1]

/** Short label for a User-Agent string, e.g. "Chrome on macOS". */
export function describeUserAgent(ua: string): string {
  const browser = match(ua, BROWSERS)
  const system = match(ua, SYSTEMS)

  if (browser && system) return `${browser} on ${system}`
  return browser ?? system ?? 'Unknown device'
}
