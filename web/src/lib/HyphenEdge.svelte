<script lang="ts">
  // One letter cell's share of a hyphen edge (specs/_design/cells.md « Hyphen
  // edges »): a strip along one side of the cell, painted with the dashes. Every
  // dash end is a whole number of px from the cell's box, so it lies on a whole
  // pixel even when the cell's side is not.
  //
  // What depends on the cell side, the dashes and the width of their strip, is
  // read from variables the grid sets (GridViewport.svelte): a pinch changes
  // no cell's drawing (client/shell.md rule 18).
  import type { EdgeDrawing } from './gridLayout'

  let { drawing }: { drawing: EdgeDrawing } = $props()
</script>

<span
  class="hyphen-edge {drawing.side} {drawing.kind}"
  style:--edge-width={drawing.width === null ? null : `${drawing.width}px`}
  aria-hidden="true"
></span>

<style>
  /* The strip runs along its side from the cell's start to the grid line that
     crosses the edge at its end, which stays plain: --line-right and
     --line-bottom, set on the cell, are 1px where the cell's own line was
     taken away for a hyphen edge. The hyphen grey dashes sit over the
     backgrounds and the flash overlay (z-index -1, after it in the cell),
     under the letter and every mark; my selection border's band is on top,
     like the rest of that border (z-index 7, after it in the cell). */
  .hyphen-edge {
    position: absolute;
    pointer-events: none;
  }

  /* The dashes' share of the thickness: the cell before the edge (its right
     or bottom side) holds the grid line's pixel, the cell after it the rest. */
  .hyphen-edge.hyphen.right,
  .hyphen-edge.hyphen.bottom {
    --edge-width: var(--hyphen-width-before);
  }

  .hyphen-edge.hyphen.left,
  .hyphen-edge.hyphen.top {
    --edge-width: var(--hyphen-width-after);
  }

  .hyphen-edge.right,
  .hyphen-edge.left {
    top: 0;
    bottom: var(--line-bottom);
    width: var(--edge-width);
  }

  .hyphen-edge.right {
    right: 0;
  }

  .hyphen-edge.left {
    left: 0;
  }

  .hyphen-edge.bottom,
  .hyphen-edge.top {
    left: 0;
    right: var(--line-right);
    height: var(--edge-width);
  }

  .hyphen-edge.bottom {
    bottom: 0;
  }

  .hyphen-edge.top {
    top: 0;
  }

  .hyphen-edge.hyphen {
    z-index: -1;
  }

  .hyphen-edge.band {
    z-index: 7;
    background-color: var(--nock-selected);
  }

  /* The dashes, from the start of the strip: in hyphen grey, or navy on my
     selection border's band. */
  .hyphen-edge.hyphen.right,
  .hyphen-edge.hyphen.left {
    background-image: var(--hyphen-dashes-down);
  }

  .hyphen-edge.hyphen.bottom,
  .hyphen-edge.hyphen.top {
    background-image: var(--hyphen-dashes-across);
  }

  .hyphen-edge.band.right,
  .hyphen-edge.band.left {
    background-image: var(--band-dashes-down);
  }

  .hyphen-edge.band.bottom,
  .hyphen-edge.band.top {
    background-image: var(--band-dashes-across);
  }
</style>
