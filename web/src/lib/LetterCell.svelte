<script lang="ts">
  // One letter cell of the grid (spec 042, specs/_design/cells.md), drawn by
  // GridViewport.svelte. Its props are plain values, apart from the lists of
  // cursors and arrows, which keep their value while they do not change: a
  // frame that does not change what the cell draws does not draw it again
  // (client/foundation.md rule 8).
  //
  // The cell's marks, in the drawing order of spec 042: the letter, then the
  // flash overlay (under it, z-index -1), the dashes of a hyphen edge (over
  // the flash, under the letter), the catch-up ring (1), the revealed notch
  // (3), the other players' triangles or icons (2) and the arrows (6); last,
  // my selection border (7) and its dashed side along a hyphen edge.
  import { t } from './i18n'
  import { ARROW_GLYPHS, arrowSide, cellId, hyphenDrawings } from './gridLayout'
  import type { PlacedArrow } from './gridLayout'
  import HyphenEdge from './HyphenEdge.svelte'
  import PlayerIcon from './PlayerIcon.svelte'
  import type { Corner, DrawnCursor } from './remoteSelections'

  let {
    row,
    column,
    letter,
    isUnconfirmed,
    isPencil,
    author,
    finder,
    isAuthorsViewOn,
    isLocked,
    isRevealed,
    isWrong,
    flash,
    isCaughtUp,
    isSelected,
    isInWord,
    tintedBy,
    tintColour,
    isOthersTintOn,
    isAccessibilityOn,
    hyphenRight,
    hyphenBottom,
    hyphenLeft,
    hyphenTop,
    isRightSelected,
    isBelowSelected,
    cursors,
    arrows,
  }: {
    row: number
    column: number
    // The letter the cell shows, a pending edit's included; '' when empty.
    letter: string
    // True while the letter shown is a pending edit with no answer yet.
    isUnconfirmed: boolean
    // True while the letter shown is a pencil letter (spec 020).
    isPencil: boolean
    // The author's player id, '' when none.
    author: string
    // The colour index of the letter's finder (spec 045), as text; '' when it
    // has none or while the Auteurs mode is off.
    finder: string
    isAuthorsViewOn: boolean
    isLocked: boolean
    // True when a reveal locked the cell (spec 024).
    isRevealed: boolean
    // True while the letter shown was found wrong by the last check of it.
    isWrong: boolean
    // The colour index of the cell's flash, as text; '' while it does not
    // flash.
    flash: string
    // True while a catch-up highlights the cell (spec 034).
    isCaughtUp: boolean
    // True on my selected cell.
    isSelected: boolean
    // True on the cells of my selected word.
    isInWord: boolean
    // The ids of the players whose word holds the cell, separated by spaces.
    tintedBy: string
    // The colour index of the first of them; null when no word of theirs
    // holds it.
    tintColour: number | null
    isOthersTintOn: boolean
    isAccessibilityOn: boolean
    // The hyphen edges that touch the cell (gameplay/viewport.md rule 5).
    hyphenRight: boolean
    hyphenBottom: boolean
    hyphenLeft: boolean
    hyphenTop: boolean
    // True when my selected cell is the one right of this cell, or below it.
    isRightSelected: boolean
    isBelowSelected: boolean
    // The other players' cursors on the cell, in roster order.
    cursors: DrawnCursor[]
    // The arrows of the clues whose word starts in the cell.
    arrows: PlacedArrow[]
  } = $props()

  // The triangle of another player in each corner of a cell: a right triangle
  // in a 10 by 10 box, its legs along the corner's two edges.
  const TRIANGLE_POINTS: Record<Corner, string> = {
    'top-left': '0,0 10,0 0,10',
    'top-right': '0,0 10,0 10,10',
    'bottom-right': '10,0 10,10 0,10',
    'bottom-left': '0,0 10,10 0,10',
  }

  // What the cell draws for the hyphen edges that touch it. What depends on
  // the cell size is set on the grid (GridViewport's hyphenStyle).
  let edges = $derived(
    hyphenDrawings(
      { right: hyphenRight, bottom: hyphenBottom, left: hyphenLeft, top: hyphenTop },
      isSelected,
      isRightSelected,
      isBelowSelected,
    ),
  )

  // The colour of the letter while the Auteurs mode is on: its finder's ink,
  // or ink when it has no finder; null while the mode is off, so that the
  // cell's own rules (pencil grey, ink) apply.
  let finderInk = $derived(letterColourOf(finder))

  function letterColourOf(finderColour: string): string | null {
    if (!isAuthorsViewOn) {
      return null
    }
    if (finderColour === '') {
      return 'var(--nock-ink)'
    }
    return `var(--player-ink-${finderColour})`
  }
</script>

<div
  class="cell letter"
  class:locked={isLocked}
  data-testid="cell"
  data-row={row}
  data-column={column}
  data-type="letter"
  role="gridcell"
  id={cellId(row, column)}
  aria-selected={isSelected}
  data-letter={letter}
  data-unconfirmed={String(isUnconfirmed)}
  data-pencil={String(isPencil)}
  data-author={author}
  data-author-colour={finder}
  data-locked={String(isLocked)}
  data-revealed={String(isRevealed)}
  data-wrong={String(isWrong)}
  data-flash={flash}
  data-caught-up={String(isCaughtUp)}
  data-selected={String(isSelected)}
  data-in-word={String(isInWord)}
  data-tinted-by={tintedBy}
  class:selected={isSelected}
  class:in-word={isInWord}
  class:tinted={tintColour !== null && isOthersTintOn}
  class:hyphen-right={hyphenRight}
  class:hyphen-bottom={hyphenBottom}
  style:--tint={tintColour === null ? null : `var(--player-colour-${tintColour})`}
  style:--finder-ink={finderInk}
  style:grid-row={row + 1}
  style:grid-column={column + 1}
>{#if letter !== ''}<span class="cell-letter" data-testid="cell-letter">{letter}</span
    >{/if}{#if flash !== ''}<span
      class="cell-flash"
      data-testid="cell-flash"
      aria-hidden="true"
      style:background-color={`var(--player-colour-${flash})`}
    ></span>{/if}{#each edges as edge (`${edge.side} ${edge.kind}`)}{#if edge.kind === 'hyphen'}<HyphenEdge drawing={edge} />{/if}{/each}{#if hyphenRight && hyphenBottom}<span
      class="hyphen-corner"
      aria-hidden="true"
    ></span>{/if}{#if isCaughtUp}<span
      class="catch-up-mark"
      data-testid="catch-up-mark"
      aria-hidden="true"
    ></span>{/if}{#if isRevealed}<span
      class="reveal-mark nock-reveal-notch"
      data-testid="reveal-mark"
      aria-hidden="true"
    ></span><span class="visually-hidden" data-testid="reveal-label"
      >{t('a11y.revealed')}</span
    >{/if}{#each cursors as cursor (cursor.playerId)}<span
      class="remote-selection"
      data-testid="remote-selection"
      data-player-id={cursor.playerId}
      data-colour={String(cursor.colour)}
      data-corner={cursor.corner}
      data-shape={isAccessibilityOn ? 'icon' : 'triangle'}
      aria-hidden="true"
      >{#if isAccessibilityOn}<PlayerIcon colour={cursor.colour} />{:else}<svg
          class="triangle"
          viewBox="0 0 10 10"
          preserveAspectRatio="none"
          aria-hidden="true"
          ><polygon
            points={TRIANGLE_POINTS[cursor.corner]}
            style:fill={`var(--player-colour-${cursor.colour})`}
          /></svg
        >{/if}</span
    >{/each}{#each arrows as placed (`${placed.clueRow},${placed.clueColumn},${placed.clueIndex}`)}<svg
      class="clue-arrow {placed.place}"
      data-testid="clue-arrow"
      data-arrow={placed.arrow}
      data-side={arrowSide(placed.arrow)}
      data-clue-row={placed.clueRow}
      data-clue-column={placed.clueColumn}
      data-clue-index={placed.clueIndex}
      aria-hidden="true"
      viewBox="0 0 24 24"
      ><g class="halo"
        ><path d={ARROW_GLYPHS[placed.arrow].path} /><polygon
          points={ARROW_GLYPHS[placed.arrow].head}
        /></g
      ><path d={ARROW_GLYPHS[placed.arrow].path} /><polygon
        points={ARROW_GLYPHS[placed.arrow].head}
      /></svg
    >{/each}{#if isSelected}<span
      class="cell-selection"
      data-testid="cell-selection"
      aria-hidden="true"
    ></span>{/if}{#each edges as edge (`${edge.side} ${edge.kind}`)}{#if edge.kind === 'band'}<HyphenEdge drawing={edge} />{/if}{/each}</div>

<style>
  /* Every cell of the grid draws its own right and bottom grid line (spec
     042); GridViewport.svelte and ClueCell.svelte hold the same rule for
     theirs. */
  .cell {
    box-sizing: border-box;
    min-width: 0;
    min-height: 0;
    border-right: 1px solid var(--nock-rule);
    border-bottom: 1px solid var(--nock-rule);
    background: var(--nock-white);
  }

  /* A letter cell is a stacking context of its own (isolation), so the
     z-index of its marks orders them inside the cell only, and never against
     the rest of the page (the vote banner). It clips its marks, and holds the
     letter's font, which `cell-letter` inherits (spec 042). */
  .letter {
    --line-right: 0px;
    --line-bottom: 0px;
    position: relative;
    isolation: isolate;
    overflow: hidden;
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: var(--nock-font-ui);
    font-size: calc(var(--cell) * 0.56);
    font-weight: 500;
    line-height: 1;
    color: var(--nock-ink);
    text-transform: uppercase;
  }

  /* A hyphen edge (gameplay/viewport.md rule 5): the cell's own grid line along
     it is taken away, and the dashes of HyphenEdge.svelte are drawn in its
     place. The 1px padding keeps the letter where it was, and --line-right and
     --line-bottom keep the marks drawn against the cell's sides where they
     were, off the line's pixel. The line across the edge's end stays plain:
     the cell's other line runs to the corner, or, when both of its lines are
     hyphen edges, the corner pixel is drawn in rule grey. */
  .letter.hyphen-right {
    --line-right: 1px;
    border-right-width: 0;
    padding-right: 1px;
  }

  .letter.hyphen-bottom {
    --line-bottom: 1px;
    border-bottom-width: 0;
    padding-bottom: 1px;
  }

  .hyphen-corner {
    position: absolute;
    right: 0;
    bottom: 0;
    z-index: -1;
    width: 1px;
    height: 1px;
    background: var(--nock-rule);
    pointer-events: none;
  }

  /* The capital is centred on its own cap height and baseline, not on the line
     box. An engine without text-box centres the line box. */
  .cell-letter {
    text-box: trim-both cap alphabetic;
  }

  /* A letter found wrong by a check: struck through in red, drawn through the
     letter that the cell holds. */
  .letter[data-wrong='true'] {
    text-decoration-line: line-through;
    text-decoration-thickness: max(2px, 0.07em);
    text-decoration-color: var(--nock-red);
  }

  /* A pencil letter (spec 020): in italics, the sign that does not rely on
     colour, and in the pencil grey. While the cell flashes, a pencil letter
     takes the ink like a normal letter (the data-flash rule below) and its
     italics alone mark it (spec 020 decision 12). */
  .letter[data-pencil='true'] {
    font-style: italic;
    color: var(--nock-pencil);
  }

  /* The backgrounds of a letter cell (spec 042): exactly one applies, the
     first that matches in this order: flash, my selected cell, locked, my
     word, another player's word, white. The rules below come in the reverse
     order and have the same specificity, so the later one wins. */

  /* The word of another player, while « Mots des autres » is on: their colour
     at 16 % over white. */
  .letter.tinted {
    background: color-mix(in srgb, var(--tint) 16%, var(--nock-white));
  }

  .letter.in-word {
    background: var(--nock-word);
  }

  /* Checked right, or revealed: locked grey and a bold letter (spec 035). */
  .letter.locked {
    background: var(--nock-locked);
    font-weight: 700;
  }

  /* My cell: the selected blue, with a 2px navy border drawn inside it. The
     cell's own outline is that border for spec 035 AC-2, but the engines paint
     it under the cell's marks; the cell-selection element below draws it again
     over every mark of the cell. */
  .letter.selected {
    background: var(--nock-selected);
    outline: 2px solid var(--nock-navy);
    outline-offset: -2px;
  }

  /* My selection border as the top layer of the cell (spec 042, decision 10):
     on the cell's padding box, over the arrows (6) and every other mark. */
  .cell-selection {
    position: absolute;
    inset: 0 var(--line-right) var(--line-bottom) 0;
    z-index: 7;
    box-sizing: border-box;
    border: 2px solid var(--nock-navy);
    pointer-events: none;
  }

  /* A flashing cell (spec 016): the cell turns white and its letter ink; the
     cell-flash element below lays the replacer's colour at 38 % over the
     white. A pencil letter takes the ink too (spec 020 decision 12). */
  .letter:not([data-flash='']) {
    background: var(--nock-white);
    color: var(--nock-ink);
  }

  /* The replacer's colour, set on the element. Its negative z-index paints it
     over the cell's background and under the letter and the marks, inside the
     cell's own stacking context (isolation on .letter). */
  .cell-flash {
    position: absolute;
    inset: 0;
    z-index: -1;
    opacity: 0.38;
    pointer-events: none;
  }

  /* A cell changed while the page was away (spec 034): a 3px ink ring on the
     cell's inner edge, under the other marks. */
  .catch-up-mark {
    position: absolute;
    inset: 0 var(--line-right) var(--line-bottom) 0;
    z-index: 1;
    box-sizing: border-box;
    border: 3px solid var(--nock-ink);
    pointer-events: none;
  }

  /* The Auteurs mode (spec 045): each letter in its finder's ink, or ink when
     it has no finder (--finder-ink, set on the cell), on every background of
     the cell, the flash included. It replaces the pencil grey (the italics
     stay) and the ink of a flash. The strike of a wrong letter turns ink, so
     that it still shows on a red letter. The grid (GridViewport.svelte) has
     the authors-view class while the mode is on. */
  :global(.grid.authors-view) .letter {
    color: var(--finder-ink);
  }

  :global(.grid.authors-view) .letter[data-wrong='true'] {
    text-decoration-color: var(--nock-ink);
  }

  /* A revealed letter (spec 024, spec 042): the orange-red notch of app.css
     (nock-reveal-notch), drawn over the triangles and the ring. */
  .reveal-mark {
    z-index: 3;
    bottom: var(--line-bottom);
    left: calc((100% - var(--line-right)) / 2);
  }

  /* During a flash the notch is ink, which keeps 3:1 on every flash colour
     (spec 042, lead's decision 2). */
  .letter:not([data-flash='']) .reveal-mark {
    background-color: var(--nock-ink);
  }

  /* Another player on the cell (spec 042): a plain triangle of side --triangle
     in their colour, in the corner they took when they arrived. With
     « Accessibilité » on, their icon instead, smaller and set in from the
     corner. */
  .remote-selection {
    --inset: 0px;
    position: absolute;
    z-index: 2;
    width: var(--triangle);
    height: var(--triangle);
    pointer-events: none;
  }

  .remote-selection[data-shape='icon'] {
    --inset: max(1px, calc(var(--cell) * 0.04));
    width: max(6px, calc(var(--cell) * 0.24));
    height: max(6px, calc(var(--cell) * 0.24));
  }

  .remote-selection[data-corner='top-left'] {
    top: var(--inset);
    left: var(--inset);
  }

  .remote-selection[data-corner='top-right'] {
    top: var(--inset);
    right: calc(var(--inset) + var(--line-right));
  }

  .remote-selection[data-corner='bottom-right'] {
    bottom: calc(var(--inset) + var(--line-bottom));
    right: calc(var(--inset) + var(--line-right));
  }

  .remote-selection[data-corner='bottom-left'] {
    bottom: calc(var(--inset) + var(--line-bottom));
    left: var(--inset);
  }

  /* A triangle is a triangle for the pointer too: its box is clipped to the
     drawn shape, so a point of the box outside the shape reaches what is under
     it (the cell). */
  .remote-selection[data-shape='triangle'][data-corner='top-left'] {
    clip-path: polygon(0% 0%, 100% 0%, 0% 100%);
  }

  .remote-selection[data-shape='triangle'][data-corner='top-right'] {
    clip-path: polygon(0% 0%, 100% 0%, 100% 100%);
  }

  .remote-selection[data-shape='triangle'][data-corner='bottom-right'] {
    clip-path: polygon(100% 0%, 100% 100%, 0% 100%);
  }

  .remote-selection[data-shape='triangle'][data-corner='bottom-left'] {
    clip-path: polygon(0% 0%, 100% 100%, 0% 100%);
  }

  .triangle {
    display: block;
    width: 100%;
    height: 100%;
  }

  .triangle polygon {
    stroke: none;
  }

  /* A direction arrow (spec 042), in the letter cell where its word starts:
     a box of side --arrow whose edge at -1px lies on the grid line, over every
     mark of the cell but my selection border. */
  .clue-arrow {
    --arrow: max(9px, calc(var(--cell) * 0.26));
    position: absolute;
    z-index: 6;
    width: var(--arrow);
    height: var(--arrow);
    pointer-events: none;
  }

  .clue-arrow path {
    fill: none;
    stroke: var(--nock-ink);
    stroke-width: 2.4;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .clue-arrow polygon {
    fill: var(--nock-ink);
  }

  /* The thin white halo (_design/cells.md « Direction arrows »): the same path
     and head drawn first, under the ink, in white and wider, so 1.2 units of
     white border every ink edge. Drawn, never a CSS filter. */
  .clue-arrow .halo path {
    stroke: var(--nock-white);
    stroke-width: 4.8;
  }

  .clue-arrow .halo polygon {
    fill: var(--nock-white);
    stroke: var(--nock-white);
    stroke-width: 2.4;
    stroke-linejoin: round;
  }

  /* The places of gridLayout.ts (ArrowPlace). */
  .clue-arrow.right {
    left: -1px;
    top: calc(var(--cell) * 0.5 - var(--arrow) / 2);
  }

  .clue-arrow.right-high {
    left: -1px;
    top: calc(var(--cell) * 0.25 - var(--arrow) / 2);
  }

  .clue-arrow.right-low {
    left: -1px;
    top: calc(var(--cell) * 0.72 - var(--arrow) / 2);
  }

  .clue-arrow.down {
    top: -1px;
    left: calc(var(--cell) * 0.5 - var(--arrow) / 2);
  }

  .clue-arrow.down-then-right {
    top: -1px;
    left: calc(var(--cell) * 0.06);
  }

  .clue-arrow.down-then-right-moved {
    top: -1px;
    left: calc(var(--cell) * 0.4);
  }

  .clue-arrow.right-then-down {
    left: -1px;
    top: calc(var(--cell) * 0.06);
  }
</style>
