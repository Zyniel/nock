<script lang="ts">
  // The separator (a middle dot) between two texts of a line (spec 046): a pictogram
  // drawn by CSS on an empty element, so it is never read as text. It sits in
  // a run of inline text, 4 px from the texts on each side.
</script>

<span class="meta-sep" data-testid="meta-sep" aria-hidden="true"></span>

<style>
  .meta-sep {
    margin: 0 4px;
  }

  .meta-sep::before {
    content: '·';
  }
</style>
