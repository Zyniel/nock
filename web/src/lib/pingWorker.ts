// The heartbeat's ticks (platform/reconnection.md rule 3), kept in a dedicated
// worker: the browser slows or stops a hidden page's own timers, not a worker's.
// The page posts the interval in milliseconds once; the worker then posts
// 'tick' at that pace until the page terminates it. Vite builds this file into
// the app's assets, so it is a file of the app's own origin
// (platform/serving.md: the security headers allow nothing else).

// The worker's global scope, as far as this script uses it. Declared here
// because the app's type check knows the page's globals, not a worker's.
interface PingWorkerScope {
  onmessage: ((event: MessageEvent<number>) => void) | null
  postMessage(message: 'tick'): void
}

declare const self: PingWorkerScope

let tickTimer: ReturnType<typeof setInterval> | undefined

self.onmessage = (event: MessageEvent<number>) => {
  clearInterval(tickTimer)
  tickTimer = setInterval(() => self.postMessage('tick'), event.data)
}
