<script lang="ts">
  // The button that starts a grid (spec 010): « Jouer » on a grid card,
  // « Rejouer » on a history row (spec 029). One tap creates one room on the
  // grid and loads its page; the button stays disabled while the request runs.
  // When the room could not be created, `hasFailed` turns true: the card or the
  // row shows its error line. The caller gives the button's class, test id,
  // name or description, and its text.
  import type { Snippet } from 'svelte'
  import type { HTMLButtonAttributes } from 'svelte/elements'
  import { playGrid } from './playGrid'

  let {
    number,
    hasFailed = $bindable(false),
    children,
    ...attributes
  }: {
    number: number
    hasFailed?: boolean
    children: Snippet
  } & Omit<HTMLButtonAttributes, 'type' | 'disabled' | 'onclick' | 'children'> = $props()

  let isStarting = $state(false)

  // A page restored from the back-forward cache keeps its old state: start again.
  function onPageShow(event: PageTransitionEvent): void {
    if (event.persisted) {
      isStarting = false
    }
  }

  async function play(): Promise<void> {
    if (isStarting) {
      return
    }
    isStarting = true
    hasFailed = false
    const started = await playGrid(number)
    if (!started) {
      isStarting = false
      hasFailed = true
    }
  }
</script>

<svelte:window onpageshow={onPageShow} />

<button type="button" {...attributes} disabled={isStarting} onclick={play}
  >{@render children()}</button
>
