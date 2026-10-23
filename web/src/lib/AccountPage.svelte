<script lang="ts">
  import { onMount } from 'svelte'
  import AccountEmailForm from './AccountEmailForm.svelte'
  import EntryFrame from './EntryFrame.svelte'
  import {
    LINK_TOKEN,
    deleteAccount,
    fetchAccountStatus,
    signIn,
    signOut,
    storeMissingIdentities,
  } from './account'
  import { t } from './i18n'

  // The account page `/account` (spec 033). Opened from a sign-in link, its URL
  // fragment holds the link's token: the page drops it from its URL, then signs
  // in with it. Otherwise it shows whether this browser is signed in. Spec 048
  // draws it as one card in the entry frame; each state is one line in it, and
  // the deletion is asked once more in the same card.
  type State = 'loading' | 'signing_in' | 'signed_in' | 'link_invalid' | 'signed_out' | 'deleted' | 'error'

  let pageState: State = $state('loading')
  let email = $state('')
  // The room the link was asked from, after a sign-in that linked it.
  let roomCode: string | null = $state(null)
  // Whether the deletion is asked: `account-delete` is a disclosure that shows
  // and hides the panel with the warning and the confirmation.
  let isDeleteAsked = $state(false)
  let deleteButton: HTMLButtonElement | null = $state(null)

  async function signInWithLink(token: string): Promise<void> {
    pageState = 'signing_in'
    // The token leaves the URL before anything else: no history entry keeps it.
    history.replaceState(null, '', '/account')
    const result = await signIn(token)
    if (result === 'invalid') {
      pageState = 'link_invalid'
      return
    }
    if (result === null) {
      pageState = 'error'
      return
    }
    storeMissingIdentities(result.rooms)
    email = result.email
    roomCode = result.room_code
    pageState = 'signed_in'
  }

  async function loadStatus(): Promise<void> {
    const status = await fetchAccountStatus()
    if (status === null) {
      pageState = 'error'
      return
    }
    if (status.signed_in && status.email !== null) {
      email = status.email
      pageState = 'signed_in'
      return
    }
    pageState = 'signed_out'
  }

  // The token of a sign-in link in the URL's fragment, or null.
  function linkToken(): string | null {
    const token = location.hash.slice(1)
    return LINK_TOKEN.test(token) ? token : null
  }

  // A sign-in link opened while this page shows only changes the fragment, and
  // the browser does not load the page again: the page signs in with it then.
  function followLink(): void {
    const token = linkToken()
    if (token !== null) {
      void signInWithLink(token)
    }
  }

  // Once, when the page shows.
  onMount(() => {
    const token = linkToken()
    if (token !== null) {
      void signInWithLink(token)
    } else {
      void loadStatus()
    }
    window.addEventListener('hashchange', followLink)
    return () => window.removeEventListener('hashchange', followLink)
  })

  function toggleDeletion(): void {
    isDeleteAsked = !isDeleteAsked
  }

  // `account-delete-cancel`: the question closes and the focus goes back to
  // `account-delete`, as a disclosure does, rather than drop to the page with
  // the hidden panel.
  function keepAccount(): void {
    isDeleteAsked = false
    deleteButton?.focus()
  }

  async function leave(): Promise<void> {
    isDeleteAsked = false
    if (await signOut()) {
      pageState = 'signed_out'
    } else {
      pageState = 'error'
    }
  }

  async function confirmDeletion(): Promise<void> {
    isDeleteAsked = false
    if (await deleteAccount()) {
      pageState = 'deleted'
    } else {
      pageState = 'error'
    }
  }
</script>


<main class="nock-plain-page account-page" data-testid="account-page" data-state={pageState}>
  <EntryFrame>
    <div class="nock-card" data-testid="account-card">
      <h1 class="nock-card-title">{t('account.page_heading')}</h1>
      <!-- While the first request runs (`loading`), the card holds its title
           only, so that no signed-out form flashes before the address. -->
      {#if pageState === 'signing_in'}
        <p class="nock-muted-line" data-testid="account-state-line" role="status">
          {t('account.signing_in')}
        </p>
      {:else if pageState === 'signed_in'}
        <p class="nock-card-text account-email" data-testid="account-email">
          {t('account.signed_in_as', { email })}
        </p>
        {#if roomCode !== null}
          <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
          <a
            class="nock-text-link"
            data-testid="account-room-link"
            href={`/r/${roomCode}`}
            tabindex="0">{t('account.back_to_room', { code: roomCode })}</a
          >
        {/if}
        <div class="nock-button-row" data-testid="account-actions">
          <button
            type="button"
            class="nock-button nock-button-secondary"
            data-testid="account-sign-out"
            onclick={leave}>{t('account.sign_out')}</button
          >
          <!-- Pressed (quiet) while the deletion is asked. -->
          <button
            type="button"
            class="nock-button"
            class:nock-button-secondary={!isDeleteAsked}
            class:nock-button-quiet={isDeleteAsked}
            data-testid="account-delete"
            aria-expanded={isDeleteAsked ? 'true' : 'false'}
            aria-controls="account-delete-panel"
            bind:this={deleteButton}
            onclick={toggleDeletion}>{t('account.delete')}</button
          >
        </div>
        <div
          id="account-delete-panel"
          class="account-delete-panel"
          data-testid="account-delete-panel"
          hidden={!isDeleteAsked}
        >
          <p class="nock-card-text" data-testid="account-delete-warning">
            {t('account.delete_warning')}
          </p>
          <div class="nock-button-row">
            <button
              type="button"
              class="nock-button nock-button-primary"
              data-testid="account-delete-confirm"
              onclick={confirmDeletion}>{t('account.delete_confirm')}</button
            >
            <button
              type="button"
              class="nock-button nock-button-secondary"
              data-testid="account-delete-cancel"
              onclick={keepAccount}>{t('account.delete_cancel')}</button
            >
          </div>
        </div>
      {:else if pageState === 'link_invalid'}
        <p class="nock-error-line" data-testid="account-state-line" role="alert">
          {t('account.link_invalid')}
        </p>
        <AccountEmailForm room={null} />
      {:else if pageState === 'signed_out'}
        <p class="nock-card-text">{t('account.signed_out_intro')}</p>
        <AccountEmailForm room={null} />
      {:else if pageState === 'deleted'}
        <p class="nock-done-line" data-testid="account-state-line" role="status">
          {t('account.deleted')}
        </p>
        <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
        <a class="nock-button nock-button-primary" data-testid="account-home" href="/" tabindex="0"
          >{t('share.home')}</a
        >
      {:else if pageState === 'error'}
        <p class="nock-error-line" data-testid="account-state-line" role="alert">
          {t('account.error.generic')}
        </p>
      {/if}
    </div>
  </EntryFrame>
</main>

<style>
  /* A long address wraps anywhere rather than widen the page. */
  .account-email {
    overflow-wrap: anywhere;
  }

  /* The deletion asked once more, under a line-grey divider, as wide as the
     card's content: the warning, then its two buttons 12 px below. */
  .account-delete-panel {
    display: grid;
    gap: 12px;
    justify-items: start;
    justify-self: stretch;
    padding-top: 12px;
    border-top: 1px solid var(--nock-line);
  }

  .account-delete-panel[hidden] {
    display: none;
  }
</style>
