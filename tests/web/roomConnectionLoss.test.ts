// The room's connection when it is lost or ends, as RoomPage.svelte runs it
// today (the connection block 1856-2271; B-049 moves it to roomConnection.ts,
// no behaviour change): the retry delays, the connect limit, the heartbeat
// and the silence, the page back into view or the network back, the final
// closes, dispose(), and the browser's dependencies.
//
// The constants are roomSession.ts's: a ping every 2 s, a loss after 4 s of
// silence, a connect limit of 6 s, retry delays of 1, 2, 4 then 8 s, each
// times 0.8 + 0.4 x the random draw.

import assert from 'node:assert/strict'
import { afterEach, beforeEach, mock, test } from 'node:test'

import { BROWSER_DEPS } from '../../web/src/lib/roomConnection'
import {
  ABNORMAL_CLOSE,
  FakeSocket,
  NO_JOIN_PLAN,
  PING,
  ROOM_URL,
  advance,
  joinedHarness,
  lastSocket,
  letterCell,
  makeHarness,
  snapshotFrame,
} from './roomConnectionHarness'
import type { LogEntry } from './roomConnectionHarness'

beforeEach(() => {
  mock.timers.enable({ apis: ['setTimeout', 'setInterval'] })
})

afterEach(() => {
  mock.timers.reset()
  mock.restoreAll()
})

// ---- Loss and reconnection ----

test('a loss before the first snapshot drops the socket and the page connects again', () => {
  const harness = makeHarness()
  harness.connection.start()
  const lost = lastSocket(harness)
  lost.open()
  lost.closeWith(ABNORMAL_CLOSE)
  assert.equal(harness.session.status, 'connecting')
  assert.equal(lost.closeCalls, 1)
  assert.equal(lost.isDetached(), true)
})

test('a loss after a snapshot makes the page reconnecting', () => {
  const harness = joinedHarness(5)
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  assert.equal(harness.session.status, 'reconnecting')
})

test('onLoss runs while the page still has the status it had before the loss', () => {
  const harness = makeHarness()
  harness.join.plan = NO_JOIN_PLAN
  harness.connection.start()
  lastSocket(harness).open()
  harness.log.length = 0
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  assert.deepEqual(harness.log, [{ hook: 'loss', status: 'nickname' }])
  assert.equal(harness.session.status, 'connecting')
})

const delayCases: { draw: number; delayMs: number }[] = [
  { draw: 0, delayMs: 800 },
  { draw: 0.5, delayMs: 1000 },
  { draw: 0.9999, delayMs: 1200 },
]

for (const delayCase of delayCases) {
  const name = `a draw of ${delayCase.draw} puts the next try ${delayCase.delayMs} ms after a loss`
  test(name, () => {
    const harness = joinedHarness(5)
    harness.draw.value = delayCase.draw
    lastSocket(harness).closeWith(ABNORMAL_CLOSE)
    advance(harness, delayCase.delayMs - 1)
    assert.equal(harness.sockets.length, 1)
    advance(harness, 1)
    assert.equal(harness.sockets.length, 2)
    assert.equal(harness.sockets[1].url, ROOM_URL)
  })
}

test('the delays grow 1, 2, 4, 8 then stay at 8 s, and a snapshot starts them again', () => {
  const harness = joinedHarness(5)
  for (const delayMs of [1000, 2000, 4000, 8000, 8000]) {
    const before = harness.sockets.length
    lastSocket(harness).closeWith(ABNORMAL_CLOSE)
    advance(harness, delayMs - 1)
    assert.equal(harness.sockets.length, before, `opened before ${delayMs} ms`)
    advance(harness, 1)
    assert.equal(harness.sockets.length, before + 1, `not opened at ${delayMs} ms`)
  }
  const socket = lastSocket(harness)
  socket.open()
  socket.receive(snapshotFrame(6))
  const before = harness.sockets.length
  socket.closeWith(ABNORMAL_CLOSE)
  advance(harness, 1000)
  assert.equal(harness.sockets.length, before + 1)
})

test('a frame on a dropped socket changes nothing', () => {
  const harness = joinedHarness(5)
  const dropped = lastSocket(harness)
  dropped.closeWith(ABNORMAL_CLOSE)
  harness.log.length = 0
  dropped.receive(snapshotFrame(12))
  dropped.closeWith(1000)
  assert.equal(harness.session.seq, 5)
  assert.equal(harness.session.status, 'reconnecting')
  assert.deepEqual(harness.log, [])
})

// ---- The connect limit ----

test('a socket still connecting 6 s after it was created is lost', () => {
  const harness = makeHarness()
  harness.connection.start()
  const stuck = lastSocket(harness)
  advance(harness, 5999)
  assert.equal(stuck.closeCalls, 0)
  advance(harness, 1)
  assert.equal(stuck.closeCalls, 1)
  assert.equal(stuck.isDetached(), true)
  assert.equal(harness.session.status, 'connecting')
  advance(harness, 1000)
  assert.equal(harness.sockets.length, 2)
})

test('the connect limit is read from the clock: a timer early on it waits for the rest', () => {
  const harness = makeHarness()
  harness.connection.start()
  const stuck = lastSocket(harness)
  // The clock is 1 s behind the timers.
  harness.clock.ms -= 1000
  advance(harness, 6999)
  assert.equal(stuck.closeCalls, 0)
  advance(harness, 1)
  assert.equal(stuck.closeCalls, 1)
})

test('a socket that opened before its connect limit is kept', () => {
  const harness = makeHarness()
  harness.connection.start()
  advance(harness, 5000)
  const socket = lastSocket(harness)
  socket.open()
  advance(harness, 3000)
  assert.equal(socket.closeCalls, 0)
  assert.equal(harness.sockets.length, 1)
})

// ---- The heartbeat and the silence ----

test('an open socket sends a ping every 2 s', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  socket.sent.length = 0
  advance(harness, 1999)
  assert.deepEqual(socket.sent, [])
  advance(harness, 1)
  assert.deepEqual(socket.sent, [PING])
  // A frame keeps the socket alive; the pings go on.
  socket.receive(JSON.stringify({ type: 'pong' }))
  advance(harness, 2000)
  assert.deepEqual(socket.sent, [PING, PING])
})

test('4 s with no frame lose the socket', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  advance(harness, 3999)
  assert.equal(socket.closeCalls, 0)
  advance(harness, 1)
  assert.equal(socket.closeCalls, 1)
  assert.equal(harness.session.status, 'reconnecting')
})

test('any frame counts the silence from now again', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  advance(harness, 3000)
  socket.receive(JSON.stringify({ type: 'pong' }))
  advance(harness, 3999)
  assert.equal(socket.closeCalls, 0)
  advance(harness, 1)
  assert.equal(socket.closeCalls, 1)
})

test('a frame that is not text counts the silence from now again too', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  advance(harness, 3000)
  socket.receive(new Uint8Array([1]))
  advance(harness, 3999)
  assert.equal(socket.closeCalls, 0)
  advance(harness, 1)
  assert.equal(socket.closeCalls, 1)
})

test('the silence is read from the clock: a timer early on it waits for the rest', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  // The clock is 500 ms behind the timers.
  harness.clock.ms -= 500
  advance(harness, 4499)
  assert.equal(socket.closeCalls, 0)
  advance(harness, 1)
  assert.equal(socket.closeCalls, 1)
})

test('a hidden page loses no socket to the silence', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  harness.page.isHidden = true
  advance(harness, 20000)
  assert.equal(socket.closeCalls, 0)
  assert.equal(harness.session.status, 'joined')
})

test('back into view, an open socket pings at once and counts its silence from then', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  harness.page.isHidden = true
  advance(harness, 10000)
  harness.page.isHidden = false
  socket.sent.length = 0
  harness.connection.onVisible()
  assert.deepEqual(socket.sent, [PING])
  advance(harness, 3999)
  assert.equal(socket.closeCalls, 0)
  advance(harness, 1)
  assert.equal(socket.closeCalls, 1)
})

test('onVisible while the page is still hidden does nothing', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  harness.page.isHidden = true
  socket.sent.length = 0
  harness.connection.onVisible()
  assert.deepEqual(socket.sent, [])
})

test('back into view during a delay, the next try goes at once', () => {
  const harness = joinedHarness(5)
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  advance(harness, 200)
  harness.connection.onVisible()
  assert.equal(harness.sockets.length, 2)
  advance(harness, 1000)
  assert.equal(harness.sockets.length, 2)
})

// ---- The network back ----

test('the network back during a delay, the next try goes at once', () => {
  const harness = joinedHarness(5)
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  advance(harness, 200)
  harness.connection.onOnline()
  assert.equal(harness.sockets.length, 2)
  advance(harness, 1000)
  assert.equal(harness.sockets.length, 2)
})

test('the network back replaces a socket still connecting, with no loss', () => {
  const harness = makeHarness()
  harness.connection.start()
  const stuck = lastSocket(harness)
  advance(harness, 2000)
  harness.log.length = 0
  harness.connection.onOnline()
  assert.equal(stuck.closeCalls, 1)
  assert.equal(stuck.isDetached(), true)
  assert.equal(harness.sockets.length, 2)
  assert.equal(harness.session.status, 'connecting')
  assert.deepEqual(harness.log, [])
})

test('the network back leaves an open socket alone', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  harness.connection.onOnline()
  assert.equal(socket.closeCalls, 0)
  assert.equal(harness.sockets.length, 1)
})

// ---- Final closes ----

// Only the room deleted calls onEnded (the page's leaveDeletedRoom).
const finalCases: { code: number; status: string; endedCalls: number }[] = [
  { code: 4404, status: 'not_found', endedCalls: 1 },
  { code: 4429, status: 'throttled', endedCalls: 0 },
  { code: 4001, status: 'replaced', endedCalls: 0 },
]

function endedCallsIn(log: LogEntry[]): number {
  return log.filter((entry) => entry.hook === 'ended').length
}

for (const finalCase of finalCases) {
  const name = `a close with ${finalCase.code} ends the tries as ${finalCase.status}, edits dropped`
  test(name, () => {
    const harness = joinedHarness(5)
    harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
    const socket = lastSocket(harness)
    socket.closeWith(finalCase.code)
    assert.equal(harness.session.status, finalCase.status)
    assert.deepEqual(harness.session.pendingEdits, [])
    assert.equal(socket.isDetached(), true)
    advance(harness, 30000)
    assert.equal(harness.sockets.length, 1)
    assert.equal(harness.connection.send(PING), false)
    assert.equal(endedCallsIn(harness.log), finalCase.endedCalls)
  })
}

test('a close after a refused join ends the tries and keeps the refusal status', () => {
  const harness = makeHarness()
  harness.connection.start()
  const socket = lastSocket(harness)
  socket.open()
  socket.receive(JSON.stringify({ type: 'error', code: 'room_full' }))
  assert.equal(harness.session.status, 'full')
  socket.closeWith(1000)
  assert.equal(harness.session.status, 'full')
  advance(harness, 30000)
  assert.equal(harness.sockets.length, 1)
  assert.equal(endedCallsIn(harness.log), 0)
})

test('the room deleted once shown calls onEnded after the status and the drop', () => {
  const harness = joinedHarness(5)
  harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
  harness.log.length = 0
  lastSocket(harness).closeWith(4404)
  assert.deepEqual(harness.log, [{ hook: 'ended', status: 'not_found', pendingEdits: 0 }])
})

// ---- dispose() ----

test('dispose closes the socket, detaches it and stops every timer', () => {
  const harness = joinedHarness(5)
  const socket = lastSocket(harness)
  const sentBefore = socket.sent.length
  harness.connection.dispose()
  assert.equal(socket.closeCalls, 1)
  assert.equal(socket.isDetached(), true)
  advance(harness, 30000)
  assert.equal(socket.sent.length, sentBefore)
  assert.equal(harness.sockets.length, 1)
  assert.equal(harness.session.status, 'joined')
})

test('dispose during a delay opens no socket afterwards', () => {
  const harness = joinedHarness(5)
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  harness.connection.dispose()
  advance(harness, 30000)
  assert.equal(harness.sockets.length, 1)
})

test('dispose of a socket still connecting stops its connect limit', () => {
  const harness = makeHarness()
  harness.connection.start()
  harness.connection.dispose()
  advance(harness, 30000)
  assert.equal(harness.sockets.length, 1)
  assert.equal(harness.session.status, 'connecting')
})

// ---- The browser's dependencies, read when called ----

test('BROWSER_DEPS reads the clock when called', () => {
  mock.method(performance, 'now', () => 1234.5)
  assert.equal(BROWSER_DEPS.now(), 1234.5)
})

test('BROWSER_DEPS draws from Math.random when called', () => {
  mock.method(Math, 'random', () => 0.25)
  assert.equal(BROWSER_DEPS.random(), 0.25)
})

test('BROWSER_DEPS reads document.hidden when called', () => {
  const hadDocument = Reflect.has(globalThis, 'document')
  const document = { hidden: true }
  Reflect.set(globalThis, 'document', document)
  try {
    assert.equal(BROWSER_DEPS.isHidden(), true)
    document.hidden = false
    assert.equal(BROWSER_DEPS.isHidden(), false)
  } finally {
    if (!hadDocument) {
      Reflect.deleteProperty(globalThis, 'document')
    }
  }
})

test('BROWSER_DEPS opens the WebSocket of the page when called', () => {
  const opened: string[] = []
  class StubWebSocket extends FakeSocket {
    constructor(url: string) {
      super(url, [])
      opened.push(url)
    }
  }
  const original: unknown = Reflect.get(globalThis, 'WebSocket')
  Reflect.set(globalThis, 'WebSocket', StubWebSocket)
  try {
    const socket = BROWSER_DEPS.openSocket(ROOM_URL)
    assert.ok(socket instanceof StubWebSocket)
    assert.deepEqual(opened, [ROOM_URL])
  } finally {
    Reflect.set(globalThis, 'WebSocket', original)
  }
})
