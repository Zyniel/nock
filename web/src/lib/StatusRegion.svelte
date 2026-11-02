<script lang="ts" module>
  // How long the region stays empty before it receives a message. A screen reader
  // reads a change of the region, so the message is written in a later batch of
  // changes than the one that emptied it: the same message twice is read twice.
  const WRITE_DELAY_MS = 50
</script>

<script lang="ts">
  import { onDestroy } from 'svelte'

  // A status region (client/hud.md rules 17 and 18): `role="status"`, read but not
  // seen, empty until its first message. The room page holds one for its life and
  // each room sheet holds one.
  let { testId }: { testId: string } = $props()

  let text = $state('')
  let writeTimer: ReturnType<typeof setTimeout> | undefined

  // Empty the region, then write `message` in it.
  export function write(message: string): void {
    clearTimeout(writeTimer)
    text = ''
    writeTimer = setTimeout(() => {
      text = message
    }, WRITE_DELAY_MS)
  }

  // Empty the region and drop a message that was about to be written.
  export function clear(): void {
    clearTimeout(writeTimer)
    text = ''
  }

  onDestroy(() => clearTimeout(writeTimer))
</script>

<p class="visually-hidden" role="status" data-testid={testId}>{text}</p>
