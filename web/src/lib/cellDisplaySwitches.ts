// The two display switches of the grid cells (spec 042), kept in this browser:
// « Mots des autres » (the other players' word tint, on by default) and
// « Accessibilité » (the players' icons, off by default). They send nothing.

import { readItem, writeItem } from './storage'

export const OTHERS_TINT_KEY = 'nock.others_tint'
export const ACCESSIBILITY_KEY = 'nock.accessibility'

// The tint is on unless "false" is stored; a browser that refuses storage
// starts with it on.
export function readOthersTint(): boolean {
  return readItem(OTHERS_TINT_KEY) !== 'false'
}

// The Accessibilité mode is off unless "true" is stored; a browser that
// refuses storage starts with it off.
export function readAccessibility(): boolean {
  return readItem(ACCESSIBILITY_KEY) === 'true'
}

// Remember a switch's new value as "true" or "false".
export function writeSwitch(key: string, isOn: boolean): void {
  writeItem(key, isOn ? 'true' : 'false')
}
