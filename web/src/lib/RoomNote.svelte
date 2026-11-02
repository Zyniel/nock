<script lang="ts" module>
  // A note shows for NOTE_SHOWN_MS, then fades out in NOTE_FADE_MS (spec 041's
  // `nock-note` fade) and leaves the page NOTE_LEAVE_MS after the fade began:
  // a few frames after the fade's end, so that it has been drawn fully faded.
  const NOTE_SHOWN_MS = 3000
  const NOTE_FADE_MS = 250
  const NOTE_LEAVE_MS = NOTE_FADE_MS + 100
  // How far under the viewport's top the vote banner lies in the column layout.
  const COLUMN_BANNER_INSET_PX = 8

  // What the note over the grid shows (spec 043, "3-second notes"): a note of
  // the room, which starts with the pictogram of its line kind when it has
  // one, or the answer to « Annuler » with nothing to undo (`isUndo`), which
  // has the note's look and place.
  export interface ShownNote {
    id: number
    isUndo: boolean
    kind: string | null
    text: string
  }
</script>

<script lang="ts">
  // One 3-second note, laid over the top of the grid viewport: it takes no
  // room. The room page shows one at a time and gives each note its own
  // element, so a newer note replaces the shown one at once.
  import LinePictogram from './LinePictogram.svelte'

  let {
    note,
    layout,
    bannerHeight,
    onOpen,
    onGone,
  }: {
    note: ShownNote
    // The grid area's padding differs in the two layouts (8 px in the sheet,
    // 12 px at the top in the column); the note sits 8 px under the
    // viewport's top in both.
    layout: 'sheet' | 'column'
    // The height of the vote banner over the viewport's top, 0 when it is not
    // on the page. While it is, the note sits 8 px under the banner's bottom
    // edge, where nothing covers it (spec 043, Decision 25); it follows the
    // banner without restarting its 3 seconds.
    bannerHeight: number
    // A tap or a click on a note of the room.
    onOpen: () => void
    // The note has faded out.
    onGone: (noteId: number) => void
  } = $props()

  let isOff = $state(false)

  // The banner lies on the viewport's top edge in the sheet layout and 8 px
  // under it in the column layout (spec 047), as the note does with no banner:
  // the note moves down by the banner's height, plus those 8 px in the column
  // layout, so that it stays 8 px under the banner's bottom edge.
  let marginTop = $derived(
    bannerHeight === 0 ? 0 : bannerHeight + (layout === 'column' ? COLUMN_BANNER_INSET_PX : 0),
  )

  $effect(() => {
    const noteId = note.id
    const offTimer = setTimeout(() => {
      isOff = true
    }, NOTE_SHOWN_MS)
    const goneTimer = setTimeout(() => onGone(noteId), NOTE_SHOWN_MS + NOTE_LEAVE_MS)
    return () => {
      clearTimeout(offTimer)
      clearTimeout(goneTimer)
    }
  })
</script>

{#if note.isUndo}
  <p
    class="nock-note room-note {layout}"
    data-testid="undo-message"
    style:margin-top="{marginTop}px"
    data-off={isOff ? '' : null}
  >{note.text}</p>
{:else}
  <!-- Other players' actions are not announced (spec 022): the note is hidden
       from screen readers and is no Tab stop. -->
  <button
    type="button"
    class="nock-note room-note {layout}"
    data-testid="room-note"
    tabindex="-1"
    aria-hidden="true"
    style:margin-top="{marginTop}px"
    data-off={isOff ? '' : null}
    onclick={onOpen}
    >{#if note.kind !== null}<LinePictogram kind={note.kind} />{/if}{note.text}</button
  >
{/if}

<style>
  /* Centred on the grid viewport, 8 px under its top (and under the vote
     banner by its margin), on layer 6. A note
     longer than the viewport is wide ends with an ellipsis, on its one line. */
  .room-note {
    position: absolute;
    z-index: 6;
    left: 50%;
    transform: translateX(-50%);
    box-sizing: border-box;
    max-width: calc(100% - 16px);
    margin: 0;
    border: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    text-align: left;
  }

  .room-note.sheet {
    top: 16px;
  }

  .room-note.column {
    top: 20px;
  }

  button.room-note {
    cursor: pointer;
  }
</style>
