// The chat and the reactions of a room page (spec 022): the lines the stream
// shows, the unread count and the new-events dot of « Salon » (spec 043), the
// pacing of my own messages and what a clue shows of a reaction. Plain
// functions: no DOM and no socket.

import { nameOf } from './activityFeed'
import type { KeptFeedItem } from './activityFeed'
import { clueKey } from './clueFlags'
import { t } from './i18n'
import type { ChatLine, ReactionValue, ShownReaction } from './roomSession'

// The chat list shows the newest lines only.
export const CHAT_LIST_LIMIT = 200

// The page sends at most PACE_LIMIT chat messages, and at most PACE_LIMIT
// reactions, in any PACE_WINDOW_MS. The server allows 5 in 10 seconds: the 2
// seconds more leave room for network jitter, so the server never drops a
// message of a working page.
export const PACE_LIMIT = 5
export const PACE_WINDOW_MS = 12000

// Above this many unread lines, the count reads "99+".
const UNREAD_SHOWN_MAX = 99

// The lines of the chat list: the newest CHAT_LIST_LIMIT of the history.
export function shownChatLines(history: ChatLine[]): ChatLine[] {
  if (history.length <= CHAT_LIST_LIMIT) {
    return history
  }
  return history.slice(history.length - CHAT_LIST_LIMIT)
}

// The lines that are unread: newer than `lastSeenSeq` and not written by me.
export function unreadCount(history: ChatLine[], lastSeenSeq: number, you: string): number {
  let count = 0
  for (const line of history) {
    if (line.seq > lastSeenSeq && line.player_id !== you) {
      count += 1
    }
  }
  return count
}

// The text of the unread badge: the count in digits, or "99+" above 99.
export function unreadBadgeText(count: number): string {
  if (count > UNREAD_SHOWN_MAX) {
    return t('chat.unread_many')
  }
  return String(count)
}

// The accessible name of the « Salon » button (spec 043): it names the unread
// messages while the badge shows them, the new activity while the new-events
// dot shows; null otherwise, so the button is named by its label.
export function salonToggleLabel(count: number, hasNewEvents: boolean): string | null {
  if (count > 0) {
    return t('topbar.salon_unread', { count })
  }
  if (hasNewEvents) {
    return t('topbar.salon_events')
  }
  return null
}

// True when the feed holds a line about another player newer than
// `lastSeenItemId`, the newest line of the last time the stream showed. The
// page gives each line a larger id than the lines before it, catch-up lines
// included. A line by no player (a closed vote, spec 047) does not count.
export function hasNewEventLines(
  feed: KeptFeedItem[],
  lastSeenItemId: number,
  you: string,
): boolean {
  for (const item of feed) {
    const isOtherPlayers = item.playerId !== null && item.playerId !== you
    if (item.id > lastSeenItemId && isOtherPlayers) {
      return true
    }
  }
  return false
}

// The id of the newest line of the feed, or 0 when it is empty. Catch-up lines
// are put in seq order, so the newest is not always the last.
export function newestFeedItemId(feed: KeptFeedItem[]): number {
  let newest = 0
  for (const item of feed) {
    if (item.id > newest) {
      newest = item.id
    }
  }
  return newest
}

// The send times that still count at `now`: those of the last PACE_WINDOW_MS.
export function sendsInWindow(sendTimes: number[], now: number): number[] {
  return sendTimes.filter((sendTime) => sendTime > now - PACE_WINDOW_MS)
}

// True while PACE_LIMIT messages were sent in the last PACE_WINDOW_MS.
export function isPaced(sendTimes: number[], now: number): boolean {
  return sendsInWindow(sendTimes, now).length >= PACE_LIMIT
}

// The milliseconds until the oldest of these send times stops counting, or
// null when none counts any more.
export function msUntilNextExpiry(sendTimes: number[], now: number): number | null {
  let soonest: number | null = null
  for (const sendTime of sendsInWindow(sendTimes, now)) {
    const left = sendTime + PACE_WINDOW_MS - now
    if (soonest === null || left < soonest) {
      soonest = left
    }
  }
  return soonest
}

// What the clue of a word shows of a reaction.
export interface ClueReactionMarker {
  reaction: ReactionValue
  playerId: string
  // The emoji.
  text: string
  // The text read by a screen reader: "<nickname> : <reaction name>".
  label: string
}

// The marker of each clue that shows a reaction, by clue key
// "row,column,clue_index". `names` holds every nickname the page knows.
export function clueReactionMarkers(
  reactions: ShownReaction[],
  names: Map<string, string>,
): Map<string, ClueReactionMarker> {
  const markers = new Map<string, ClueReactionMarker>()
  for (const shown of reactions) {
    const name = nameOf(names, shown.player_id)
    const reactionName = t(`reaction.${shown.reaction}_label`)
    markers.set(clueKey(shown.clue), {
      reaction: shown.reaction,
      playerId: shown.player_id,
      text: t(`reaction.${shown.reaction}`),
      label: t('reaction.shown_label', { name, reaction: reactionName }),
    })
  }
  return markers
}
