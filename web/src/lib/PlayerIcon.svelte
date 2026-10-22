<script lang="ts">
  // A player's own icon of the Accessibilité mode (spec 042, _design.md section
  // 6): the shapes of PLAYER_ICONS for the player's colour index, filled with
  // that player's colour, with no outline. It fills its parent's box unless a
  // side is given.
  import { PLAYER_ICONS } from './icons'
  import IconShapes from './IconShapes.svelte'

  let { colour, side = '100%' }: { colour: number; side?: string } = $props()

  let shapes = $derived(PLAYER_ICONS[colour] ?? [])
</script>

<svg
  class="player-icon"
  data-testid="player-icon"
  data-icon={String(colour)}
  viewBox="0 0 10 10"
  aria-hidden="true"
  style:width={side}
  style:height={side}
  style:fill={`var(--player-colour-${colour})`}><IconShapes {shapes} /></svg
>

<style>
  .player-icon {
    display: block;
    stroke: none;
  }
</style>
