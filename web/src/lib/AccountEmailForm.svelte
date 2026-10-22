<script lang="ts">
  import { askSignInLink, type LinkAnswer } from './account'
  import { t } from './i18n'
  import type { RoomKey } from './myRooms'

  // The e-mail form of spec 033: it asks a sign-in link for the address typed.
  // The room's account dialog and the account page both show it.
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

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault()
    const typed = email
    isSending = true
    answer = await askSignInLink(typed, room)
    sentEmail = typed
    isSending = false
  }

  function errorText(failure: LinkAnswer): string {
    if (failure === 'invalid') {
      return t('account.error.email')
    }
    if (failure === 'too_many') {
      return t('account.error.too_many')
    }
    return t('account.error.send')
  }
</script>

<form class="account-email-form" data-testid="account-email-form" onsubmit={submit}>
  <label for="account-email-input">{t('account.email_label')}</label>
  <input
    id="account-email-input"
    data-testid="account-email-input"
    type="email"
    autocomplete="email"
    bind:this={input}
    bind:value={email}
  />
  <button
    type="submit"
    class="nock-button nock-button-primary"
    data-testid="account-email-submit" disabled={isSending}
    >{t('account.send')}</button
  >
</form>
{#if answer === 'sent'}
  <p data-testid="account-sent" role="status">{t('account.sent', { email: sentEmail })}</p>
{:else if answer !== null}
  <p data-testid="account-error" role="alert">{errorText(answer)}</p>
{/if}

<style>
  .account-email-form {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
  }

  .account-email-form label {
    flex-basis: 100%;
  }

  /* The input never widens the page on a small window (spec 006 AC-5). */
  .account-email-form input {
    flex: 1 1 12rem;
    min-width: 0;
    max-width: 100%;
    box-sizing: border-box;
  }

  p {
    overflow-wrap: anywhere;
  }
</style>
