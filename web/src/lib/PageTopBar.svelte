<script lang="ts">
  // The top bar of a plain page (spec 046, "Page top bar"): white, across the
  // top of the window, with the brand and, on the catalogue, "Compte" on its
  // right. On the catalogue and the grid page it is 56 px high on every
  // window; on the entry pages and the page not found it is the phone's 54 px
  // bar on a narrow window. Its buttons are 38 px high on a wide window and
  // 34 px on a narrow one. The frame around it says which the window is.
  import type { Snippet } from 'svelte'
  import TopBarBrand from './TopBarBrand.svelte'

  let {
    form,
    isWide,
    end,
  }: {
    form: 'catalogue' | 'entry'
    // Whether the window is wide (windowForm.ts).
    isWide: boolean
    // What sits on the right of the bar, if anything.
    end?: Snippet
  } = $props()
</script>

<header
  class="page-topbar"
  class:phone-bar={form === 'entry' && !isWide}
  class:narrow={!isWide}
  data-testid="page-topbar"
>
  <TopBarBrand />
  {#if end !== undefined}
    <div class="page-topbar-end">{@render end()}</div>
  {/if}
</header>

<style>
  .page-topbar {
    flex: none;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    width: 100%;
    height: 56px;
    padding: 0 16px;
    border-bottom: 1px solid var(--nock-line);
    background: var(--nock-white);
  }

  .page-topbar.phone-bar {
    height: 54px;
    padding: 0 14px;
  }

  .page-topbar-end {
    display: flex;
    align-items: center;
    margin-left: auto;
  }

  /* A computer top-bar button with no icon (spec 043): the label in 500
     0.92rem. */
  .page-topbar :global(.topbar-button) {
    height: 38px;
    padding: 0 12px;
    font-size: 0.92rem;
  }

  .page-topbar.narrow :global(.topbar-button) {
    height: 34px;
  }
</style>
