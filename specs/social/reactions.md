---
area: social
file: reactions
status: approved
---

# social/reactions - The clue flag and reactions

## Purpose

The players of a room point at a clue without leaving the grid: « Je bloque »,
a flag on the clue where help is wanted, and a short reaction on a word, shown
on its clue.

## Depends on

- `platform/realtime.md`: the messages `flag` and `react`, their events, seq
  order, delivery and error codes.
- `social/chat.md`: mute (rule 15), the page's pacing (rule 10), the stream
  the flag line joins (rule 18).
- `client/hud.md`: the clue bar that holds « Réagir » and « Je bloque ».

## Rules

### The clue flag

1. A player holds at most one flag. `flag` is input (it wakes an idle player,
   `social/presence.md`), not an edit, with no rate limit. For player p, the
   first case that applies decides:
   1. no clue and p holds none: nothing;
   2. no clue: p's flag goes, in one `flag_changed` with no clue;
   3. a clue that names no word, or whose word is full (each cell holds a
      letter, pencil or not): `invalid_target`, changing nothing but the waking;
   4. the clue of p's flag: nothing;
   5. else it becomes p's flag, in one `flag_changed`, replacing any other.
2. After a step whose events hold a `letter_changed` or a `cell_locked` (edit,
   undo, reveal, pencil letter), each player whose flagged word is now full, in
   player order, loses the flag in one `flag_changed` with no clue, after the
   step's own events and before `grid_solved` or `grid_full_wrong`
   (`gameplay/rules.md`). A check fills no cell; emptying the word again does
   not bring the flag back.
3. A player who leaves the room takes the flag along, with no `flag_changed`; a
   disconnected one keeps it. A snapshot lists the players' flags in player
   order, several on one clue allowed. Flags survive replay and a restart.
4. The page keeps the latest snapshot's flags (skipping a malformed one), takes
   each `flag_changed` and drops a flag at `player_left`. A flagged clue shows
   one marker, hidden from assistive technology, labelled `flag.marker_label`
   (« Bloqué : {names} »): the flaggers' nicknames in roster order, then the
   ids the roster lacks, each « Quelqu'un », by id as plain strings. The marker
   never moves the clue text.
5. « Je bloque » (`flag.button_label`, « Je bloque sur ce mot ») is pressed
   while my flag is on the selected word's clue. It is disabled while the page
   is not joined, while nothing is selected, and while the selected word is
   full on the page (pending letters count) and it is not pressed. A press
   sends my flag on that clue, or `clue: null` when pressed; the button and the marker change only with
   `flag_changed`. An error answering a flag changes nothing on the page.
6. A `flag_changed` with a clue adds the stream line `feed.flag` (« {name}
   bloque sur « {clue} » »); one without a clue adds none.

### Reactions

7. The reactions are `thumbs_up`, `clap`, `laugh`, `wow`, `thinking` (👍 👏 😂
   😮 🤔, `reaction.<value>`, named `reaction.<value>_label`). A well-formed
   `react` is input, never answered with an error, and dropped silently when
   the sender is muted, when its clue names no word, or past 5 reactions
   relayed in the last 10 seconds; dropped ones do not count. Else one
   `reaction`, with no seq and never logged, reaches every player once, the
   sender included, on any word, full or not. A restart empties every
   player's reaction window, connected or not.
8. « Réagir » (`reaction.button_label`) is disabled while the page is not
   joined, while nothing is selected, while I am muted (`social/chat.md` rule
   15) and while the vote banner shows (`gameplay/votes.md`). A
   press opens the picker (`reaction.picker_label`, the five in that order),
   the focus on the first option (on « Réagir » while pacing holds). An option
   sends `react` on the selected word's clue and closes the picker; Escape or a
   second press closes it sending nothing; both put the focus on « Réagir ».
   When « Réagir » becomes disabled, an open picker closes at once, sending
   nothing, and a focus inside it goes to the grid. « Réagir » exposes
   whether the picker is open and names it as what it controls
   (`aria-controls`) only while it is open.
9. A `reaction`, applied once the page has a snapshot and leaving its seq
   alone, shows on its clue when the grid has that clue: the emoji, hidden from
   assistive technology, labelled `reaction.shown_label` (« {name} :
   {reaction} »), for 3 seconds from its arrival. A newer one on that clue
   replaces it, with its own 3 seconds.

### Look

- `_design/cells.md`, « Clue cells »: the marker. `_design/foundation.md`,
  « Icons »: the flag icon.
- `_design/room.md`: « Clue bar » for « Réagir » and « Je bloque »;
  « Reactions » and « Layers » for the picker and a shown reaction.

## Acceptance criteria

The examples use FX-01 (`specs/_reference.md`) with Ana (`p1`, host), Bob
(`p2`) and Cy (`p3`); IDES is the clue (0, 3, 0), MIME (0, 2, 0).

- **AC-1** At seq 2, Bob's flag on IDES gives one `flag_changed` seq 3 to both
  players and no reply, and a later joiner's snapshot lists it; within 1 s both
  pages mark IDES, labelled « Bloqué : Bob », Bob's « Je bloque » is pressed,
  and both streams end with « Bob bloque sur « Fatales à César » ».
  (← 021 AC-1, 021 AC-2)
- **AC-2** With Bob's flag on IDES, Ana's `S` at (4, 3) after `I`, `D`, `E`
  gives `letter_changed` seq 7 then `flag_changed` seq 8 with no clue; a letter
  that fills two flagged words and solves the grid gives its letter, the two
  clearings in player order, then `grid_solved`. The page unmarks IDES and adds
  no stream line. (← 021 AC-3)
- **AC-3** Bob's flag on IDES then MIME gives one `flag_changed`, IDES unmarked
  and MIME marked; with Cy's flag on MIME, it has one marker, « Bloqué : Bob,
  Cy »; flags of `p9` then `p7`, not in the roster, give « Bloqué : Bob, Cy,
  Quelqu'un, Quelqu'un ». (← 021 AC-4)
- **AC-4** A flag on (1, 0, 0), (0, 2, 1), (9, 9, 0), on MIME once full, or on
  any word of a solved grid gets `invalid_target`, the room and its seq
  unchanged; removing a flag one lacks, or flagging one's clue again, gives
  nothing; an idle sender is woken all the same. (← 021 AC-5)
- **AC-5** With nothing selected « Je bloque » is disabled; with MIME selected
  a press sends my flag on (0, 2, 0), the button pressed only once
  `flag_changed` comes back, and a second press sends `clue: null`; Bob's flag
  on MIME leaves it unpressed; selecting the full TAMIS disables it; an
  `invalid_target` changes nothing on the page. (← 021 AC-6)
- **AC-6** A marker on IDES, on NAVAL (second clue of (0, 0)) and on FX-02's
  first clue lies in its clue cell as « Clue cells » draws it, the clue text in
  place. « Je bloque » sits in the clue bar between « Réagir » and the next
  button, is reached by Tab with the focus ring, flags by Enter, and in every
  window of `product.md` is at least 24 px square and hit at its centre; the
  contrast and language scans pass. (← 021 AC-9, 021 AC-10, 021 AC-11)
- **AC-7** Bob, flagging IDES, removed or timed out leaves only his
  `player_left`, and the page unmarks IDES; disconnected, he keeps the flag
  until he times out. Replayed from the log, and after a restart, every player
  holds the flag of the live room. (← 021 AC-7, 021 AC-8)
- **AC-8** Bob's 👏 on IDES gives no event and reaches Bob and Ana once, with
  no seq and nothing logged; within 1 s both pages show 👏 on IDES. A 😮 shows,
  labelled « Bob : Waouh », and is gone 3.5 s after; a 🤔 a second later
  replaces it for its own 3 s; one on (1, 0, 0) shows nothing.
  (← 022 AC-3, 022 AC-4)
- **AC-9** With VIDE selected, « Réagir », not expanded and with no
  `aria-controls`, opens the picker with 👍 👏 😂 😮 🤔, focus on the first,
  and is then expanded with `aria-controls` naming the picker; 😂 sends
  `react` on (2, 0, 0), closes it and focuses « Réagir »; Escape closes it
  sending nothing, and `aria-controls` is gone; in the column layout it opens
  over the grid while the Salon stays open. (← 022 AC-5)
- **AC-10** With MIME selected and the picker open, the socket closes: within
  5 s « Réagir » and « Je bloque » are disabled and the picker is closed,
  nothing sent; the next snapshot enables both again. After a close 4001 both
  stay disabled.

## Out of scope

- Flagging a cell or several clues.
- Mute, the page's pacing and the stream: `social/chat.md`. Who may mute:
  `lobby/host.md`. The clue bar's layout: `client/hud.md`. « Salon » and the
  3-second notes (flags, my own reaction): `client/room.md`.

## Code

- `src/nock/room.py`: `_flag`, `_react`, flag clearing, `after_restart`;
  `RoomConfig` holds the limits.
- `web/src/lib/clueFlags.ts`, `activityFeed.ts` (the flag line),
  `ReactionPicker.svelte`, `ClueBar.svelte`, `ClueCell.svelte` (flag and
  reaction marks), `roomCommands.ts` (flag, reaction), `expiry.ts` (reaction
  expiry), `roomSession.ts`.
- Tests: `tests/test_spec_021_*`, `tests/test_spec_022_ac03_ac05_reactions.py`;
  `tests/test_reactions_*` for AC-10.
