<script lang="ts">
  import AccountEmailForm from './AccountEmailForm.svelte'
  import type { AccountStatus } from './account'
  import { t } from './i18n'
  import type { RoomKey } from './myRooms'

  // The account dialog of the room page (spec 033), a modal dialog. The room
  // page keeps it on the page while accounts are on and opens it with `open`.
  let {
    status,
    room,
    onClosed,
  }: {
    // What GET /api/account answered.
    status: AccountStatus
    // The room the link is asked from.
    room: RoomKey
    // The dialog closed, by its close button or by Escape.
    onClosed: () => void
  } = $props()

  let dialog: HTMLDialogElement | null = $state(null)
  let emailInput: HTMLInputElement | null = $state(null)

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
  class="account-dialog"
  data-testid="account-dialog"
  aria-labelledby="account-dialog-heading"
  onclose={onClosed}
  onkeydown={keepTabInside}
>
  {#if status.signed_in}
    <h2 id="account-dialog-heading">{t('account.signed_in_heading')}</h2>
    <p>{t('account.signed_in_as', { email: status.email ?? '' })}</p>
    <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
    <a data-testid="account-page-link" href="/account" tabindex="0">{t('account.manage')}</a>
  {:else}
    <h2 id="account-dialog-heading">{t('account.dialog_heading')}</h2>
    <p>{t('account.dialog_intro')}</p>
    <AccountEmailForm {room} bind:input={emailInput} />
  {/if}
  <button type="button" data-testid="account-close" onclick={() => dialog?.close()}
    >{t('account.close')}</button
  >
</dialog>

<style>
  .account-dialog {
    box-sizing: border-box;
    width: min(28rem, calc(100vw - 2rem));
    max-height: calc(100dvh - 2rem);
    overflow: auto;
    color: #1f2330;
    background: #ffffff;
    border: 1px solid #5b6070;
    border-radius: 0.5rem;
  }

  .account-dialog h2 {
    margin: 0 0 0.5rem;
    font-size: 1.25rem;
  }

  .account-dialog p {
    overflow-wrap: anywhere;
  }

  [data-testid='account-close'] {
    margin-top: 1rem;
  }
</style>
