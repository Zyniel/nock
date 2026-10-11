// General helpers over the browser storage, shared by the modules that keep
// something on this device.

export function roomRecordKey(code: string): string {
  return `nock.room.${code}`
}

// Read a stored value; a browser that refuses storage has nothing stored.
export function readItem(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Nothing can be remembered: the page still works.
  }
}

// Parse a stored text as a JSON object; anything else is null.
export function parseObject(raw: string | null): Record<string, unknown> | null {
  if (raw === null) {
    return null
  }
  let value: unknown
  try {
    value = JSON.parse(raw)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}
