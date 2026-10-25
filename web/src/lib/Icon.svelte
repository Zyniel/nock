<script lang="ts">
  // One icon of icons.ts (specs/_design/foundation.md « Icons »): a 24 by 24 outline drawn in
  // the current colour, hidden from screen readers (the control around it
  // carries the name). Its size and stroke width come from the caller's styles.
  import { ICONS } from './icons'
  import type { IconName } from './icons'
  import IconShapes from './IconShapes.svelte'

  let { name }: { name: IconName } = $props()
</script>

<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><IconShapes shapes={ICONS[name]} /></svg>

<style>
  .icon {
    display: block;
    flex: none;
    fill: none;
    stroke: currentColor;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
</style>
