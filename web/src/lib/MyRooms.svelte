<script lang="ts">
  import { onMount } from 'svelte'
  import { t } from './i18n'
  import { fetchRoomSummaries, lastActivityText, type RoomKey, type RoomSummary } from './myRooms'

  // "My rooms" of the catalogue page (spec 032): the open rooms this device
  // keeps an identity for, as the server sums them up. The catalogue page shows
  // it only when there is at least one key, and does not wait for it.
  let { keys }: { keys: RoomKey[] } = $props()

  type State = 'loading' | 'ready' | 'error'

  let sectionState: State = $state('loading')
  let summaries: RoomSummary[] = $state([])

  async function loadSummaries(): Promise<void> {
    const loaded = await fetchRoomSummaries(keys)
    if (loaded === null) {
      sectionState = 'error'
      return
    }
    summaries = loaded
    sectionState = 'ready'
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
>
  <h2 id="my-rooms-heading">{t('my_rooms.heading')}</h2>
  {#if sectionState === 'loading'}
    <p>{t('my_rooms.loading')}</p>
  {:else if sectionState === 'error'}
    <p>{t('my_rooms.error')}</p>
  {:else if summaries.length === 0}
    <p>{t('my_rooms.empty')}</p>
  {:else}
    <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
    <ul class="my-rooms-list" role="list">
      {#each summaries as summary (summary.code)}
        <li
          data-testid="my-room"
          data-code={summary.code}
          data-grid={summary.grid_number === null ? '' : String(summary.grid_number)}
          data-solved={String(summary.solved)}
          data-last-activity={summary.last_activity_at}
        >
          <h3>{gridLabel(summary)}</h3>
          <p>{t('catalogue.item.size', { width: summary.width, height: summary.height })}</p>
          <p data-testid="my-room-players">
            {t('my_rooms.players', { names: summary.players.join(', ') })}
          </p>
          <p data-testid="my-room-activity">{lastActivityText(summary.last_activity_at)}</p>
          {#if summary.solved}
            <p data-testid="my-room-solved">{t('catalogue.progress.finished')}</p>
          {/if}
          <!-- WebKit only Tab-focuses links that have a tabindex (spec 035 AC-1). -->
          <a
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
  .my-rooms {
    margin: 0 0 1.5rem;
  }

  .my-rooms h2 {
    margin: 0 0 0.5rem;
    font-size: 1.25rem;
  }

  .my-rooms-list {
    display: grid;
    gap: 0.75rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .my-rooms-list li {
    padding: 0.75rem;
    border: 1px solid #5b6070;
    border-radius: 0.5rem;
  }

  .my-rooms-list h3 {
    margin: 0 0 0.25rem;
    font-size: 1rem;
  }

  /* A long list of nicknames wraps rather than widen the page (spec 006 AC-5). */
  .my-rooms-list p {
    margin: 0.15rem 0;
    overflow-wrap: anywhere;
  }
</style>
