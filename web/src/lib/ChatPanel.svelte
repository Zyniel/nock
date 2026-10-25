<script lang="ts">
  import LinePictogram from './LinePictogram.svelte'
  import PlayerIcon from './PlayerIcon.svelte'
  import { t } from './i18n'
  import { nameOf } from './activityFeed'
  import type { StreamEntry } from './activityFeed'
  import {
    followListTabStop,
    keepFeedEndOnResize,
    keepFeedPlace,
    noteFeedPlace,
  } from './scrollingLists'
  import type { FeedPlace } from './scrollingLists'

  // The Salon's Discussion tab (spec 043, "Discussion: the stream"): one stream
  // of the chat messages (spec 022) and the event lines (specs 013, 034), then
  // the message box and the slot of the chat notes. It stays on the page while
  // its tab is not selected, with the `hidden` attribute.
  let {
    entries,
    names,
    colours,
    you,
    isShown,
    isMuted,
    isPaced,
    isJoined,
    isAccessibilityOn,
    text = $bindable(),
    input = $bindable(null),
    onSend,
    onMuted,
  }: {
    // The stream, oldest first.
    entries: StreamEntry[]
    names: Map<string, string>
    // The colour index of each player of the kept snapshot, by id: a message
    // of anyone else has no dot.
    colours: Map<string, number>
    you: string
    // True while the tab is selected.
    isShown: boolean
    // True while the host muted me.
    isMuted: boolean
    // True while the page holds back my own chat messages.
    isPaced: boolean
    // True while the page is joined to the room.
    isJoined: boolean
    // « Accessibilité » (spec 042): each dot shows its player's icon.
    isAccessibilityOn: boolean
    // What is typed in the input. The page keeps it while the Salon is closed.
    text: string
    input?: HTMLInputElement | null
    // Send the trimmed text of a message.
    onSend: (text: string) => void
    // A mute is about to disable the input that has the focus: the room page
    // puts the focus on « Salon ».
    onMuted: () => void
  } = $props()

  let list: HTMLUListElement | null = $state(null)

  let isSendDisabled = $derived(text.trim() === '' || !isJoined || isMuted || isPaced)

  // Runs before the page disables the chat controls at a mute: when the focus
  // is on the input or the send button, it goes to « Salon » instead of being
  // lost. The typed text stays in the input.
  $effect.pre(() => {
    if (!isMuted) {
      return
    }
    const focused = document.activeElement
    const chatForm = input?.form
    if (focused !== null && chatForm?.contains(focused)) {
      onMuted()
    }
  })

  // Send the trimmed text and empty the input. The line shows when the
  // server's chat_message comes back: no local echo.
  //
  // Emptying the input disables the send button, and a focused button that
  // becomes disabled drops the focus to the page. So the focus goes to the
  // input first, however the message was sent (spec 022 AC-20).
  function submit(event: SubmitEvent): void {
    event.preventDefault()
    if (isSendDisabled) {
      return
    }
    onSend(text.trim())
    text = ''
    input?.focus()
  }

  // The stream keeps the reader's place (spec 013 AC-7): new lines bring the
  // list to its newest line only if it was at its end just before. Any item,
  // message or event line, is a new line.
  let placeBeforeNewLine: FeedPlace | null = null

  // Runs before the new lines are on the page: note where the list is.
  $effect.pre(() => {
    void entries
    if (list === null) {
      return
    }
    placeBeforeNewLine = noteFeedPlace(list)
  })

  // Runs once the new lines are on the page.
  $effect(() => {
    void entries
    if (list === null || placeBeforeNewLine === null) {
      return
    }
    keepFeedPlace(list, placeBeforeNewLine)
    placeBeforeNewLine = null
  })

  // The list is a Tab stop while it scrolls (spec 035 AC-12), and at its end it
  // stays at its end through a resize, a new root font, or the tab shown again
  // (spec 013 AC-8).
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

<div
  class="chat-panel"
  id="chat-panel"
  data-testid="chat-panel"
  role="tabpanel"
  aria-labelledby="salon-tab-discussion"
  hidden={!isShown}
>
  <h2 id="chat-heading" class="visually-hidden">{t('chat.heading')}</h2>
  <div class="activity-feed" data-testid="activity-feed">
    <!-- The explicit role: WebKit does not expose a list without bullets as a
         list. The tabindex is set from the script (spec 035 AC-12). -->
    <ul
      class="stream"
      data-testid="chat-list"
      role="list"
      aria-labelledby="chat-heading"
      bind:this={list}
    >
      {#each entries as entry (entry.key)}
        {#if entry.kind === 'message'}
          {@const colour = colours.get(entry.line.player_id)}
          <!-- No white space between the dot, the name and the text: the gaps
               are the margins. -->
          <li
            class="message"
            data-testid="chat-message"
            data-seq={String(entry.line.seq)}
            data-player-id={entry.line.player_id}
            data-you={String(entry.line.player_id === you)}
          >{#if colour !== undefined}<span
                class="chat-dot"
                class:icon={isAccessibilityOn}
                data-testid="chat-dot"
                data-colour={String(colour)}
                style:background={isAccessibilityOn ? null : `var(--player-colour-${colour})`}
                >{#if isAccessibilityOn}<PlayerIcon {colour} side="12px" />{/if}</span
              >{/if}<span class="chat-author" data-testid="chat-author"
              >{nameOf(names, entry.line.player_id)}</span
            ><span class="chat-text" data-testid="chat-text">{entry.line.text}</span></li>
        {:else}
          <li
            class="event"
            class:reveal={entry.item.kind === 'reveal'}
            data-testid="feed-item"
            data-kind={entry.item.kind}
            data-seq={String(entry.item.seq)}
            data-ok={entry.item.isCleanCheck ? 'true' : null}
          ><LinePictogram kind={entry.item.kind} testId="feed-picto" />{entry.item.text}</li>
        {/if}
      {/each}
    </ul>
  </div>
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
       note (spec 022 AC-19). -->
  <p class="chat-note">
    {#if isMuted}
      <span data-testid="chat-muted">{t('chat.muted')}</span>
    {:else if isPaced}
      <span data-testid="chat-wait">{t('chat.wait')}</span>
    {/if}
  </p>
</div>

<style>
  /* The panel fills the Salon's height left; the stream takes what the message
     box and the notes leave. */
  .chat-panel {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .chat-panel[hidden] {
    display: none;
  }

  .activity-feed {
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  /* The page keeps the reader's place itself when lines come and go (spec 013
     AC-7), the same way in every engine: no scroll anchoring from the browser
     on top of it. Its focus ring is drawn inside it, so nothing around it
     covers it (spec 035 AC-2). */
  .stream {
    flex: 1 1 0;
    min-height: 0;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
    padding: 10px 16px;
    overflow-y: auto;
    overflow-anchor: none;
    overflow-wrap: anywhere;
    list-style: none;
  }

  .stream:focus-visible {
    outline-offset: -2px;
  }

  .stream li {
    flex: none;
  }

  .message {
    font-size: 0.92rem;
    color: var(--nock-ink);
  }

  /* The player dot (specs/_design/foundation.md « Components »), 6 px before the name. */
  .chat-dot {
    display: inline-block;
    box-sizing: border-box;
    width: 10px;
    height: 10px;
    margin-right: 6px;
    vertical-align: middle;
    border-radius: 50%;
    box-shadow: 0 0 0 1px var(--nock-dot-ring);
  }

  /* « Accessibilité » (spec 042): the player's own icon, with no ring. */
  .chat-dot.icon {
    width: 12px;
    height: 12px;
    border-radius: 0;
    box-shadow: none;
    background: transparent;
  }

  .chat-author {
    margin-right: 6px;
    font-weight: 700;
  }

  /* An event line (spec 013): muted, a little smaller and set in; green for a
     check that found no wrong letter, orange-red for a reveal. */
  .event {
    padding-left: 16px;
    font-size: 0.82rem;
    color: var(--nock-muted);
  }

  .event[data-ok='true'] {
    color: var(--nock-green);
  }

  .event.reveal {
    color: var(--nock-reveal);
  }

  .chat-form {
    flex: none;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px 12px;
    border-top: 1px solid var(--nock-line);
  }

  .chat-form input {
    flex: 1 1 auto;
    min-width: 0;
    box-sizing: border-box;
    padding: 7px 12px;
    border: 1px solid var(--nock-rule);
    border-radius: 18px;
    font: 400 0.9rem/1.2 var(--nock-font-ui);
    color: var(--nock-ink);
    background: var(--nock-white);
  }

  .chat-form input::placeholder {
    color: var(--nock-muted);
  }

  /* While I am muted (spec 047): the disabled look, muted text on clue
     blue-grey. */
  .chat-form input:disabled {
    color: var(--nock-muted);
    background: var(--nock-clue-bg);
  }

  /* The « Envoyer » pill (specs/_design/foundation.md « Components »). */
  .chat-send {
    flex: none;
    box-sizing: border-box;
    min-height: 24px;
    padding: 6px 12px;
    border: 0;
    border-radius: 14px;
    font: 600 0.85rem/1.2 var(--nock-font-ui);
    color: var(--nock-navy);
    background: var(--nock-word);
    cursor: pointer;
  }

  /* Whenever spec 022 disables it (an empty message, the pacing, a page not
     joined, a muted player): spec 041's disabled look (spec 047). */
  .chat-send:disabled {
    color: var(--nock-muted);
    background: var(--nock-clue-bg);
    cursor: not-allowed;
  }

  .chat-note {
    flex: none;
    margin: 0;
    padding: 0 12px 8px;
    min-height: 1.3em;
    font: 500 0.85rem/1.3 var(--nock-font-ui);
    color: var(--nock-muted);
  }
</style>
