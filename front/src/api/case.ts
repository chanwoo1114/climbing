type Json = unknown

const toCamel = (s: string) => s.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase())
const toSnake = (s: string) => s.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`)

function convertKeys(value: Json, fn: (key: string) => string): Json {
  if (Array.isArray(value)) return value.map((v) => convertKeys(v, fn))
  if (value !== null && typeof value === 'object' && !(value instanceof Date)) {
    return Object.fromEntries(
      Object.entries(value as Record<string, Json>).map(([k, v]) => [fn(k), convertKeys(v, fn)]),
    )
  }
  return value
}

/** API 응답(snake_case) → 프론트(camelCase) */
export const keysToCamel = (value: Json): Json => convertKeys(value, toCamel)

/** 프론트(camelCase) → API 요청(snake_case) */
export const keysToSnake = (value: Json): Json => convertKeys(value, toSnake)
