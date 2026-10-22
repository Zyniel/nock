<script lang="ts">
  // The pictogram that starts an event line (spec 043, "Discussion: the
  // stream"; _design.md section 5): → for a join, ← for a departure, ✓ for a
  // check, ▲ for a reveal, drawn by CSS so that they are never read as text;
  // the filled flag icon for a flag. A kind with no pictogram draws nothing.
  // It takes the colour of its line.
  import { pictogramOfKind } from './activityFeed'
  import IconShapes from './IconShapes.svelte'
  import { ICONS } from './icons'

  let { kind, testId = null }: { kind: string; testId?: string | null } = $props()

  let pictogram = $derived(pictogramOfKind(kind))
</script>

{#if pictogram === 'flag'}
  <span class="line-pictogram" data-testid={testId} aria-hidden="true"
    ><svg class="line-flag" viewBox="0 0 24 24" aria-hidden="true"
      ><IconShapes shapes={ICONS.flag} /></svg
    ></span
  >
{:else if pictogram !== null}
  <span class="line-pictogram {pictogram}" data-testid={testId} aria-hidden="true"></span>
{/if}

<style>
  /* The gap after the pictogram is the space the design sheet draws there. */
  .line-pictogram {
    margin-right: 0.25em;
  }

  .joined::before {
    content: '→';
  }

  .left::before {
    content: '←';
  }

  .check::before {
    content: '✓';
  }

  .reveal::before {
    content: '▲';
  }

  /* The inline flag (the sheet's FLAG_ICO): 1em, a little below the baseline,
     the pole unfilled and the flag filled in the line's colour. */
  .line-flag {
    width: 1em;
    height: 1em;
    vertical-align: -0.15em;
    fill: currentColor;
    stroke: currentColor;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .line-flag :global(path:first-child) {
    fill: none;
  }
</style>
