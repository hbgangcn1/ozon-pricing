import { useEffect, useMemo, useRef } from 'react'

const DRAFT_PREFIX = 'draft:'
const DEFAULT_DEBOUNCE_MS = 350

function buildStorageKey(key) {
  return `${DRAFT_PREFIX}${key}`
}

function sanitizeDraft(value, excludeFields = []) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  const draft = { ...value }
  excludeFields.forEach((field) => {
    delete draft[field]
  })

  return draft
}

function readDraft(storageKey) {
  try {
    const raw = window.sessionStorage.getItem(storageKey)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function useDraftPersist(key, value, options = {}) {
  const {
    excludeFields = [],
    debounceMs = DEFAULT_DEBOUNCE_MS,
    enabled = true,
  } = options
  const storageKey = useMemo(() => buildStorageKey(key), [key])
  const initialSerializedRef = useRef(null)
  const hasMountedRef = useRef(false)
  const sanitizedDraft = useMemo(
    () => sanitizeDraft(value, excludeFields),
    [excludeFields, value],
  )
  const serializedDraft = useMemo(
    () => JSON.stringify(sanitizedDraft),
    [sanitizedDraft],
  )

  if (initialSerializedRef.current === null) {
    initialSerializedRef.current = serializedDraft
  }

  useEffect(() => {
    if (!enabled) return undefined

    if (!hasMountedRef.current) {
      hasMountedRef.current = true
      return undefined
    }

    if (serializedDraft === initialSerializedRef.current) {
      window.sessionStorage.removeItem(storageKey)
      return undefined
    }

    const timeoutId = window.setTimeout(() => {
      try {
        window.sessionStorage.setItem(storageKey, serializedDraft)
      } catch (error) {
        if (error?.name === 'QuotaExceededError') {
          console.warn(`Draft persistence skipped for ${storageKey}: quota exceeded`)
        }
      }
    }, debounceMs)

    return () => window.clearTimeout(timeoutId)
  }, [debounceMs, enabled, serializedDraft, storageKey])

  const loadDraft = () => {
    if (!enabled) return null
    return readDraft(storageKey)
  }

  const clearDraft = () => {
    if (!enabled) return
    window.sessionStorage.removeItem(storageKey)
  }

  const hasDraft = () => {
    if (!enabled) return false
    return loadDraft() !== null
  }

  return { loadDraft, clearDraft, hasDraft }
}

export default useDraftPersist
