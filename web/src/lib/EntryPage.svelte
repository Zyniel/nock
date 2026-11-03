<script lang="ts">
  // The entry pages of a room (spec 046, "Entry pages"): the room code line,
  // then the nickname card or the card of a status that refuses entry. The
  // room page checks the nickname and joins.
  import EntryFrame from './EntryFrame.svelte'
  import FocusableLink from './FocusableLink.svelte'
  import { t } from './i18n'
  import type { RoomStatus } from './roomSession'

  let {
    code,
    status,
    isCardShown,
    nicknameText = $bindable(),
    shownError,
    onSubmit,
  }: {
    code: string
    status: RoomStatus
    // True for a status that refuses entry: its card shows instead of the form.
    isCardShown: boolean
    // The nickname as typed (CSS shows it in capitals).
    nicknameText: string
    shownError: 'length' | 'characters' | null
    onSubmit: (event: SubmitEvent) => void
  } = $props()
</script>

<EntryFrame>
  <h1 class="room-code-line">{t('room.heading', { code })}</h1>
  {#if isCardShown}
    <div class="nock-card" data-testid="entry-card">
      <p class="nock-card-title" data-testid="room-status">
        {t(`room.status.${status}`)}
      </p>
      {#if status === 'not_found'}
        <!-- An expired room is deleted (spec 032), so it reads as one that
             never existed: the line says why a room may be gone (P3). -->
        <p class="nock-card-detail" data-testid="entry-detail">
          {t('room.status.not_found_detail')}
        </p>
      {/if}
      <!-- "Voir les grilles" is primary where it is the only way on. -->
      <FocusableLink
        class={[
          'nock-button',
          {
            'nock-button-primary': status === 'not_found',
            'nock-button-secondary': status !== 'not_found',
          },
        ]}
        data-testid="entry-home"
        href="/">{t('share.home')}</FocusableLink
      >
    </div>
  {:else}
    <form class="nock-card" data-testid="nickname-form" onsubmit={onSubmit}>
      <h2 class="nock-card-title">{t('join.heading')}</h2>
      <div class="nock-field">
        <label for="nickname-input">{t('join.nickname_label')}</label>
        <input
          id="nickname-input"
          class="nock-text-input nickname-input"
          data-testid="nickname-input"
          type="text"
          autocomplete="nickname"
          placeholder={t('room.default_nickname')}
          aria-invalid={shownError !== null ? 'true' : undefined}
          aria-describedby={shownError !== null ? 'nickname-error' : undefined}
          bind:value={nicknameText}
        />
      </div>
      {#if shownError !== null}
        <p
          class="nock-error-line nickname-error"
          id="nickname-error"
          data-testid="nickname-error"
          role="alert"
        >
          {shownError === 'length' ? t('join.error.length') : t('join.error.characters')}
        </p>
      {/if}
      <button
        type="submit"
        class="nock-button nock-button-primary"
        data-testid="nickname-submit"
        disabled={status !== 'nickname'}>{t('join.submit')}</button
      >
      <!-- The status of the nickname card: read but not seen. -->
      <p class="visually-hidden" data-testid="room-status">{t(`room.status.${status}`)}</p>
    </form>
  {/if}
</EntryFrame>

<style>
  /* The nickname shows in capitals, the placeholder too, while the value keeps
     the text as typed, so input methods and the caret work as usual (spec 012,
     room page flow step 3). */
  .nickname-input {
    text-transform: uppercase;
  }

  /* The refused nickname's reason, right under the field. */
  .nickname-error {
    margin-top: -6px;
  }
</style>
