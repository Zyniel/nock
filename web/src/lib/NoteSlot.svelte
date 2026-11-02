<script lang="ts">
  // The 3-second notes (spec 043): the note over the grid, one at a time, made
  // from the newest note of the room or from « Annuler » with nothing to undo
  // (spec 018). A note of the room waits while the vote banner is on the page.
  import { untrack } from 'svelte'
  import { announce } from './announce'
  import { t } from './i18n'
  import RoomNote from './RoomNote.svelte'
  import type { ShownNote } from './RoomNote.svelte'
  import type { RoomNote as RoomNoteView } from './roomSession'

  let {
    latestNote,
    undoRefusals,
    isBannerShown,
    isStreamShown,
    layout,
    bannerHeight,
    onOpenSalon,
  }: {
    // The newest note of the room, or null.
    latestNote: RoomNoteView | null
    // How many undos the server refused with nothing to undo.
    undoRefusals: number
    // True while the vote banner is on the page.
    isBannerShown: boolean
    // True while the stream shows: the player reads the same line there.
    isStreamShown: boolean
    layout: 'sheet' | 'column'
    // The vote banner's height as last measured.
    bannerHeight: number
    // A tap or a click on a note: the Salon opens on its Discussion tab.
    onOpenSalon: () => void
  } = $props()

  // The note over the grid, one at a time, and the newest note of the room
  // that waits for the vote banner to go.
  let shownNote: ShownNote | null = $state(null)
  let waitingNote: ShownNote | null = $state(null)
  // Each shown note gets its own id, so a newer one replaces the older at once.
  let nextShownNoteId = 1
  let handledRoomNoteId = 0
  let shownUndoRefusals = 0

  function newShownNote(isUndo: boolean, kind: string | null, text: string): ShownNote {
    const note = { id: nextShownNoteId, isUndo, kind, text }
    nextShownNoteId += 1
    return note
  }

  // The notes of the room, in one place so that the newest always wins. A new
  // note: none while the stream shows; while the vote banner is on the page it
  // waits, replacing any older waiting note; otherwise it shows, and a note
  // that waited is dropped (the result of a vote, made once the banner has
  // left, replaces the notes that waited during it, spec 047). With no new
  // note, once the banner has gone, the note that waited shows, unless the
  // stream shows by then: the player reads the same line there.
  $effect(() => {
    const latest = latestNote
    if (latest !== null && latest.id !== handledRoomNoteId) {
      handledRoomNoteId = latest.id
      receiveRoomNote(latest.kind, latest.text, isBannerShown)
      return
    }
    if (!isBannerShown) {
      showWaitingNote()
    }
  })

  function receiveRoomNote(kind: string | null, text: string, waitsForBanner: boolean): void {
    if (untrack(() => isStreamShown)) {
      waitingNote = null
      return
    }
    const note = newShownNote(false, kind, text)
    if (waitsForBanner) {
      waitingNote = note
      return
    }
    waitingNote = null
    shownNote = note
  }

  function showWaitingNote(): void {
    const note = untrack(() => waitingNote)
    if (note === null) {
      return
    }
    waitingNote = null
    if (!untrack(() => isStreamShown)) {
      shownNote = note
    }
  }

  // "Nothing to undo" (spec 018) has the note's look and place: it replaces
  // any shown note, and shows whatever else shows.
  $effect(() => {
    if (undoRefusals === shownUndoRefusals) {
      return
    }
    shownUndoRefusals = undoRefusals
    shownNote = newShownNote(true, null, t('undo.nothing'))
    announce(t('undo.nothing'))
  })

  // A note leaves once it has faded, unless a newer one replaced it.
  function onNoteGone(noteId: number): void {
    if (shownNote !== null && shownNote.id === noteId) {
      shownNote = null
    }
  }

  // A tap or a click on a note opens the Salon on its Discussion tab, as
  // « Salon » does, and removes the note.
  function openSalonFromNote(): void {
    shownNote = null
    onOpenSalon()
  }
</script>

{#if shownNote !== null}
  {#key shownNote.id}
    <RoomNote
      note={shownNote}
      {layout}
      bannerHeight={isBannerShown ? bannerHeight : 0}
      onOpen={openSalonFromNote}
      onGone={onNoteGone}
    />
  {/key}
{/if}
