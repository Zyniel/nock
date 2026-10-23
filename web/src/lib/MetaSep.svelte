<script lang="ts">
  // The separator (a middle dot) between two texts of a line (spec 046): a pictogram
  // drawn by CSS on an empty element, so it is never read as text.
</script>

<span class="meta-sep" data-testid="meta-sep" aria-hidden="true"></span>

<style>
  .meta-sep::before {
    content: '·';
  }
</style>
