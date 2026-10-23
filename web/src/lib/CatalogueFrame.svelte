<script lang="ts">
  // The catalogue frame (spec 046, "Catalogue frame"): the page top bar, then
  // one column at most 920 px wide, centred on white, its parts 16 px apart.
  // The catalogue and the grid page show their content in it. The page that
  // holds the frame is a plain page (the class `nock-plain-page`).
  import type { Snippet } from 'svelte'
  import PageTopBar from './PageTopBar.svelte'
  import { isWideWindow } from './windowForm'

  let {
    topBarEnd,
    isWide = $bindable(false),
    children,
  }: {
    // What sits on the right of the top bar: the catalogue's "Compte".
    topBarEnd?: Snippet
    // Whether the window is wide. The frame works it out; a page that needs it
    // too (the catalogue, for its account dialog) reads it with `bind:isWide`.
    isWide?: boolean
    children: Snippet
  } = $props()

  // Worked out once here for the bar and the column, and again after each
  // resize or rotation.
  function followWindow(): void {
    isWide = isWideWindow(window.innerWidth, window.innerHeight)
  }

  followWindow()
</script>

<svelte:window onresize={followWindow} />

<PageTopBar form="catalogue" {isWide} end={topBarEnd} />
<div class="catalogue-column" class:narrow={!isWide} data-testid="catalogue-column">
  {@render children()}
</div>

<style>
  .catalogue-column {
    box-sizing: border-box;
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
    align-content: start;
    width: 100%;
    max-width: 920px;
    margin: 0 auto;
    padding: 24px;
  }

  .catalogue-column.narrow {
    padding: 16px;
  }
</style>
