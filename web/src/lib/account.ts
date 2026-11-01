// The optional account of spec 033, seen from the pages: the account routes of
// the server and the room identities an account brings to this device. Plain
// functions: no DOM.

import { HISTORY_KEY, readHistory, type HistoryRecord } from './history'
import { identityKey, readIdentity, writeIdentity } from './joinRules'
import type { RoomKey } from './myRooms'
import { readItem, removeItem, roomRecordKey, writeItem } from './storage'

// What GET /api/account answers while accounts are on.
export interface AccountStatus {
  signed_in: boolean
  email: string | null
}

// One room identity of the account, as GET /api/account/rooms gives it.
export interface AccountIdentity {
  code: string
  player_id: string
  resume_token: string
  nickname: string
}

// What POST /api/account/sign-in answers.
export interface SignInResult {
  email: string
  room_code: string | null
  rooms: AccountIdentity[]
}

// How a link request ended, for the message the form shows.
export type LinkAnswer = 'sent' | 'invalid' | 'too_many' | 'failed'

// The token of a sign-in link, as the account page reads it from its URL.
export const LINK_TOKEN = /^[A-Za-z0-9_-]{43}$/

const ACCOUNT_URL = '/api/account'
const LINK_URL = '/api/account/link'
const SIGN_IN_URL = '/api/account/sign-in'
const SIGN_OUT_URL = '/api/account/sign-out'
const ROOMS_URL = '/api/account/rooms'
// The codes of the rooms whose identity came from the account (a JSON array).
const ACCOUNT_ROOMS_KEY = 'nock.account_rooms'

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isAccountStatus(value: unknown): value is AccountStatus {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.signed_in === 'boolean' && (record.email === null || isString(record.email))
  )
}

function isAccountIdentity(value: unknown): value is AccountIdentity {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    isString(record.code) &&
    isString(record.player_id) &&
    isString(record.resume_token) &&
    isString(record.nickname)
  )
}

function isSignInResult(value: unknown): value is SignInResult {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    isString(record.email) &&
    (record.room_code === null || isString(record.room_code)) &&
    Array.isArray(record.rooms) &&
    record.rooms.every(isAccountIdentity)
  )
}

// The account status, or null when accounts are off (404) or the request failed:
// a page then shows no account control.
export async function fetchAccountStatus(): Promise<AccountStatus | null> {
  try {
    const response = await fetch(ACCOUNT_URL)
    if (response.status !== 200) {
      return null
    }
    const body: unknown = await response.json()
    return isAccountStatus(body) ? body : null
  } catch {
    return null
  }
}

// Ask a sign-in link for `email`, from the room of `room` when one is given.
export async function askSignInLink(email: string, room: RoomKey | null): Promise<LinkAnswer> {
  try {
    const response = await fetch(LINK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, room }),
    })
    if (response.status === 202) {
      return 'sent'
    }
    if (response.status === 422) {
      return 'invalid'
    }
    if (response.status === 429) {
      return 'too_many'
    }
    return 'failed'
  } catch {
    return 'failed'
  }
}

// Use the token of a sign-in link: the answer, 'invalid' for a link that is no
// longer valid (404), or null for any other failure.
export async function signIn(token: string): Promise<SignInResult | 'invalid' | null> {
  try {
    const response = await fetch(SIGN_IN_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
    if (response.status === 404) {
      return 'invalid'
    }
    if (response.status !== 200) {
      return null
    }
    const body: unknown = await response.json()
    return isSignInResult(body) ? body : null
  } catch {
    return null
  }
}

// End the session of this browser; true when the server answered 204.
export async function signOut(): Promise<boolean> {
  try {
    const response = await fetch(SIGN_OUT_URL, { method: 'POST' })
    return response.status === 204
  } catch {
    return false
  }
}

// Delete the account; true when the server answered 204.
export async function deleteAccount(): Promise<boolean> {
  try {
    const response = await fetch(ACCOUNT_URL, { method: 'DELETE' })
    return response.status === 204
  } catch {
    return false
  }
}

// The room identities of the account, or null when the request failed.
export async function fetchAccountRooms(): Promise<AccountIdentity[] | null> {
  try {
    const response = await fetch(ROOMS_URL)
    if (response.status !== 200) {
      return null
    }
    const body: unknown = await response.json()
    if (!Array.isArray(body) || !body.every(isAccountIdentity)) {
      return null
    }
    return body
  } catch {
    return null
  }
}

// Link this page's player of a room to the account. Its answer changes nothing
// on the page, so it is not read.
export async function linkRoom(key: RoomKey): Promise<void> {
  try {
    await fetch(ROOMS_URL, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(key),
    })
  } catch {
    // Nothing changes on the page.
  }
}

// The codes of the rooms whose identity this device took from the account. A
// stored value that is not a JSON array reads as none, and an item that is not a
// string is left out.
function readAccountRoomCodes(): string[] {
  const raw = readItem(ACCOUNT_ROOMS_KEY)
  if (raw === null) {
    return []
  }
  let stored: unknown
  try {
    stored = JSON.parse(raw)
  } catch {
    return []
  }
  if (!Array.isArray(stored)) {
    return []
  }
  const codes: string[] = []
  for (const item of stored) {
    if (isString(item)) {
      codes.push(item)
    }
  }
  return codes
}

// Store each identity of the account whose room has no valid identity on this
// device yet, as spec 012's record, and remember its code in `nock.account_rooms`.
// An identity already stored is never replaced.
export function storeMissingIdentities(identities: AccountIdentity[]): void {
  const accountCodes = readAccountRoomCodes()
  let hasNewCode = false
  for (const identity of identities) {
    if (readIdentity(identity.code) !== null) {
      continue
    }
    writeIdentity(identity.code, {
      player_id: identity.player_id,
      resume_token: identity.resume_token,
      nickname: identity.nickname,
    })
    if (!accountCodes.includes(identity.code)) {
      accountCodes.push(identity.code)
      hasNewCode = true
    }
  }
  if (hasNewCode) {
    writeItem(ACCOUNT_ROOMS_KEY, JSON.stringify(accountCodes))
  }
}

// Remove from this device what the account brought: for each code of
// `nock.account_rooms`, its identity, its room record and its history records,
// then the list itself. A seat the device took itself is not in the list.
export function forgetAccountSeats(): void {
  const accountCodes = readAccountRoomCodes()
  for (const code of accountCodes) {
    removeItem(identityKey(code))
    removeItem(roomRecordKey(code))
  }
  const storedRecords = readHistory()
  const keptRecords: HistoryRecord[] = []
  for (const record of storedRecords) {
    if (!accountCodes.includes(record.code)) {
      keptRecords.push(record)
    }
  }
  if (keptRecords.length < storedRecords.length) {
    writeItem(HISTORY_KEY, JSON.stringify(keptRecords))
  }
  removeItem(ACCOUNT_ROOMS_KEY)
}
