<script lang="ts">
  import { onDestroy, type Snippet } from 'svelte'
  import { takeAnnouncing } from './announce'
  import StatusRegion from './StatusRegion.svelte'

  // The frame the room sheets share (client/hud.md rule 13): the host's
  // settings, the account, the recap and the room-gone dialog. A modal dialog
  // named by its title, centred in the column layout and a bottom sheet in the
  // sheet layout (app.css, `.room-sheet`). It holds what they do alike: the
  // Tab trap, the rules of Escape and of the backdrop, and the close event. The
  // sheets put their content in it and keep their own look. It holds the
  // sheet's status region (client/hud.md rule 18): while the sheet is open it
  // takes the messages that the page's region would take.
  let {
    layout,
    title,
    titleId,
    testId,
    extraClass = '',
    role = 'dialog',
    describedBy,
    dataState,
    canCancel,
    closesOnBackdrop,
    keepsFocusOnPress = false,
    onClosed,
    children,
  }: {
    // The room's layout: a dialog in the column layout, a bottom sheet in the
    // sheet layout.
    layout: 'sheet' | 'column'
    title: string
    // The id of the title, which names the dialog.
    titleId: string
    testId: string
    // Classes of the sheet besides `room-sheet`: `over-all`, `under-page-topbar`.
    extraClass?: string
    role?: 'dialog' | 'alertdialog'
    // The id of the element that describes an alert dialog.
    describedBy?: string
    // A `data-state` the tests read.
    dataState?: string
    // Whether Escape closes the sheet.
    canCancel: boolean
    // Whether a press and its release both on the backdrop close the sheet.
    closesOnBackdrop: boolean
    // Whether a press anywhere but on a control leaves the focus where it is.
    keepsFocusOnPress?: boolean
    // The sheet closed, whatever closed it.
    onClosed: () => void
    children: Snippet
  } = $props()

  // What Tab moves between.
  const TABBABLE_SELECTOR =
    'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]'

  let dialog: HTMLDialogElement | null = $state(null)
  // True from a press that started on the backdrop until the click it ends in.
  let isPressOnBackdrop = false
  let region: StatusRegion | undefined = $state()
  // Gives the messages back to the region behind, or null while the sheet is shut.
  let releaseAnnouncing: (() => void) | null = null

  function stopAnnouncing(): void {
    if (releaseAnnouncing !== null) {
      releaseAnnouncing()
      releaseAnnouncing = null
    }
  }

  // The sheet is closed, whatever closed it.
  function closed(): void {
    stopAnnouncing()
    onClosed()
  }

  onDestroy(stopAnnouncing)

  // Show the sheet over the page; the browser moves the focus into it. Nothing
  // happens when it is already open or is no longer on the page.
  export function open(): void {
    if (dialog === null || dialog.open || !dialog.isConnected) {
      return
    }
    // A close whose event has not come yet leaves its place on the stack.
    stopAnnouncing()
    region?.clear()
    releaseAnnouncing = takeAnnouncing((text) => region?.write(text))
    dialog.showModal()
  }

  // Close the sheet if it is open. Returns whether it was open.
  export function close(): boolean {
    if (dialog === null || !dialog.open) {
      return false
    }
    stopAnnouncing()
    dialog.close()
    return true
  }

  // The controls of the sheet that Tab moves between, in document order.
  function tabStops(): HTMLElement[] {
    if (dialog === null) {
      return []
    }
    const stops: HTMLElement[] = []
    for (const element of dialog.querySelectorAll<HTMLElement>(TABBABLE_SELECTOR)) {
      const isShown = element.getClientRects().length > 0
      if (isShown && element.tabIndex >= 0 && !element.matches(':disabled')) {
        stops.push(element)
      }
    }
    return stops
  }

  // Tab and Shift+Tab go round the controls of the sheet: the page behind it is
  // inert, and the focus must not leave for the browser's own controls.
  function keepTabInside(event: KeyboardEvent): void {
    if (event.altKey || event.ctrlKey || event.metaKey) {
      return
    }
    const stops = tabStops()
    if (stops.length === 0) {
      event.preventDefault()
      return
    }
    const first = stops[0]
    const last = stops[stops.length - 1]
    const focused = document.activeElement
    if (event.shiftKey && (focused === first || focused === dialog)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && focused === last) {
      event.preventDefault()
      first.focus()
    }
  }

  function onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape' && !canCancel) {
      event.preventDefault()
      return
    }
    if (event.key === 'Tab') {
      keepTabInside(event)
    }
  }

  // The browser's close request (Escape, the Android back gesture).
  function onCancel(event: Event): void {
    if (!canCancel) {
      event.preventDefault()
    }
  }

  // A mouse event is on the backdrop when it lands on the dialog itself,
  // outside its box.
  function isOnBackdrop(event: MouseEvent): boolean {
    if (dialog === null || event.target !== dialog) {
      return false
    }
    const box = dialog.getBoundingClientRect()
    const isInside =
      event.clientX >= box.left &&
      event.clientX <= box.right &&
      event.clientY >= box.top &&
      event.clientY <= box.bottom
    return !isInside
  }

  // Keep the focus where it is, unless the press is on a control.
  function keepFocusOnPress(event: MouseEvent): void {
    const target = event.target
    if (target instanceof Element && target.closest(TABBABLE_SELECTOR) !== null) {
      return
    }
    event.preventDefault()
  }

  function onPress(event: MouseEvent): void {
    isPressOnBackdrop = isOnBackdrop(event)
    if (keepsFocusOnPress) {
      keepFocusOnPress(event)
    }
  }

  // The click that ends a press closes the sheet when the press and the click
  // are both on the backdrop.
  function onClick(event: MouseEvent): void {
    const startedOnBackdrop = isPressOnBackdrop
    isPressOnBackdrop = false
    if (closesOnBackdrop && startedOnBackdrop && isOnBackdrop(event)) {
      dialog?.close()
    }
  }
</script>

<dialog
  bind:this={dialog}
  class="room-sheet {extraClass}"
  class:bottom={layout === 'sheet'}
  data-testid={testId}
  data-state={dataState}
  {role}
  aria-labelledby={titleId}
  aria-describedby={describedBy}
  oncancel={onCancel}
  onclose={closed}
  onkeydown={onKeydown}
  onmousedown={onPress}
  onclick={onClick}
>
  <h2 class="room-sheet-title" id={titleId}>{title}</h2>
  {@render children()}
  <StatusRegion bind:this={region} testId="sheet-status-region" />
</dialog>
