<script lang="ts">
  // One clue cell of the grid (spec 042, specs/_design/cells.md « Clue
  // cells »), drawn by GridViewport.svelte: its one or two clues, with their
  // flags (spec 021) and reactions (spec 022).
  import { t } from './i18n'
  import { cellId } from './gridLayout'
  import { ICONS } from './icons'
  import IconShapes from './IconShapes.svelte'
  import type { ClueView } from './roomSession'
  import type { ClueFlagMarker } from './clueFlags'
  import type { ClueReactionMarker } from './chat'

  let {
    row,
    column,
    clues,
    activeClueIndex,
    clueFlags,
    clueReactions,
  }: {
    row: number
    column: number
    clues: ClueView[]
    // The index of the clue of my selected word in this cell; null when my
    // selected word's clue is in no clue of it.
    activeClueIndex: number | null
    // The marker of each flagged clue, by clue key "row,column,clue_index"
    // (spec 021). A clue nobody flagged has no entry.
    clueFlags: Map<string, ClueFlagMarker>
    // The reaction each clue shows, by clue key "row,column,clue_index" (spec
    // 022). A clue that shows no reaction has no entry.
    clueReactions: Map<string, ClueReactionMarker>
  } = $props()
</script>

<div
  class="cell clue-cell"
  data-testid="cell"
  data-row={row}
  data-column={column}
  data-type="clue"
  data-author-colour=""
  role="gridcell"
  id={cellId(row, column)}
  style:grid-row={row + 1}
  style:grid-column={column + 1}
>
  {#each clues as clue, index (index)}
    {@const flagMarker = clueFlags.get(`${row},${column},${index}`)}
    {@const reactionMarker = clueReactions.get(`${row},${column},${index}`)}
    {#if index === 1}
      <div class="separator" data-testid="clue-separator"></div>
    {/if}
    <div
      class="clue"
      data-testid="clue"
      data-clue-index={index}
      data-arrow={clue.arrow}
      data-active={String(activeClueIndex === index)}
      data-flagged={String(flagMarker !== undefined)}
      class:active={activeClueIndex === index}
    >
      <span class="clue-text" data-testid="clue-text">{clue.text}</span>
      {#if flagMarker !== undefined}
        <!-- Over the top left corner of its own clue: it takes no room
             from the clue text and never moves it (spec 021). -->
        <span
          class="clue-flag"
          data-testid="clue-flag"
          data-flagged-by={flagMarker.flaggedBy}
          aria-hidden="true"
          ><svg viewBox="0 0 24 24" aria-hidden="true"
            ><IconShapes shapes={ICONS.flag} /></svg
          ></span
        >
        <span class="visually-hidden" data-testid="clue-flag-label"
          >{t('flag.marker_label', { names: flagMarker.names })}</span
        >
      {/if}
      {#if reactionMarker !== undefined}
        <!-- Drawn over the middle of its clue: it takes no room from
             the clue text (spec 022). -->
        <span
          class="clue-reaction"
          data-testid="clue-reaction"
          data-reaction={reactionMarker.reaction}
          data-player-id={reactionMarker.playerId}
          aria-hidden="true">{reactionMarker.text}</span
        >
        <span class="visually-hidden" data-testid="clue-reaction-label"
          >{reactionMarker.label}</span
        >
      {/if}
    </div>
  {/each}
</div>

<style>
  /* Every cell of the grid draws its own right and bottom grid line (spec
     042); GridViewport.svelte and LetterCell.svelte hold the same rule for
     theirs. */
  .cell {
    box-sizing: border-box;
    min-width: 0;
    min-height: 0;
    border-right: 1px solid var(--nock-rule);
    border-bottom: 1px solid var(--nock-rule);
    background: var(--nock-white);
  }

  /* A clue cell (spec 042): its clues fill its content box, one alone or two
     in halves of equal height around the separator. It does not clip: at zoom
     1 a long clue may reach past its edges. The padding is 2px by 3px; only on
     tiny cells (a large grid beside the in-app keyboard on a low window) does
     it give way, the sides below 15px and the top and bottom below 12px, so
     that the clues keep a box that takes taps (FX-02's 5.8px cells leave a
     clue about 2.5px wide, which Firefox's taps reach). */
  .clue-cell {
    --clue-padding-x: min(3px, calc(var(--cell) * 0.2));
    display: flex;
    flex-direction: column;
    padding: min(2px, calc(var(--cell) * 0.17)) var(--clue-padding-x);
    background: var(--nock-clue-bg);
  }

  /* A clue holds its text, centred, and the marks drawn over it (the flag, a
     reaction), placed against it. */
  .clue {
    position: relative;
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* The clue of my selected word: its own half of the cell (decided by the
     human on 2026-10-16). */
  .clue.active {
    background: var(--nock-selected);
    border-radius: 2px;
  }

  /* One size for every clue cell; the text keeps the clue as written and the
     capitals are the CSS's. A long text that reaches past its cell takes no
     tap: a tap goes to the cell or the clue under it (its own clue takes the
     taps on its box). */
  .clue-text {
    pointer-events: none;
    display: block;
    width: 100%;
    /* IBM Plex Sans Condensed's ascent and descent take 1.3em, more than the
       1.12 line: this padding holds the 0.09em that the first and last lines'
       glyphs reach past their lines, so the text's box holds all of it and no
       clue text is cut at full zoom (spec 006 AC-1). The text stays centred. */
    padding-block: 0.09em;
    font-family: var(--nock-font-clue);
    font-size: max(6px, calc(var(--cell) * 0.145));
    font-weight: 600;
    line-height: 1.12;
    letter-spacing: 0.01em;
    text-transform: uppercase;
    text-align: center;
    overflow-wrap: break-word;
    -webkit-hyphens: manual;
    hyphens: manual;
    color: var(--nock-clue-ink);
  }

  .separator {
    flex: none;
    height: 1px;
    margin: 0 14%;
    background: var(--nock-clue-ink);
    opacity: 0.55;
  }

  /* The flag of spec 021 on its own clue: the red flag icon on a square of
     clue blue-grey at the clue's top left, 1px right of the cell's left edge
     (the clue starts 3px in), or on that edge's padding when it is thinner
     than 1px. It is drawn over the clue text and never moves it; a tap on it is
     a tap on its clue. */
  .clue-flag {
    position: absolute;
    z-index: 2;
    top: 0;
    left: calc(min(1px, var(--clue-padding-x)) - var(--clue-padding-x));
    display: grid;
    place-items: center;
    width: max(8px, calc(var(--cell) * 0.22));
    height: max(8px, calc(var(--cell) * 0.22));
    background: var(--nock-clue-bg);
    border-radius: 0 0 3px 0;
  }

  .clue-flag svg {
    width: 86%;
    height: 86%;
    fill: var(--nock-red);
    stroke: var(--nock-red);
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  /* A shown reaction (spec 022): the white pill of specs/_design/room.md « Reactions »,
     centred on its own clue (one half of a two-clue cell). Positioned against
     the clue, so it adds no layout, and on layer 8, above the flag and the
     cells around it, since it may reach past the cell's edges. It lies inside
     its clue, so a tap on it is a tap on its clue. */
  .clue-reaction {
    position: absolute;
    z-index: 8;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    padding: 2px 6px;
    font-size: 16px;
    line-height: 1.2;
    white-space: nowrap;
    color: var(--nock-ink);
    background: var(--nock-white);
    border: 1px solid var(--nock-line);
    border-radius: 12px;
    box-shadow: 0 4px 10px -4px var(--nock-shadow-soft);
  }
</style>
