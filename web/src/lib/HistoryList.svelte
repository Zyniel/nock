<script lang="ts">
  import HistoryItem from './HistoryItem.svelte'
  import type { HistoryRecord } from './history'
  import { t } from './i18n'

  // The finished grids of the catalogue page (spec 029), already merged and in
  // their order. The catalogue page shows it only when there is a record.
  let { records }: { records: HistoryRecord[] } = $props()
</script>

<section class="history" data-testid="history" aria-labelledby="history-heading">
  <h2 id="history-heading">{t('history.heading')}</h2>
  <!-- The explicit role: WebKit does not expose a list without bullets as a list. -->
  <ul class="history-list" role="list">
    {#each records as record (record.code)}
      <HistoryItem {record} />
    {/each}
  </ul>
</section>

<style>
  .history {
    margin: 1.5rem 0 0;
  }

  .history h2 {
    margin: 0 0 0.5rem;
    font-size: 1.25rem;
  }

  .history-list {
    display: grid;
    gap: 0.75rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }
</style>
