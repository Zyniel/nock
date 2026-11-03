// The room's connection, as RoomPage.svelte runs it today (send 647-656,
// submitNickname 780-795, startEdit 950-959, the connection block 1856-2271;
// B-049 moves it to roomConnection.ts, no behaviour change): joining, the
// snapshots and frames, and what the page sends. The loss, the timers and
// the end of the connection are in roomConnectionLoss.test.ts.
//
// A resent message goes every 100 ms (EDIT_SEND_INTERVAL_MS).

import assert from 'node:assert/strict'
import { afterEach, beforeEach, mock, test } from 'node:test'

import {
  ABNORMAL_CLOSE,
  CHECK_GRID,
  JOIN_WITH_IDENTITY,
  NO_JOIN_PLAN,
  PING,
  ROOM_URL,
  SELECT_CELL,
  UNDO,
  advance,
  joinedHarness,
  lastSocket,
  letterCell,
  makeHarness,
  reopen,
  snapshotFrame,
} from './roomConnectionHarness'

beforeEach(() => {
  mock.timers.enable({ apis: ['setTimeout', 'setInterval'] })
})

afterEach(() => {
  mock.timers.reset()
})

// ---- Opening and joining ----

test('the connection opens its socket on start, not before', () => {
  const harness = makeHarness()
  assert.equal(harness.sockets.length, 0)
  harness.connection.start()
  assert.equal(harness.sockets.length, 1)
  assert.equal(harness.sockets[0].url, ROOM_URL)
})

test('an open socket joins with the identity of the join plan and the page is joining', () => {
  const harness = makeHarness()
  harness.connection.start()
  lastSocket(harness).open()
  assert.deepEqual(harness.log, [{ hook: 'open' }, { sent: JOIN_WITH_IDENTITY }])
  assert.equal(harness.session.status, 'joining')
})

test('an open socket with a nickname and no identity joins with that nickname', () => {
  const harness = makeHarness()
  harness.join.plan = { identity: null, nickname: 'Invité' }
  harness.connection.start()
  lastSocket(harness).open()
  assert.deepEqual(harness.log, [
    { hook: 'open' },
    { sent: { type: 'join', nickname: 'Invité', resume_token: null } },
  ])
  assert.equal(harness.session.status, 'joining')
})

test('an open socket with no identity and no nickname shows the form and sends nothing', () => {
  const harness = makeHarness()
  harness.join.plan = NO_JOIN_PLAN
  harness.connection.start()
  lastSocket(harness).open()
  assert.deepEqual(harness.log, [{ hook: 'open' }])
  assert.equal(harness.session.status, 'nickname')
})

test('join from the form makes the page joining and sends the nickname', () => {
  const harness = makeHarness()
  harness.join.plan = NO_JOIN_PLAN
  harness.connection.start()
  lastSocket(harness).open()
  harness.connection.join('BOB')
  assert.equal(harness.session.status, 'joining')
  assert.deepEqual(lastSocket(harness).sent, [
    { type: 'join', nickname: 'BOB', resume_token: null },
  ])
})

test('the join of a socket opened after a loss keeps the page reconnecting', () => {
  const harness = joinedHarness(5)
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  const socket = reopen(harness, 1000)
  assert.deepEqual(socket.sent, [JOIN_WITH_IDENTITY])
  assert.equal(harness.session.status, 'reconnecting')
})

// ---- Snapshots and frames ----

test('the first snapshot calls onSnapshot before anything waiting is sent', () => {
  const harness = makeHarness()
  harness.selection.message = SELECT_CELL
  harness.connection.start()
  const socket = lastSocket(harness)
  socket.open()
  // Made while joining: shown at once, sent once the socket has its snapshot.
  harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
  harness.log.length = 0
  socket.receive(snapshotFrame(5))
  assert.deepEqual(harness.log, [
    { hook: 'snapshot', seq: 5, isFirst: true, status: 'joined' },
    { sent: { type: 'edit_letter', row: 0, column: 1, letter: 'A', base_seq: null } },
    { hook: 'frame' },
  ])
})

test('a message sent from onSnapshot goes out before the waiting edits', () => {
  // The page restores the saved selection inside onSnapshot.
  const harness = makeHarness()
  harness.inSnapshot.action = () => {
    harness.connection.send(SELECT_CELL)
  }
  harness.connection.start()
  const socket = lastSocket(harness)
  socket.open()
  harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
  socket.receive(snapshotFrame(5))
  assert.deepEqual(socket.sent, [
    JOIN_WITH_IDENTITY,
    SELECT_CELL,
    { type: 'edit_letter', row: 0, column: 1, letter: 'A', base_seq: null },
  ])
})

test('the first snapshot sends no selection', () => {
  const harness = makeHarness()
  harness.selection.message = SELECT_CELL
  harness.connection.start()
  lastSocket(harness).open()
  lastSocket(harness).receive(snapshotFrame(5))
  advance(harness, 500)
  assert.deepEqual(lastSocket(harness).sent, [JOIN_WITH_IDENTITY])
})

test('a second snapshot on the same socket is not a first one and sends no selection', () => {
  const harness = joinedHarness(5)
  harness.selection.message = SELECT_CELL
  harness.log.length = 0
  lastSocket(harness).receive(snapshotFrame(8))
  advance(harness, 500)
  assert.deepEqual(harness.log, [
    { hook: 'snapshot', seq: 8, isFirst: false, status: 'joined' },
    { hook: 'frame' },
  ])
})

test('a frame that is not a snapshot calls onFrame only', () => {
  const harness = joinedHarness(5)
  harness.log.length = 0
  lastSocket(harness).receive(JSON.stringify({ type: 'unknown_event', seq: 6 }))
  lastSocket(harness).receive('not json')
  assert.deepEqual(harness.log, [{ hook: 'frame' }, { hook: 'frame' }])
})

test('a frame that is not text calls no hook and changes nothing', () => {
  const harness = joinedHarness(5)
  harness.log.length = 0
  lastSocket(harness).receive(new Uint8Array([1, 2, 3]))
  assert.deepEqual(harness.log, [])
  assert.equal(harness.session.seq, 5)
})

// ---- Edits and requests ----

test('an edit while joined is kept pending and sent at once with its base_seq', () => {
  const harness = joinedHarness(5)
  harness.connection.edit(letterCell(0, 1), 'B', 'confirm', 5)
  assert.deepEqual(lastSocket(harness).sent.at(-1), {
    type: 'confirm_pencil',
    row: 0,
    column: 1,
    base_seq: 5,
  })
  assert.deepEqual(harness.session.pendingEdits, [
    { row: 0, column: 1, letter: 'B', baseSeq: 5, kind: 'confirm' },
  ])
})

test('a request while joined and idle is sent at once', () => {
  const harness = joinedHarness(5)
  harness.connection.request(UNDO)
  assert.deepEqual(lastSocket(harness).sent.at(-1), UNDO)
})

test('a request before the first snapshot is kept, then sent after it', () => {
  const harness = makeHarness()
  harness.connection.start()
  const socket = lastSocket(harness)
  socket.open()
  harness.connection.request(UNDO)
  assert.deepEqual(socket.sent, [JOIN_WITH_IDENTITY])
  socket.receive(snapshotFrame(5))
  assert.deepEqual(socket.sent, [JOIN_WITH_IDENTITY, UNDO])
})

test('after a loss: the selection, then the edits and requests in order, one per 100 ms', () => {
  const harness = joinedHarness(5)
  harness.selection.message = SELECT_CELL
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  // Made while offline, in this order.
  harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
  harness.connection.request(UNDO)
  harness.connection.edit(letterCell(0, 1), 'B', 'pencil', null)
  harness.connection.request(CHECK_GRID)
  advance(harness, 1000)
  const socket = lastSocket(harness)
  socket.open()
  harness.log.length = 0
  socket.receive(snapshotFrame(9))
  // Each pending edit keeps the seq the page had when it was made.
  const letterA = { type: 'edit_letter', row: 0, column: 1, letter: 'A', base_seq: 5 }
  const pencilB = { type: 'pencil_edit', row: 0, column: 1, letter: 'B', base_seq: 5 }
  assert.deepEqual(harness.log, [
    { hook: 'snapshot', seq: 9, isFirst: false, status: 'joined' },
    { sent: SELECT_CELL },
    { hook: 'frame' },
  ])
  advance(harness, 99)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL])
  advance(harness, 1)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL, letterA])
  advance(harness, 100)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL, letterA, UNDO])
  advance(harness, 100)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL, letterA, UNDO, pencilB])
  advance(harness, 100)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL, letterA, UNDO, pencilB, CHECK_GRID])
})

test('after a loss with nothing selected, the first pending edit goes at once', () => {
  const harness = joinedHarness(5)
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
  const socket = reopen(harness, 1000)
  socket.receive(snapshotFrame(9))
  assert.deepEqual(socket.sent, [
    JOIN_WITH_IDENTITY,
    { type: 'edit_letter', row: 0, column: 1, letter: 'A', base_seq: 5 },
  ])
})

test('during a resend, a request and an edit wait their turn behind it', () => {
  const harness = joinedHarness(5)
  harness.selection.message = SELECT_CELL
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
  const socket = reopen(harness, 1000)
  socket.receive(snapshotFrame(9))
  harness.connection.request(UNDO)
  harness.connection.edit(letterCell(0, 1), 'C', 'edit', null)
  const letterA = { type: 'edit_letter', row: 0, column: 1, letter: 'A', base_seq: 5 }
  const letterC = { type: 'edit_letter', row: 0, column: 1, letter: 'C', base_seq: null }
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL])
  advance(harness, 100)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL, letterA])
  advance(harness, 100)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL, letterA, UNDO])
  advance(harness, 100)
  assert.deepEqual(socket.sent.slice(1), [SELECT_CELL, letterA, UNDO, letterC])
})

test('a loss during a resend keeps the requests not sent yet for the next snapshot', () => {
  const harness = joinedHarness(5)
  lastSocket(harness).closeWith(ABNORMAL_CLOSE)
  harness.connection.edit(letterCell(0, 1), 'A', 'edit', null)
  harness.connection.request(UNDO)
  harness.connection.edit(letterCell(0, 1), 'B', 'edit', null)
  harness.connection.request(CHECK_GRID)
  const firstSocket = reopen(harness, 1000)
  firstSocket.receive(snapshotFrame(9))
  advance(harness, 50)
  // Only A went out; the snapshot reset the delay to its first value.
  firstSocket.closeWith(ABNORMAL_CLOSE)
  advance(harness, 1000)
  const secondSocket = lastSocket(harness)
  secondSocket.open()
  secondSocket.receive(snapshotFrame(10))
  advance(harness, 300)
  const letterA = { type: 'edit_letter', row: 0, column: 1, letter: 'A', base_seq: 5 }
  const letterB = { type: 'edit_letter', row: 0, column: 1, letter: 'B', base_seq: 5 }
  assert.deepEqual(secondSocket.sent, [JOIN_WITH_IDENTITY, letterA, UNDO, letterB, CHECK_GRID])
})

// ---- send() ----

test('send returns false and sends nothing while the socket is connecting', () => {
  const harness = makeHarness()
  harness.connection.start()
  assert.equal(harness.connection.send(PING), false)
  assert.deepEqual(lastSocket(harness).sent, [])
})

test('send returns true once the socket is open, and sends the message as JSON', () => {
  const harness = joinedHarness(5)
  assert.equal(harness.connection.send({ type: 'chat', text: 'Salut' }), true)
  assert.deepEqual(lastSocket(harness).sent.at(-1), { type: 'chat', text: 'Salut' })
})

test('send returns false after the socket is lost', () => {
  const harness = joinedHarness(5)
  const lost = lastSocket(harness)
  lost.closeWith(ABNORMAL_CLOSE)
  const sentBefore = lost.sent.length
  assert.equal(harness.connection.send(PING), false)
  assert.equal(lost.sent.length, sentBefore)
})
