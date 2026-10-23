<script lang="ts">
  import { onMount } from 'svelte'
  import MetaSep from './MetaSep.svelte'
  import { t } from './i18n'
  import { fetchRoomSummaries, lastActivityText, type RoomKey, type RoomSummary } from './myRooms'
  import { displayNickname } from './nickname'

  // "My rooms" of the catalogue page (spec 032): the open rooms this device
  // keeps an identity for, as the server sums them up. The catalogue page shows
  // it only when there is at least one key, and does not wait for it. It stays
  // hidden while it loads and when no room is open (spec 046, P4).
  // `onloaded` gets the summaries once they arrive (the history of spec 029).
  let { keys, onloaded }: { keys: RoomKey[]; onloaded: (summaries: RoomSummary[]) => void } =
    $props()

  type State = 'loading' | 'ready' | 'error'

  let sectionState: State = $state('loading')
  let summaries: RoomSummary[] = $state([])

  const isHidden = $derived(
    sectionState === 'loading' || (sectionState === 'ready' && summaries.length === 0),
  )

  async function loadSummaries(): Promise<void> {
    const loaded = await fetchRoomSummaries(keys)
    if (loaded === null) {
      sectionState = 'error'
      return
    }
    summaries = loaded
    sectionState = 'ready'
    onloaded(loaded)
  }

  // Once, when the page shows.
  onMount(() => {
    void loadSummaries()
  })

  function gridLabel(summary: RoomSummary): string {
    if (summary.grid_number === null) {
      return t('my_rooms.unnumbered')
    }
    return t('catalogue.item.number', { number: summary.grid_number })
  }
</script>

<section
  class="my-rooms"
  data-testid="my-rooms"
  data-state={sectionState}
  aria-labelledby="my-rooms-heading"
  hidden={isHidden}
>
  <h2 class="nock-section-heading" id="my-rooms-heading">{t('my_rooms.heading')}</h2>
  {#if sectionState === 'error'}
    <p class="nock-error-line" data-testid="my-rooms-error">{t('my_rooms.error')}</p>
  {:else if sectionState === 'ready'}
    <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
    <ul class="my-rooms-list" role="list">
      {#each summaries as summary, index (index)}
        <li
          class="nock-list-row"
          data-testid="my-room"
          data-code={summary.code}
          data-grid={summary.grid_number === null ? '' : String(summary.grid_number)}
          data-solved={String(summary.solved)}
          data-last-activity={summary.last_activity_at}
        >
          <div class="nock-row-text">
            <h3 class="nock-row-title" data-testid="my-room-title">
              <span
                >{gridLabel(summary)}<MetaSep />{t('catalogue.item.size', {
                  width: summary.width,
                  height: summary.height,
                })}</span
              >
              {#if summary.solved}
                <span
                  class="nock-status-pill nock-status-pill-finished"
                  data-testid="my-room-solved">{t('catalogue.progress.finished')}</span
                >
              {/if}
            </h3>
            <p class="nock-row-line" data-testid="my-room-players">
              {t('my_rooms.players', { names: summary.players.map(displayNickname).join(', ') })}
            </p>
            <p class="nock-row-line" data-testid="my-room-activity">
              {lastActivityText(summary.last_activity_at)}
            </p>
          </div>
          <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
          <a
            class="nock-button"
            class:nock-button-primary={!summary.solved}
            class:nock-button-secondary={summary.solved}
            data-testid="my-room-link"
            href={`/r/${summary.code}`}
            tabindex="0"
            aria-label={t('my_rooms.open_label', { code: summary.code })}>{t('my_rooms.open')}</a
          >
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  /* The heading, then the list 16 px under it, or the error line 6 px under
     it, as the screens sheet draws them. */
  .my-rooms {
    display: grid;
    gap: 16px;
    min-width: 0;
  }

  .my-rooms[data-state='error'] {
    gap: 6px;
  }

  /* The `hidden` attribute wins over the grid display. */
  .my-rooms[hidden] {
    display: none;
  }

  .my-rooms-list {
    display: grid;
    gap: 10px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
</style>
