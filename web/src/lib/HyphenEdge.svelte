<script lang="ts">
  // One letter cell's share of a hyphen edge (specs/_design/cells.md « Hyphen
  // edges »): a strip along one side of the cell, `width` px across, holding
  // the dashes. Every position is a whole number of px from the cell's box, so
  // every dash end lies on a whole pixel even when the cell's side is not.
  import type { DashRun, EdgeDrawing } from './gridLayout'

  let { drawing, dashes }: { drawing: EdgeDrawing; dashes: DashRun[] } = $props()

  let isAcross = $derived(drawing.side === 'right' || drawing.side === 'left')
</script>

<span
  class="hyphen-edge {drawing.side} {drawing.kind}"
  style:--edge-width="{drawing.width}px"
  aria-hidden="true"
  >{#each dashes as dash, index (index)}<span
      class="dash"
      style:top={isAcross ? `${dash.start}px` : null}
      style:height={isAcross ? `${dash.end - dash.start}px` : null}
      style:left={isAcross ? null : `${dash.start}px`}
      style:width={isAcross ? null : `${dash.end - dash.start}px`}
    ></span>{/each}</span
>

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
    background: var(--nock-selected);
  }

  .dash {
    position: absolute;
  }

  .right .dash,
  .left .dash {
    left: 0;
    right: 0;
  }

  .bottom .dash,
  .top .dash {
    top: 0;
    bottom: 0;
  }

  .hyphen .dash {
    background: var(--nock-hyphen);
  }

  .band .dash {
    background: var(--nock-navy);
  }
</style>
