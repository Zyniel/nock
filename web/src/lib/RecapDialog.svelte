<script lang="ts">
  import { onMount } from 'svelte'
  import { newLinkCopier } from './copyLink'
  import { t } from './i18n'
  import { displayNickname } from './nickname'
  import PlayerIcon from './PlayerIcon.svelte'
  import { fetchRecap, recapColour, shownRecapPlayers, type Recap } from './recap'
  import { timerText } from './timer'

  // The recap dialog of spec 028, a modal dialog with the look of spec 047: a
  // room sheet (app.css), centred in the column layout and a bottom sheet in the
  // sheet layout, over its own darker scrim that covers the whole window. The
  // room page puts it on the page when `recap-open` is clicked and takes it away
  // once it closes, so each opening fetches the recap again.
  let {
    code,
    you,
    playerColours,
    layout,
    isAccessibilityOn,
    onClose,
  }: {
    // The room's code, for the recap route.
    code: string
    // The player of this page.
    you: string
    // The colour index of each player the page's snapshot lists.
    playerColours: Map<string, number>
    // The room's layout (spec 043): a dialog in the column layout, a bottom
    // sheet in the sheet layout.
    layout: 'sheet' | 'column'
    // Whether the "Accessibilite" switch is on (spec 042): each player's dot
    // is then their own icon.
    isAccessibilityOn: boolean
    // The dialog closed, by its close button or by Escape.
    onClose: () => void
  } = $props()

  type State = 'loading' | 'ready' | 'error'

  let dialog: HTMLDialogElement | null = $state(null)
  let dialogState: State = $state('loading')
  let recap = $state<Recap | null>(null)
  // True while the line "Lien copie" shows under the share link, after a
  // successful copy, for spec 011's time. The button keeps its label.
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
  class="room-sheet recap"
  class:bottom={layout === 'sheet'}
  data-testid="recap"
  data-state={dialogState}
  aria-labelledby="recap-heading"
  onclose={onClose}
  onkeydown={keepTabInside}
>
  <h2 class="room-sheet-title" id="recap-heading">{t('recap.heading')}</h2>
  {#if recap !== null}
    <p class="recap-time" data-testid="recap-time">
      {t('recap.time', { time: timerText(recap.elapsed_ms) })}
    </p>
    <div class="recap-lines" data-testid="recap-lines">
      <p data-testid="recap-checks">{t('recap.checks', { count: recap.checks })}</p>
      <p data-testid="recap-reveals">
        {t('recap.reveals', { letters: recap.letter_reveals, words: recap.word_reveals })}
      </p>
      <p data-testid="recap-revealed">
        {t('recap.revealed_letters', { count: recap.revealed_letters })}
      </p>
    </div>
    <h3 class="recap-section-heading" id="recap-players-heading">
      {t('recap.players_heading')}
    </h3>
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
          class="recap-player"
          data-testid="recap-player"
          data-player-id={player.player_id}
          data-letters={String(player.letters)}
          data-words={String(player.words)}
          data-you={String(isYou)}
        >
          <!-- The player dot, or their icon while "Accessibilite" is on. A
               player the page no longer knows has an empty slot: their colour
               may now be someone else's (spec 047, Decision 4). -->
          <span
            class="recap-colour"
            class:icon={isAccessibilityOn}
            data-testid="recap-colour"
            data-colour={colour}
            style:background={colour === '' || isAccessibilityOn
              ? null
              : `var(--player-colour-${colour})`}
            >{#if isAccessibilityOn && colour !== ''}<PlayerIcon
                colour={Number(colour)}
                side="12px"
              />{/if}</span
          >
          <span class="recap-name" data-testid="recap-name"
            >{player.nickname === null ? t('feed.someone') : displayNickname(player.nickname)}</span
          >
          {#if isYou}
            <span class="recap-you" data-testid="recap-you">{t('roster.you')}</span>
          {/if}
          <span class="recap-values" data-testid="recap-values"
            ><span data-testid="recap-letters"
              >{t('recap.player_letters', { count: player.letters })}</span
            ><span class="recap-sep" data-testid="recap-sep" aria-hidden="true"></span><span
              data-testid="recap-words">{t('recap.player_words', { count: player.words })}</span
            ></span
          >
        </li>
      {/each}
    </ul>
    {#if shareUrl !== null}
      <h3
        class="recap-section-heading"
        id="recap-share-label"
        data-testid="recap-share-heading"
      >
        {t('recap.share_label')}
      </h3>
      <div class="recap-share-row" data-testid="recap-share-row">
        <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
        <a
          class="recap-share-link"
          data-testid="recap-share-link"
          href={shareUrl}
          tabindex="0"
          aria-describedby="recap-share-label">{shareUrl}</a
        >
        <button
          type="button"
          class="nock-button nock-button-secondary recap-copy"
          data-testid="recap-copy"
          onclick={copyShareLink}>{t('room.share.copy')}</button
        >
      </div>
      {#if copied}
        <p class="recap-copied" data-testid="recap-copied" role="status">
          {t('room.share.copied')}
        </p>
      {/if}
    {/if}
  {:else if dialogState === 'error'}
    <p class="nock-error-line" data-testid="recap-error" role="alert">{t('recap.error')}</p>
  {:else}
    <p class="recap-loading" data-testid="recap-loading" role="status">{t('recap.loading')}</p>
  {/if}
  <button
    type="button"
    class="nock-button nock-button-primary recap-close"
    data-testid="recap-close"
    onclick={() => dialog?.close()}>{t('recap.close')}</button
  >
</dialog>

<style>
  /* The frame is the room sheet's (app.css): 440 px and centred in the column
     layout, a bottom sheet with no handle in the sheet layout, its parts in a
     column 14 px apart. Its scrim is the darker dialog scrim, over the whole
     window, the top bar included. */
  dialog.recap::backdrop {
    top: 0;
    background: var(--nock-scrim-dialog);
  }

  .recap-time {
    margin: 0;
    font: 700 2.1rem/1 var(--nock-font-ui);
    color: var(--nock-navy);
    font-variant-numeric: tabular-nums;
  }

  /* The checks, the reveals and the revealed letters, 4 px apart. */
  .recap-lines {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .recap-lines p {
    margin: 0;
    font: 400 0.95rem var(--nock-font-ui);
    color: var(--nock-ink);
  }

  /* The dialog section heading (_design.md section 4). */
  .recap-section-heading {
    margin: 0;
    font: 600 0.78rem/1.2 var(--nock-font-ui);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--nock-muted);
  }

  .recap-players {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  /* One row per player: dot, name, "(vous)", then the counts on the right. A
     row too narrow for them puts the counts under the name. */
  .recap-player {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    font-size: 0.95rem;
  }

  /* The player dot (_design.md section 11). */
  .recap-colour {
    flex: none;
    box-sizing: border-box;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    box-shadow: 0 0 0 1px var(--nock-dot-ring);
  }

  /* A player the page no longer knows: an empty slot, so the names stay
     aligned. */
  .recap-colour[data-colour=''] {
    background: transparent;
    box-shadow: none;
  }

  /* "Accessibilite" (spec 042): the player's own icon, with no ring. */
  .recap-colour.icon {
    width: 12px;
    height: 12px;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }

  .recap-name {
    font-weight: 600;
    color: var(--nock-ink);
    overflow-wrap: anywhere;
  }

  .recap-you {
    color: var(--nock-muted);
  }

  .recap-values {
    margin-left: auto;
    font-size: 0.85rem;
    color: var(--nock-muted);
    font-variant-numeric: tabular-nums;
  }

  /* In the sheet layout the counts always take a line of their own, under
     the name (past the dot and its gap). */
  .bottom .recap-values {
    flex-basis: 100%;
    margin-left: 18px;
  }

  /* The middle dot between the counts: a pictogram, a space on each side. */
  .recap-sep {
    margin: 0 0.25em;
  }

  .recap-sep::before {
    content: '·';
  }

  /* The URL box, then "Copier le lien" on its right; in the sheet layout the
     button goes under the full-width box. */
  .recap-share-row {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .bottom .recap-share-row {
    flex-wrap: wrap;
  }

  /* The URL box (_design.md section 11): one line with an ellipsis. */
  .recap-share-link {
    flex: 1 1 0;
    display: block;
    box-sizing: border-box;
    min-width: 0;
    padding: 8px 10px;
    border: 1px solid var(--nock-rule);
    border-radius: 6px;
    font: 400 0.85rem/1.2 var(--nock-font-ui);
    color: var(--nock-ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .bottom .recap-share-link {
    flex-basis: 100%;
  }

  .recap-copy {
    flex: none;
    padding: 8px 12px;
  }

  /* The confirmation line (_design.md section 11), 8 px under the share row
     as the screens sheet draws it. */
  .recap-copied {
    margin: -6px 0 0;
    font: 500 0.85rem/1.3 var(--nock-font-ui);
    color: var(--nock-green);
  }

  .recap-loading {
    margin: 0;
    font: 400 0.95rem var(--nock-font-ui);
    color: var(--nock-muted);
  }

  .recap-close {
    align-self: flex-end;
  }
</style>
