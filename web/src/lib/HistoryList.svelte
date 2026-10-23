<script lang="ts">
  import HistoryItem from './HistoryItem.svelte'
  import type { HistoryRecord } from './history'
  import { t } from './i18n'

  // The history, the finished grids of the catalogue page (spec 029,
  // spec 046), already merged and in their order. The catalogue page shows it
  // only when there is a record.
  let { records }: { records: HistoryRecord[] } = $props()
</script>

<section class="history" data-testid="history" aria-labelledby="history-heading">
  <h2 class="nock-section-heading" id="history-heading">{t('history.heading')}</h2>
  <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
  <ul class="history-list" role="list">
    {#each records as record (record.code)}
      <HistoryItem {record} />
    {/each}
  </ul>
</section>

<style>
  /* The heading, then the rows 16 px under it, as "My rooms" (spec 046). */
  .history {
    display: grid;
    gap: 16px;
    min-width: 0;
  }

  .history-list {
    display: grid;
    gap: 10px;
    margin: 0;
    padding: 0;
    list-style: none;
  }
</style>
