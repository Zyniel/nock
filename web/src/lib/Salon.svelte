<script lang="ts">
  // The Salon (spec 043, "Salon"): a bottom sheet in the sheet layout, a side
  // column in the column layout. It shows the words' progress, then two tabs,
  // Discussion and Joueurs. It stays on the page while closed, with the
  // `hidden` attribute; the room page decides when it opens.
  import { tick } from 'svelte'
  import ChatPanel from './ChatPanel.svelte'
  import PlayersPanel from './PlayersPanel.svelte'
  import type { StreamEntry } from './activityFeed'
  import { listenForEscape } from './escapeKey'
  import { t } from './i18n'
  import type { PlayerView } from './roomSession'

  let {
    layout,
    isOpen,
    tab = $bindable(),
    filledWords,
    totalWords,
    entries,
    names,
    players,
    you,
    isHost,
    isMuted,
    isPaced,
    isJoined,
    isAccessibilityOn,
    clues,
    shareLink,
    chatText = $bindable(),
    onSend,
    onMute,
    onRemove,
    onEscape,
    onMuted,
  }: {
    layout: 'sheet' | 'column'
    isOpen: boolean
    // The selected tab; the choice holds for the page's life.
    tab: 'discussion' | 'players'
    // The words whose every cell shows a letter, and all the words.
    filledWords: number
    totalWords: number
    // The stream of the Discussion tab, oldest first.
    entries: StreamEntry[]
    names: Map<string, string>
    players: PlayerView[]
    you: string
    isHost: boolean
    isMuted: boolean
    isPaced: boolean
    isJoined: boolean
    isAccessibilityOn: boolean
    // The clue of each player's selected word, by player id.
    clues: Map<string, string>
    shareLink: string
    chatText: string
    onSend: (text: string) => void
    onMute: (playerId: string, isPlayerMuted: boolean) => void
    onRemove: (playerId: string) => void
    // Escape while the focus is inside the Salon.
    onEscape: () => void
    // A mute is about to disable the focused chat input.
    onMuted: () => void
  } = $props()

  let salon: HTMLElement | null = $state(null)
  let chatInput: HTMLInputElement | null = $state(null)
  let copyButton: HTMLButtonElement | null = $state(null)
  let discussionTab: HTMLButtonElement | null = $state(null)
  let playersTab: HTMLButtonElement | null = $state(null)

  let progressShare = $derived(totalWords === 0 ? 0 : filledWords / totalWords)

  // Move the focus into the Salon once it shows: to the message input when the
  // Discussion tab is selected and the input is enabled, else to the selected
  // tab.
  export async function focusInside(): Promise<void> {
    await tick()
    if (tab === 'discussion' && chatInput !== null && !chatInput.disabled) {
      chatInput.focus()
      return
    }
    selectedTabButton()?.focus()
  }

  // Put the focus on « Copier le lien » once the Joueurs tab shows.
  export async function focusCopyLink(): Promise<void> {
    await tick()
    copyButton?.focus()
  }

  function selectedTabButton(): HTMLButtonElement | null {
    return tab === 'discussion' ? discussionTab : playersTab
  }

  // ArrowLeft and ArrowRight select the other tab and move the focus to it.
  async function onTabKeydown(event: KeyboardEvent): Promise<void> {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
      return
    }
    event.preventDefault()
    tab = tab === 'discussion' ? 'players' : 'discussion'
    await tick()
    selectedTabButton()?.focus()
  }

  $effect(() => {
    if (salon === null) {
      return
    }
    return listenForEscape(salon, onEscape)
  })
</script>

<aside
  class="salon {layout}"
  id="salon"
  data-testid="salon"
  aria-label={t('topbar.salon')}
  hidden={!isOpen}
  bind:this={salon}
>
  {#if layout === 'sheet'}
    <div class="salon-handle" data-testid="salon-handle" aria-hidden="true"></div>
  {/if}
  <div class="salon-progress" data-testid="salon-progress">
    <span class="salon-progress-text" data-testid="salon-progress-text"
      >{t('salon.progress', { filled: filledWords, total: totalWords })}</span
    >
    <div class="salon-progress-bar" data-testid="salon-progress-bar" aria-hidden="true">
      <div class="salon-progress-fill" style:width="{progressShare * 100}%"></div>
    </div>
  </div>
  <div class="salon-tabs" data-testid="salon-tabs" role="tablist">
    <button
      type="button"
      class="salon-tab"
      id="salon-tab-discussion"
      data-testid="salon-tab-discussion"
      role="tab"
      aria-selected={tab === 'discussion'}
      aria-controls="chat-panel"
      tabindex={tab === 'discussion' ? 0 : -1}
      bind:this={discussionTab}
      onclick={() => (tab = 'discussion')}
      onkeydown={onTabKeydown}>{t('chat.heading')}</button
    >
    <button
      type="button"
      class="salon-tab"
      id="salon-tab-players"
      data-testid="salon-tab-players"
      role="tab"
      aria-selected={tab === 'players'}
      aria-controls="roster"
      tabindex={tab === 'players' ? 0 : -1}
      bind:this={playersTab}
      onclick={() => (tab = 'players')}
      onkeydown={onTabKeydown}>{t('salon.players_tab', { count: players.length })}</button
    >
  </div>
  <ChatPanel
    {entries}
    {names}
    {you}
    isShown={tab === 'discussion'}
    {isMuted}
    {isPaced}
    {isJoined}
    bind:text={chatText}
    bind:input={chatInput}
    {onSend}
    {onMuted}
  />
  <PlayersPanel
    {players}
    {you}
    {isHost}
    isShown={tab === 'players'}
    {isAccessibilityOn}
    {clues}
    {shareLink}
    bind:copyButton
    {onMute}
    {onRemove}
  />
</aside>

<style>
  .salon {
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    background: var(--nock-white);
  }

  .salon[hidden] {
    display: none;
  }

  /* The bottom sheet over the play area: it moves nothing under it. */
  .salon.sheet {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 8;
    height: 62dvh;
    border-radius: 14px 14px 0 0;
    box-shadow: 0 -10px 30px -12px var(--nock-shadow);
  }

  /* The side column, in the flow: opening or closing it changes the play
     area's width. */
  .salon.column {
    flex: none;
    width: 340px;
    min-height: 0;
    border-left: 1px solid var(--nock-line);
  }

  /* Decorative: no drag in this step. */
  .salon-handle {
    flex: none;
    width: 40px;
    height: 4px;
    margin: 8px auto 4px;
    border-radius: 2px;
    background: var(--nock-handle);
  }

  .salon-progress {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 16px 8px;
  }

  .column .salon-progress {
    padding-top: 14px;
  }

  .salon-progress-text {
    flex: none;
    font: 600 0.85rem/1 var(--nock-font-ui);
    color: var(--nock-navy);
    font-variant-numeric: tabular-nums;
  }

  .salon-progress-bar {
    flex: 1 1 auto;
    height: 6px;
    overflow: hidden;
    border-radius: 3px;
    background: var(--nock-word);
  }

  .salon-progress-fill {
    height: 100%;
    background: var(--nock-navy);
  }

  .salon-tabs {
    flex: none;
    display: flex;
    border-bottom: 1px solid var(--nock-line);
  }

  .salon-tab {
    flex: 1 1 0;
    min-width: 0;
    padding: 10px;
    border: 0;
    border-bottom: 2px solid transparent;
    font: 600 0.95rem/1 var(--nock-font-ui);
    color: var(--nock-muted);
    background: transparent;
    cursor: pointer;
  }

  .salon-tab[aria-selected='true'] {
    color: var(--nock-navy);
    border-bottom-color: var(--nock-navy);
  }

  .salon-tab:focus-visible {
    outline-offset: -2px;
  }
</style>
