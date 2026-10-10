import fr from '../i18n/fr.json'

export type MessageKey = keyof typeof fr

// Return the French text of a key. Each {name} is replaced by the matching
// value; a placeholder with no value is left as written.
export function t(key: MessageKey, values?: Record<string, string | number>): string {
  const text: string = fr[key]
  if (values === undefined) {
    return text
  }
  return text.replace(/\{(\w+)\}/g, (placeholder: string, name: string) => {
    if (name in values) {
      return String(values[name])
    }
    return placeholder
  })
}
