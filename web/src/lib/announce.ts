// Where the messages that a screen reader should read go (client/hud.md rules
// 17 and 18). The room page holds one status region for its life, and each room
// sheet holds one while it is open: the page behind a modal dialog is inert, so
// only the sheet's region is read. The region that was taken last is the one
// that receives the messages, and the one taken before it gets them again once
// that one is released.

// Writes a message in a status region.
export type Announcer = (text: string) => void

// The regions that take messages, the oldest first.
const announcers: Announcer[] = []

// Make `write` the region that receives the messages. Returns the function that
// gives that place back to the region taken before it.
export function takeAnnouncing(write: Announcer): () => void {
  announcers.push(write)
  return () => {
    const index = announcers.indexOf(write)
    if (index !== -1) {
      announcers.splice(index, 1)
    }
  }
}

// Announce `text` in the region that receives the messages now. Nothing happens
// when there is none.
export function announce(text: string): void {
  const write = announcers[announcers.length - 1]
  if (write !== undefined) {
    write(text)
  }
}
