<script lang="ts">
  import AccountEmailForm from './AccountEmailForm.svelte'
  import RoomSheet from './RoomSheet.svelte'
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
    // The dialog closed: by its close button, Escape or the backdrop.
    onClosed: () => void
  } = $props()

  let sheet: RoomSheet | undefined = $state()
  let emailInput: HTMLInputElement | null = $state(null)

  // Close the dialog if it is open (client/hud.md rule 16: the room is gone).
  export function close(): void {
    sheet?.close()
  }

  // Show the dialog and move the focus into it: to the address input when it
  // shows, else the browser's choice, its first control.
  export function open(): void {
    sheet?.open()
    emailInput?.focus()
  }
</script>

<RoomSheet
  bind:this={sheet}
  {layout}
  title={status.signed_in ? t('account.signed_in_heading') : t('account.dialog_heading')}
  titleId="account-dialog-heading"
  testId="account-dialog"
  extraClass={room === null ? 'account-dialog under-page-topbar' : 'account-dialog'}
  canCancel={true}
  closesOnBackdrop={true}
  {onClosed}
>
  {#if status.signed_in}
    <p>{t('account.signed_in_as', { email: status.email ?? '' })}</p>
    <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
    <a class="nock-text-link" data-testid="account-page-link" href="/account" tabindex="0">{t('account.manage')}</a>
  {:else}
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
      onclick={() => sheet?.close()}>{t('account.close')}</button
    >
  </div>
</RoomSheet>

<style>
  p {
    margin: 0;
    font-size: 0.95rem;
    overflow-wrap: anywhere;
  }

  .intro {
    font-size: 0.9rem;
    color: var(--nock-muted);
  }

  /* The text link to the account page (app.css), as wide as its text. */
  a {
    align-self: flex-start;
  }

  /* « Fermer », right-aligned. */
  .dialog-end {
    display: flex;
    justify-content: flex-end;
  }
</style>
