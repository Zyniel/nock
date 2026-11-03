<script lang="ts">
  // The open vote (spec 025, spec 047): the live region that reads the question
  // when a vote opens and the result when it closes, always on the page, then
  // the banner over the top of the grid viewport while the vote is open. The
  // room page sends the ballot and gives the grid the focus.
  import { tick } from 'svelte'
  import { nameOf } from './activityFeed'
  import { t } from './i18n'
  import type { VoteClock, VoteOutcome, VoteView } from './roomSession'
  import { VOTE_TICK_MS, voteCountdown } from './voteCountdown'

  let {
    openVote,
    isShown,
    isJoined,
    votedIds,
    voteClock,
    names,
    you,
    lastVoteOutcome,
    layout,
    height = $bindable(0),
    onVote,
    onFocusGrid,
  }: {
    openVote: VoteView | null
    // The banner shows the open vote, never once the grid is solved.
    isShown: boolean
    // True while the page is joined: a socket with its snapshot.
    isJoined: boolean
    // The votes this page cast a ballot on.
    votedIds: number[]
    // The countdown the session keeps, for the open vote or an older one.
    voteClock: VoteClock | null
    // The known nicknames, by player id (spec 013).
    names: Map<string, string>
    // My player id.
    you: string
    // How the last vote ended, for the live region; null before any end.
    lastVoteOutcome: VoteOutcome | null
    layout: 'sheet' | 'column'
    // The banner's height, with its border: a note that shows while the banner
    // is on the page sits under it (spec 043, Decision 25).
    height?: number
    // Send my ballot on the vote and remember it was cast.
    onVote: (voteId: number, yes: boolean) => void
    onFocusGrid: () => void
  } = $props()

  let isMyRequest = $derived(openVote !== null && openVote.player_id === you)
  let hasVoted = $derived(openVote !== null && votedIds.includes(openVote.vote_id))
  let voteQuestionText = $derived(openVote === null ? '' : voteQuestion(openVote))
  let voteResultText = $derived(
    lastVoteOutcome === null ? '' : t(`vote.result.${lastVoteOutcome}`),
  )
  // What a screen reader hears: the question when a vote opens, the result
  // when it closes.
  let voteAnnouncement = $derived(openVote !== null ? voteQuestionText : voteResultText)

  // ---- The countdown of the open vote (spec 047) ----

  // The countdown of the open vote when this page saw it open, else null: a
  // vote known only from a snapshot shows no seconds and no bar.
  let openVoteClock = $derived(openVote === null ? null : clockOfVote(openVote))
  // The page's clock (performance.now()), read again every VOTE_TICK_MS while
  // the banner counts.
  let voteNowMs = $state(0)
  let countdown = $derived(
    openVoteClock === null ? null : voteCountdown(openVoteClock, voteNowMs),
  )

  $effect(() => {
    if (openVoteClock === null || !isShown) {
      return
    }
    voteNowMs = performance.now()
    const ticker = setInterval(() => {
      voteNowMs = performance.now()
    }, VOTE_TICK_MS)
    return () => clearInterval(ticker)
  })

  // The countdown the session keeps for `vote`, or null when it keeps none for
  // that vote.
  function clockOfVote(vote: VoteView): VoteClock | null {
    if (voteClock === null || voteClock.vote_id !== vote.vote_id) {
      return null
    }
    return voteClock
  }

  // The question of a vote, with the requester's nickname (spec 013's known
  // names). The page inserts it as text.
  function voteQuestion(vote: VoteView): string {
    return t(`vote.question.${vote.kind}`, { name: nameOf(names, vote.player_id) })
  }

  // The ballot buttons are disabled while the page is not joined: a ballot sent
  // then would be dropped while the page showed it as cast (decision 18).
  let isVotingOffline = $derived(!isJoined)

  // Send my ballot on the open vote, once, then give the focus to the status
  // that replaces the buttons, so it never falls back to the page (decision 19).
  function castVote(yes: boolean): void {
    if (openVote === null || isVotingOffline || votedIds.includes(openVote.vote_id)) {
      return
    }
    onVote(openVote.vote_id, yes)
    void focusVoteStatus()
  }

  // `tick` resolves once the DOM shows `vote-status` instead of the buttons.
  async function focusVoteStatus(): Promise<void> {
    await tick()
    voteStatus?.focus()
  }

  // ---- Focus when the banner changes (decision 19) ----

  let voteBanner: HTMLElement | null = $state(null)
  let voteStatus: HTMLElement | null = $state(null)

  // What the banner holds: nothing, or the question of one vote.
  let bannerContent = $derived(
    !isShown || openVote === null ? 'none' : `vote-${openVote.vote_id}`,
  )
  let lastBannerContent = 'none'

  // Runs before the page changes the banner: when the focus is inside it, the
  // vote closed or the banner leaves, and the focus goes to the grid instead of
  // falling back to the page.
  $effect.pre(() => {
    const content = bannerContent
    if (content === lastBannerContent) {
      return
    }
    lastBannerContent = content
    const focused = document.activeElement
    if (voteBanner !== null && focused !== null && voteBanner.contains(focused)) {
      void focusGridAfterUpdate()
    }
  })

  // Runs before the ballot buttons are disabled by a lost connection: a focus on
  // one goes to the grid instead of falling back to the page, as the chat does
  // for a mute (gameplay/votes.md rule 6).
  $effect.pre(() => {
    if (!isVotingOffline) {
      return
    }
    const focused = document.activeElement
    // The banner's only buttons are « Oui » and « Non »: the status line that
    // replaces them after a ballot is not a button and keeps the focus.
    const isOnBallotButton =
      focused instanceof HTMLButtonElement && voteBanner !== null && voteBanner.contains(focused)
    if (isOnBallotButton) {
      onFocusGrid()
    }
  })

  async function focusGridAfterUpdate(): Promise<void> {
    await tick()
    onFocusGrid()
  }
</script>

<div
  class="visually-hidden"
  data-testid="vote-announcement"
  role="status"
  aria-live="polite"
  aria-atomic="true"
>{voteAnnouncement}</div>
{#if isShown}
  <!-- The question, the row of the ballot (or the line that takes its place)
       with the seconds left on its right, then the bar of the time left
       (spec 047). -->
  <div
    class="vote-banner {layout}"
    data-testid="vote-banner"
    role="group"
    aria-labelledby="vote-question"
    bind:this={voteBanner}
    bind:offsetHeight={height}
  >
    <p id="vote-question" class="vote-question" data-testid="vote-question">
      {voteQuestionText}
    </p>
    <div class="vote-row" data-testid="vote-row">
      {#if isMyRequest || hasVoted}
        <!-- Not a Tab stop, but it takes the focus after a ballot. -->
        <span
          class="vote-status"
          data-testid="vote-status"
          tabindex="-1"
          bind:this={voteStatus}>{isMyRequest ? t('vote.waiting') : t('vote.cast')}</span
        >
      {:else}
        <button
          type="button"
          class="nock-button nock-button-primary vote-button"
          data-testid="vote-yes"
          disabled={isVotingOffline}
          onclick={() => castVote(true)}>{t('vote.yes')}</button
        >
        <button
          type="button"
          class="nock-button nock-button-secondary vote-button"
          data-testid="vote-no"
          disabled={isVotingOffline}
          onclick={() => castVote(false)}>{t('vote.no')}</button
        >
      {/if}
      {#if countdown !== null}
        <span class="vote-seconds" data-testid="vote-seconds"
          >{t('vote.seconds_left', { count: countdown.seconds })}</span
        >
      {/if}
    </div>
    {#if countdown !== null}
      <div class="vote-timebar" data-testid="vote-timebar" aria-hidden="true">
        <div
          class="vote-timebar-fill"
          data-testid="vote-timebar-fill"
          style:width="{countdown.share * 100}%"
        ></div>
      </div>
    {/if}
  </div>
{/if}

<style>
  /* ---- The vote banner (spec 025, spec 047; specs/_design/overlays.md « Vote ») ----

     Over the grid (spec 025 decision 9): absolutely placed, so it takes no
     height from the grid. The vote wins over the Salon sheet and the scrim
     (spec 022 decision 16), which come later in the page, the sheet on layer
     8 and the scrim on layer 7: it is drawn above them. Its top, left and right edges are 8 px inside
     the grid area: `grid-area` in the sheet layout (its 8 px padding, so the
     banner lies on the viewport's edges), the viewport in the column layout
     (under the grid area's 12 px top padding). */
  .vote-banner {
    position: absolute;
    left: 8px;
    right: 8px;
    z-index: 9;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 10px 12px;
    border: 2px solid var(--nock-navy);
    border-radius: 10px;
    background: var(--nock-white);
    box-shadow: 0 10px 24px -12px var(--nock-shadow);
  }

  .vote-banner.sheet {
    top: 8px;
  }

  .vote-banner.column {
    top: 20px;
  }

  .vote-question {
    margin: 0;
    font: 600 0.95rem/1.3 var(--nock-font-ui);
    color: var(--nock-ink);
  }

  /* The ballot, or the line that takes its place, then the seconds on the
     right. */
  .vote-row {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 31px;
  }

  .vote-button {
    flex: none;
    padding: 7px 16px;
  }

  .vote-status {
    min-width: 0;
    font: 500 0.85rem/1.3 var(--nock-font-ui);
    color: var(--nock-muted);
  }

  .vote-seconds {
    flex: none;
    margin-left: auto;
    font: 500 0.85rem/1 var(--nock-font-ui);
    color: var(--nock-muted);
    font-variant-numeric: tabular-nums;
    white-space: nowrap;
  }

  /* The time left: a word-blue track and its navy fill, which moves in steps
     with no transition (spec 047, Decision 3). */
  .vote-timebar {
    height: 4px;
    border-radius: 2px;
    background: var(--nock-word);
    overflow: hidden;
  }

  .vote-timebar-fill {
    height: 100%;
    background: var(--nock-navy);
    transition: none;
  }
</style>
