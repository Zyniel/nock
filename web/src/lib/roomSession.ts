// The state of one room page and the rules that keep it in `seq` order.
// Plain functions: no socket and no DOM, so the rules are easy to read.

export type RoomStatus = 'connecting' | 'joined' | 'not_found' | 'closed'

export interface GridSize {
  width: number
  height: number
}

// Only what the shell reads from a snapshot (later specs read more).
export interface Snapshot {
  type: 'snapshot'
  seq: number
  grid: GridSize
}

// A message with an integer `seq` that is not a snapshot.
export interface RoomEvent {
  type: string
  seq: number
}

export interface RoomSession {
  status: RoomStatus
  snapshot: Snapshot | null
  // `null` until the first snapshot.
  seq: number | null
  // Events that arrived too early, waiting for the ones before them.
  pending: RoomEvent[]
}

export const ROOM_NOT_FOUND_CLOSE_CODE = 4404

export function newSession(): RoomSession {
  return { status: 'connecting', snapshot: null, seq: null, pending: [] }
}

// Parse one frame. Returns null when it is not a JSON object with a string type.
function parseFrame(text: string): Record<string, unknown> | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null
  }
  const message = value as Record<string, unknown>
  if (typeof message.type !== 'string') {
    return null
  }
  return message
}

function toSnapshot(message: Record<string, unknown>): Snapshot | null {
  const grid = message.grid as Record<string, unknown> | null | undefined
  if (typeof grid !== 'object' || grid === null) {
    return null
  }
  const { width, height } = grid
  if (typeof width !== 'number' || typeof height !== 'number') {
    return null
  }
  if (typeof message.seq !== 'number' || !Number.isInteger(message.seq)) {
    return null
  }
  return { type: 'snapshot', seq: message.seq, grid: { width, height } }
}

function toEvent(message: Record<string, unknown>): RoomEvent | null {
  if (typeof message.seq !== 'number' || !Number.isInteger(message.seq)) {
    return null
  }
  return { type: String(message.type), seq: message.seq }
}

// In this spec, applying an event only advances `seq`. What each event changes
// in the snapshot belongs to the spec that owns that event.
function applyEvent(session: RoomSession, event: RoomEvent): void {
  session.seq = event.seq
}

// Apply every buffered event that follows `seq`, one after the other.
function drainPending(session: RoomSession): void {
  while (session.seq !== null) {
    const nextSeq = session.seq + 1
    const index = session.pending.findIndex((event) => event.seq === nextSeq)
    if (index === -1) {
      return
    }
    const [event] = session.pending.splice(index, 1)
    applyEvent(session, event)
  }
}

function receiveSnapshot(session: RoomSession, snapshot: Snapshot): void {
  session.snapshot = snapshot
  session.seq = snapshot.seq
  session.status = 'joined'
  session.pending = session.pending.filter((event) => event.seq > snapshot.seq)
  drainPending(session)
}

function receiveEvent(session: RoomSession, event: RoomEvent): void {
  if (session.seq === null) {
    return // before the first snapshot: dropped
  }
  if (event.seq <= session.seq) {
    return // already included
  }
  if (event.seq === session.seq + 1) {
    applyEvent(session, event)
    drainPending(session)
    return
  }
  const isBuffered = session.pending.some((buffered) => buffered.seq === event.seq)
  if (!isBuffered) {
    session.pending.push(event)
  }
}

// Take one frame received from the server and update the session.
export function receiveFrame(session: RoomSession, text: string): void {
  const message = parseFrame(text)
  if (message === null) {
    return
  }
  if (message.type === 'snapshot') {
    const snapshot = toSnapshot(message)
    if (snapshot !== null) {
      receiveSnapshot(session, snapshot)
    }
    return
  }
  const event = toEvent(message)
  if (event !== null) {
    receiveEvent(session, event)
  }
}

export function statusAfterClose(code: number): RoomStatus {
  return code === ROOM_NOT_FOUND_CLOSE_CODE ? 'not_found' : 'closed'
}

export function gridLabel(session: RoomSession): string {
  if (session.snapshot === null) {
    return ''
  }
  return `${session.snapshot.grid.width}x${session.snapshot.grid.height}`
}
