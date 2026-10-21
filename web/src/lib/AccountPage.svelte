<script lang="ts">
  import { onMount } from 'svelte'
  import AccountEmailForm from './AccountEmailForm.svelte'
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
  // in with it. Otherwise it shows whether this browser is signed in.
  type State = 'loading' | 'signing_in' | 'signed_in' | 'link_invalid' | 'signed_out' | 'deleted' | 'error'

  let pageState: State = $state('loading')
  let email = $state('')
  // The room the link was asked from, after a sign-in that linked it.
  let roomCode: string | null = $state(null)
  let isDeleteAsked = $state(false)

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

  async function leave(): Promise<void> {
    if (await signOut()) {
      pageState = 'signed_out'
    } else {
      pageState = 'error'
    }
  }

  async function confirmDeletion(): Promise<void> {
    if (await deleteAccount()) {
      pageState = 'deleted'
    } else {
      pageState = 'error'
    }
  }
</script>

<main class="account-page" data-testid="account-page" data-state={pageState}>
  <h1>{t('account.page_heading')}</h1>
  {#if pageState === 'signing_in'}
    <p>{t('account.signing_in')}</p>
  {:else if pageState === 'signed_in'}
    <p data-testid="account-email">{t('account.signed_in_as', { email })}</p>
    {#if roomCode !== null}
      <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
      <p>
        <a data-testid="account-room-link" href={`/r/${roomCode}`} tabindex="0"
          >{t('account.back_to_room', { code: roomCode })}</a
        >
      </p>
    {/if}
    <div class="account-actions">
      <button type="button" data-testid="account-sign-out" onclick={leave}
        >{t('account.sign_out')}</button
      >
      <button type="button" data-testid="account-delete" onclick={() => (isDeleteAsked = true)}
        >{t('account.delete')}</button
      >
    </div>
    {#if isDeleteAsked}
      <p data-testid="account-delete-warning">{t('account.delete_warning')}</p>
      <div class="account-actions">
        <button type="button" data-testid="account-delete-confirm" onclick={confirmDeletion}
          >{t('account.delete_confirm')}</button
        >
        <button
          type="button"
          data-testid="account-delete-cancel"
          onclick={() => (isDeleteAsked = false)}>{t('account.delete_cancel')}</button
        >
      </div>
    {/if}
  {:else if pageState === 'link_invalid'}
    <p>{t('account.link_invalid')}</p>
    <AccountEmailForm room={null} />
  {:else if pageState === 'signed_out'}
    <p>{t('account.signed_out_intro')}</p>
    <AccountEmailForm room={null} />
  {:else if pageState === 'deleted'}
    <p>{t('account.deleted')}</p>
  {:else if pageState === 'error'}
    <p>{t('account.error.generic')}</p>
  {/if}
</main>

<style>
  .account-page p {
    overflow-wrap: anywhere;
  }

  .account-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 1rem 0;
  }
</style>
