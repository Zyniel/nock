<script lang="ts">
  // The frame of the room's two popovers, the Aide menu and the Menu (spec 043,
  // "Popovers: shared rules"). It stays on the page while closed, with the
  // `hidden` attribute. It hangs under the top bar at its button, takes the
  // focus when it opens, and gives Escape to the room page.
  import { tick } from 'svelte'
  import type { Snippet } from 'svelte'
  import { listenForEscape } from './escapeKey'

  let {
    testId,
    label,
    isOpen,
    form,
    side,
    anchor,
    element = $bindable(null),
    onEscape,
    children,
  }: {
    testId: string
    // The accessible name of the group.
    label: string
    isOpen: boolean
    // The form of the top bar: the place of the popover follows it.
    form: 'phone' | 'computer'
    // 'left': the popover starts at its button's left edge (the Aide menu);
    // 'right': it ends at the right (the Menu).
    side: 'left' | 'right'
    // The top-bar button that opens it.
    anchor: HTMLButtonElement | null
    element?: HTMLElement | null
    onEscape: () => void
    children: Snippet
  } = $props()

  // The space kept between a popover and the window's edges, and between the
  // top bar and a popover (specs/_design/room.md « Layers »).
  const EDGE_PX = 6
  const UNDER_BAR_PX = 4

  let top = $state(0)
  let left: number | null = $state(null)
  let right: number | null = $state(null)

  // The elements a popover can give the focus to, in document order.
  const ITEM_SELECTOR = 'button, a[href]'

  // Work out the place from the top bar and the button, as they are now.
  function place(): void {
    if (element === null || anchor === null) {
      return
    }
    const bar = anchor.closest('header')
    const barBottom = bar === null ? 0 : bar.getBoundingClientRect().bottom
    const buttonBox = anchor.getBoundingClientRect()
    top = barBottom + UNDER_BAR_PX
    if (side === 'right') {
      left = null
      right = form === 'phone' ? EDGE_PX : window.innerWidth - buttonBox.right
      return
    }
    right = null
    const width = element.getBoundingClientRect().width
    const farthestLeft = window.innerWidth - EDGE_PX - width
    left = Math.max(0, Math.min(buttonBox.left, farthestLeft))
  }

  // The first item that is not disabled takes the focus; with none, the
  // popover itself does.
  function focusFirstItem(): void {
    if (element === null) {
      return
    }
    for (const item of Array.from(element.querySelectorAll<HTMLElement>(ITEM_SELECTOR))) {
      if (!(item instanceof HTMLButtonElement && item.disabled)) {
        item.focus()
        return
      }
    }
    element.focus()
  }

  async function placeAndFocus(): Promise<void> {
    await tick()
    place()
    focusFirstItem()
  }

  // Each opening places the popover and moves the focus into it. While it is
  // open it follows the window's size.
  let wasOpen = false
  $effect(() => {
    const open = isOpen
    if (open && !wasOpen) {
      void placeAndFocus()
    }
    wasOpen = open
    if (!open) {
      return
    }
    window.addEventListener('resize', place)
    return () => window.removeEventListener('resize', place)
  })

  // Escape while the focus is inside the popover.
  $effect(() => {
    if (element === null) {
      return
    }
    return listenForEscape(element, onEscape)
  })
</script>

<div
  class="nock-menu room-popover"
  data-testid={testId}
  id={testId}
  role="group"
  aria-label={label}
  tabindex="-1"
  hidden={!isOpen}
  style:top="{top}px"
  style:left={left === null ? null : `${left}px`}
  style:right={right === null ? null : `${right}px`}
  style:max-height="calc(100dvh - {top}px - {EDGE_PX}px)"
  bind:this={element}
>
  {@render children()}
</div>

<style>
  /* Over the play area, layer 8 (specs/_design/room.md « Layers »). Its content scrolls
     inside it when the window is too low for it. */
  .room-popover {
    position: fixed;
    z-index: 8;
    box-sizing: border-box;
    max-width: calc(100vw - 12px);
    overflow-y: auto;
  }

  /* The popover scrolls, and would cut a ring drawn outside an item: the
     rings are drawn inside. */
  .room-popover:focus-visible,
  .room-popover :global(:focus-visible) {
    outline-offset: -2px;
  }
</style>
