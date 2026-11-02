// The room's connection (spec 017, platform/reconnection.md): the socket, the
// join, the snapshots and frames, the heartbeat and the silence, the connect
// limit, the retries with their jitter, the resend of what waited after a
// loss, and the final closes. Besides the frame parser (roomSession.ts) it is
// the only writer of `session.status`. No DOM and no runes: the browser comes
// in through ConnectionDeps, and the page's side runs through ConnectionHooks.

import type { JoinPlan } from './joinRules'
import { editMessage } from './roomCommands'
import type { EditKind } from './roomCommands'
import {
  CONNECT_LIMIT_MS,
  EDIT_SEND_INTERVAL_MS,
  PING_INTERVAL_MS,
  SILENCE_LIMIT_MS,
  addPendingEdit,
  isFinalClose,
  receiveFrame,
  reconnectDelay,
  statusAfterFinalClose,
  statusAfterLoss,
} from './roomSession'
import type { LetterCellView, RoomSession, Snapshot } from './roomSession'

// The socket's readyState values the connection reads (the WebSocket ones).
export const SOCKET_CONNECTING = 0
export const SOCKET_OPEN = 1

// What the connection needs of a socket: the browser's WebSocket, or a fake.
// The handlers take the browser's event types so that a WebSocket fits. The
// connection sets no onerror: a failed socket also closes, and onclose hears it.
export interface ConnectionSocket {
  readyState: number
  send(text: string): void
  close(): void
  onopen: ((event: Event) => void) | null
  onmessage: ((event: MessageEvent) => void) | null
  onclose: ((event: CloseEvent) => void) | null
}

// The one field of the page's document the connection reads. Declared here
// because the Node tests type-check this module without the DOM library.
declare const document: { readonly hidden: boolean }

// What the connection needs of the browser.
export interface ConnectionDeps {
  openSocket(url: string): ConnectionSocket
  // The page clock, in milliseconds.
  now(): number
  // A random draw in [0, 1), for the jitter of the retry delays.
  random(): number
  // True while the page is out of view.
  isHidden(): boolean
}

// The browser itself. Each one reads its global when called, so that a test
// that replaces WebSocket, Math.random or document.hidden is heard.
export const BROWSER_DEPS: ConnectionDeps = {
  openSocket: (url: string) => new WebSocket(url),
  now: () => performance.now(),
  random: () => Math.random(),
  isHidden: () => document.hidden,
}

// The page's side of the connection. Each hook runs synchronously.
export interface ConnectionHooks {
  // The join to send when a socket opens: the identity first, else the
  // nickname of an automatic join, else neither (the page shows the form).
  joinPlan(): JoinPlan
  // A socket opened, before its join is sent.
  onOpen(): void
  // A new snapshot was applied, before anything waiting is sent. `isFirst` is
  // true for the page's first snapshot only.
  onSnapshot(snapshot: Snapshot, isFirst: boolean): void
  // A text frame was read (after onSnapshot when it was a snapshot).
  onFrame(): void
  // The socket was lost, while the page still shows the status it had.
  onLoss(): void
  // The room was deleted: the socket closed for good with not_found.
  onEnded(): void
  // The select_cell of the page's selection, or null with nothing selected.
  // After a loss it is sent first, as the server forgot the selection.
  selectionMessage(): object | null
}

export interface RoomConnection {
  // Open the first socket.
  start(): void
  // Close the socket and stop every timer; nothing is heard afterwards.
  dispose(): void
  // Send a message on the open socket. Returns whether it went out.
  send(message: object): boolean
  // Show an edit at once, keep it pending until the server answers, and send
  // it with `baseSeq` (a resend after a loss keeps the seq it was made at).
  edit(cell: LetterCellView, letter: string | null, kind: EditKind, baseSeq: number | null): void
  // Send an undo, a check or a reveal after the edits pending when it is made.
  request(message: object): void
  // Join with the nickname of the form.
  join(nickname: string): void
  // The browser has a network again.
  onOnline(): void
  // The page's visibility changed.
  onVisible(): void
}

// An undo, a check or a reveal made while the page is not joined, kept until
// the next snapshot. `editsBefore` counts the edits made before it: it goes out
// after them and before any later edit.
interface KeptRequest {
  message: object
  editsBefore: number
}

// A message waiting its turn in the send queue. `request` is set for an undo,
// a check or a reveal, so that a loss can keep it again; an edit stays pending
// and is resent anyway, and a select_cell is sent again after the next snapshot.
interface QueuedMessage {
  message: object
  request: KeptRequest | null
}

// The join message of a plan, or null when the plan has nothing to join with.
function joinMessage(plan: JoinPlan): object | null {
  if (plan.identity !== null) {
    return {
      type: 'join',
      nickname: plan.identity.nickname,
      resume_token: plan.identity.resume_token,
    }
  }
  if (plan.nickname !== null) {
    return { type: 'join', nickname: plan.nickname, resume_token: null }
  }
  return null
}

export function createRoomConnection(
  url: string,
  session: RoomSession,
  hooks: ConnectionHooks,
  deps: ConnectionDeps = BROWSER_DEPS,
): RoomConnection {
  let socket: ConnectionSocket | null = null

  // ---- The timers: heartbeat, silence, retry and connect limit ----

  // The next delay of the reconnection is `reconnectDelay(reconnectAttempt)`.
  let reconnectAttempt = 0
  let pingTimer: ReturnType<typeof setInterval> | undefined
  let silenceTimer: ReturnType<typeof setTimeout> | undefined
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined
  // Watches the socket being opened for its connect limit.
  let connectTimer: ReturnType<typeof setTimeout> | undefined
  // The page clock when the silence of the open socket started: its last
  // frame, or the page's return into view.
  let silenceStartedAt = 0

  function stopHeartbeat(): void {
    clearInterval(pingTimer)
    clearTimeout(silenceTimer)
    pingTimer = undefined
    silenceTimer = undefined
  }

  function stopReconnectTimer(): void {
    clearTimeout(reconnectTimer)
    reconnectTimer = undefined
  }

  function stopConnectTimer(): void {
    clearTimeout(connectTimer)
    connectTimer = undefined
  }

  // ---- What the page sends after a snapshot (platform/reconnection.md rules 5 and 7) ----

  // Until the socket has its snapshot nothing is sent: edits stay pending, and
  // undos, checks and reveals are kept. They are then sent one every
  // EDIT_SEND_INTERVAL_MS, oldest first, through the send queue.
  let isSynced = false
  let sendQueue: QueuedMessage[] = []
  let sendTimer: ReturnType<typeof setInterval> | undefined
  // How many edits the page has made since it opened.
  let editsMade = 0
  let keptRequests: KeptRequest[] = []

  // Send a message when the socket is open; after a close nothing is sent.
  // Returns whether it went out: a socket that is no longer open, even before
  // the page has seen its close, drops what it is given.
  function send(message: object): boolean {
    if (socket === null || socket.readyState !== SOCKET_OPEN) {
      return false
    }
    socket.send(JSON.stringify(message))
    return true
  }

  // Stop the send queue. The requests it still holds are kept again, before any
  // kept since, for the next snapshot.
  function stopSendQueue(): void {
    clearInterval(sendTimer)
    sendTimer = undefined
    const stillQueued: KeptRequest[] = []
    for (const queued of sendQueue) {
      if (queued.request !== null) {
        stillQueued.push(queued.request)
      }
    }
    keptRequests = [...stillQueued, ...keptRequests]
    sendQueue = []
    isSynced = false
  }

  function sendNextQueued(): void {
    const next = sendQueue.shift()
    if (next === undefined) {
      clearInterval(sendTimer)
      sendTimer = undefined
      return
    }
    send(next.message)
  }

  // Send an edit now, or behind the messages still queued. Before the snapshot of
  // the socket nothing is sent: the edit is pending and is resent with the others.
  function sendEdit(message: object): void {
    if (!isSynced) {
      return
    }
    if (sendTimer === undefined) {
      send(message)
      return
    }
    sendQueue.push({ message, request: null })
  }

  function edit(
    cell: LetterCellView,
    letter: string | null,
    kind: EditKind,
    baseSeq: number | null,
  ): void {
    addPendingEdit(session, cell.row, cell.column, letter, kind)
    editsMade += 1
    sendEdit(editMessage({ row: cell.row, column: cell.column, letter, kind }, baseSeq))
  }

  // Kept while the page is not joined, queued behind a running resend, else
  // sent at once.
  function request(message: object): void {
    const kept: KeptRequest = { message, editsBefore: editsMade }
    if (!isSynced) {
      keptRequests.push(kept)
      return
    }
    if (sendTimer === undefined) {
      send(message)
      return
    }
    sendQueue.push({ message, request: kept })
  }

  // My pending edits, each as the message of its kind and with the base_seq it
  // had, and the kept requests, in the order they were made. The pending edits
  // are the newest edits made: counting from 0, the first of them is edit
  // number editsMade minus their count.
  function pendingInOrder(): QueuedMessage[] {
    const ordered: QueuedMessage[] = []
    const firstEditNumber = editsMade - session.pendingEdits.length
    let requestIndex = 0
    session.pendingEdits.forEach((pending, index) => {
      const editNumber = firstEditNumber + index
      // The requests made before this edit go before it.
      while (
        requestIndex < keptRequests.length &&
        keptRequests[requestIndex].editsBefore <= editNumber
      ) {
        const kept = keptRequests[requestIndex]
        ordered.push({ message: kept.message, request: kept })
        requestIndex += 1
      }
      ordered.push({ message: editMessage(pending, pending.baseSeq), request: null })
    })
    for (const kept of keptRequests.slice(requestIndex)) {
      ordered.push({ message: kept.message, request: kept })
    }
    return ordered
  }

  // Once the socket has its snapshot, send what waited: after a loss the
  // selection first (the server cleared it), then the pending edits and the
  // kept requests in order. They are paced, the first one at once, then one
  // every EDIT_SEND_INTERVAL_MS.
  function sendAfterSnapshot(isAfterLoss: boolean): void {
    stopSendQueue()
    isSynced = true
    if (isAfterLoss) {
      const selectCell = hooks.selectionMessage()
      if (selectCell !== null) {
        sendQueue.push({ message: selectCell, request: null })
      }
    }
    sendQueue.push(...pendingInOrder())
    keptRequests = []
    sendTimer = setInterval(sendNextQueued, EDIT_SEND_INTERVAL_MS)
    sendNextQueued()
  }

  // ---- The socket ----

  // Stop listening to a socket and close it.
  function dropSocket(dropped: ConnectionSocket): void {
    if (socket === dropped) {
      stopSendQueue()
      stopConnectTimer()
    }
    dropped.onopen = null
    dropped.onmessage = null
    dropped.onclose = null
    dropped.close()
    if (socket === dropped) {
      socket = null
    }
  }

  // Any frame from the server shows the connection is alive: the silence starts
  // again from now.
  function restartSilenceTimer(opened: ConnectionSocket): void {
    silenceStartedAt = deps.now()
    clearTimeout(silenceTimer)
    silenceTimer = setTimeout(() => checkSilence(opened), SILENCE_LIMIT_MS)
  }

  // The silence is read from the clock, as the page's timers may run late:
  // at SILENCE_LIMIT_MS of it the connection is lost at once, its socket
  // dropped so that its late frames and close change nothing. A hidden page
  // loses no socket to the silence: its return counts it again
  // (platform/reconnection.md rule 3).
  function checkSilence(opened: ConnectionSocket): void {
    silenceTimer = undefined
    if (deps.isHidden()) {
      return
    }
    const silentMs = deps.now() - silenceStartedAt
    if (silentMs >= SILENCE_LIMIT_MS) {
      connectionLost(opened)
      return
    }
    silenceTimer = setTimeout(() => checkSilence(opened), SILENCE_LIMIT_MS - silentMs)
  }

  function startHeartbeat(opened: ConnectionSocket): void {
    stopHeartbeat()
    pingTimer = setInterval(() => send({ type: 'ping' }), PING_INTERVAL_MS)
    restartSilenceTimer(opened)
  }

  // A socket still connecting CONNECT_LIMIT_MS after it was created is dropped:
  // a loss. The time is read from the clock, so a hidden page whose timers ran
  // late drops it at its first timer after them (platform/reconnection.md
  // rule 6).
  function watchConnectLimit(opened: ConnectionSocket, createdAt: number): void {
    const leftMs = CONNECT_LIMIT_MS - (deps.now() - createdAt)
    connectTimer = setTimeout(() => {
      connectTimer = undefined
      if (opened !== socket || opened.readyState !== SOCKET_CONNECTING) {
        return
      }
      if (deps.now() - createdAt >= CONNECT_LIMIT_MS) {
        connectionLost(opened)
        return
      }
      watchConnectLimit(opened, createdAt)
    }, leftMs)
  }

  // The socket is lost: show it, then try again after the next delay.
  function connectionLost(lost: ConnectionSocket): void {
    if (lost !== socket) {
      return
    }
    stopHeartbeat()
    dropSocket(lost)
    hooks.onLoss()
    session.status = statusAfterLoss(session)
    const delay = reconnectDelay(reconnectAttempt, deps.random)
    reconnectAttempt += 1
    stopReconnectTimer()
    reconnectTimer = setTimeout(() => {
      reconnectTimer = undefined
      openSocket()
    }, delay)
  }

  // The socket closed for good: no more tries, and nothing will be sent again,
  // so what waited to be sent is dropped (client/hud.md rule 19).
  function connectionEnded(ended: ConnectionSocket, closeCode: number): void {
    stopHeartbeat()
    stopReconnectTimer()
    dropSocket(ended)
    session.status = statusAfterFinalClose(closeCode, session.status)
    dropWaitingSends()
    if (session.status === 'not_found') {
      hooks.onEnded()
    }
  }

  // Drop the letters waiting to be sent and the kept undos, checks and reveals.
  function dropWaitingSends(): void {
    stopSendQueue()
    session.pendingEdits = []
    keptRequests = []
  }

  // The first message of a socket: the join of the plan, or the form.
  function joinOnOpen(opened: ConnectionSocket): void {
    hooks.onOpen()
    const message = joinMessage(hooks.joinPlan())
    if (message === null) {
      session.status = 'nickname'
      return
    }
    if (session.snapshot === null) {
      session.status = 'joining'
    }
    opened.send(JSON.stringify(message))
  }

  function join(nickname: string): void {
    session.status = 'joining'
    send({ type: 'join', nickname, resume_token: null })
  }

  function onSocketMessage(opened: ConnectionSocket, data: unknown): void {
    restartSilenceTimer(opened)
    if (typeof data !== 'string') {
      return
    }
    const snapshotBefore = session.snapshot
    receiveFrame(session, data)
    const snapshot = session.snapshot
    if (snapshot !== null && snapshot !== snapshotBefore) {
      hooks.onSnapshot(snapshot, snapshotBefore === null)
      reconnectAttempt = 0
      // After a loss: the first snapshot of this socket (isSynced is still
      // false), when the page had a snapshot on an earlier socket. A second
      // snapshot on the same socket is not one.
      const isAfterLoss = snapshotBefore !== null && !isSynced
      sendAfterSnapshot(isAfterLoss)
    }
    hooks.onFrame()
  }

  function openSocket(): void {
    const opened = deps.openSocket(url)
    socket = opened
    stopConnectTimer()
    watchConnectLimit(opened, deps.now())

    opened.onopen = () => {
      stopConnectTimer()
      startHeartbeat(opened)
      joinOnOpen(opened)
    }
    opened.onmessage = (event: MessageEvent) => onSocketMessage(opened, event.data)
    opened.onclose = (event: CloseEvent) => {
      if (isFinalClose(session, event.code)) {
        connectionEnded(opened, event.code)
      } else {
        connectionLost(opened)
      }
    }
  }

  // ---- The network back and the page back into view ----

  function onOnline(): void {
    if (reconnectTimer !== undefined) {
      stopReconnectTimer()
      openSocket()
      return
    }
    // A socket still connecting may never open on a dead network: replace it.
    if (socket !== null && socket.readyState === SOCKET_CONNECTING) {
      stopHeartbeat()
      dropSocket(socket)
      openSocket()
    }
  }

  // Back into view (platform/reconnection.md rules 3 and 6): a try waiting on
  // its delay goes at once; an open socket sends `ping` at once and counts its
  // silence from now. Going out of view changes nothing.
  function onVisible(): void {
    if (deps.isHidden()) {
      return
    }
    if (reconnectTimer !== undefined) {
      stopReconnectTimer()
      openSocket()
      return
    }
    if (socket !== null && socket.readyState === SOCKET_OPEN) {
      send({ type: 'ping' })
      startHeartbeat(socket)
    }
  }

  // Leaving the page closes the socket; its handlers must not react to it.
  function dispose(): void {
    stopHeartbeat()
    stopReconnectTimer()
    stopConnectTimer()
    if (socket !== null) {
      dropSocket(socket)
    }
  }

  return {
    start: openSocket,
    dispose,
    send,
    edit,
    request,
    join,
    onOnline,
    onVisible,
  }
}
