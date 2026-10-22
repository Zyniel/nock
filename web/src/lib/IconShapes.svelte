<svelte:options namespace="svg" />

<script lang="ts">
  // The shapes of one icon of icons.ts, drawn as they are listed there. The
  // caller puts them in its own `svg`, which sets the box and the colours.
  import type { IconShape } from './icons'

  let { shapes }: { shapes: readonly IconShape[] } = $props()
</script>

{#each shapes as shape, index (index)}{#if shape.kind === 'path'}<path
      d={shape.d}
    />{:else if shape.kind === 'rect'}<rect
      x={shape.x}
      y={shape.y}
      width={shape.width}
      height={shape.height}
      rx={shape.rx}
    />{:else if shape.kind === 'circle'}<circle
      cx={shape.cx}
      cy={shape.cy}
      r={shape.r}
    />{:else}<polygon points={shape.points} />{/if}{/each}
