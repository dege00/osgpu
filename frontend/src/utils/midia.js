export function urlMidia(url) {
  if (!url) return ''
  if (!/^https?:\/\//i.test(url)) return url
  try {
    const u = new URL(url)
    return `${u.pathname}${u.search}${u.hash}`
  } catch {
    return url
  }
}
