// The copy buttons of the share links: the room page's invitation link
// (`copy-link`, spec 011) and the recap's share link (`recap-copy`, spec 028).
// A click writes the link to the clipboard; after a successful copy the button
// reads "copied" for COPIED_DISPLAY_MS. Without a usable clipboard (none, or one
// that refuses) nothing changes.

// How long a copy button reads "copied" after a successful copy (spec 011).
const COPIED_DISPLAY_MS = 2000

// The handler of one copy button.
export interface LinkCopier {
  // Write `link` to the clipboard.
  copy: (link: string) => Promise<void>
  // Cancel the timer that ends the "copied" display. Call it when the button's
  // page goes away, so that the timer does not fire on a destroyed page.
  stop: () => void
}

// The handler of one copy button. `onCopiedChange(true)` comes after each
// successful copy, and `onCopiedChange(false)` COPIED_DISPLAY_MS after the last
// one.
export function newLinkCopier(onCopiedChange: (isCopied: boolean) => void): LinkCopier {
  let copiedTimer: ReturnType<typeof setTimeout> | undefined

  async function copy(link: string): Promise<void> {
    if (navigator.clipboard === undefined || navigator.clipboard === null) {
      return
    }
    try {
      await navigator.clipboard.writeText(link)
    } catch {
      return
    }
    onCopiedChange(true)
    clearTimeout(copiedTimer)
    copiedTimer = setTimeout(() => {
      onCopiedChange(false)
    }, COPIED_DISPLAY_MS)
  }

  function stop(): void {
    clearTimeout(copiedTimer)
  }

  return { copy, stop }
}
