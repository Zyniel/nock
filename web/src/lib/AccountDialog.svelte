<script lang="ts">
  import AccountEmailForm from './AccountEmailForm.svelte'
  import type { AccountStatus } from './account'
  import { t } from './i18n'
  import type { RoomKey } from './myRooms'

  // The account dialog of spec 033, a modal dialog with the look of a room
  // sheet (spec 043): centred in the column layout, a bottom sheet in the sheet
  // layout. The room page, and the catalogue's "Compte" (spec 046), keep it
  // on the page while accounts are on and open it with `open`. Outside a room
  // the signed-out intro does not speak of a room, the link is asked with no
  // room, and the bottom sheet leaves the 56 px page top bar uncovered.
  let {
    layout,
    status,
    room,
    onClosed,
  }: {
    layout: 'sheet' | 'column'
    // What GET /api/account answered.
    status: AccountStatus
    // The room the link is asked from, or null outside a room.
    room: RoomKey | null
    // The dialog closed, by its close button or by Escape.
    onClosed: () => void
  } = $props()

  let dialog: HTMLDialogElement | null = $state(null)
  let emailInput: HTMLInputElement | null = $state(null)

  // Close the dialog if it is open (client/hud.md rule 16: the room is gone).
  export function close(): void {
    dialog?.close()
  }

  // Show the dialog and move the focus into it: to the address input when it
  // shows, else to its first control.
  export function open(): void {
    if (dialog === null || dialog.open) {
      return
    }
    dialog.showModal()
    if (emailInput !== null) {
      emailInput.focus()
      return
    }
    tabStops()[0]?.focus()
  }

  // A click on the backdrop lands on the dialog itself, outside its box.
  function closeOnBackdrop(event: MouseEvent): void {
    if (dialog === null || event.target !== dialog) {
      return
    }
    const box = dialog.getBoundingClientRect()
    const isInside =
      event.clientX >= box.left &&
      event.clientX <= box.right &&
      event.clientY >= box.top &&
      event.clientY <= box.bottom
    if (!isInside) {
      dialog.close()
    }
  }

  // The controls of the dialog that Tab moves between, in document order.
  function tabStops(): HTMLElement[] {
    if (dialog === null) {
      return []
    }
    const selector = 'a[href], button:not(:disabled), input:not(:disabled)'
    return Array.from(dialog.querySelectorAll<HTMLElement>(selector))
  }

  // Tab and Shift+Tab go round the controls of the dialog: the page behind it is
  // inert, and the focus must not leave for the browser's own controls.
  function keepTabInside(event: KeyboardEvent): void {
    if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) {
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
</script>

<dialog
  bind:this={dialog}
  class="room-sheet account-dialog"
  class:bottom={layout === 'sheet'}
  class:under-page-topbar={room === null}
  data-testid="account-dialog"
  aria-labelledby="account-dialog-heading"
  onclick={closeOnBackdrop}
  onclose={onClosed}
  onkeydown={keepTabInside}
>
  {#if status.signed_in}
    <h2 class="room-sheet-title" id="account-dialog-heading">{t('account.signed_in_heading')}</h2>
    <p>{t('account.signed_in_as', { email: status.email ?? '' })}</p>
    <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
    <a class="nock-text-link" data-testid="account-page-link" href="/account" tabindex="0">{t('account.manage')}</a>
  {:else}
    <h2 class="room-sheet-title" id="account-dialog-heading">{t('account.dialog_heading')}</h2>
    <p class="intro">
      {room === null ? t('account.signed_out_intro') : t('account.dialog_intro')}
    </p>
    <AccountEmailForm {room} bind:input={emailInput} />
  {/if}
  <div class="dialog-end">
    <button
      type="button"
      class="nock-button nock-button-secondary"
      data-testid="account-close"
      onclick={() => dialog?.close()}>{t('account.close')}</button
    >
  </div>
</dialog>

<style>
  .account-dialog p {
    margin: 0;
    font-size: 0.95rem;
    overflow-wrap: anywhere;
  }

  .account-dialog .intro {
    font-size: 0.9rem;
    color: var(--nock-muted);
  }

  /* The text link to the account page (app.css), as wide as its text. */
  .account-dialog a {
    align-self: flex-start;
  }

  /* « Fermer », right-aligned. */
  .dialog-end {
    display: flex;
    justify-content: flex-end;
  }
</style>
