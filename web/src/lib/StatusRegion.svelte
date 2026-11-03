<script lang="ts" module>
  // How long the region stays empty before it receives a message. A screen reader
  // reads a change of the region, so the message is written in a later batch of
  // changes than the one that emptied it: the same message twice is read twice.
  const WRITE_DELAY_MS = 50

  // How long a message stays in the region after it was written; the region is
  // empty again after it (client/hud.md rule 17).
  const MESSAGE_HOLD_MS = 5000
</script>

<script lang="ts">
  import { onDestroy } from 'svelte'

  // A status region (client/hud.md rules 17 and 18): `role="status"`, read but not
  // seen, empty until its first message and again `MESSAGE_HOLD_MS` after its last
  // message was written. The room page holds one for its life and each room sheet
  // holds one.
  let { testId }: { testId: string } = $props()

  let text = $state('')
  // The region's next change: writing a message, or emptying it once the message
  // was held long enough. A new message or `clear()` cancels it.
  let nextChangeTimer: ReturnType<typeof setTimeout> | undefined

  // Empty the region, then write `message` in it and empty it again
  // `MESSAGE_HOLD_MS` later.
  export function write(message: string): void {
    clearTimeout(nextChangeTimer)
    text = ''
    nextChangeTimer = setTimeout(() => {
      text = message
      nextChangeTimer = setTimeout(() => {
        text = ''
      }, MESSAGE_HOLD_MS)
    }, WRITE_DELAY_MS)
  }

  // Empty the region and drop a message that was about to be written.
  export function clear(): void {
    clearTimeout(nextChangeTimer)
    text = ''
  }

  onDestroy(() => clearTimeout(nextChangeTimer))
</script>

<p class="visually-hidden" role="status" data-testid={testId}>{text}</p>
