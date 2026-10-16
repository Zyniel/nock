// The end-of-game recap (spec 028): what the server answers for a solved room and
// for its share link, and the choices the recap dialog makes about its rows.
// Plain functions: no DOM.

export interface RecapPlayer {
  player_id: string
  // null: an author the room's log never saw join
  nickname: string | null
  letters: number
  words: number
  // removed by the host (spec 014)
  removed: boolean
}

export interface Recap {
  grid_number: number | null
  elapsed_ms: number
  checks: number
  letter_reveals: number
  word_reveals: number
  revealed_letters: number
  letter_cells: number
  word_count: number
  players: RecapPlayer[]
  // "/recap/<token>", or null for a room made before spec 028
  share_path: string | null
}

export interface PublicRecap {
  grid_number: number | null
  elapsed_ms: number
  team: string[]
}

function isNumberOrNull(value: unknown): boolean {
  return value === null || typeof value === 'number'
}

function isStringOrNull(value: unknown): boolean {
  return value === null || typeof value === 'string'
}

// Tell whether a parsed JSON value looks like one row of a recap.
function isRecapPlayer(value: unknown): value is RecapPlayer {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    typeof record.player_id === 'string' &&
    isStringOrNull(record.nickname) &&
    typeof record.letters === 'number' &&
    typeof record.words === 'number' &&
    typeof record.removed === 'boolean'
  )
}

// Tell whether a parsed JSON value looks like a recap.
export function isRecap(value: unknown): value is Recap {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    isNumberOrNull(record.grid_number) &&
    typeof record.elapsed_ms === 'number' &&
    typeof record.checks === 'number' &&
    typeof record.letter_reveals === 'number' &&
    typeof record.word_reveals === 'number' &&
    typeof record.revealed_letters === 'number' &&
    typeof record.letter_cells === 'number' &&
    typeof record.word_count === 'number' &&
    Array.isArray(record.players) &&
    record.players.every(isRecapPlayer) &&
    isStringOrNull(record.share_path)
  )
}

// Tell whether a parsed JSON value looks like a public recap.
export function isPublicRecap(value: unknown): value is PublicRecap {
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const record = value as Record<string, unknown>
  return (
    isNumberOrNull(record.grid_number) &&
    typeof record.elapsed_ms === 'number' &&
    Array.isArray(record.team) &&
    record.team.every((name: unknown) => typeof name === 'string')
  )
}

// Fetch a JSON body of the expected shape. Null when the request fails, when the
// server answers anything but 200, or when the body has another shape.
async function fetchExpected<T>(
  url: string,
  isExpected: (value: unknown) => value is T,
): Promise<T | null> {
  try {
    const response = await fetch(url)
    if (response.status !== 200) {
      return null
    }
    const body: unknown = await response.json()
    if (!isExpected(body)) {
      return null
    }
    return body
  } catch {
    return null
  }
}

// The recap of a solved room, or null when it is not available.
export function fetchRecap(code: string): Promise<Recap | null> {
  return fetchExpected(`/api/rooms/${code}/recap`, isRecap)
}

// The public recap of a share link, or null when it is not available.
export function fetchPublicRecap(token: string): Promise<PublicRecap | null> {
  return fetchExpected(`/api/recaps/${token}`, isPublicRecap)
}

// The rows of the dialog, in the recap's order: every player except one the host
// removed who has no letter and no word.
export function shownRecapPlayers(players: RecapPlayer[]): RecapPlayer[] {
  return players.filter((player) => {
    const broughtNothing = player.letters === 0 && player.words === 0
    return !(player.removed && broughtNothing)
  })
}

// The colour of a row's swatch, as spec 019 sets an author mark's: the colour
// index of a player the page's snapshot lists, else '' (the neutral grey: the
// colour of a player who left may now be someone else's).
export function recapColour(playerId: string, playerColours: Map<string, number>): string {
  const colour = playerColours.get(playerId)
  if (colour === undefined) {
    return ''
  }
  return String(colour)
}
