// The end of a flash, a catch-up highlight or a reaction a fixed time after it
// appeared. Plain functions: no DOM and no runes, so the timing is easy to read.

export interface ExpiryTracker {
  // Start the time of each item that has none yet. An item that left the list
  // still ends at its time; the callback finds nothing to end.
  schedule(items: { id: number }[]): void
  // Cancel every time still running.
  dispose(): void
}

// A tracker whose items each end `ms` after `schedule` first saw them: `end`
// gets the item's id. An id that ended is scheduled anew if it shows again.
export function trackExpiries(ms: number, end: (id: number) => void): ExpiryTracker {
  const scheduledIds = new Set<number>()
  const timers = new Set<ReturnType<typeof setTimeout>>()

  function schedule(items: { id: number }[]): void {
    for (const item of items) {
      if (scheduledIds.has(item.id)) {
        continue
      }
      scheduledIds.add(item.id)
      const timer = setTimeout(() => {
        timers.delete(timer)
        scheduledIds.delete(item.id)
        end(item.id)
      }, ms)
      timers.add(timer)
    }
  }

  function dispose(): void {
    for (const timer of timers) {
      clearTimeout(timer)
    }
    timers.clear()
    scheduledIds.clear()
  }

  return { schedule, dispose }
}
