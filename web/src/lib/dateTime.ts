// The one reading of the dates the server sends. Plain function: no DOM.

// An ISO 8601 date-time such as "2026-05-01T10:20:30.5Z": a fraction of a second
// is optional, the offset is "Z" or "+hh:mm". `Date.parse` alone is lenient and
// differs between engines.
const DATE_TIME_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$/

// Tell whether a value is an ISO 8601 date-time that reads as a date.
export function isDateTime(value: unknown): value is string {
  if (typeof value !== 'string' || !DATE_TIME_PATTERN.test(value)) {
    return false
  }
  return !Number.isNaN(Date.parse(value))
}
