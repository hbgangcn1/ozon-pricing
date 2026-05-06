import { describe, it, expect } from 'vitest'
import { safeReturnTo } from '../lib/safeReturnTo'

describe('safeReturnTo', () => {
  describe('returns fallback for invalid input', () => {
    it.each([
      undefined,
      null,
      '',
      123,
      {},
      [],
    ])('returns /pricing for %s', (input) => {
      expect(safeReturnTo(input)).toBe('/pricing')
    })
  })

  describe('returns fallback for non-absolute paths', () => {
    it.each([
      'pricing',
      'relative/path',
      'http://evil.com',
      'https://evil.com/path',
    ])('returns /pricing for %s', (input) => {
      expect(safeReturnTo(input)).toBe('/pricing')
    })
  })

  describe('returns fallback for protocol-relative URLs (XSS vector)', () => {
    it.each([
      '//evil.com',
      '//evil.com/x',
    ])('returns /pricing for %s', (input) => {
      expect(safeReturnTo(input)).toBe('/pricing')
    })
  })

  describe('returns fallback for root and auth paths', () => {
    it.each([
      '/',
      '/login',
      '/login/',
      '/login?reason=expired',
      '/login#hash',
      '/register',
      '/register/step2',
      '/forgot-password',
      '/forgot-password?token=x',
    ])('returns /pricing for %s', (input) => {
      expect(safeReturnTo(input)).toBe('/pricing')
    })
  })

  describe('passes through valid business paths preserving query/hash', () => {
    it.each([
      ['/pricing', '/pricing'],
      ['/settings', '/settings'],
      ['/logistics', '/logistics'],
      ['/users', '/users'],
      ['/pricing?id=1', '/pricing?id=1'],
      ['/settings#section', '/settings#section'],
      ['/pricing?a=1&b=2#x', '/pricing?a=1&b=2#x'],
    ])('returns %s for %s', (input, expected) => {
      expect(safeReturnTo(input)).toBe(expected)
    })
  })

  describe('paths starting with auth prefix but distinct (NOT fallback)', () => {
    it.each([
      ['/loginx', '/loginx'],
      ['/registers', '/registers'],
      ['/forgot-password-help', '/forgot-password-help'],
    ])('returns %s for %s', (input, expected) => {
      expect(safeReturnTo(input)).toBe(expected)
    })
  })

  describe('custom fallback parameter', () => {
    it.each([
      ['/login', '/dashboard', '/dashboard'],
      [null, '/home', '/home'],
      ['/pricing', '/home', '/pricing'],
    ])('returns %s for %s with fallback %s', (input, fallback, expected) => {
      expect(safeReturnTo(input, fallback)).toBe(expected)
    })
  })
})
