// Start a solo game from the catalogue (spec 010): a room created on a grid.

import { markStarted } from './catalogue'
import { writeRoomCreated } from './roomRecord'

// Create a room on a catalogue grid, remember it, and load its page.
// Returns false when the room could not be created.
export async function playGrid(number: number): Promise<boolean> {
  markStarted(number)
  let code: unknown
  try {
    const response = await fetch('/api/rooms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grid_number: number }),
    })
    if (!response.ok) {
      return false
    }
    const body = (await response.json()) as Record<string, unknown> | null
    code = body === null ? null : body.code
  } catch {
    return false
  }
  if (typeof code !== 'string' || code === '') {
    return false
  }
  writeRoomCreated(code, number)
  location.assign(`/r/${code}`)
  return true
}
