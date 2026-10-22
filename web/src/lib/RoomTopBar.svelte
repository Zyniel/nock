<script lang="ts">
  // The room's top bar (spec 043, "Top bar"): the timer slot and five buttons.
  // The phone top bar (54 px) draws each icon above its label; the computer top
  // bar (56 px) starts with the brand and draws each icon beside its label. The
  // room page decides which form shows and what each button does.
  import RoomTimer from './RoomTimer.svelte'
  import TopBarButton from './TopBarButton.svelte'
  import { unreadBadgeText } from './chat'
  import { t } from './i18n'
  import { NOCK_MARK_POINTS } from './icons'

  let {
    form,
    isTimerShown,
    timerBaseMs,
    isTimerRunning,
    timerAnchor,
    isSolved,
    isPencilMode,
    isAideOpen,
    isMenuOpen,
    isSalonOpen,
    unreadLines,
    salonLabel,
    aideButton = $bindable(null),
    menuButton = $bindable(null),
    chatToggle = $bindable(null),
    onShowTimer,
    onUndo,
    onTogglePencil,
    onToggleAide,
    onToggleSalon,
    onToggleMenu,
  }: {
    form: 'phone' | 'computer'
    isTimerShown: boolean
    timerBaseMs: number
    isTimerRunning: boolean
    timerAnchor: number
    // Once the grid is solved, « Annuler » and « Crayon » are disabled.
    isSolved: boolean
    isPencilMode: boolean
    isAideOpen: boolean
    isMenuOpen: boolean
    isSalonOpen: boolean
    // The messages of others that came since the stream was last shown.
    unreadLines: number
    // The accessible name of « Salon » while the badge shows, else null.
    salonLabel: string | null
    aideButton?: HTMLButtonElement | null
    menuButton?: HTMLButtonElement | null
    chatToggle?: HTMLButtonElement | null
    onShowTimer: () => void
    onUndo: () => void
    onTogglePencil: () => void
    onToggleAide: () => void
    onToggleSalon: () => void
    onToggleMenu: () => void
  } = $props()
</script>

{#snippet undoButton()}
  <TopBarButton
    testId="undo-button"
    icon="undo"
    label={t('room.undo')}
    disabled={isSolved}
    onclick={onUndo}
  />
{/snippet}

{#snippet pencilButton()}
  <TopBarButton
    testId="pencil-toggle"
    icon="crayon"
    label={t('pencil.toggle')}
    ariaPressed={isPencilMode}
    disabled={isSolved}
    onclick={onTogglePencil}
  />
{/snippet}

{#snippet aideMenuButton()}
  <TopBarButton
    testId="aide-button"
    icon="aide"
    label={t('topbar.aide')}
    ariaExpanded={isAideOpen}
    ariaControls="aide-menu"
    bind:element={aideButton}
    onclick={onToggleAide}
  >
    {#if form === 'computer'}
      <span class="aide-caret" data-testid="aide-caret" aria-hidden="true"></span>
    {/if}
  </TopBarButton>
{/snippet}

{#snippet salonButton()}
  <TopBarButton
    testId="chat-toggle"
    icon="salon"
    label={t('topbar.salon')}
    ariaLabel={salonLabel}
    ariaExpanded={isSalonOpen}
    ariaControls="salon"
    bind:element={chatToggle}
    onclick={onToggleSalon}
  >
    {#if unreadLines > 0}
      <span class="nock-badge chat-unread" data-testid="chat-unread" aria-hidden="true"
        >{unreadBadgeText(unreadLines)}</span
      >
    {/if}
  </TopBarButton>
{/snippet}

{#snippet roomMenuButton()}
  <TopBarButton
    testId="menu-button"
    icon="menu"
    label={t('topbar.menu')}
    ariaExpanded={isMenuOpen}
    ariaControls="room-menu"
    bind:element={menuButton}
    onclick={onToggleMenu}
  />
{/snippet}

<header class="room-topbar {form}" data-testid="room-topbar">
  {#if form === 'computer'}
    <span class="topbar-brand" data-testid="topbar-brand"
      ><svg viewBox="0 0 10 14" aria-hidden="true"><polygon points={NOCK_MARK_POINTS} /></svg
      >{t('app.title')}</span
    >
  {/if}
  <div class="timer-slot">
    {#if isTimerShown}
      <RoomTimer baseMs={timerBaseMs} isRunning={isTimerRunning} anchor={timerAnchor} />
    {:else}
      <TopBarButton
        testId="timer-show"
        icon="chrono"
        label={t('timer.label')}
        ariaLabel={t('timer.toggle_label')}
        onclick={onShowTimer}
      />
    {/if}
  </div>
  <div class="topbar-buttons">
    {#if form === 'phone'}
      {@render undoButton()}
      {@render aideMenuButton()}
      {@render salonButton()}
      {@render pencilButton()}
      {@render roomMenuButton()}
    {:else}
      {@render undoButton()}
      {@render pencilButton()}
      {@render aideMenuButton()}
      {@render salonButton()}
      {@render roomMenuButton()}
    {/if}
  </div>
</header>

<style>
  .room-topbar {
    position: relative;
    box-sizing: border-box;
    flex: none;
    display: flex;
    align-items: center;
    width: 100%;
    background: var(--nock-white);
    border-bottom: 1px solid var(--nock-line);
  }

  /* ---- Every top-bar button (_design.md section 11) ---- */

  .room-topbar :global(.topbar-button) {
    position: relative;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0;
    border: 0;
    border-radius: 6px;
    color: var(--nock-navy);
    background: transparent;
    cursor: pointer;
  }

  .room-topbar :global(.topbar-button.pressed) {
    background: var(--nock-word);
  }

  .room-topbar :global(.topbar-button:disabled) {
    color: var(--nock-muted);
    background: transparent;
    cursor: not-allowed;
  }

  .room-topbar :global(.topbar-label) {
    font-weight: 500;
    line-height: 1;
    white-space: nowrap;
  }

  .room-topbar :global(.icon) {
    stroke-width: 1.8;
  }

  .timer-slot {
    flex: none;
    display: flex;
    align-items: center;
    margin-right: auto;
  }

  .topbar-buttons {
    display: flex;
    min-width: 0;
  }

  /* The badge of unread messages on « Salon » (spec 022's count). */
  .chat-unread {
    position: absolute;
  }

  /* ---- The phone top bar: icons over labels ---- */

  .phone {
    height: 54px;
    padding: 0 4px 0 10px;
  }

  .phone .timer-slot,
  .phone .topbar-buttons {
    align-self: stretch;
  }

  .phone .topbar-buttons {
    flex: 0 1 auto;
  }

  .phone :global(.topbar-button) {
    flex: 0 1 56px;
    min-width: 40px;
    width: 56px;
    height: 100%;
    flex-direction: column;
    gap: 2px;
    padding: 0;
  }

  .phone :global(.topbar-button .icon) {
    width: 22px;
    height: 22px;
  }

  .phone :global(.topbar-label) {
    font-size: 0.68rem;
  }

  .phone .chat-unread {
    top: 5px;
    right: 8px;
  }

  /* ---- The computer top bar: the brand, then icons beside labels ---- */

  .computer {
    height: 56px;
    padding: 0 16px;
    gap: 4px;
  }

  .topbar-brand {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-right: auto;
    font: 700 1.3rem/1 var(--nock-font-ui);
    letter-spacing: 0.01em;
    color: var(--nock-navy);
  }

  .topbar-brand svg {
    width: 12px;
    height: 18px;
    fill: var(--nock-navy);
  }

  .computer .timer-slot {
    margin-right: 10px;
  }

  .computer .topbar-buttons {
    flex: none;
    gap: 6px;
  }

  .computer :global(.topbar-button) {
    flex: none;
    height: 38px;
    gap: 6px;
    padding: 0 12px;
  }

  .computer :global(.topbar-button .icon) {
    width: 20px;
    height: 20px;
  }

  .computer :global(.topbar-label) {
    font-size: 0.92rem;
  }

  .computer .chat-unread {
    top: 2px;
    left: 24px;
  }

  /* The ▾ after « Aide »: a pictogram drawn by CSS, never read as text. */
  .aide-caret::after {
    content: '▾';
    font-size: 0.8rem;
    line-height: 1;
  }
</style>
