// The one reading of the dates the server sends (dateTime.ts): an ISO 8601
// date-time that is a real one in every engine, the calendar included
// (gameplay/history.md rule 2, lobby/summaries.md rule 2).

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { isDateTime } from '../../web/src/lib/dateTime'

const REAL_DATE_TIMES = [
  '2026-10-14T08:30:00Z',
  '2028-02-29T09:30:00.5+01:00',
  '2026-12-31T23:59:59Z',
  '2026-01-01T00:00:00-23:59',
  '2026-04-30T08:30:00+23:59',
]

const IMPOSSIBLE_DATE_TIMES = [
  '2026-02-30T08:30:00Z',
  '2026-02-29T08:30:00Z',
  '2026-04-31T08:30:00Z',
  '2026-13-01T08:30:00Z',
  '2026-00-10T08:30:00Z',
  '2026-10-00T08:30:00Z',
  '2026-10-14T24:00:00Z',
  '2026-10-14T08:60:00Z',
  '2026-10-14T08:30:60Z',
  '2026-10-14T08:30:00+24:00',
  '2026-10-14T08:30:00+01:60',
]

const NOT_ISO_VALUES: unknown[] = [
  '2026-10-14 08:30:00Z',
  '2026-10-14',
  'yesterday',
  '',
  20261014,
  null,
  undefined,
]

test('a real ISO date-time is one, leap day and offsets included', () => {
  for (const value of REAL_DATE_TIMES) {
    assert.equal(isDateTime(value), true, value)
  }
})

test('a date-time the calendar does not have is not one', () => {
  for (const value of IMPOSSIBLE_DATE_TIMES) {
    assert.equal(isDateTime(value), false, value)
  }
})

test('a value that is not an ISO 8601 date-time string is not one', () => {
  for (const value of NOT_ISO_VALUES) {
    assert.equal(isDateTime(value), false, String(value))
  }
})
