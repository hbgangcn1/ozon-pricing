export function safeReturnTo(rt, fallback = '/pricing') {
  if (typeof rt !== 'string' || !rt.trim()) {
    return fallback;
  }

  if (!rt.startsWith('/') || rt.startsWith('//') || rt === '/') {
    return fallback;
  }

  const path = rt.split('?')[0].split('#')[0];

  if (/^\/(login|register|forgot-password)(\/|$)/.test(path)) {
    return fallback;
  }

  return rt;
}
