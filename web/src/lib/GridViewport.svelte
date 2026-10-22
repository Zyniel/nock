<script lang="ts">
  import { flushSync } from 'svelte'
  import { t } from './i18n'
  import {
    ARROW_GLYPHS,
    GRID_LINE_PX,
    ZOOM_MAX,
    ZOOM_MIN,
    arrowSide,
    arrowsByCell,
    clampZoom,
    distanceBetween,
    fitCellSize,
    triangleSide,
  } from './gridLayout'
  import type { PlacedArrow } from './gridLayout'
  import { actionForKey } from './letterEntry'
  import { LEGEND_GAP_PX, finderColour } from './authorsView'
  import type { LegendName } from './authorsView'
  import AuthorsLegend from './AuthorsLegend.svelte'
  import { ICONS } from './icons'
  import IconShapes from './IconShapes.svelte'
  import PlayerIcon from './PlayerIcon.svelte'
  import { isArrowKey, selectionAfterArrow, selectionAfterTab } from './navigation'
  import { shownCell, shownGrid } from './roomSession'
  import type {
    CaughtUpCell,
    CellFlash,
    GridView,
    LetterCellView,
    PendingEdit,
  } from './roomSession'
  import { positionKey, wordKey } from './wordSelection'
  import type { Position, Selection, Word } from './wordSelection'
  import type { Corner, RemoteSelection } from './remoteSelections'
  import type { ClueFlagMarker } from './clueFlags'
  import type { ClueReactionMarker } from './chat'

  interface Finger {
    clientX: number
    clientY: number
  }

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

  // The triangle of another player in each corner of a cell: a right triangle
  // in a 10 by 10 box, its legs along the corner's two edges.
  const TRIANGLE_POINTS: Record<Corner, string> = {
    'top-left': '0,0 10,0 0,10',
    'top-right': '0,0 10,0 10,10',
    'bottom-right': '10,0 10,10 0,10',
    'bottom-left': '0,0 10,10 0,10',
  }

  // A remote selection that holds a corner of its cell, the one drawn there.
  interface DrawnCursor {
    remote: RemoteSelection
    corner: Corner
  }

  // The colour index of a letter cell's finder (see finderColour), or '' while
  // the Auteurs mode is off: then no cell has a finder.
  function finderOf(cell: LetterCellView): string {
    if (!isAuthorsViewOn) {
      return ''
    }
    return finderColour(cell, playerColours)
  }

  // The colour of a letter while the Auteurs mode is on: its finder's ink, or
  // ink when it has no finder; null while the mode is off, so that the cell's
  // own rules (pencil grey, ink) apply.
  function letterColourOf(finder: string): string | null {
    if (!isAuthorsViewOn) {
      return null
    }
    if (finder === '') {
      return 'var(--nock-ink)'
    }
    return `var(--player-ink-${finder})`
  }

  // The DOM id of a cell, used by aria-activedescendant.
  function cellId(row: number, column: number): string {
    return `cell-${row}-${column}`
  }

  // The cursors drawn on a cell: the remote selections there that hold a
  // corner. A player who waits for a corner is not drawn.
  function cursorsOn(row: number, column: number): DrawnCursor[] {
    const drawn: DrawnCursor[] = []
    for (const remote of remoteSelections) {
      if (remote.row === row && remote.column === column && remote.corner !== null) {
        drawn.push({ remote, corner: remote.corner })
      }
    }
    return drawn
  }

  // The remote selections whose word holds a cell, in roster order.
  function tintsOn(row: number, column: number): RemoteSelection[] {
    const key = positionKey(row, column)
    return remoteSelections.filter((remote) => remote.wordPositions.has(key))
  }

  // The colour index of the flash on a cell, or '' when it does not flash.
  function flashOf(row: number, column: number): string {
    for (const flash of flashes) {
      if (flash.row === row && flash.column === column) {
        return String(flash.colour)
      }
    }
    return ''
  }

  // True while a catch-up highlights the cell (spec 034).
  function isCaughtUp(row: number, column: number): boolean {
    return caughtUpCells.some((cell) => cell.row === row && cell.column === column)
  }

  // The arrows drawn in a letter cell: those of the clues whose word starts
  // there (spec 042).
  function arrowsIn(row: number, column: number): PlacedArrow[] {
    return arrowsOfCells.get(positionKey(row, column)) ?? []
  }

  let gridElement: HTMLDivElement | undefined = $state()

  let arrowsOfCells = $derived(arrowsByCell(grid))

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

  function announcementOf(current: Selection | null, word: Word | null): string {
    if (current === null || word === null) {
      return ''
    }
    const direction = t(
      word.direction === 'across' ? 'a11y.direction.across' : 'a11y.direction.down',
    )
    if (word.cells.length === 1) {
      return t('a11y.announcement_one', { clue: word.text, direction })
    }
    const index = word.cells.findIndex(
      (cell: Position) => cell.row === current.row && cell.column === current.column,
    )
    if (index === -1) {
      return ''
    }
    return t('a11y.announcement', {
      clue: word.text,
      direction,
      length: word.cells.length,
      position: index + 1,
    })
  }

  // After Escape, the next Tab or Shift+Tab leaves the grid (spec 035).
  let isReleased = false
  let activeKey = $derived(activeWord === null ? '' : wordKey(activeWord))
  let wordPositions = $derived(
    new Set((activeWord?.cells ?? []).map((cell) => positionKey(cell.row, cell.column))),
  )

  function isSelected(row: number, column: number): boolean {
    return selection !== null && selection.row === row && selection.column === column
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

  // The legend is in the flow right under the viewport, and its margins and
  // height add up to legendRoom, the height the viewport gives it. Its top is
  // 8 px below the bottom of the part of the grid's box that shows: the grid
  // is centred in the viewport while it is shorter, so the room left under the
  // grid is taken back from the legend's top margin. While it lies over the
  // grid, its margins and height add up to nothing: it is pulled up over the
  // viewport's bottom, its bottom 8 px above it.
  //
  // That room is kept in quarter pixels, which every engine lays out exactly:
  // the two margins then add up to the same height as legendRoom, and the
  // viewport's height does not move by a fraction of a pixel at each frame
  // (its height sets the room under the grid, which sets the margins).
  let gridHeight = $derived(cellSize * grid.height + GRID_LINE_PX)
  let roomUnderGrid = $derived(quarterPixels(Math.max(0, (viewportHeight - gridHeight) / 2)))
  let legendMarginTop = $derived(
    isLegendOverGrid ? -(legendHeight + LEGEND_GAP_PX) : LEGEND_GAP_PX - roomUnderGrid,
  )
  let legendMarginBottom = $derived(
    isLegendOverGrid ? LEGEND_GAP_PX : legendRoom - legendHeight - LEGEND_GAP_PX + roomUnderGrid,
  )

  // A length in px, rounded down to a quarter of a pixel.
  function quarterPixels(length: number): number {
    return Math.floor(length * 4) / 4
  }

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
  function onArrowKey(key: string): void {
    if (selection === null || !isArrowKey(key)) {
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

  function isModifierKey(key: string): boolean {
    return key === 'Shift' || key === 'Control' || key === 'Alt' || key === 'Meta'
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
    if (isModifierKey(event.key)) {
      return
    }
    const wasReleased = isReleased
    isReleased = false
    const hasAnyModifier = event.ctrlKey || event.metaKey || event.altKey || event.shiftKey
    if (event.key === 'Escape' && !hasAnyModifier) {
      isReleased = true
      return
    }
    const isPlainTab = event.key === 'Tab' && !event.ctrlKey && !event.metaKey && !event.altKey
    if (isPlainTab && wasReleased) {
      startTabNavigationFromGrid()
      return
    }
    const isUndo =
      (event.ctrlKey || event.metaKey) &&
      !event.altKey &&
      !event.shiftKey &&
      event.key.toLowerCase() === 'z'
    if (isUndo && onUndo !== undefined) {
      event.preventDefault()
      onUndo()
      return
    }
    const hasModifier = event.ctrlKey || event.metaKey || event.altKey
    const isTab = !hasModifier && event.key === 'Tab'
    if (isTab) {
      event.preventDefault()
      onTabKey(event.shiftKey)
      return
    }
    if (!hasModifier && isArrowKey(event.key) && selection !== null) {
      event.preventDefault()
      onArrowKey(event.key)
      return
    }
    const action = actionForKey(
      event.key,
      event.ctrlKey,
      event.metaKey,
      event.altKey,
      event.isComposing,
    )
    if (action.kind === 'ignore') {
      return
    }
    if (selection === null) {
      // Backspace never leaves the page, even with nothing selected.
      if (action.kind === 'erase') {
        event.preventDefault()
      }
      return
    }
    event.preventDefault()
    if (action.kind === 'letter') {
      onLetter(action.letter)
    } else {
      onErase()
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

  // Touch gestures, handled here: one finger pans, two fingers pinch (the zoom
  // follows the ratio of the finger distances).
  $effect(() => {
    const element = viewport
    if (element === undefined) {
      return
    }
    const target: HTMLDivElement = element
    // The fingers now on the screen, with their last known position.
    const fingers = new Map<number, Finger>()
    let startDistance = 0
    let startZoom = ZOOM_MIN

    function onPointerDown(event: PointerEvent): void {
      if (event.pointerType === 'mouse') {
        return
      }
      fingers.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY })
      if (fingers.size === 2) {
        const [first, second] = [...fingers.values()]
        startDistance = distanceBetween(first, second)
        startZoom = zoom
      }
    }

    function onPointerMove(event: PointerEvent): void {
      const finger = fingers.get(event.pointerId)
      if (finger === undefined) {
        return
      }
      if (fingers.size === 1) {
        target.scrollLeft -= event.clientX - finger.clientX
        target.scrollTop -= event.clientY - finger.clientY
      }
      finger.clientX = event.clientX
      finger.clientY = event.clientY
      if (fingers.size === 2 && startDistance > 0) {
        const [first, second] = [...fingers.values()]
        const ratio = distanceBetween(first, second) / startDistance
        const centerX = (first.clientX + second.clientX) / 2
        const centerY = (first.clientY + second.clientY) / 2
        zoomAround(clampZoom(startZoom * ratio), centerX, centerY)
      }
    }

    function onPointerEnd(event: PointerEvent): void {
      fingers.delete(event.pointerId)
      if (fingers.size < 2) {
        startDistance = 0
      }
    }

    // Change the zoom and scroll so the point between the fingers stays put.
    function zoomAround(newZoom: number, centerX: number, centerY: number): void {
      if (newZoom === zoom || cellSize === 0) {
        return
      }
      const box = target.getBoundingClientRect()
      const offsetX = centerX - box.left
      const offsetY = centerY - box.top
      const gridX = (target.scrollLeft + offsetX) / cellSize
      const gridY = (target.scrollTop + offsetY) / cellSize
      zoom = newZoom
      flushSync()
      target.scrollLeft = gridX * cellSize - offsetX
      target.scrollTop = gridY * cellSize - offsetY
    }

    target.addEventListener('pointerdown', onPointerDown)
    target.addEventListener('pointermove', onPointerMove)
    target.addEventListener('pointerup', onPointerEnd)
    target.addEventListener('pointercancel', onPointerEnd)
    return () => {
      target.removeEventListener('pointerdown', onPointerDown)
      target.removeEventListener('pointermove', onPointerMove)
      target.removeEventListener('pointerup', onPointerEnd)
      target.removeEventListener('pointercancel', onPointerEnd)
    }
  })
</script>

<div
  class="viewport"
  data-testid="grid-viewport"
  data-zoom={String(zoom)}
  data-zoom-min={String(ZOOM_MIN)}
  data-zoom-max={String(ZOOM_MAX)}
  bind:this={viewport}
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
    style:grid-template-columns="repeat({grid.width}, var(--cell))"
    style:grid-auto-rows="var(--cell)"
  >
    {#each rows as rowCells, rowIndex (rowIndex)}
      <div class="row" data-testid="grid-row" role="row" data-row={rowIndex}>
        {#each rowCells as cell (cell.column)}
          {#if cell.type === 'letter'}
            {@const shown = shownCell(cell, pendingEdits)}
            {@const cursors = cursorsOn(cell.row, cell.column)}
            {@const tints = tintsOn(cell.row, cell.column)}
            {@const isInWord = wordPositions.has(positionKey(cell.row, cell.column))}
            {@const finder = finderOf(cell)}
            {@const caughtUp = isCaughtUp(cell.row, cell.column)}
            {@const flash = flashOf(cell.row, cell.column)}
            {@const letter = shown.letter ?? ''}
            <!-- The cell's marks, in the drawing order of spec 042: the letter,
                 then the flash overlay (under it, z-index -1), the catch-up ring
                 (1), the revealed notch (3), the other players' triangles or
                 icons (2) and the arrows (6); last, my selection border (7). -->
            <div
              class="cell letter"
              class:locked={cell.locked}
              data-testid="cell"
              data-row={cell.row}
              data-column={cell.column}
              data-type="letter"
              role="gridcell"
              id={cellId(cell.row, cell.column)}
              aria-selected={isSelected(cell.row, cell.column)}
              data-letter={letter}
              data-unconfirmed={String(shown.unconfirmed)}
              data-pencil={String(shown.pencil)}
              data-author={cell.author ?? ''}
              data-author-colour={finder}
              data-locked={String(cell.locked)}
              data-revealed={String(cell.revealed)}
              data-wrong={String(cell.wrong && !shown.unconfirmed)}
              data-flash={flash}
              data-caught-up={String(caughtUp)}
              data-selected={String(isSelected(cell.row, cell.column))}
              data-in-word={String(isInWord)}
              data-tinted-by={tints.map((remote) => remote.playerId).join(' ')}
              class:selected={isSelected(cell.row, cell.column)}
              class:in-word={isInWord}
              class:tinted={tints.length > 0 && isOthersTintOn}
              style:--tint={tints.length > 0 ? `var(--player-colour-${tints[0].colour})` : null}
              style:--finder-ink={letterColourOf(finder)}
              style:--triangle="{triangleSide(cellSize)}px"
              style:grid-row={cell.row + 1}
              style:grid-column={cell.column + 1}
            >{#if letter !== ''}<span class="cell-letter" data-testid="cell-letter"
                  >{letter}</span
                >{/if}{#if flash !== ''}<span
                  class="cell-flash"
                  data-testid="cell-flash"
                  aria-hidden="true"
                  style:background-color={`var(--player-colour-${flash})`}
                ></span>{/if}{#if caughtUp}<span
                  class="catch-up-mark"
                  data-testid="catch-up-mark"
                  aria-hidden="true"
                ></span>{/if}{#if cell.revealed}<span
                  class="reveal-mark"
                  data-testid="reveal-mark"
                  aria-hidden="true"
                ></span><span class="visually-hidden" data-testid="reveal-label"
                  >{t('a11y.revealed')}</span
                >{/if}{#each cursors as cursor (cursor.remote.playerId)}<span
                  class="remote-selection"
                  data-testid="remote-selection"
                  data-player-id={cursor.remote.playerId}
                  data-colour={String(cursor.remote.colour)}
                  data-corner={cursor.corner}
                  data-shape={isAccessibilityOn ? 'icon' : 'triangle'}
                  aria-hidden="true"
                  >{#if isAccessibilityOn}<PlayerIcon
                      colour={cursor.remote.colour}
                    />{:else}<svg
                      class="triangle"
                      viewBox="0 0 10 10"
                      preserveAspectRatio="none"
                      aria-hidden="true"
                      ><polygon
                        points={TRIANGLE_POINTS[cursor.corner]}
                        style:fill={`var(--player-colour-${cursor.remote.colour})`}
                      /></svg
                    >{/if}</span
                >{/each}{#each arrowsIn(cell.row, cell.column) as placed (`${placed.clueRow},${placed.clueColumn},${placed.clueIndex}`)}<svg
                  class="clue-arrow {placed.place}"
                  data-testid="clue-arrow"
                  data-arrow={placed.arrow}
                  data-side={arrowSide(placed.arrow)}
                  data-clue-row={placed.clueRow}
                  data-clue-column={placed.clueColumn}
                  data-clue-index={placed.clueIndex}
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  ><path d={ARROW_GLYPHS[placed.arrow].path} /><polygon
                    points={ARROW_GLYPHS[placed.arrow].head}
                  /></svg
                >{/each}{#if isSelected(cell.row, cell.column)}<span
                  class="cell-selection"
                  data-testid="cell-selection"
                  aria-hidden="true"
                ></span>{/if}</div>
          {:else if cell.type === 'clue'}
            <div
              class="cell clue-cell"
              data-testid="cell"
              data-row={cell.row}
              data-column={cell.column}
              data-type="clue"
              data-author-colour=""
              role="gridcell"
              id={cellId(cell.row, cell.column)}
              style:grid-row={cell.row + 1}
              style:grid-column={cell.column + 1}
            >
              {#each cell.clues as clue, index (index)}
                {@const flagMarker = clueFlags.get(`${cell.row},${cell.column},${index}`)}
                {@const reactionMarker = clueReactions.get(`${cell.row},${cell.column},${index}`)}
                {#if index === 1}
                  <div class="separator" data-testid="clue-separator"></div>
                {/if}
                <div
                  class="clue"
                  data-testid="clue"
                  data-clue-index={index}
                  data-arrow={clue.arrow}
                  data-active={String(activeKey === `${cell.row},${cell.column},${index}`)}
                  data-flagged={String(flagMarker !== undefined)}
                  class:active={activeKey === `${cell.row},${cell.column},${index}`}
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
    inset: 0;
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
    inset: 0;
    z-index: 1;
    box-sizing: border-box;
    border: 3px solid var(--nock-ink);
    pointer-events: none;
  }

  /* The Auteurs mode (spec 045): each letter in its finder's ink, or ink when
     it has no finder (--finder-ink, set on the cell), on every background of
     the cell, the flash included. It replaces the pencil grey (the italics
     stay) and the ink of a flash. The strike of a wrong letter turns ink, so
     that it still shows on a red letter. */
  .grid.authors-view .letter {
    color: var(--finder-ink);
  }

  .grid.authors-view .letter[data-wrong='true'] {
    text-decoration-color: var(--nock-ink);
  }

  /* A revealed letter (spec 024, spec 042): an orange-red notch pointing up,
     centred on the bottom edge, drawn over the triangles and the ring. */
  .reveal-mark {
    position: absolute;
    z-index: 3;
    bottom: 0;
    left: 50%;
    transform: translateX(-50%);
    width: max(7px, calc(var(--cell) * 0.22));
    height: max(4px, calc(var(--cell) * 0.11));
    background-color: var(--nock-reveal);
    clip-path: polygon(50% 0%, 100% 100%, 0% 100%);
    pointer-events: none;
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
    right: var(--inset);
  }

  .remote-selection[data-corner='bottom-right'] {
    bottom: var(--inset);
    right: var(--inset);
  }

  .remote-selection[data-corner='bottom-left'] {
    bottom: var(--inset);
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
     mark of the cell but my selection border, with a thin white halo. */
  .clue-arrow {
    --arrow: max(9px, calc(var(--cell) * 0.26));
    position: absolute;
    z-index: 6;
    width: var(--arrow);
    height: var(--arrow);
    pointer-events: none;
    filter: drop-shadow(0 0 0.8px var(--nock-white)) drop-shadow(0 0 0.8px var(--nock-white));
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

  /* The focus outline stays inside the scrolling viewport. */
  .grid:focus-visible {
    outline-offset: -3px;
  }

  /* An empty cell: rule grey, holding nothing. */
  .empty {
    overflow: hidden;
    background: var(--nock-rule);
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

  /* A shown reaction (spec 022): the white pill of _design.md section 8,
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
