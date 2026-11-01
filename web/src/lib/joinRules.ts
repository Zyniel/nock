// The rules of joining a room: the nickname rule and what the browser stored.
// Plain functions: the socket and the page live in RoomPage.svelte.

import { parseObject, readItem, roomRecordKey, writeItem } from './storage'

const NICKNAME_MIN_LENGTH = 2
const NICKNAME_MAX_LENGTH = 20
const NICKNAME_PUNCTUATION = " -'’_"

export const NICKNAME_KEY = 'nock.nickname'

export interface Identity {
  player_id: string
  resume_token: string
  nickname: string
}

export type NicknameCheck =
  | { ok: true; nickname: string }
  | { ok: false; reason: 'length' | 'characters' }

// The join message the page sends at once.
export interface JoinPlan {
  nickname: string
  resume_token: string | null
}

export function identityKey(code: string): string {
  return `nock.identity.${code}`
}

// The same rule as `normalize_nickname` on the server: NFC, trimmed, in
// capitals, then NFC again, since the capitals of a few Greek letters are not in
// NFC. The rules are checked on that result, which is the nickname a join sends.
export function checkNickname(text: string): NicknameCheck {
  const nickname = text.normalize('NFC').trim().toUpperCase().normalize('NFC')
  const characters = Array.from(nickname)
  if (characters.length < NICKNAME_MIN_LENGTH || characters.length > NICKNAME_MAX_LENGTH) {
    return { ok: false, reason: 'length' }
  }
  let hasLetterOrDigit = false
  for (const character of characters) {
    const isLetter = /^\p{L}$/u.test(character)
    const isDigit = character >= '0' && character <= '9'
    const isMark = /^[\p{Mn}\p{Mc}]$/u.test(character)
    if (!isLetter && !isDigit && !isMark && !NICKNAME_PUNCTUATION.includes(character)) {
      return { ok: false, reason: 'characters' }
    }
    if (isLetter || isDigit) {
      hasLetterOrDigit = true
    }
  }
  if (!hasLetterOrDigit) {
    return { ok: false, reason: 'characters' }
  }
  return { ok: true, nickname }
}

function isFilled(value: unknown): value is string {
  return typeof value === 'string' && value !== ''
}

// The identity stored for this room, or null when absent or not valid.
export function readIdentity(code: string): Identity | null {
  const record = parseObject(readItem(identityKey(code)))
  if (record === null) {
    return null
  }
  const { player_id, resume_token, nickname } = record
  if (!isFilled(player_id) || !isFilled(resume_token) || !isFilled(nickname)) {
    return null
  }
  return { player_id, resume_token, nickname }
}

export function writeIdentity(code: string, identity: Identity): void {
  writeItem(identityKey(code), JSON.stringify(identity))
}

export function readNickname(): string | null {
  return readItem(NICKNAME_KEY)
}

export function writeNickname(nickname: string): void {
  writeItem(NICKNAME_KEY, nickname)
}

// True when spec 010 stored a room record with a numeric grid: this device
// created the room from the catalogue.
function isRoomCreatedHere(code: string): boolean {
  const record = parseObject(readItem(roomRecordKey(code)))
  return record !== null && typeof record.grid === 'number'
}

// The join to send at once when the socket opens, or null to show the form.
// `heldIdentity` is the identity of the page's last snapshot, held in memory: it
// comes first, so that a browser refusing storage still rejoins, and an identity
// another tab stored meanwhile does not replace it.
export function planAutomaticJoin(
  code: string,
  defaultNickname: string,
  heldIdentity: Identity | null,
): JoinPlan | null {
  const identity = heldIdentity ?? readIdentity(code)
  if (identity !== null) {
    return { nickname: identity.nickname, resume_token: identity.resume_token }
  }
  if (!isRoomCreatedHere(code)) {
    return null
  }
  const remembered = readNickname()
  if (remembered !== null) {
    const check = checkNickname(remembered)
    if (check.ok) {
      return { nickname: remembered, resume_token: null }
    }
  }
  return { nickname: defaultNickname, resume_token: null }
}
