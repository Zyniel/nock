<script lang="ts">
  // The content of the room's Menu (spec 043, "Menu"): the three display
  // switches, « Inviter », the host's settings and the account when they
  // apply, then the timer and the way back to the grids. A detail is hidden
  // from screen readers: a switch's state is its `aria-pressed`.
  import { t } from './i18n'

  let {
    isAuthorsViewOn,
    isOthersTintOn,
    isAccessibilityOn,
    isHost,
    isAccountShown,
    isTimerShown,
    onToggleAuthors,
    onToggleOthersTint,
    onToggleAccessibility,
    onInvite,
    onOpenHostSettings,
    onOpenAccount,
    onToggleTimer,
  }: {
    isAuthorsViewOn: boolean
    isOthersTintOn: boolean
    isAccessibilityOn: boolean
    // « Réglages de l'hôte » is there while `you` is the host.
    isHost: boolean
    // « Compte » is there while accounts are on (spec 033).
    isAccountShown: boolean
    isTimerShown: boolean
    onToggleAuthors: () => void
    onToggleOthersTint: () => void
    onToggleAccessibility: () => void
    onInvite: () => void
    onOpenHostSettings: () => void
    onOpenAccount: () => void
    onToggleTimer: () => void
  } = $props()

  // A switch flips in place and keeps the focus, so that several can be
  // flipped in a row; a click does not focus a button in every engine.
  function flipSwitch(event: MouseEvent, onToggle: () => void): void {
    if (event.currentTarget instanceof HTMLButtonElement) {
      event.currentTarget.focus()
    }
    onToggle()
  }
</script>

{#snippet switchItem(
  testId: string,
  label: string,
  isOn: boolean,
  detail: string,
  onToggle: () => void,
)}
  <button
    type="button"
    class="nock-menu-item"
    data-testid={testId}
    aria-pressed={isOn}
    onclick={(event) => flipSwitch(event, onToggle)}
    ><span>{label}</span><span class="nock-menu-detail" aria-hidden="true">{detail}</span></button
  >
{/snippet}

{@render switchItem(
  'authors-switch',
  t('authors.switch'),
  isAuthorsViewOn,
  isAuthorsViewOn ? t('authors.on') : t('authors.off'),
  onToggleAuthors,
)}
{@render switchItem(
  'others-tint-switch',
  t('others_tint.switch'),
  isOthersTintOn,
  isOthersTintOn ? t('others_tint.on') : t('others_tint.off'),
  onToggleOthersTint,
)}
{@render switchItem(
  'access-switch',
  t('access.switch'),
  isAccessibilityOn,
  isAccessibilityOn ? t('access.on') : t('access.off'),
  onToggleAccessibility,
)}
<button type="button" class="nock-menu-item" data-testid="invite-open" onclick={onInvite}
  ><span>{t('menu.invite')}</span><span class="nock-menu-detail" aria-hidden="true"
    >{t('menu.invite_detail')}</span
  ></button
>
{#if isHost}
  <button
    type="button"
    class="nock-menu-item"
    data-testid="host-settings-open"
    onclick={onOpenHostSettings}><span>{t('settings.heading')}</span></button
  >
{/if}
{#if isAccountShown}
  <button type="button" class="nock-menu-item" data-testid="account-open" onclick={onOpenAccount}
    ><span>{t('account.open')}</span></button
  >
{/if}
<hr class="nock-menu-separator" />
<button type="button" class="nock-menu-item" data-testid="timer-toggle" onclick={onToggleTimer}
  ><span>{isTimerShown ? t('timer.hide') : t('timer.toggle_label')}</span></button
>
<!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
<a class="nock-menu-item back-to-grids" data-testid="back-to-grids" href="/" tabindex="0"
  ><span>{t('menu.back')}</span></a
>

<style>
  .back-to-grids {
    text-decoration: none;
  }
</style>
