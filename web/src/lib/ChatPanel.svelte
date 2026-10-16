<script lang="ts">
  import { tick } from 'svelte'
  import { t } from './i18n'
  import { nameOf } from './activityFeed'
  import { shownChatLines } from './chat'
  import { listenForEscape } from './escapeKey'
  import {
    followListTabStop,
    keepFeedEndOnResize,
    keepFeedPlace,
    noteFeedPlace,
    scrollToEnd,
  } from './scrollingLists'
  import type { FeedPlace } from './scrollingLists'
  import type { ChatLine, PlayerView } from './roomSession'

  // The chat panel of spec 022. It is on the page only while it is open: the
  // room page decides when, and this component handles what happens inside.
  let {
    history,
    players,
    names,
    you,
    isHost,
    isMuted,
    isPaced,
    isJoined,
    isBelowPicker,
    text = $bindable(),
    onSend,
    onMute,
    onClose,
    onFocusToggle,
  }: {
    // The whole chat history of the snapshot, in seq order.
    history: ChatLine[]
    players: PlayerView[]
    names: Map<string, string>
    you: string
    isHost: boolean
    // True while the host muted me.
    isMuted: boolean
    // True while the page holds back my own chat messages.
    isPaced: boolean
    // True while the page is joined to the room.
    isJoined: boolean
    // True when the room is too narrow to put the panel beside the picker.
    isBelowPicker: boolean
    // What is typed in the input. The page keeps it while the panel is closed.
    text: string
    // Send the trimmed text of a message.
    onSend: (text: string) => void
    onMute: (playerId: string, isPlayerMuted: boolean) => void
    // Close the panel and put the focus on the toggle.
    onClose: () => void
    onFocusToggle: () => void
  } = $props()

  let panel: HTMLElement | null = $state(null)
  let input: HTMLInputElement | null = $state(null)
  let list: HTMLUListElement | null = $state(null)

  let lines = $derived(shownChatLines(history))
  // The other players, in roster order: the host's mute buttons.
  let otherPlayers = $derived(players.filter((player) => player.player_id !== you))
  let isSendDisabled = $derived(text.trim() === '' || !isJoined || isMuted || isPaced)

  // `tick` resolves once the panel is on the page. A muted player's input is
  // disabled: the focus then stays on the toggle.
  async function focusInputAfterOpening(): Promise<void> {
    await tick()
    if (input !== null && !input.disabled) {
      input.focus()
    } else {
      onFocusToggle()
    }
  }

  void focusInputAfterOpening()

  // Escape while the focus is inside the panel closes it.
  $effect(() => {
    if (panel === null) {
      return
    }
    return listenForEscape(panel, onClose)
  })

  // Runs before the page disables the chat controls at a mute: when the focus
  // is on the input or the send button, it goes to the toggle instead of being
  // lost. The panel stays open and the typed text stays in the input.
  $effect.pre(() => {
    if (!isMuted) {
      return
    }
    const focused = document.activeElement
    const chatForm = input?.form
    if (focused !== null && chatForm?.contains(focused)) {
      onFocusToggle()
    }
  })

  // Send the trimmed text and empty the input. The line shows when the
  // server's chat_message comes back: no local echo.
  //
  // Emptying the input disables the send button, and a focused button that
  // becomes disabled drops the focus to the page. So the focus goes to the
  // input first, however the message was sent: Enter, the button from the
  // keyboard, a click or a tap. Pacing never disables the input (spec 022
  // AC-20).
  function submit(event: SubmitEvent): void {
    event.preventDefault()
    if (isSendDisabled) {
      return
    }
    onSend(text.trim())
    text = ''
    input?.focus()
  }

  // The chat list keeps the reader's place as the feed list does (spec 013
  // AC-7): a new line brings the list to its newest line only if the list was
  // at its end just before. The list starts at its newest line each time the
  // panel opens. `placeList` is the list whose place is followed.
  let newestSeq = $derived(lines.length === 0 ? null : lines[lines.length - 1].seq)
  let placeList: HTMLUListElement | null = null
  let placeBeforeNewLine: FeedPlace | null = null

  // Runs before the new line is on the page: note where the list is.
  $effect.pre(() => {
    const newest = newestSeq
    const element = list
    if (element === null || newest === null || element !== placeList) {
      return
    }
    placeBeforeNewLine = noteFeedPlace(element)
  })

  // Runs once the new line is on the page, or once the list is on the page.
  $effect(() => {
    const newest = newestSeq
    const element = list
    if (element === null) {
      placeList = null
      return
    }
    if (element !== placeList) {
      placeList = element
      placeBeforeNewLine = null
      scrollToEnd(element)
      return
    }
    if (newest === null || placeBeforeNewLine === null) {
      return
    }
    keepFeedPlace(element, placeBeforeNewLine)
    placeBeforeNewLine = null
  })

  // The chat list is a Tab stop while it scrolls (spec 035 AC-12), and at its
  // end it stays at its end through a resize or a new root font (spec 013 AC-8).
  $effect(() => {
    if (list === null) {
      return
    }
    const stopTabStop = followListTabStop(list)
    const stopEndOnResize = keepFeedEndOnResize(list)
    return () => {
      stopTabStop()
      stopEndOnResize()
    }
  })
</script>

<section
  class="chat-panel"
  class:below-picker={isBelowPicker}
  id="chat-panel"
  data-testid="chat-panel"
  aria-labelledby="chat-heading"
  bind:this={panel}
>
  <h2 id="chat-heading">{t('chat.heading')}</h2>
  <!-- The tabindex is set from the script (spec 035 AC-12). -->
  <ul
    class="chat-list"
    data-testid="chat-list"
    role="list"
    aria-labelledby="chat-heading"
    bind:this={list}
  >
    {#each lines as line (line.seq)}
      <li
        data-testid="chat-message"
        data-seq={String(line.seq)}
        data-player-id={line.player_id}
        data-you={String(line.player_id === you)}
      >
        <span class="chat-author" data-testid="chat-author">{nameOf(names, line.player_id)}</span
        ><span class="chat-text" data-testid="chat-text">{line.text}</span>
      </li>
    {/each}
  </ul>
  {#if isHost}
    <section
      class="chat-moderation"
      data-testid="chat-moderation"
      aria-labelledby="chat-moderation-heading"
    >
      <h3 id="chat-moderation-heading">{t('chat.moderation_heading')}</h3>
      <div class="mute-rows">
        {#each otherPlayers as player (player.player_id)}
          <div class="mute-row" data-testid="mute-row" data-player-id={player.player_id}>
            <span data-testid="mute-name">{player.nickname}</span>
            <button
              type="button"
              class="mute-player"
              data-testid="mute-player"
              data-muted={String(player.muted)}
              aria-label={player.muted
                ? t('chat.unmute_label', { name: player.nickname })
                : t('chat.mute_label', { name: player.nickname })}
              onclick={() => onMute(player.player_id, player.muted)}
              >{player.muted ? t('chat.unmute') : t('chat.mute')}</button
            >
          </div>
        {/each}
      </div>
    </section>
  {/if}
  <form class="chat-form" onsubmit={submit}>
    <label class="visually-hidden" for="chat-input">{t('chat.input_label')}</label>
    <input
      id="chat-input"
      data-testid="chat-input"
      type="text"
      maxlength="280"
      autocomplete="off"
      placeholder={t('chat.placeholder')}
      disabled={isMuted}
      bind:value={text}
      bind:this={input}
    />
    <button type="submit" class="chat-send" data-testid="chat-send" disabled={isSendDisabled}
      >{t('chat.send')}</button
    >
  </form>
  <!-- The slot of the chat notes: always present, empty when no note applies
       and one line high, so a note coming or going leaves the panel's box
       alone. It shows one note at a time: the mute note wins over the wait
       note, which shows again after an unmute if the pacing still holds
       (spec 022 AC-19). -->
  <p class="chat-note">
    {#if isMuted}
      <span data-testid="chat-muted">{t('chat.muted')}</span>
    {:else if isPaced}
      <span data-testid="chat-wait">{t('chat.wait')}</span>
    {/if}
  </p>
</section>

<style>
  /* Drawn over the page below the header, like the vote banner: absolutely
     placed, so it moves nothing. The vote banner comes later in the document
     with the same z-index, so it is drawn over the panel and its buttons always
     stay uncovered. */
  /* At the right, as wide as the room allows up to 22rem, and never past the
     bottom of the window: the list gives up its height first. */
  .chat-panel {
    position: absolute;
    z-index: 1;
    box-sizing: border-box;
    top: var(--popover-top);
    background: #ffffff;
    border: 1px solid #5b6070;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgb(0 0 0 / 20%);
    /* The picker's height and the gap under it. */
    --picker-row: calc(2.5rem + 2px);
    right: 0.5rem;
    width: min(22rem, 100% - 1rem);
    max-height: calc(100% - var(--popover-top) - 0.5rem);
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    padding: 0.5rem;
    font-size: 0.875rem;
  }

  /* On a narrow page the picker's row stays free above the panel, whether the
     picker is open or not, so the two never overlap and the panel does not move
     when the picker opens (spec 022 decision 15). */
  .chat-panel.below-picker {
    top: calc(var(--popover-top) + var(--picker-row));
    max-height: calc(100% - var(--popover-top) - var(--picker-row) - 0.5rem);
  }

  .chat-panel h2 {
    flex: none;
    margin: 0;
    font-size: 1rem;
  }

  /* About seven lines; the older ones scroll (spec 022 AC-11). The page keeps
     the reader's place itself, as for the feed: no scroll anchoring. Room is
     left around it for its focus outline, drawn outside (spec 035 AC-2). */
  .chat-list {
    flex: 0 1 auto;
    height: 9rem;
    min-height: 2.75rem;
    overflow-y: auto;
    overflow-anchor: none;
    overflow-wrap: anywhere;
    margin: 0.25rem 0;
    padding: 0 0.25rem;
    list-style: none;
    line-height: 1.3;
  }

  .chat-author {
    margin-right: 0.4em;
    font-weight: bold;
  }

  /* The host's mute buttons. On a low window they give up height after the
     list, and scroll; the focus outline is then drawn inside the buttons. */
  .chat-moderation {
    flex: 0 1 auto;
    min-height: 2rem;
    overflow-y: auto;
  }

  .chat-moderation h3 {
    margin: 0 0 0.25rem;
    font-size: 0.875rem;
  }

  .chat-moderation :focus-visible {
    outline-offset: -3px;
  }

  .mute-rows {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.75rem;
  }

  .mute-row {
    display: flex;
    align-items: center;
    gap: 0.25rem;
  }

  .mute-player {
    box-sizing: border-box;
    min-width: 24px;
    min-height: 24px;
    padding: 0 0.4rem;
    font-size: 0.8rem;
  }

  .chat-form {
    flex: none;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .chat-form input {
    flex: 1 1 auto;
    min-width: 0;
    box-sizing: border-box;
    min-height: 28px;
    font: inherit;
  }

  .chat-send {
    flex: none;
    box-sizing: border-box;
    min-width: 24px;
    min-height: 28px;
  }

  .chat-note {
    flex: none;
    margin: 0;
    min-height: 1.2em;
    line-height: 1.2;
    font-size: 0.8rem;
    color: #4a4f5c;
  }
</style>
