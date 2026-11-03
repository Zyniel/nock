// The fakes and helpers of the room connection's tests
// (roomConnection.test.ts and roomConnectionLoss.test.ts): a fake socket, a
// fake clock, random draw and page visibility, and hooks that log what the
// connection calls. The timers are node:test's mock timers, which each test
// file enables.

import assert from 'node:assert/strict'
import { mock } from 'node:test'

import {
  SOCKET_CONNECTING,
  SOCKET_OPEN,
  createRoomConnection,
} from '../../web/src/lib/roomConnection'
import type {
  ConnectionHooks,
  ConnectionSocket,
  RoomConnection,
} from '../../web/src/lib/roomConnection'
import { newSession } from '../../web/src/lib/roomSession'
import type { LetterCellView, RoomSession, Snapshot } from '../../web/src/lib/roomSession'
import type { Identity } from '../../web/src/lib/joinRules'

export const ROOM_URL = 'ws://nock.test/api/rooms/ABCD/ws'
const SOCKET_CLOSED = 3
export const ABNORMAL_CLOSE = 1006

export const IDENTITY: Identity = { player_id: 'p1', resume_token: 'token-1', nickname: 'ANA' }
export const JOIN_WITH_IDENTITY = { type: 'join', nickname: 'ANA', resume_token: 'token-1' }

// What the page's joinPlan hook returns: the identity to join with, else the
// nickname of an automatic join, else neither (the nickname form).
export interface JoinPlanHook {
  identity: Identity | null
  nickname: string | null
}

export const NO_JOIN_PLAN: JoinPlanHook = { identity: null, nickname: null }
export const SELECT_CELL = { type: 'select_cell', row: 0, column: 1, direction: 'across' }
export const UNDO = { type: 'undo' }
export const CHECK_GRID = { type: 'check', target: { scope: 'grid' } }
export const PING = { type: 'ping' }

// One entry of what happened, in order: a message a socket sent, or a hook
// the connection called.
export type LogEntry = Record<string, unknown>

export class FakeSocket implements ConnectionSocket {
  readyState: number = SOCKET_CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  readonly url: string
  readonly sent: unknown[] = []
  closeCalls = 0
  private readonly log: LogEntry[]

  constructor(url: string, log: LogEntry[]) {
    this.url = url
    this.log = log
  }

  send(text: string): void {
    const message: unknown = JSON.parse(text)
    this.sent.push(message)
    this.log.push({ sent: message })
  }

  close(): void {
    this.closeCalls += 1
    this.readyState = SOCKET_CLOSED
  }

  // The server accepts the socket.
  open(): void {
    this.readyState = SOCKET_OPEN
    this.onopen?.()
  }

  // A frame from the server; a socket the page dropped hears nothing.
  receive(data: unknown): void {
    this.onmessage?.({ data })
  }

  // The socket closes with `code`.
  closeWith(code: number): void {
    this.readyState = SOCKET_CLOSED
    this.onclose?.({ code })
  }

  isDetached(): boolean {
    return (
      this.onopen === null &&
      this.onmessage === null &&
      this.onclose === null &&
      this.onerror === null
    )
  }
}

export interface Harness {
  connection: RoomConnection
  session: RoomSession
  sockets: FakeSocket[]
  log: LogEntry[]
  // What the fakes return: the clock, the random draw, the page hidden, the
  // join plan the page worked out, and the select_cell of the selection.
  clock: { ms: number }
  draw: { value: number }
  page: { isHidden: boolean }
  join: { plan: JoinPlanHook }
  selection: { message: object | null }
  // What the page does inside onSnapshot, after the hook is logged.
  inSnapshot: { action: (() => void) | null }
}

export function makeHarness(): Harness {
  const session = newSession()
  const sockets: FakeSocket[] = []
  const log: LogEntry[] = []
  const clock = { ms: 0 }
  const draw = { value: 0.5 }
  const page = { isHidden: false }
  const join: { plan: JoinPlanHook } = { plan: { identity: IDENTITY, nickname: null } }
  const selection: { message: object | null } = { message: null }
  const inSnapshot: { action: (() => void) | null } = { action: null }
  const hooks: ConnectionHooks = {
    joinPlan: () => join.plan,
    onOpen: () => {
      log.push({ hook: 'open' })
    },
    onSnapshot: (snapshot: Snapshot, isFirst: boolean) => {
      log.push({ hook: 'snapshot', seq: snapshot.seq, isFirst, status: session.status })
      inSnapshot.action?.()
    },
    onFrame: () => {
      log.push({ hook: 'frame' })
    },
    onLoss: () => {
      log.push({ hook: 'loss', status: session.status })
    },
    onEnded: () => {
      log.push({
        hook: 'ended',
        status: session.status,
        pendingEdits: session.pendingEdits.length,
      })
    },
    selectionMessage: () => selection.message,
  }
  const connection = createRoomConnection(ROOM_URL, session, hooks, {
    openSocket: (url: string) => {
      const socket = new FakeSocket(url, log)
      sockets.push(socket)
      return socket
    },
    now: () => clock.ms,
    random: () => draw.value,
    isHidden: () => page.isHidden,
  })
  return { connection, session, sockets, log, clock, draw, page, join, selection, inSnapshot }
}

// Move the timers and the clock together, one millisecond at a time, so that
// a timer set by another timer runs at its own time.
export function advance(harness: Harness, ms: number): void {
  for (let step = 0; step < ms; step += 1) {
    harness.clock.ms += 1
    mock.timers.tick(1)
  }
}

export function lastSocket(harness: Harness): FakeSocket {
  const socket = harness.sockets.at(-1)
  assert.ok(socket !== undefined, 'no socket was opened')
  return socket
}

// The snapshot frame of a 2 by 1 grid: a clue cell, then the letter cell (0, 1).
export function snapshotFrame(seq: number): string {
  return JSON.stringify({
    type: 'snapshot',
    seq,
    you: 'p1',
    resume_token: 'token-1',
    grid: {
      width: 2,
      height: 1,
      cells: [
        { type: 'clue', row: 0, column: 0, clues: [{ text: 'Note', arrow: 'right' }] },
        { type: 'letter', row: 0, column: 1, letter: null, locked: false },
      ],
    },
    players: [{ player_id: 'p1', nickname: 'ANA', colour: 1, state: 'active' }],
  })
}

export function letterCell(row: number, column: number): LetterCellView {
  return {
    type: 'letter',
    row,
    column,
    letter: null,
    locked: false,
    revealed: false,
    author: null,
    wrong: false,
    pencil: false,
    hyphen_right: false,
    hyphen_down: false,
  }
}

// Start the connection, open its socket and give it a snapshot.
export function joinedHarness(seq: number): Harness {
  const harness = makeHarness()
  harness.connection.start()
  lastSocket(harness).open()
  lastSocket(harness).receive(snapshotFrame(seq))
  return harness
}

// After a loss, wait for the next try and open its socket.
export function reopen(harness: Harness, delayMs: number): FakeSocket {
  const before = harness.sockets.length
  advance(harness, delayMs)
  assert.equal(harness.sockets.length, before + 1)
  const socket = lastSocket(harness)
  socket.open()
  return socket
}
