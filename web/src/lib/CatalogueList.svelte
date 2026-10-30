<script lang="ts">
  // The grid cards of the catalogue and of the grid page (spec 004, spec 046
  // "Grid cards"): one card per row on a phone, two on a computer. The cards
  // show their drawing only while the list's content box holds two of them per
  // row; a resize observer follows its width.
  import CatalogueItem from './CatalogueItem.svelte'
  import type { GridSummary } from './catalogue'
  import { THUMB_MIN_LIST_WIDTH_PX } from './gridThumb'

  let {
    grids,
    accountProgress,
  }: { grids: GridSummary[]; accountProgress: Record<string, unknown> | null } = $props()

  let listWidth = $state(0)
  const isThumbShown = $derived(listWidth >= THUMB_MIN_LIST_WIDTH_PX)

  function onListResize(entries: ResizeObserverEntry[]): void {
    for (const entry of entries) {
      listWidth = entry.contentRect.width
    }
  }

  // Watch the list's width while it is on the page (a Svelte action).
  function watchWidth(list: HTMLElement): { destroy: () => void } {
    const observer = new ResizeObserver(onListResize)
    observer.observe(list)
    return { destroy: () => observer.disconnect() }
  }
</script>

<div class="catalogue-list" data-testid="catalogue-list" use:watchWidth>
  {#each grids as grid (grid.number)}
    <CatalogueItem summary={grid} {isThumbShown} {accountProgress} />
  {/each}
</div>

<style>
  .catalogue-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 400px), 1fr));
    gap: 12px;
  }
</style>
