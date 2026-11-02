<script lang="ts">
  // The Salon's Joueurs tab (spec 043, "Joueurs"): one row of two lines per
  // player, the host's « Couper » and « Retirer » on the other players' rows,
  // then the invitation link. It stays on the page while its tab is not
  // selected, with the `hidden` attribute.
  import PlayerIcon from './PlayerIcon.svelte'
  import { announce } from './announce'
  import { newLinkCopier } from './copyLink'
  import { t } from './i18n'
  import { displayNickname } from './nickname'
  import type { PlayerView } from './roomSession'

  let {
    players,
    you,
    isHost,
    isShown,
    isAccessibilityOn,
    clues,
    shareLink,
    copyButton = $bindable(null),
    onMute,
    onRemove,
  }: {
    // The players of the snapshot, in its order.
    players: PlayerView[]
    you: string
    // True while `you` is the host.
    isHost: boolean
    // True while the tab is selected.
    isShown: boolean
    // « Accessibilité » (spec 042): each dot shows its player's icon.
    isAccessibilityOn: boolean
    // The clue of each player's selected word, by player id.
    clues: Map<string, string>
    shareLink: string
    copyButton?: HTMLButtonElement | null
    onMute: (playerId: string, isPlayerMuted: boolean) => void
    onRemove: (playerId: string) => void
  } = $props()

  // True for 2 seconds after a successful copy (spec 011's time).
  let copied = $state(false)
  const linkCopier = newLinkCopier((isCopied) => {
    copied = isCopied
    if (isCopied) {
      announce(t('room.share.copied'))
    }
  })

  // Leaving the page must not leave the timer to fire on a destroyed page.
  $effect(() => {
    return () => linkCopier.stop()
  })

  // Write the link to the clipboard. Without a usable clipboard nothing changes.
  async function copyLink(): Promise<void> {
    await linkCopier.copy(shareLink)
  }
</script>

<div
  class="roster"
  id="roster"
  data-testid="roster"
  role="tabpanel"
  aria-labelledby="salon-tab-players"
  hidden={!isShown}
>
  <h2 id="roster-heading" class="visually-hidden">{t('roster.heading')}</h2>
  <!-- The explicit role: WebKit does not expose a list without bullets as a
       list. -->
  <ul class="players" role="list" aria-labelledby="roster-heading">
    {#each players as player (player.player_id)}
      {@const isYou = player.player_id === you}
      {@const name = displayNickname(player.nickname)}
      {@const clue = clues.get(player.player_id)}
      <li
        class="player"
        data-testid="roster-player"
        data-player-id={player.player_id}
        data-colour={String(player.colour)}
        data-state={player.state}
        data-you={String(isYou)}
        data-host={String(player.is_host)}
      >
        <span
          class="roster-colour"
          class:icon={isAccessibilityOn}
          data-testid="roster-colour"
          data-colour={String(player.colour)}
          style:background={isAccessibilityOn ? null : `var(--player-colour-${player.colour})`}
          >{#if isAccessibilityOn}<PlayerIcon colour={player.colour} side="12px" />{/if}</span
        >
        <div class="line-one">
          <span class="roster-nickname" class:own={isYou} data-testid="roster-nickname"
            >{name}</span
          >
          {#if isYou}
            <span class="roster-you" data-testid="roster-you">{t('roster.you')}</span>
          {/if}
          {#if player.is_host}
            <span class="roster-host" data-testid="roster-host">{t('roster.host')}</span>
          {/if}
          {#if isHost && !isYou}
            <span class="host-buttons">
              <button
                type="button"
                class="nock-button nock-button-secondary small"
                data-testid="mute-player"
                data-muted={String(player.muted)}
                aria-label={player.muted
                  ? t('chat.unmute_label', { name })
                  : t('chat.mute_label', { name })}
                onclick={() => onMute(player.player_id, player.muted)}
                >{player.muted ? t('chat.unmute') : t('chat.mute')}</button
              >
              <button
                type="button"
                class="nock-button nock-button-secondary small"
                data-testid="remove-player"
                aria-label={t('host.remove_label', { name })}
                onclick={() => onRemove(player.player_id)}>{t('host.remove')}</button
              >
            </span>
          {/if}
        </div>
        <div class="line-two">
          <span class="roster-state" data-testid="roster-state"
            >{t(`presence.${player.state}`)}</span
          >
          {#if clue !== undefined}
            <span class="roster-sep" data-testid="roster-sep" aria-hidden="true"></span>
            <span class="roster-clue" data-testid="roster-clue">{clue}</span>
          {/if}
        </div>
      </li>
    {/each}
  </ul>
  <div class="share-panel" data-testid="share-panel">
    <span id="share-label" class="share-label" data-testid="share-label"
      >{t('room.share.label')}</span
    >
    <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
    <a
      class="share-link"
      data-testid="share-link"
      href={shareLink}
      tabindex="0"
      aria-describedby="share-label">{shareLink}</a
    >
    <button
      type="button"
      class="nock-button nock-button-primary copy-link"
      data-testid="copy-link"
      bind:this={copyButton}
      onclick={copyLink}>{t('room.share.copy')}</button
    >
    {#if copied}
      <p class="share-copied" data-testid="share-copied">
        {t('room.share.copied')}
      </p>
    {/if}
  </div>
</div>

<style>
  /* The panel scrolls when its content is higher than it; the list never
     scrolls on its own. */
  .roster {
    flex: 1 1 0;
    min-height: 0;
    box-sizing: border-box;
    padding: 10px 16px;
    overflow-y: auto;
    overflow-wrap: anywhere;
    /* A control scrolled into view (a tap, the keyboard) stops a few pixels
       inside the panel's edge: the panel scrolls by whole pixels, and a
       button left a fraction of a pixel outside would lose its last row of
       pixels to a tap (spec 014 AC-8). */
    scroll-padding: 4px 0;
  }

  .roster[hidden] {
    display: none;
  }

  .players {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin: 0;
    padding: 0;
    list-style: none;
    font-size: 0.95rem;
  }

  /* Two lines: the dot in the first column, both lines in the second, so line
     2 starts on the nickname's left edge. */
  .player {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    column-gap: 8px;
    align-items: center;
  }

  .roster-colour {
    grid-row: 1;
    grid-column: 1;
    box-sizing: border-box;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    box-shadow: 0 0 0 1px var(--nock-dot-ring);
  }

  /* « Accessibilité » (spec 042): the player's own icon, with no ring. */
  .roster-colour.icon {
    width: 12px;
    height: 12px;
    border-radius: 0;
    box-shadow: none;
    background: transparent;
  }

  .line-one {
    grid-row: 1;
    grid-column: 2;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 8px;
    min-width: 0;
  }

  .line-two {
    grid-row: 2;
    grid-column: 2;
    display: flex;
    align-items: baseline;
    min-width: 0;
    font-size: 0.85rem;
    color: var(--nock-muted);
  }

  .roster-nickname {
    min-width: 0;
    font-weight: 400;
    color: var(--nock-ink);
  }

  .roster-nickname.own {
    font-weight: 700;
  }

  /* No opacity: dimmed text would not reach 4.5:1 (spec 035 AC-7). The state
     is also written on line 2. */
  .player[data-state='idle'] .roster-nickname {
    font-style: italic;
  }

  .player[data-state='disconnected'] .roster-nickname {
    font-style: italic;
    text-decoration: line-through;
  }

  .roster-you {
    font-weight: 400;
    color: var(--nock-muted);
  }

  /* The « hôte » tag (specs/_design/foundation.md « Components »). */
  .roster-host {
    padding: 2px 8px;
    border-radius: 10px;
    font: 600 0.72rem/1.3 var(--nock-font-ui);
    color: var(--nock-navy);
    background: var(--nock-clue-bg);
  }

  .host-buttons {
    display: flex;
    gap: 6px;
    margin-left: auto;
  }

  /* The whole box takes a tap, its rounded corners included (spec 014 AC-8):
     a square layer over the button (the ::before below) catches the pointer
     there. */
  .small {
    padding: 6px 10px;
    font-size: 0.8rem;
    position: relative;
  }

  .small::before {
    content: '';
    position: absolute;
    inset: -1px;
  }

  .roster-state {
    flex: none;
  }

  /* The « · » between the state and the clue: a pictogram drawn by CSS. */
  .roster-sep::before {
    content: '·';
    margin: 0 0.35em;
  }

  .roster-clue {
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .share-panel {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
    margin-top: 14px;
  }

  /* The dialog section heading style (specs/_design/foundation.md « Typography »). */
  .share-label {
    font: 600 0.78rem/1.2 var(--nock-font-ui);
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--nock-muted);
  }

  /* The URL box: one line with an ellipsis. */
  .share-link {
    display: block;
    box-sizing: border-box;
    align-self: stretch;
    padding: 8px 10px;
    border: 1px solid var(--nock-rule);
    border-radius: 6px;
    font-size: 0.85rem;
    color: var(--nock-ink);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  /* The confirmation line (specs/_design/foundation.md « Components »). */
  .share-copied {
    margin: 0;
    font: 500 0.85rem/1.3 var(--nock-font-ui);
    color: var(--nock-green);
  }
</style>
