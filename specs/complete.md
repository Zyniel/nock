# Collaborative mots fléchés: epics, user stories and acceptance criteria

Oct 10, 2026 · @François

This backlog proposes 10 epics and 37 user stories, each with testable acceptance criteria, for a collaborative multiplayer mots fléchés game. Le Parisien's page could not be opened from Claude's web tools, so nothing here is checked against it. The baseline is the usual press-site player, marked as assumed, and the reference grid is an original fixture, not one of their grids.

## Baseline and improvements

The improved version changes five things for the player; each maps to one or two epics. The baseline column describes a typical single-player press-site grid and still needs confirming on Le Parisien from screenshots.

| Area | Assumed baseline | Improved version | Epic |
| --- | --- | --- | --- |
| Players | One player per grid | 2 to 8 players fill the same grid live | E3, E4 |
| Coordination | None needed | Cursors, authorship colours, pencil letters, clue flags, chat | E5 |
| Help | Check and reveal buttons, used freely | Shared hint budget, optional vote before a reveal | E6 |
| Progress | Kept in one browser | Kept in the room, resumed from any device by link | E9 |
| Outcome | Timer and a completion message | Recap of who solved what, shareable without spoilers | E7 |

## Reference grid

FX-01 is an original 5×5 grid with 8 words, 18 letter cells and 7 clue cells; the acceptance criteria use it as the golden test case. It covers the four arrow types, a clue cell holding two clues at (0,0), and two letters that belong to one word only (N and T). A script confirmed that every arrow resolves to its answer and that no letter run lacks a clue.

Le Parisien's grids are published editorial content. Treat them as a UX reference and keep them out of the product unless a licence allows it. FX-02, a full-size grid for the layout and performance criteria, is still to be chosen.

Solved layout, coordinates as (row, column) from zero. Arrows: → right, ↓ down, ↳ down then right, ↴ right then down.

|  | c0 | c1 | c2 | c3 | c4 |
| --- | --- | --- | --- | --- | --- |
| r0 | Passoire fine ↳ / De la marine ↴ | N | Artiste muet ↓ | Fatales à César ↓ | Flaire ↓ |
| r1 | T | A | M | I | S |
| r2 | Sans contenu → | V | I | D | E |
| r3 | Fin de prière → | A | M | E | N |
| r4 | Alourdit le ballon → | L | E | S | T |

| Word | Clue cell | Arrow | First letter | Direction | Clue | Answer |
| --- | --- | --- | --- | --- | --- | --- |
| W1 | (0,0) | down then right | (1,0) | across | Passoire fine | TAMIS |
| W2 | (0,0) | right then down | (0,1) | down | De la marine | NAVAL |
| W3 | (0,2) | down | (1,2) | down | Artiste muet | MIME |
| W4 | (0,3) | down | (1,3) | down | Fatales à César | IDES |
| W5 | (0,4) | down | (1,4) | down | Flaire | SENT |
| W6 | (2,0) | right | (2,1) | across | Sans contenu | VIDE |
| W7 | (3,0) | right | (3,1) | across | Fin de prière | AMEN |
| W8 | (4,0) | right | (4,1) | across | Alourdit le ballon | LEST |

Terms used below: clue cell (case définition), letter cell (case lettre), arrow (flèche), force (difficulty level, commonly 1 to 4).

## Epic map

Six epics make the MVP: a group can open a link, fill one grid together and see it validated. Numeric thresholds in the criteria (300 ms sync, 30-day room life) are proposed defaults to adjust.

| ID | Epic | Outcome | Release | Stories | Depends on | Suggested agent |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Grid content and model | Grids exist as validated, licensed data with a catalogue | MVP | 4 | None | Domain and content |
| E2 | Solo solving | One player fills a grid comfortably on phone and desktop | MVP | 5 | E1 | Front-end grid |
| E3 | Rooms and presence | Players gather on one grid through a link and see each other | MVP | 4 | E2 | Realtime |
| E4 | Real-time sync | Every player sees the same grid whatever the network does | MVP | 4 | E3 | Realtime |
| E5 | Collaboration aids | Players coordinate without overwriting each other | V1 | 4 | E4 | Front-end grid |
| E6 | Help and validation | Checks and reveals are a group resource | MVP for 6.1 and 6.4, V1 for 6.2 and 6.3 | 4 | E4 | Game rules |
| E7 | Completion and recap | The group sees its time and who solved what | V1 | 3 | E6 | Game rules |
| E8 | Game modes | Groups can race instead of cooperating | Later | 2 | E7 | Game rules |
| E9 | Accounts and resume | A room survives a closed tab and a change of device | V1 | 3 | E3 | Platform |
| E10 | Quality bar | Accessibility, performance, integrity and privacy hold everywhere | MVP | 4 | All | Review and test |

Handing this to the agents:

1. Write one shared contract spec first: glossary, grid schema (US-1.1) and the list of room events. E2 to E7 all read it.
2. Give each agent one epic spec: its stories and criteria, FX-01, what is out of scope and what it depends on.
3. Keep the IDs (US-4.2, AC-4.2.1) in code, tests and commits, so each criterion traces to a test.
4. Have a separate agent write the tests from the criteria. A builder should not grade its own work.

## E1 Grid content and model

Every other epic reads the grid through this model, so it ships first. Out of scope: a grid editor and automatic grid generation.

### US-1.1 Grid schema

As a builder agent, I need one grid schema, so that every component reads a grid the same way.

- **AC-1.1.1** A grid declares its width, its height and one type per cell: letter, clue or empty.
- **AC-1.1.2** A clue cell holds one or two clues. Each clue has a text, one of the four arrow types, and resolves to an ordered list of letter cells.
- **AC-1.1.3** Answers are stored as uppercase A to Z without accents, spaces or hyphens: ÊTRE is ETRE, ARC-EN-CIEL is ARCENCIEL.
- **AC-1.1.4** FX-01 written in the schema survives load, save and load again with no difference.

### US-1.2 Grid validation at import

As a content editor, I want invalid grids rejected at import, so that players never meet an unsolvable grid.

- **AC-1.2.1** Given a clue whose arrow points to a clue cell, an empty cell or outside the grid, when I import, then the import fails and names the cell.
- **AC-1.2.2** Given a run of two or more letter cells in a row or column with no clue, the import fails and names the run.
- **AC-1.2.3** Given two crossing words that disagree on their shared letter, the import fails and names both words.
- **AC-1.2.4** FX-01 imports and reports 8 words, 18 letter cells and 7 clue cells.

### US-1.3 Grid catalogue

As a player, I want to browse grids by difficulty and size, so that I pick one that suits my group.

- **AC-1.3.1** Each grid lists its number, publication date, force, dimensions and word count.
- **AC-1.3.2** The list filters by force and sorts newest first by default.
- **AC-1.3.3** A grid I started or finished shows that status on my device or account.
- **AC-1.3.4** An unpublished grid is absent from the list and its direct URL returns "not found".

### US-1.4 Licensed content only

As the product owner, I want every grid tied to a source and a licence, so that we publish only what we may use.

- **AC-1.4.1** Import refuses a grid with no author, source or licence field.
- **AC-1.4.2** No component fetches grids from a third-party site, at run time or in a batch.
- **AC-1.4.3** When a grid is withdrawn, open rooms on it can finish and no new room can start.

## E2 Solo solving

A solo game is a room of one, so nothing here is rewritten when other players join. Out of scope: printing and offline play.

### US-2.1 Grid rendering

As a player, I want the grid and its clues readable on my phone, so that I can play without a desktop.

- **AC-2.1.1** On a 360 px wide screen, FX-02 can be panned and pinch-zoomed, and no clue text is cut off at full zoom.
- **AC-2.1.2** Each clue draws its arrow on the side of its word's first letter cell.
- **AC-2.1.3** A cell with two clues shows both, separated by a line; FX-01 shows this at (0,0).
- **AC-2.1.4** A new game on FX-01 renders 7 clue cells and 18 empty letter cells.
- **AC-2.1.5** The game is a responsive web app with no native app and no install. Every screen works from 320 px wide up to desktop, in portrait and landscape, on current Chrome, Safari, Firefox and Edge.

### US-2.2 Word selection and direction

As a player, I want to pick a word with one tap, so that I always know which clue I am answering.

- **AC-2.2.1** Tapping a letter cell selects it and highlights its whole word and that word's clue.
- **AC-2.2.2** Tapping the selected cell again switches between its across and down word. On a cell with one word (N or T in FX-01), nothing changes.
- **AC-2.2.3** Tapping a clue selects the first empty cell of its word. In a two-clue cell, each half selects its own word.
- **AC-2.2.4** The selected word's clue is repeated at 14 px or more in a bar that stays visible above the keyboard.

### US-2.3 Letter entry

As a player, I want typing to flow along the word, so that I fill an answer without re-selecting cells.

- **AC-2.3.1** Typing a letter fills the cell and moves to the next cell of the word. At the last cell the cursor stays.
- **AC-2.3.2** Typing é, à or ç enters E, A or C. Digits, spaces and punctuation are ignored.
- **AC-2.3.3** Backspace clears the current cell. On an empty cell it moves back one cell and clears that one.
- **AC-2.3.4** Typing over a filled cell replaces its letter, unless the cell is locked (AC-4.2.3).

### US-2.4 Keyboard and navigation

As a player, I want to move around the grid from the keyboard, so that I never need the mouse on desktop.

- **AC-2.4.1** Arrow keys move to the next letter cell in that direction and skip clue cells.
- **AC-2.4.2** Tab and Shift+Tab move to the next and previous unfinished word.
- **AC-2.4.3** On touch screens, an in-app AZERTY keyboard with 26 letters and a delete key replaces the system keyboard.

### US-2.5 Instant solo start

As a player, I want to start a grid alone at once, so that I can invite people later without losing my letters.

- **AC-2.5.1** From the catalogue, a grid is playable in one tap, with no sign-up.
- **AC-2.5.2** A solo game becomes a shared room when I invite someone, and every letter is kept.
- **AC-2.5.3** Reloading the page restores my letters and my selected cell.

## E3 Rooms and presence

A room is one grid shared by up to 8 players and reached by a link. Out of scope: matchmaking with strangers and voice chat.

### US-3.1 Room creation and invitation

As a host, I want a link to send to my friends, so that they land directly on our grid.

- **AC-3.1.1** Creating a room gives a share link and a 6-character room code.
- **AC-3.1.2** The link opens the room on the grid, on phone and desktop, with no install.
- **AC-3.1.3** Room codes are random, not sequential. Ten wrong codes from one address within a minute are throttled.

### US-3.2 Guest join

As an invited player, I want to join with only a nickname, so that I am playing within seconds.

- **AC-3.2.1** Given a valid link, when I enter a nickname of 2 to 20 characters, then I am in the room.
- **AC-3.2.2** Each player gets a colour no other player in the room has. A duplicate nickname gets a numeric suffix.
- **AC-3.2.3** I see the current letters, timer and hint budget within 1 second of joining.
- **AC-3.2.4** Joining a room that already has 8 players shows "room full" and does not add me.

### US-3.3 Presence

As a player, I want to see who is here and where they are working, so that we don't solve the same clue twice.

- **AC-3.3.1** A roster lists each player with a colour and a state: active, idle after 2 minutes without input, or disconnected.
- **AC-3.3.2** Another player's selected cell is outlined in their colour and their word lightly tinted, within 300 ms of their move.
- **AC-3.3.3** When two players select the same cell, both outlines are visible.
- **AC-3.3.4** My own selection is styled differently from every other player's.
- **AC-3.3.5** An activity feed lists joins, departures, checks, reveals, flags and setting changes in the order they happened.

### US-3.4 Host controls

As a host, I want to manage who is in the room, so that an unwanted visitor can't spoil the game.

- **AC-3.4.1** The host can remove a player, who then cannot rejoin from the same browser.
- **AC-3.4.2** The host can lock the room; new joiners then see "room locked".
- **AC-3.4.3** If the host is disconnected for more than 60 seconds, the longest-present player becomes host.
- **AC-3.4.4** A change of room settings is announced to all players in the activity feed.

## E4 Real-time sync

The server holds the only true grid; clients display it and send edits. This is the riskiest epic, so its criteria are written to run as automated tests. Out of scope: peer-to-peer sync.

### US-4.1 Shared letters

As a player, I want my friends' letters to appear as they type, so that the grid feels like one sheet of paper.

- **AC-4.1.1** A letter typed by one player appears for the others within 300 ms at the 95th percentile on a 4G connection.
- **AC-4.1.2** My own letter appears at once, before the server confirms it.
- **AC-4.1.3** Given 4 simulated clients sending 1,000 random edits on FX-01, when the edits stop, then all clients and the server hold the same grid.
- **AC-4.1.4** Edits to different cells never delay or cancel each other.

### US-4.2 Same-cell conflicts

As a player, I want a clear rule when two of us type in one cell, so that nobody is surprised by a vanishing letter.

- **AC-4.2.1** When two players type in the same cell at once, the edit the server receives last wins and every client shows it.
- **AC-4.2.2** The player whose letter was replaced sees the cell flash in the other player's colour.
- **AC-4.2.3** A cell confirmed correct by a check or a reveal is locked and rejects edits from everyone.

### US-4.3 Disconnection and reconnection

As a player on a train, I want to keep my place when my connection drops, so that I rejoin without starting over.

- **AC-4.3.1** A banner shows within 5 seconds of a lost connection, and I can keep typing.
- **AC-4.3.2** On reconnection, my offline letters are sent. Where the server's cell changed in the meantime, the server's letter is kept.
- **AC-4.3.3** Reconnecting within 5 minutes restores my nickname, colour and authorship with nothing to re-enter.
- **AC-4.3.4** Other players see my state change in the roster within 10 seconds.

### US-4.4 Durable room state

As a player, I want the room to survive a server incident, so that an hour of solving is never lost.

- **AC-4.4.1** Given a server restart during a game, when players reconnect, then at most the last second of edits is missing.
- **AC-4.4.2** A player joining mid-game receives the full state in one message, then every later edit with none skipped.
- **AC-4.4.3** Undo reverts my own last edit, and only when nobody has changed that cell since.

## E5 Collaboration aids

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking. Out of scope: voice and video.

### US-5.1 Authorship view

As a player, I want to see who wrote each letter, so that I know whom to ask about a doubtful answer.

- **AC-5.1.1** An "authors" switch tints each filled cell with the colour of the last player who edited it.
- **AC-5.1.2** With the switch off, all letters share one neutral colour.
- **AC-5.1.3** Authorship survives reconnection and feeds the recap (US-7.2).

### US-5.2 Pencil letters

As a player, I want to mark a guess as uncertain, so that others don't build on it blindly.

- **AC-5.2.1** A letter typed in pencil mode shows in grey italics for every player.
- **AC-5.2.2** Any player can confirm a pencil letter with one action; it then shows as a normal letter.
- **AC-5.2.3** Completion (US-6.4) evaluates pencil and normal letters the same way.

### US-5.3 Clue flag

As a stuck player, I want to flag a clue, so that my team-mates know where help is wanted.

- **AC-5.3.1** Flagging a clue shows a marker on its clue cell for all players and adds a line to the activity feed.
- **AC-5.3.2** The flag clears when every cell of the word is filled.
- **AC-5.3.3** A player holds one flag at a time; a new flag replaces the previous one.

### US-5.4 Chat and reactions

As a player, I want to talk to the room, so that we can share half-ideas without leaving the grid.

- **AC-5.4.1** The room has a text chat. Messages are at most 280 characters and arrive in the same order for everyone.
- **AC-5.4.2** A reaction from a set of 5 appears on a chosen word for 3 seconds.
- **AC-5.4.3** The chat can be collapsed and then shows an unread count.
- **AC-5.4.4** The host can mute a player's chat. Messages are deleted when the room expires.

## E6 Help and validation

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone. Out of scope: generated hints and dictionary lookups.

### US-6.1 Check a letter, a word or the grid

As a player, I want to check what we wrote, so that an early mistake doesn't block the crossing words.

- **AC-6.1.1** A check strikes through each wrong letter in its scope for all players and locks each correct letter.
- **AC-6.1.2** Empty cells in the scope are ignored.
- **AC-6.1.3** The result is computed on the server from the letters in place. The answer itself is not sent.
- **AC-6.1.4** Each check adds a line to the activity feed with the player and the scope.

### US-6.2 Reveal a letter or a word

As a blocked team, we want to reveal a letter or a word, so that the game keeps moving.

- **AC-6.2.1** A revealed cell shows the right letter with a corner marker, is locked and has no author.
- **AC-6.2.2** Reveals draw on a room budget set by the host; the default is 5 letters and 1 word.
- **AC-6.2.3** At zero budget, the reveal controls are disabled and say why.

### US-6.3 Group decision on help

As a host, I want to choose how help is granted, so that the room plays at the difficulty it agreed on.

- **AC-6.3.1** At room creation the host picks a help mode: free, vote or none.
- **AC-6.3.2** In vote mode, a reveal or a grid check needs a yes from more than half of the connected players within 20 seconds. The requester counts as a yes.
- **AC-6.3.3** A vote that fails or times out changes nothing and spends no budget.
- **AC-6.3.4** In none mode, the check and reveal controls are hidden.

### US-6.4 Completion detection

As a team, we want the game to recognise the finished grid, so that we don't have to press anything to win.

- **AC-6.4.1** When the last empty cell is filled and every letter is right, the grid is marked solved for all players within 1 second and input is locked.
- **AC-6.4.2** When the grid is full with at least one wrong letter, all players see "grid full, not yet correct" with no hint of where.
- **AC-6.4.3** On FX-01, entering the 18 letters triggers completion. With the M at (1,2) replaced by N, it does not.

## E7 Completion and recap

The recap credits contributions without turning a cooperative game into a ranking. Out of scope: public leaderboards.

### US-7.1 Shared timer

As a team, we want one timer, so that we can compare our time from one grid to the next.

- **AC-7.1.1** The timer starts at the first letter typed and reads the same for all players, within 1 second.
- **AC-7.1.2** It pauses while no player is connected and resumes at the next connection.
- **AC-7.1.3** Each player can hide it on their own screen.

### US-7.2 End-of-game recap

As a player, I want to see what each of us brought, so that the win feels shared.

- **AC-7.2.1** The recap shows total time, checks used and reveals used.
- **AC-7.2.2** For each player it shows the final correct letters they authored and the words they completed by writing the last missing letter.
- **AC-7.2.3** Revealed letters are credited to nobody. Player letter counts plus revealed letters equal the grid's letter cells: 18 on FX-01.
- **AC-7.2.4** A share link shows the time and the team, and no letter of the solution.

### US-7.3 Game history

As a returning player, I want my finished grids listed, so that I pick a new one and remember the old ones.

- **AC-7.3.1** My history lists each finished grid with its date, time taken and team-mates' nicknames.
- **AC-7.3.2** Replaying a finished grid opens a new room with an empty grid.

## E8 Game modes

Cooperative play is the default and the only MVP mode; these two stories add competition later on the same engine. Out of scope: ranked play and tournaments.

### US-8.1 Race

As a group, we want to race on the same grid, so that we can find out who is fastest.

- **AC-8.1.1** In race mode each player fills a private copy; no letter of another player is ever sent to my browser.
- **AC-8.1.2** I see each opponent's progress as a percentage of filled cells, updated within 2 seconds.
- **AC-8.1.3** The first player with a fully correct grid wins; the others can keep playing and get a finishing rank.
- **AC-8.1.4** Checks and reveals are disabled in race mode.

### US-8.2 Teams

As a larger group, we want two teams racing, so that we keep the cooperation inside each team.

- **AC-8.2.1** The host splits players into 2 teams before the first letter; teams are fixed afterwards.
- **AC-8.2.2** Inside a team, every E3 to E6 rule applies. Between teams, the AC-8.1.1 and AC-8.1.2 rules apply.

## E9 Accounts and resume

The MVP ships with guests only: a guest can do everything needed to finish a grid. Accounts arrive in V1 and only add memory across devices. Out of scope: payments and subscriptions.

### US-9.1 Room resume

As a player, I want to come back to our grid tomorrow, so that a long grid doesn't need one sitting.

- **AC-9.1.1** A room stays open for 30 days after its last edit, then is deleted.
- **AC-9.1.2** Opening the link on another device shows the same letters, timer and hint budget.
- **AC-9.1.3** "My rooms" lists my open rooms with their grid, players and last activity.

### US-9.2 Optional account

As a regular player, I want an account, so that my history follows me across devices.

- **AC-9.2.1** A guest can create an account from inside a room with an emailed link, and keeps the same seat, colour and authorship.
- **AC-9.2.2** No action needed to finish a grid requires an account.
- **AC-9.2.3** Deleting my account removes my personal data within 30 days. Other players' recaps then show "former player".

### US-9.3 Catching up after an absence

As a player who plays at different hours from my friends, I want to see what changed, so that I pick up where the team is.

- **AC-9.3.1** On my return, cells changed since my last visit are highlighted for 5 seconds.
- **AC-9.3.2** The activity feed lists words completed, checks and reveals since my last visit, newest first.

## E10 Quality bar

These criteria apply to every story above and belong in each agent's definition of done.

### US-10.1 Accessibility

As a player using a keyboard or a screen reader, I want the full game, so that I can play with my group.

- **AC-10.1.1** Every action is reachable from the keyboard, with a visible focus.
- **AC-10.1.2** On selecting a cell, a screen reader announces the clue, direction, word length and position. On FX-01 at (2,2) with the down word selected: "Artiste muet, vertical, 4 lettres, lettre 2".
- **AC-10.1.3** Colour is never the only signal: each player's cursor also carries their initials. Text contrast is at least 4.5:1.
- **AC-10.1.4** The interface is in French by default, with every string in a translation file.

### US-10.2 Performance

As a player on a mid-range phone, I want a responsive grid, so that typing never lags.

- **AC-10.2.1** FX-02 is interactive within 2.5 seconds on a mid-range phone over 4G.
- **AC-10.2.2** A typed letter shows locally within 50 ms.
- **AC-10.2.3** With 8 players each typing 2 letters a second, AC-4.1.1 still holds.

### US-10.3 Integrity

As a team, we want a game nobody can shortcut, so that finishing means something.

- **AC-10.3.1** No payload sent to a browser contains an answer letter the room has not earned. An automated test inspects all traffic of a full FX-01 game.
- **AC-10.3.2** The server accepts an edit only if it is one A to Z letter, on a letter cell of the room's grid, from a member of the room.
- **AC-10.3.3** A client sending more than 20 edits a second is throttled.
- **AC-10.3.4** Nicknames and chat are escaped: a nickname containing an HTML tag displays as plain text.

### US-10.4 Privacy and operations

As the product owner, I want minimal data and clear signals, so that we stay compliant and can diagnose a bad game.

- **AC-10.4.1** A guest is stored as a nickname and a random identifier, nothing else. Playing needs no advertising cookie.
- **AC-10.4.2** Room data, chat included, is deleted at room expiry (AC-9.1.1).
- **AC-10.4.3** A dashboard shows rooms created, players per room, completion rate, median solving time, sync latency and disconnection rate.
- **AC-10.4.4** An operator can replay the ordered edits of a room from the logs.

## Open decisions

Four choices are settled for the MVP and ticked below. Three remain open: the grid source, competitive play and the Le Parisien baseline.

- [ ] Grid source: commission an author, license from a publisher, or generate and review? This blocks E1.
- [x] Same-cell rule: decided, last write wins (AC-4.2.1).
- [x] Room size: decided, 8 players per room (AC-3.2.4).
- [x] Identity: decided, guests only for the MVP. Accounts stay in V1 (US-9.2).
- [ ] Competitive play: is E8 wanted at all?
- [x] Platform: decided, web only and responsive on any device (AC-2.1.5).
- [ ] Le Parisien baseline: confirm it from screenshots of the listing, an open grid and its help menu.
