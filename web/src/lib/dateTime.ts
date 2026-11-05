// The one reading of the dates the server sends. Plain function: no DOM.

// An ISO 8601 date-time such as "2026-05-01T10:20:30.5Z": a fraction of a second
// is optional, the offset is "Z", "+hh:mm" or "-hh:mm". The groups are the year, month, day,
// hour, minute, second and, for a numeric offset, its hour and minute.
// `Date.parse` alone is lenient and differs between engines, so the calendar is
// checked on these fields instead.
const DATE_TIME_PATTERN =
  /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:Z|[+-](\d{2}):(\d{2}))$/

// Tell whether a year has a 29th of February.
function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0
}

// Count the days in a month (1 to 12) of a year.
function daysInMonth(year: number, month: number): number {
  if (month === 2) {
    return isLeapYear(year) ? 29 : 28
  }
  const thirtyDayMonths = [4, 6, 9, 11]
  return thirtyDayMonths.includes(month) ? 30 : 31
}

// Tell whether a value is an ISO 8601 date-time the calendar has.
export function isDateTime(value: unknown): value is string {
  if (typeof value !== 'string') {
    return false
  }
  const match = DATE_TIME_PATTERN.exec(value)
  if (match === null) {
    return false
  }
  const year = Number(match[1])
  const month = Number(match[2])
  const day = Number(match[3])
  const hour = Number(match[4])
  const minute = Number(match[5])
  const second = Number(match[6])
  // A "Z" offset has no hour or minute group.
  const offsetHour = Number(match[7] ?? 0)
  const offsetMinute = Number(match[8] ?? 0)

  const monthIsReal = month >= 1 && month <= 12
  if (!monthIsReal) {
    return false
  }
  const dayIsReal = day >= 1 && day <= daysInMonth(year, month)
  const timeIsReal = hour <= 23 && minute <= 59 && second <= 59
  const offsetIsReal = offsetHour <= 23 && offsetMinute <= 59
  return dayIsReal && timeIsReal && offsetIsReal
}
