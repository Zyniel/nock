// The reveal allowance's counts (lobby/host.md rule 8): whole numbers from 0 to
// 99.
const MAX_REVEAL_COUNT = 99

// True for a whole number from 0 to 99.
export function isValidCount(value: number | null): value is number {
  return value !== null && Number.isInteger(value) && value >= 0 && value <= MAX_REVEAL_COUNT
}
