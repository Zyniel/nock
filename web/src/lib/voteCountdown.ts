// The countdown of an open vote (spec 047): the seconds left and the share of the
// time left, read from the page's own clock. Plain functions: no DOM.

import type { VoteClock } from './roomSession'

// How often the banner reads the clock again: its seconds and its bar move in
// steps of this length, with no transition.
export const VOTE_TICK_MS = 250

export interface VoteCountdown {
  // The whole seconds left, rounded up: 20 when the vote opens, 0 once the time
  // is up.
  seconds: number
  // The share of the vote's time left, from 1 down to 0.
  share: number
}

// The countdown of a vote at the clock reading `nowMs` (performance.now()). A
// reading from before the opening counts as the opening itself.
export function voteCountdown(clock: VoteClock, nowMs: number): VoteCountdown {
  const elapsedMs = Math.max(0, nowMs - clock.openedMs)
  const leftMs = Math.max(0, clock.durationMs - elapsedMs)
  return {
    seconds: Math.ceil(leftMs / 1000),
    share: leftMs / clock.durationMs,
  }
}
