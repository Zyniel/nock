<script lang="ts">
  // The entry frame (spec 046, "Entry frame"): the page top bar, then the page
  // grey down to the window's bottom, holding one centred column at most 420 px
  // wide; it is the page's `main`, after the top bar, which is the banner. The
  // entry pages of a room and the page not found show their room code line and
  // their card in it. The page that holds the frame is a plain
  // page (the class `nock-plain-page`), so that the grey reaches the bottom.
  import type { Snippet } from 'svelte'
  import PageTopBar from './PageTopBar.svelte'
  import { isWindowWide } from './wideWindow'

  let { children }: { children: Snippet } = $props()

  // Whether the window is wide, worked out here once for the bar and the body,
  // and again after each resize or rotation.
  const isWide = $derived(isWindowWide())
</script>

<PageTopBar form="entry" {isWide} />
<main class="page-body" class:narrow={!isWide} data-testid="page-body">
  <div class="page-column" data-testid="page-column">
    {@render children()}
  </div>
</main>

<style>
  .page-body {
    flex: 1 0 auto;
    box-sizing: border-box;
    padding: 48px 24px;
    background: var(--nock-page);
  }

  .page-body.narrow {
    padding: 20px 16px;
  }

  .page-column {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 14px;
    align-items: start;
    justify-items: stretch;
    width: min(420px, 100%);
    margin: 0 auto;
  }

  /* The room code line (room.heading), above the card. */
  .page-column :global(.room-code-line) {
    margin: 0;
    font: 600 0.85rem/1 var(--nock-font-ui);
    color: var(--nock-muted);
  }
</style>
