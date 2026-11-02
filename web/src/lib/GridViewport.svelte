<script lang="ts">
  import { untrack } from 'svelte'
  import { t } from './i18n'
  import {
    GRID_LINE_PX,
    ZOOM_MAX,
    ZOOM_MIN,
    arrowsByCell,
    cellId,
    dashesImage,
    fitCellSize,
    hyphenDashes,
    hyphenThickness,
    hyphenWidthAfter,
    hyphenWidthBefore,
    hyphensByCell,
    scrollShowingCell,
    triangleSide,
  } from './gridLayout'
  import type { CellHyphens, PlacedArrow, ScrollAxis } from './gridLayout'
  import ClueCell from './ClueCell.svelte'
  import LetterCell from './LetterCell.svelte'
  import { pinchPan } from './pinchPan'
  import type { PinchPanZoom } from './pinchPan'
  import { gridKeyAction, announcementOf } from './gridKeys'
  import { legendMargins } from './legendLayout'
  import { finderColour } from './authorsView'
  import type { LegendName } from './authorsView'
  import AuthorsLegend from './AuthorsLegend.svelte'
  import { selectionAfterArrow, selectionAfterTab } from './navigation'
  import type { ArrowKey } from './navigation'
  import { latestPendingEdits, shownCellWith, shownGrid } from './roomSession'
  import type {
    CaughtUpCell,
    CellFlash,
    GridView,
    LetterCellView,
    PendingEdit,
  } from './roomSession'
  import { positionKey, wordKey } from './wordSelection'
  import type { Selection, Word } from './wordSelection'
  import { NO_REMOTES, remotesByCell } from './remoteSelections'
  import type { CellRemotes, RemoteSelection } from './remoteSelections'
  import type { ClueFlagMarker } from './clueFlags'
  import type { ClueReactionMarker } from './chat'

  let {
    grid,
    words,
    selection,
    activeWord,
    onCellTap,
    onClueTap,
    onSelect,
    onLetter,
    onErase,
    onUndo,
    pendingEdits,
    flashes,
    caughtUpCells,
    remoteSelections,
    isAuthorsViewOn,
    isOthersTintOn,
    isAccessibilityOn,
    playerColours,
    legendNames,
    legendRoom,
    isLegendOverGrid,
    legendMaxWidth,
    legendHeight = $bindable(0),
    clueFlags,
    clueReactions,
  }: {
    grid: GridView
    words: Word[]
    selection: Selection | null
    activeWord: Word | null
    onCellTap: (row: number, column: number) => void
    onClueTap: (word: Word) => void
    onSelect: (next: Selection) => void
    onLetter: (letter: string) => void
    onErase: () => void
    // Control+z or Meta+z; absent: those keys are left to the browser.
    onUndo?: () => void
    pendingEdits: PendingEdit[]
    flashes: CellFlash[]
    // The cells a catch-up highlights, as changed while the page was away (spec
    // 034).
    caughtUpCells: CaughtUpCell[]
    // The other players' selections, in roster order (spec 013), each with the
    // corner it holds on its cell (spec 042).
    remoteSelections: RemoteSelection[]
    // The Auteurs mode of spec 045: true while its switch is on.
    isAuthorsViewOn: boolean
    // « Mots des autres » (spec 042): true while the other players' words are
    // tinted.
    isOthersTintOn: boolean
    // « Accessibilité » (spec 042): true while the other players' cursors are
    // their icons rather than plain triangles.
    isAccessibilityOn: boolean
    // The colour index of each player of the kept snapshot, by player id.
    playerColours: Map<string, number>
    // The names the Auteurs legend shows while the mode is on.
    legendNames: LegendName[]
    // The height the grid gives the legend under it while the mode is on, in
    // px; 0 while it is off, or while the legend lies over the grid.
    legendRoom: number
    // True while the legend lies over the viewport's bottom, taking no room
    // (spec 045, decision 8).
    isLegendOverGrid: boolean
    // The legend's largest width in px: the clue bar's width in the column
    // layout (spec 045, decision 9); null in the sheet layout, where the grid
    // area's content box, narrower than the clue bar, limits it.
    legendMaxWidth: number | null
    // The legend's height as drawn, in px, for the room page.
    legendHeight?: number
    // The marker of each flagged clue, by clue key "row,column,clue_index"
    // (spec 021). A clue nobody flagged has no entry.
    clueFlags: Map<string, ClueFlagMarker>
    // The reaction each clue shows, by clue key "row,column,clue_index" (spec
    // 022). A clue that shows no reaction has no entry.
    clueReactions: Map<string, ClueReactionMarker>
  } = $props()

  // The colour index of a letter cell's finder (see finderColour), or '' while
  // the Auteurs mode is off: then no cell has a finder.
  function finderOf(cell: LetterCellView): string {
    if (!isAuthorsViewOn) {
      return ''
    }
    return finderColour(cell, playerColours)
  }

  // What a frame redraws (client/foundation.md rule 8): each letter cell reads
  // what it draws from the maps below, by its "row,column", and is given it as
  // plain values (LetterCell.svelte); a cell whose values stay the same does
  // not draw again. A cell with nothing to draw finds no entry, and takes one
  // shared empty value.

  // What the other players draw on each cell. The map before is kept, so that
  // a cell they did not change keeps its value (see remotesByCell).
  let previousRemotes = new Map<string, CellRemotes>()
  let remotesOfCells = $derived.by(() => {
    const next = remotesByCell(remoteSelections, previousRemotes)
    previousRemotes = next
    return next
  })

  // The colour index of the flash of each flashing cell, as text.
  let flashOfCells = $derived(flashColoursByCell(flashes))

  function flashColoursByCell(cellFlashes: CellFlash[]): Map<string, string> {
    const colours = new Map<string, string>()
    for (const flash of cellFlashes) {
      colours.set(positionKey(flash.row, flash.column), String(flash.colour))
    }
    return colours
  }

  // The cells a catch-up highlights (spec 034).
  let caughtUpKeys = $derived(caughtUpKeysOf(caughtUpCells))

  function caughtUpKeysOf(cells: CaughtUpCell[]): Set<string> {
    const keys = new Set<string>()
    for (const cell of cells) {
      keys.add(positionKey(cell.row, cell.column))
    }
    return keys
  }

  // The newest pending edit of each cell.
  let latestEdits = $derived(latestPendingEdits(pendingEdits))

  // The arrows drawn in a letter cell: those of the clues whose word starts
  // there (spec 042).
  function arrowsIn(row: number, column: number): PlacedArrow[] {
    return arrowsOfCells.get(positionKey(row, column)) ?? []
  }

  // The hyphen edges that touch a letter cell (gameplay/viewport.md rule 5),
  // or null when it touches none.
  function hyphensOn(row: number, column: number): CellHyphens | null {
    return hyphensOfCells.get(positionKey(row, column)) ?? null
  }

  let gridElement: HTMLDivElement | undefined = $state()

  let arrowsOfCells = $derived(arrowsByCell(grid))
  let hyphensOfCells = $derived(hyphensByCell(grid))

  // The cells of each row, in column order: the grid is drawn row by row.
  let rows = $derived(rowsOf(grid))

  function rowsOf(view: GridView): GridView['cells'][number][][] {
    const result: GridView['cells'][number][][] = []
    for (let row = 0; row < view.height; row += 1) {
      result.push([])
    }
    for (const cell of view.cells) {
      result[cell.row].push(cell)
    }
    for (const rowCells of result) {
      rowCells.sort((first, second) => first.column - second.column)
    }
    return result
  }

  // What a screen reader says when the selection moves (spec 035).
  let announcement = $derived(announcementOf(selection, activeWord))

  // After Escape, the next Tab or Shift+Tab leaves the grid (spec 035).
  let isReleased = false
  let activeKey = $derived(activeWord === null ? '' : wordKey(activeWord))
  let wordPositions = $derived(
    new Set((activeWord?.cells ?? []).map((cell) => positionKey(cell.row, cell.column))),
  )

  function isSelected(row: number, column: number): boolean {
    return selection !== null && selection.row === row && selection.column === column
  }

  // The index of the clue of my selected word in the clue cell at (row,
  // column), or null when that clue is not in this cell.
  function activeClueIndexIn(row: number, column: number): number | null {
    if (activeWord === null || activeWord.clueRow !== row || activeWord.clueColumn !== column) {
      return null
    }
    return activeWord.clueIndex
  }

  // One handler for the whole grid: find the cell or the clue that was tapped.
  function onGridClick(event: MouseEvent): void {
    if (!(event.target instanceof Element)) {
      return
    }
    const clueElement = event.target.closest('[data-testid="clue"]')
    const cellElement = event.target.closest('[data-testid="cell"]')
    if (cellElement === null) {
      return
    }
    const row = Number(cellElement.getAttribute('data-row'))
    const column = Number(cellElement.getAttribute('data-column'))
    if (clueElement !== null) {
      const clueIndex = Number(clueElement.getAttribute('data-clue-index'))
      const key = `${row},${column},${clueIndex}`
      const word = words.find((candidate) => wordKey(candidate) === key)
      if (word !== undefined) {
        onClueTap(word)
        gridElement?.focus()
      }
    } else if (cellElement.getAttribute('data-type') === 'letter') {
      tappedCellKey = positionKey(row, column)
      onCellTap(row, column)
      gridElement?.focus()
    }
  }

  let viewport: HTMLDivElement | undefined = $state()
  let areaWidth = $state(0)
  let areaHeight = $state(0)
  // The viewport's height as drawn, not rounded: where the grid's box ends in
  // it (the Auteurs legend sits under that).
  let viewportHeight = $state(0)
  let zoom = $state(ZOOM_MIN)

  let fitSize = $derived(fitCellSize(areaWidth, areaHeight, grid.width, grid.height))
  let cellSize = $derived(fitSize * zoom)
  // The dashes of every hyphen edge at the current cell size, as « Hyphen
  // edges » gives them, and their thickness. They are set on the grid, as
  // variables HyphenEdge.svelte reads, so that a pinch changes no cell's
  // drawing (client/foundation.md rule 8).
  let hyphenStyle = $derived(hyphenStyleOf(cellSize))

  interface HyphenStyle {
    widthBefore: string
    widthAfter: string
    dashesDown: string
    dashesAcross: string
    bandDashesDown: string
    bandDashesAcross: string
  }

  function hyphenStyleOf(side: number): HyphenStyle {
    const dashes = hyphenDashes(side)
    const thickness = hyphenThickness(side)
    return {
      widthBefore: `${hyphenWidthBefore(thickness)}px`,
      widthAfter: `${hyphenWidthAfter(thickness)}px`,
      dashesDown: dashesImage(dashes, 'to bottom', 'var(--nock-hyphen)'),
      dashesAcross: dashesImage(dashes, 'to right', 'var(--nock-hyphen)'),
      bandDashesDown: dashesImage(dashes, 'to bottom', 'var(--nock-navy)'),
      bandDashesAcross: dashesImage(dashes, 'to right', 'var(--nock-navy)'),
    }
  }

  // The exact size of the viewport, rounded down. clientWidth and clientHeight
  // round to the nearest pixel, sometimes up, and a grid fitted to them then
  // overflows the viewport by a fraction of a pixel: Firefox makes such a
  // viewport a Tab stop between the vote banner and the grid (spec 025 AC-8).
  // The room page also calls it when it changes the play area itself, so the
  // grid refits at once (spec 043).
  export function measureViewport(): void {
    if (viewport !== undefined) {
      const box = viewport.getBoundingClientRect()
      areaWidth = Math.floor(box.width)
      areaHeight = Math.floor(box.height)
      viewportHeight = box.height
    }
  }

  // ---- The Auteurs legend (spec 045) ----

  // The legend is in the flow right under the viewport; legendLayout.ts works
  // its margins out so that they and its height add up to legendRoom, the
  // height the viewport gives it.
  let gridHeight = $derived(cellSize * grid.height + GRID_LINE_PX)
  let legendMarginsNow = $derived(
    legendMargins({
      isOverGrid: isLegendOverGrid,
      legendHeight,
      legendRoom,
      viewportHeight,
      gridHeight,
    }),
  )
  let legendMarginTop = $derived(legendMarginsNow.marginTop)
  let legendMarginBottom = $derived(legendMarginsNow.marginBottom)

  // Follow the size of the viewport (the area the grid must fit in at zoom 1).
  $effect(() => {
    const element = viewport
    if (element === undefined) {
      return
    }
    measureViewport()
    const observer = new ResizeObserver(measureViewport)
    observer.observe(element)
    return () => observer.disconnect()
  })

  // The viewport element: the reaction picker floats over its bottom (spec 043).
  export function viewportElement(): HTMLElement | null {
    return viewport ?? null
  }

  // Put the focus back on the grid (the in-app keyboard uses it).
  export function focusGrid(): void {
    gridElement?.focus({ preventScroll: true })
  }

  // Arrow keys move the selection to the next letter cell (spec 009).
  function onArrowKey(key: ArrowKey): void {
    if (selection === null) {
      return
    }
    const next = selectionAfterArrow(grid, words, selection, key)
    if (next !== null) {
      onSelect(next)
    }
  }

  // Tab and Shift+Tab select the next or previous unfinished word (spec 009).
  function onTabKey(shiftKey: boolean): void {
    const next = selectionAfterTab(shownGrid(grid, pendingEdits), words, selection, shiftKey ? -1 : 1)
    if (next !== null) {
      onSelect(next)
    }
  }

  function onGridFocusChange(): void {
    isReleased = false
  }

  // The browser's Tab or Shift+Tab that leaves the grid starts from the grid.
  // WebKit starts it from the node last clicked, a cell or a clue inside the
  // grid, so Shift+Tab found the grid itself and the focus stayed there (spec
  // 021 AC-10 selects a word with a tap first). Focusing the grid anew makes
  // the grid the starting point in every engine.
  function startTabNavigationFromGrid(): void {
    if (gridElement === undefined) {
      return
    }
    gridElement.blur()
    gridElement.focus({ preventScroll: true })
  }

  // Navigation keys (spec 009), then letter keys and Backspace (spec 008).
  function onGridKeydown(event: KeyboardEvent): void {
    const action = gridKeyAction(event, isReleased, selection !== null, onUndo !== undefined)
    // A modifier key alone keeps a release; any other key ends or sets it.
    if (action.kind === 'modifier') {
      return
    }
    isReleased = action.kind === 'release'
    if (action.kind === 'leaveGrid') {
      startTabNavigationFromGrid()
    } else if (action.kind === 'undo') {
      event.preventDefault()
      onUndo?.()
    } else if (action.kind === 'tab') {
      event.preventDefault()
      onTabKey(action.step === -1)
    } else if (action.kind === 'arrow') {
      event.preventDefault()
      onArrowKey(action.key)
    } else if (action.kind === 'letter') {
      event.preventDefault()
      onLetter(action.letter)
    } else if (action.kind === 'erase') {
      event.preventDefault()
      onErase()
    } else if (action.kind === 'swallow') {
      event.preventDefault()
    }
  }

  // Taps and clicks on the grid select a word; keys on the focused grid type.
  $effect(() => {
    const element = gridElement
    if (element === undefined) {
      return
    }
    element.addEventListener('click', onGridClick)
    element.addEventListener('keydown', onGridKeydown)
    element.addEventListener('focus', onGridFocusChange)
    element.addEventListener('blur', onGridFocusChange)
    return () => {
      element.removeEventListener('focus', onGridFocusChange)
      element.removeEventListener('blur', onGridFocusChange)
      element.removeEventListener('click', onGridClick)
      element.removeEventListener('keydown', onGridKeydown)
    }
  })

  // Touch gestures (pinchPan.ts): one finger pans, two fingers pinch.
  const pinchZoom: PinchPanZoom = {
    zoom: () => zoom,
    cellSize: () => cellSize,
    setZoom: (newZoom: number) => {
      zoom = newZoom
    },
  }

  // ---- Following the selection while zoomed (viewport rule 3) ----

  // The cell of the last tap on a letter cell: the selection it makes is in
  // view already and must not scroll. Plain, not state: only the effect below
  // reads it.
  let tappedCellKey: string | null = null
  let selectedCellKey = $derived(
    selection === null ? null : positionKey(selection.row, selection.column),
  )

  // Only a change of selected cell scrolls: everything else the scroll reads
  // (zoom, sizes, direction) is untracked, so a pinch, a pan, a resize or a
  // refit never brings the selected cell back.
  $effect(() => {
    const key = selectedCellKey
    untrack(() => followSelectedCell(key))
  })

  function followSelectedCell(key: string | null): void {
    const isFromCellTap = key !== null && key === tappedCellKey
    tappedCellKey = null
    if (key === null || isFromCellTap || zoom <= ZOOM_MIN || selection === null) {
      return
    }
    const cellElement = document.getElementById(cellId(selection.row, selection.column))
    if (viewport === undefined || gridElement === undefined || cellElement === null) {
      return
    }
    const viewBox = viewport.getBoundingClientRect()
    const cellBox = cellElement.getBoundingClientRect()
    const gridBox = gridElement.getBoundingClientRect()
    const across = axisOf(
      viewport.scrollLeft,
      viewBox.left,
      viewBox.width,
      cellBox.left,
      cellBox.width,
      gridBox.left,
      gridBox.right,
    )
    const down = axisOf(
      viewport.scrollTop,
      viewBox.top,
      viewBox.height,
      cellBox.top,
      cellBox.height,
      gridBox.top,
      gridBox.bottom,
    )
    const left = scrollShowingCell(across)
    const top = scrollShowingCell(down)
    // At once: an explicit 'instant' overrides any smooth scroll-behavior.
    viewport.scrollTo({ left, top, behavior: 'instant' })
  }

  // One axis of the viewport, from boxes on screen to positions in what it
  // scrolls: a point at `screen` px is at `screen - viewStart + scroll`.
  function axisOf(
    scroll: number,
    viewStart: number,
    viewSide: number,
    cellStart: number,
    cellSide: number,
    gridStart: number,
    gridEnd: number,
  ): ScrollAxis {
    const offset = scroll - viewStart
    return {
      scroll,
      viewSide,
      cellStart: cellStart + offset,
      cellSide,
      gridStart: gridStart + offset,
      gridEnd: gridEnd + offset,
    }
  }
</script>

<div
  class="viewport"
  data-testid="grid-viewport"
  data-zoom={String(zoom)}
  data-zoom-min={String(ZOOM_MIN)}
  data-zoom-max={String(ZOOM_MAX)}
  bind:this={viewport}
  use:pinchPan={pinchZoom}
>
  <div
    class="grid"
    data-testid="grid"
    data-width={String(grid.width)}
    data-height={String(grid.height)}
    aria-label={t('grid.label')}
    role="grid"
    tabindex="0"
    aria-describedby="grid-hint"
    aria-activedescendant={selection === null
      ? undefined
      : cellId(selection.row, selection.column)}
    bind:this={gridElement}
    data-selected-row={selection === null ? '' : String(selection.row)}
    data-selected-column={selection === null ? '' : String(selection.column)}
    data-direction={selection === null ? '' : selection.direction}
    data-word={activeKey}
    class:authors-view={isAuthorsViewOn}
    style:--cell="{cellSize}px"
    style:--triangle="{triangleSide(cellSize)}px"
    style:--hyphen-width-before={hyphenStyle.widthBefore}
    style:--hyphen-width-after={hyphenStyle.widthAfter}
    style:--hyphen-dashes-down={hyphenStyle.dashesDown}
    style:--hyphen-dashes-across={hyphenStyle.dashesAcross}
    style:--band-dashes-down={hyphenStyle.bandDashesDown}
    style:--band-dashes-across={hyphenStyle.bandDashesAcross}
    style:grid-template-columns="repeat({grid.width}, var(--cell))"
    style:grid-auto-rows="var(--cell)"
  >
    {#each rows as rowCells, rowIndex (rowIndex)}
      <div class="row" data-testid="grid-row" role="row" data-row={rowIndex}>
        {#each rowCells as cell (cell.column)}
          {#if cell.type === 'letter'}
            {@const key = positionKey(cell.row, cell.column)}
            {@const latestEdit = latestEdits.get(key) ?? null}
            {@const shown = shownCellWith(cell, latestEdit)}
            {@const remotes = remotesOfCells.get(key) ?? NO_REMOTES}
            {@const hyphens = hyphensOn(cell.row, cell.column)}
            <LetterCell
              row={cell.row}
              column={cell.column}
              letter={shown.letter ?? ''}
              isUnconfirmed={shown.unconfirmed}
              isPencil={shown.pencil}
              author={cell.author ?? ''}
              finder={finderOf(cell)}
              {isAuthorsViewOn}
              isLocked={cell.locked}
              isRevealed={cell.revealed}
              isWrong={cell.wrong && !shown.unconfirmed}
              flash={flashOfCells.get(key) ?? ''}
              isCaughtUp={caughtUpKeys.has(key)}
              isSelected={isSelected(cell.row, cell.column)}
              isInWord={wordPositions.has(key)}
              tintedBy={remotes.tintedBy.join(' ')}
              tintColour={remotes.tintColour}
              {isOthersTintOn}
              {isAccessibilityOn}
              hyphenRight={hyphens?.right === true}
              hyphenBottom={hyphens?.bottom === true}
              hyphenLeft={hyphens?.left === true}
              hyphenTop={hyphens?.top === true}
              isRightSelected={isSelected(cell.row, cell.column + 1)}
              isBelowSelected={isSelected(cell.row + 1, cell.column)}
              cursors={remotes.cursors}
              arrows={arrowsIn(cell.row, cell.column)}
            />
          {:else if cell.type === 'clue'}
            <ClueCell
              row={cell.row}
              column={cell.column}
              clues={cell.clues}
              activeClueIndex={activeClueIndexIn(cell.row, cell.column)}
              {clueFlags}
              {clueReactions}
            />
          {:else}
            <div
              class="cell empty"
              data-testid="cell"
              data-row={cell.row}
              data-column={cell.column}
              data-type="empty"
              data-author-colour=""
              role="gridcell"
              id={cellId(cell.row, cell.column)}
              style:grid-row={cell.row + 1}
              style:grid-column={cell.column + 1}
            ></div>
          {/if}
        {/each}
      </div>
    {/each}
  </div>
</div>
{#if isAuthorsViewOn}
  <AuthorsLegend
    names={legendNames}
    marginTop={legendMarginTop}
    marginBottom={legendMarginBottom}
    isOverGrid={isLegendOverGrid}
    maxWidth={legendMaxWidth}
    bind:height={legendHeight}
  />
{/if}
<div
  class="visually-hidden"
  data-testid="grid-announcement"
  role="status"
  aria-live="polite"
  aria-atomic="true"
>{announcement}</div>
<div class="visually-hidden" id="grid-hint" data-testid="grid-hint">{t('a11y.grid_hint')}</div>

<style>
  /* The grid is centred in it while it fits (spec 043); zoomed past the
     viewport, its auto margins are 0 and it scrolls from its top left corner.
     A stacking context of its own (isolation), so the z-index of a reaction
     or a flag below orders it inside the grid only, and never against the rest
     of the page (the vote banner). */
  .viewport {
    width: 100%;
    flex: 1 1 0;
    min-height: 0;
    display: flex;
    overflow: auto;
    isolation: isolate;
    /* The app handles touch pan and pinch itself. */
    touch-action: none;
    scrollbar-width: none;
  }

  .viewport::-webkit-scrollbar {
    display: none;
  }

  /* The grid lines (spec 042): the grid draws the left and top line, each cell
     its own right and bottom line, so every line is one pixel wide. The grid
     clips at its outer edge: a long clue text may spill over the cells around
     it, never past the grid, so the grid that fits its viewport leaves nothing
     to scroll (spec 006). Every mark of a letter cell is already inside it. */
  .grid {
    position: relative;
    flex: none;
    display: grid;
    width: max-content;
    margin: auto;
    overflow: clip;
    border-left: 1px solid var(--nock-rule);
    border-top: 1px solid var(--nock-rule);
  }

  /* The rows only group the cells: the cells stay items of the CSS grid. */
  .row {
    display: contents;
  }

  /* An empty cell's grid lines; LetterCell.svelte and ClueCell.svelte hold the
     same rule for theirs. */
  .cell {
    box-sizing: border-box;
    min-width: 0;
    min-height: 0;
    border-right: 1px solid var(--nock-rule);
    border-bottom: 1px solid var(--nock-rule);
    background: var(--nock-white);
  }

  /* The focus outline stays inside the scrolling viewport. */
  .grid:focus-visible {
    outline-offset: -3px;
  }

  /* The same ring again, over the cells (foundation rule 7). The letter cells are
     positioned and opaque, so the engines paint them over the grid's own
     outline, which then shows only along the clue cells. This overlay covers
     the whole grid and is painted after the cells and their marks (layer 9,
     above a reaction's 8); it takes no pointer. It is a pseudo-element, so it
     is neither a child of the grid (which holds only its rows, spec 035 AC-5)
     nor in the accessibility tree. The grid keeps its own outline, which is
     what is read as its focus ring. An absolute box is placed against the
     grid's padding box, so the overlay reaches 1px out over the grid's left
     and top line to take the grid's border box: its ring lies on the same
     pixels as the grid's own. */
  .grid:focus-visible::after {
    content: '';
    position: absolute;
    inset: -1px 0 0 -1px;
    z-index: 9;
    pointer-events: none;
    outline: var(--focus-outline);
    outline-offset: -3px;
  }

  /* An empty cell: rule grey, holding nothing. */
  .empty {
    overflow: hidden;
    background: var(--nock-rule);
  }
</style>
