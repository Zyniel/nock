<script lang="ts">
  // The room's top bar (spec 043, "Top bar"): the timer slot and five or six
  // buttons. The phone top bar (54 px) draws each icon above its label; the
  // computer top bar (56 px) starts with the brand link and draws each icon beside
  // its label. On a touch screen « Clavier » shows and hides the in-app
  // keyboard (spec 044). The room page decides which form shows and what each
  // button does. While the room opens (spec 046) the bar is drawn as once
  // joined, with an empty timer slot, and `inert`: nothing in it acts yet.
  import RoomTimer from './RoomTimer.svelte'
  import TopBarBrand from './TopBarBrand.svelte'
  import TopBarButton from './TopBarButton.svelte'
  import { unreadBadgeText } from './chat'
  import { t } from './i18n'

  let {
    form,
    isOpening,
    isTimerShown,
    timerBaseMs,
    isTimerRunning,
    timerAnchor,
    isSolved,
    isPencilMode,
    isTouchScreen,
    isKeyboardShown,
    isAideOpen,
    isMenuOpen,
    isSalonOpen,
    unreadLines,
    hasNewEvents,
    salonLabel,
    aideButton = $bindable(null),
    menuButton = $bindable(null),
    chatToggle = $bindable(null),
    onShowTimer,
    onUndo,
    onTogglePencil,
    onToggleKeyboard,
    onToggleAide,
    onToggleSalon,
    onToggleMenu,
  }: {
    form: 'phone' | 'computer'
    // True before the first snapshot (spec 046, "Opening the room").
    isOpening: boolean
    isTimerShown: boolean
    timerBaseMs: number
    isTimerRunning: boolean
    timerAnchor: number
    // Once the grid is solved, « Annuler », « Crayon » and « Clavier » are
    // disabled.
    isSolved: boolean
    isPencilMode: boolean
    // « Clavier » shows on a touch screen only, pressed while the in-app
    // keyboard shows.
    isTouchScreen: boolean
    isKeyboardShown: boolean
    isAideOpen: boolean
    isMenuOpen: boolean
    isSalonOpen: boolean
    // The messages of others that came since the stream was last shown.
    unreadLines: number
    // True while the new-events dot shows: lines of other players came since
    // the stream was last shown, and no message is unread.
    hasNewEvents: boolean
    // The accessible name of « Salon » while the badge or the dot shows, else
    // null.
    salonLabel: string | null
    aideButton?: HTMLButtonElement | null
    menuButton?: HTMLButtonElement | null
    chatToggle?: HTMLButtonElement | null
    onShowTimer: () => void
    onUndo: () => void
    onTogglePencil: () => void
    onToggleKeyboard: () => void
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

{#snippet keyboardButton()}
  <TopBarButton
    testId="keyboard-toggle"
    icon="clavier"
    label={t('keyboard.label')}
    ariaPressed={isKeyboardShown}
    disabled={isSolved}
    onclick={onToggleKeyboard}
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
    {:else if hasNewEvents}
      <span class="salon-dot" data-testid="salon-dot" aria-hidden="true"></span>
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

<header class="room-topbar {form}" data-testid="room-topbar" inert={isOpening}>
  {#if form === 'computer'}
    <TopBarBrand />
  {/if}
  <div class="timer-slot">
    {#if isOpening}
      <!-- The timer slot stays empty until the room exists (spec 046). -->
    {:else if isTimerShown}
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
      <!-- The fourth slot: « Clavier » on a touch screen, where ✎ is the
           pencil toggle; « Crayon » elsewhere. -->
      {@render undoButton()}
      {@render aideMenuButton()}
      {@render salonButton()}
      {#if isTouchScreen}
        {@render keyboardButton()}
      {:else}
        {@render pencilButton()}
      {/if}
      {@render roomMenuButton()}
    {:else}
      {@render undoButton()}
      {@render pencilButton()}
      {@render aideMenuButton()}
      {@render salonButton()}
      {#if isTouchScreen}
        {@render keyboardButton()}
      {/if}
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

  /* Every top-bar button has its look in TopBarButton.svelte; each form of
     the bar gives it its size. */

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

  /* The new-events dot (specs/_design/foundation.md « Components »): an 8 px red circle. */
  .salon-dot {
    position: absolute;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--nock-red);
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

  .phone .salon-dot {
    top: 8px;
    right: 15px;
  }

  /* ---- The computer top bar: the brand, then icons beside labels ---- */

  .computer {
    height: 56px;
    padding: 0 16px;
    gap: 4px;
  }

  .computer :global(.topbar-brand) {
    margin-right: auto;
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

  /* The dot takes the badge's place on a computer (specs/_design/room.md « Computer top bar »). */
  .computer .chat-unread,
  .computer .salon-dot {
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
