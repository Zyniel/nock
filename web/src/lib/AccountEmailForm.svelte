<script lang="ts">
  import { askSignInLink, type LinkAnswer } from './account'
  import { t } from './i18n'
  import type { RoomKey } from './myRooms'

  // The e-mail form of spec 033: it asks a sign-in link for the address typed.
  // The room's account dialog and the account page both show it. Its parts are
  // in a column, 12 px apart (spec 048): the field, the error line when the
  // request failed, the button, and the confirmation line once the link is sent.
  let {
    room,
    input = $bindable(null),
  }: {
    // The room the link is asked from, or null on the account page.
    room: RoomKey | null
    // The address input, so that the dialog can move the focus to it.
    input?: HTMLInputElement | null
  } = $props()

  let email = $state('')
  let isSending = $state(false)
  let answer: LinkAnswer | null = $state(null)
  // The address of the last request sent, which `account-sent` names.
  let sentEmail = $state('')

  // Only a refused address is the address's fault: its border turns red. A
  // refusal for too many requests or a failed send leaves it as it is.
  const isAddressRefused = $derived(answer === 'invalid')
  // Whether the error line shows: the input is then described by it.
  const isErrorShown = $derived(answer !== null && answer !== 'sent')

  // The error line's id. A page holds one e-mail form at most (the account
  // page, or the account sheet of a room or of the catalogue), as the input's
  // own id already assumes.
  const ERROR_ID = 'account-email-error'

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault()
    const typed = email
    // A new submit clears the answer to the last one.
    answer = null
    isSending = true
    answer = await askSignInLink(typed, room)
    sentEmail = typed
    isSending = false
  }

  // The text of the error line, for the failed answer shown.
  function errorText(): string {
    if (answer === 'invalid') {
      return t('account.error.email')
    }
    if (answer === 'too_many') {
      return t('account.error.too_many')
    }
    return t('account.error.send')
  }
</script>

<!-- `novalidate`: the server judges the address, so that a refused one shows
     `account-error` rather than the browser's own bubble (spec 046 AC-23). -->
<form class="account-email-form" data-testid="account-email-form" novalidate onsubmit={submit}>
  <div class="nock-field">
    <label for="account-email-input">{t('account.email_label')}</label>
    <input
      id="account-email-input"
      class="nock-text-input"
      data-testid="account-email-input"
      type="email"
      autocomplete="email"
      aria-invalid={isAddressRefused ? 'true' : undefined}
      aria-describedby={isErrorShown ? ERROR_ID : undefined}
      bind:this={input}
      bind:value={email}
    />
  </div>
  {#if isErrorShown}
    <p id={ERROR_ID} class="nock-error-line" data-testid="account-error" role="alert">
      {errorText()}
    </p>
  {/if}
  <button
    type="submit"
    class="nock-button nock-button-primary"
    data-testid="account-email-submit"
    disabled={isSending}>{t('account.send')}</button
  >
  {#if answer === 'sent'}
    <p class="nock-done-line" data-testid="account-sent" role="status">
      {t('account.sent', { email: sentEmail })}
    </p>
  {/if}
</form>

<style>
  /* As wide as the card or the sheet that holds it; its button keeps its own
     width. */
  .account-email-form {
    display: grid;
    gap: 12px;
    justify-items: start;
    justify-self: stretch;
    min-width: 0;
  }
</style>
