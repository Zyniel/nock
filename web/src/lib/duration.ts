// The text of a duration, such as the median solving time of the operator's
// dashboard (spec 038), shared with the history of an account (spec 029).
// A plain function: no DOM.

import { t } from './i18n'
import { twoDigits } from './timer'

const SECONDS_PER_MINUTE = 60
const SECONDS_PER_HOUR = 3600

// The whole seconds of `milliseconds`, rounded down, as "12 min 30 s" under one
// hour ("0 min 05 s" for 5 seconds) and as "1 h 02 min 05 s" from one hour.
export function durationText(milliseconds: number): string {
  const totalSeconds = Math.floor(milliseconds / 1000)
  const hours = Math.floor(totalSeconds / SECONDS_PER_HOUR)
  const minutes = Math.floor((totalSeconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE)
  const seconds = twoDigits(totalSeconds % SECONDS_PER_MINUTE)
  if (hours === 0) {
    return t('duration.minutes', { minutes, seconds })
  }
  return t('duration.hours', { hours, minutes: twoDigits(minutes), seconds })
}
