<script lang="ts">
  // The legend of the Auteurs mode (spec 045, _design.md sections 4 and 7):
  // « Auteurs : », then each player's name in their ink, in join order. It is
  // a key to colours, which a screen reader does not show, so it is hidden from
  // screen readers. The grid viewport places it under the grid and reports its
  // height, which sets the room the grid gives it.
  import { t } from './i18n'
  import type { LegendName } from './authorsView'

  let {
    names,
    marginTop,
    marginBottom,
    isOverGrid,
    maxWidth,
    height = $bindable(0),
  }: {
    names: LegendName[]
    // The margins that put the legend 8 px under the grid's shown bottom and
    // keep its room in the flow under the grid viewport, in px.
    marginTop: number
    marginBottom: number
    // True while it lies over the bottom of the grid viewport (spec 045,
    // decision 8): then it is drawn above the cells and lets taps through.
    isOverGrid: boolean
    // Its largest width in px, the clue bar's (decision 9); null: the width of
    // the grid area's content box.
    maxWidth: number | null
    // The legend's height, in px, as drawn.
    height?: number
  } = $props()

  let borderBox: readonly ResizeObserverSize[] = $state([])

  // The height follows the drawn legend: one line, or more when it wraps.
  $effect(() => {
    if (borderBox.length > 0) {
      height = borderBox[0].blockSize
    }
  })
</script>

<div
  class="authors-legend"
  data-testid="authors-legend"
  aria-hidden="true"
  class:over-grid={isOverGrid}
  style:max-width={maxWidth === null ? null : `${maxWidth}px`}
  style:margin-top="{marginTop}px"
  style:margin-bottom="{marginBottom}px"
  bind:borderBoxSize={borderBox}
>
  <span data-testid="authors-legend-label">{t('authors.legend')}</span>
  {#each names as entry (entry.playerId)}
    <span
      class="authors-legend-name"
      data-testid="authors-legend-name"
      data-player-id={entry.playerId}
      data-colour={String(entry.colour)}
      style:color="var(--player-ink-{entry.colour})">{entry.name}</span
    >
  {/each}
</div>

<style>
  /* A white pill in the flow under the grid viewport, centred on the grid
     area, never wider than the clue bar: in the column layout its largest
     width is the clue bar's, set on the element, and it may reach past the
     grid's sides; in the sheet layout the grid area's content box limits it.
     Its items keep 8 px apart; when they do not fit on one line it wraps, each
     line centred (as the screens sheet's `.legend`). */
  .authors-legend {
    position: relative;
    flex: none;
    align-self: center;
    box-sizing: border-box;
    width: max-content;
    max-width: 100%;
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    column-gap: 8px;
    row-gap: 2px;
    padding: 4px 12px;
    background: var(--nock-legend-bg);
    border: 1px solid var(--nock-line);
    border-radius: 14px;
    font: 500 0.8rem/1.2 var(--nock-font-ui);
    color: var(--nock-muted);
    text-align: center;
  }

  /* Over the viewport's bottom, on the layer of the 3-second notes (spec 043);
     a tap or a click on it reaches the cell under it. */
  .over-grid {
    z-index: 6;
    pointer-events: none;
  }

  /* Each name in its player's ink, set on the element. */
  .authors-legend-name {
    font-weight: 700;
  }
</style>
