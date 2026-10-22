<script lang="ts">
  import { onMount } from 'svelte'
  import { newLinkCopier } from './copyLink'
  import { t } from './i18n'
  import { displayNickname } from './nickname'
  import { fetchRecap, recapColour, shownRecapPlayers, type Recap } from './recap'
  import { timerText } from './timer'

  // The recap dialog of spec 028, a modal dialog. The room page puts it on the
  // page when `recap-open` is clicked and takes it away once it closes, so each
  // opening fetches the recap again.
  let {
    code,
    you,
    playerColours,
    onClose,
  }: {
    // The room's code, for the recap route.
    code: string
    // The player of this page.
    you: string
    // The colour index of each player the page's snapshot lists.
    playerColours: Map<string, number>
    // The dialog closed, by its close button or by Escape.
    onClose: () => void
  } = $props()

  type State = 'loading' | 'ready' | 'error'

  let dialog: HTMLDialogElement | null = $state(null)
  let dialogState: State = $state('loading')
  let recap = $state<Recap | null>(null)
  // True while the copy button reads "copied", after a successful copy, as the
  // invitation link's button does (spec 011).
  let copied = $state(false)
  const shareLinkCopier = newLinkCopier((isCopied) => {
    copied = isCopied
  })

  let shownPlayers = $derived(recap === null ? [] : shownRecapPlayers(recap.players))
  let shareUrl = $derived(shareUrlOf(recap))

  // The whole address of the share page, or null for a room with no share link.
  function shareUrlOf(loaded: Recap | null): string | null {
    if (loaded === null || loaded.share_path === null) {
      return null
    }
    return location.origin + loaded.share_path
  }

  async function loadRecap(): Promise<void> {
    const loaded = await fetchRecap(code)
    if (loaded === null) {
      dialogState = 'error'
      return
    }
    recap = loaded
    dialogState = 'ready'
  }

  onMount(() => {
    dialog?.showModal()
    void loadRecap()
    return () => shareLinkCopier.stop()
  })

  // Write the share link to the clipboard. Without a usable clipboard nothing
  // changes.
  async function copyShareLink(): Promise<void> {
    if (shareUrl === null) {
      return
    }
    await shareLinkCopier.copy(shareUrl)
  }

  // The controls of the dialog that Tab moves between, in document order.
  function tabStops(): HTMLElement[] {
    if (dialog === null) {
      return []
    }
    return Array.from(dialog.querySelectorAll<HTMLElement>('a[href], button:not(:disabled)'))
  }

  // Tab and Shift+Tab go round the controls of the dialog: the page behind it is
  // inert, and the focus must not leave for the browser's own controls.
  function keepTabInside(event: KeyboardEvent): void {
    if (event.key !== 'Tab' || event.altKey || event.ctrlKey || event.metaKey) {
      return
    }
    const stops = tabStops()
    if (stops.length === 0) {
      event.preventDefault()
      return
    }
    const first = stops[0]
    const last = stops[stops.length - 1]
    const focused = document.activeElement
    if (event.shiftKey && (focused === first || focused === dialog)) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && focused === last) {
      event.preventDefault()
      first.focus()
    }
  }
</script>

<dialog
  bind:this={dialog}
  class="recap"
  data-testid="recap"
  data-state={dialogState}
  aria-labelledby="recap-heading"
  onclose={onClose}
  onkeydown={keepTabInside}
>
  <h2 id="recap-heading">{t('recap.heading')}</h2>
  {#if recap !== null}
    <p data-testid="recap-time">{t('recap.time', { time: timerText(recap.elapsed_ms) })}</p>
    <p data-testid="recap-checks">{t('recap.checks', { count: recap.checks })}</p>
    <p data-testid="recap-reveals">
      {t('recap.reveals', { letters: recap.letter_reveals, words: recap.word_reveals })}
    </p>
    <h3 id="recap-players-heading">{t('recap.players_heading')}</h3>
    <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
    <ul
      class="recap-players"
      data-testid="recap-players"
      role="list"
      aria-labelledby="recap-players-heading"
    >
      {#each shownPlayers as player}
        {@const isYou = player.player_id === you}
        {@const colour = recapColour(player.player_id, playerColours)}
        <li
          data-testid="recap-player"
          data-player-id={player.player_id}
          data-letters={String(player.letters)}
          data-words={String(player.words)}
          data-you={String(isYou)}
        >
          <span
            class="recap-colour"
            data-testid="recap-colour"
            data-colour={colour}
            style:background={colour === '' ? null : `var(--player-colour-${colour})`}
          ></span>
          <span class="recap-name" data-testid="recap-name"
            >{player.nickname === null ? t('feed.someone') : displayNickname(player.nickname)}</span
          >
          {#if isYou}
            <span class="recap-you">{t('roster.you')}</span>
          {/if}
          <span data-testid="recap-letters"
            >{t('recap.player_letters', { count: player.letters })}</span
          >
          <span data-testid="recap-words"
            >{t('recap.player_words', { count: player.words })}</span
          >
        </li>
      {/each}
    </ul>
    <p data-testid="recap-revealed">
      {t('recap.revealed_letters', { count: recap.revealed_letters })}
    </p>
    {#if shareUrl !== null}
      <p class="recap-share">
        <span id="recap-share-label">{t('recap.share_label')}</span>
        <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
        <a
          data-testid="recap-share-link"
          href={shareUrl}
          tabindex="0"
          aria-describedby="recap-share-label">{shareUrl}</a
        >
        <button type="button" data-testid="recap-copy" onclick={copyShareLink}
          >{copied ? t('room.share.copied') : t('room.share.copy')}</button
        >
      </p>
    {/if}
  {:else if dialogState === 'error'}
    <p data-testid="recap-error" role="alert">{t('recap.error')}</p>
  {:else}
    <p data-testid="recap-loading">{t('recap.loading')}</p>
  {/if}
  <button
    type="button"
    class="recap-close"
    data-testid="recap-close"
    onclick={() => dialog?.close()}
    >{t('recap.close')}</button
  >
</dialog>

<style>
  /* Inside the window at every size, and it scrolls when its content is taller
     (spec 028). A modal dialog is fixed, so the percentages are of the window. */
  .recap {
    box-sizing: border-box;
    width: min(30rem, calc(100% - 1rem));
    max-width: calc(100% - 1rem);
    max-height: calc(100% - 1rem);
    overflow-y: auto;
    padding: 1rem;
    color: var(--nock-ink);
    background: var(--nock-white);
    border: 1px solid var(--nock-line);
    border-radius: 0.5rem;
  }

  .recap h2 {
    margin: 0 0 0.5rem;
    font-size: 1.25rem;
  }

  .recap h3 {
    margin: 0.75rem 0 0.25rem;
    font-size: 1rem;
  }

  .recap p {
    margin: 0.25rem 0;
  }

  .recap-players {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* One row per player; it wraps on a narrow window. */
  .recap-players li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.1rem 0.5rem;
    padding: 0.15rem 0;
  }

  .recap-colour {
    flex: none;
    display: inline-block;
    width: 0.8rem;
    height: 0.8rem;
    border-radius: 50%;
  }

  /* A player who is no longer in the room, whose colour may now be someone
     else's: the hatching of a departed author's band (spec 019), a pattern no
     player's swatch has. A player's swatch is a plain colour, with no pattern. */
  .recap-colour[data-colour=''] {
    background-image: var(--author-departed-hatching);
  }

  .recap-name {
    font-weight: 600;
    overflow-wrap: anywhere;
  }

  .recap-you {
    color: var(--nock-muted);
  }

  .recap-share {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.25rem 0.5rem;
  }

  /* The address is one long word: it breaks anywhere rather than overflow. */
  .recap-share a {
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .recap-share button {
    flex: none;
  }

  .recap-close {
    margin-top: 0.75rem;
  }
</style>
