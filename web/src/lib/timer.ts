// The shared timer of a room page (spec 027): the value it shows, its text and the
// choice to hide it. Plain functions: no DOM and no socket.

import { t } from './i18n'
import { readItem, removeItem, writeItem } from './storage'

// While the timer runs, the page works out the value to show again at least this
// often, in milliseconds.
export const TIMER_REFRESH_MS = 250

// The key that holds the choice to hide the timer, for every room opened in this
// browser. A hidden timer is the value "true"; a shown timer has no key.
export const TIMER_HIDDEN_KEY = 'nock.timer_hidden'
const TIMER_HIDDEN_VALUE = 'true'

const SECONDS_PER_MINUTE = 60
const SECONDS_PER_HOUR = 3600

// The value to show, in whole milliseconds: the time counted when `anchor` was
// read, plus the time since then while the timer runs. `anchor` and `now` are
// performance.now() readings.
export function timerValueMs(
  baseMs: number,
  isRunning: boolean,
  anchor: number,
  now: number,
): number {
  let value = baseMs
  if (isRunning) {
    value += Math.max(0, now - anchor)
  }
  return Math.max(0, Math.floor(value))
}

// A number on two digits: 5 gives "05". The duration text uses it too.
export function twoDigits(value: number): string {
  return String(value).padStart(2, '0')
}

// The text of a time: whole seconds, rounded down, as "m:ss" under one hour and
// as "h:mm:ss" from one hour.
export function timerText(elapsedMs: number): string {
  const totalSeconds = Math.floor(elapsedMs / 1000)
  const seconds = twoDigits(totalSeconds % SECONDS_PER_MINUTE)
  if (totalSeconds < SECONDS_PER_HOUR) {
    const minutes = Math.floor(totalSeconds / SECONDS_PER_MINUTE)
    return t('timer.minutes_seconds', { minutes, seconds })
  }
  const hours = Math.floor(totalSeconds / SECONDS_PER_HOUR)
  const minutesInHour = Math.floor((totalSeconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE)
  return t('timer.hours_minutes_seconds', { hours, minutes: twoDigits(minutesInHour), seconds })
}

// True when this browser hides the timer. A key that holds anything else than
// "true" counts as absent.
export function readTimerHidden(): boolean {
  return readItem(TIMER_HIDDEN_KEY) === TIMER_HIDDEN_VALUE
}

// Remember the choice of this browser: "true" under the key to hide the timer,
// no key to show it.
export function writeTimerHidden(isHidden: boolean): void {
  if (isHidden) {
    writeItem(TIMER_HIDDEN_KEY, TIMER_HIDDEN_VALUE)
    return
  }
  removeItem(TIMER_HIDDEN_KEY)
}
