// The overlays of the room: the Aide menu and the Menu (one popover at a time),
// the Salon, and the reaction picker. Plain functions: no DOM and no runes. The
// page keeps the state and asks `overlaysAfter` what each action leaves open
// (spec 043: in the sheet layout one overlay shows at a time; in the column
// layout the popovers and the picker leave the Salon column as it is).

export type Layout = 'sheet' | 'column'
export type Popover = 'aide' | 'menu'

export interface OverlayState {
  popover: Popover | null
  // The Salon has one state per layout: the sheet starts closed, the column
  // remembers the player's choice.
  isSheetSalonOpen: boolean
  isColumnSalonOpen: boolean
  isPickerOpen: boolean
}

export type OverlayAction =
  // « Aide » or « Menu »: a second press on the open popover closes it.
  | { kind: 'togglePopover'; popover: Popover }
  | { kind: 'closePopover' }
  // Open or close the Salon of the current layout.
  | { kind: 'setSalon'; isOpen: boolean }
  // « Réagir »: a second press closes the picker.
  | { kind: 'togglePicker' }
  | { kind: 'closePicker' }
  // A tap or a click on the scrim.
  | { kind: 'scrim' }
  // The layout changed.
  | { kind: 'layoutChanged' }
  // The room was deleted: the room-gone dialog covers the page.
  | { kind: 'roomGone' }
  // A Tab moved the focus; `leftMenu` and `leftSalon` say whether the focus is
  // now outside the open menu and outside the Salon sheet.
  | { kind: 'tabLeft'; leftMenu: boolean; leftSalon: boolean }

// The overlays left open after `action`. The state it gets is not changed.
export function overlaysAfter(
  state: OverlayState,
  action: OverlayAction,
  layout: Layout,
): OverlayState {
  switch (action.kind) {
    case 'togglePopover':
      return afterTogglePopover(state, action.popover, layout)
    case 'closePopover':
      return { ...state, popover: null }
    case 'setSalon':
      return afterSetSalon(state, action.isOpen, layout)
    case 'togglePicker':
      return afterTogglePicker(state, layout)
    case 'closePicker':
      return { ...state, isPickerOpen: false }
    case 'scrim':
      return { ...state, popover: null, isSheetSalonOpen: false }
    case 'layoutChanged':
      return { ...state, popover: null, isPickerOpen: false, isSheetSalonOpen: false }
    case 'roomGone':
      return { ...state, popover: null, isSheetSalonOpen: false, isPickerOpen: false }
    case 'tabLeft':
      return afterTabLeft(state, action.leftMenu, action.leftSalon)
  }
}

function afterTogglePopover(state: OverlayState, popover: Popover, layout: Layout): OverlayState {
  if (state.popover === popover) {
    return { ...state, popover: null }
  }
  const opened = { ...state, popover, isPickerOpen: false }
  if (layout === 'sheet') {
    opened.isSheetSalonOpen = false
  }
  return opened
}

function afterSetSalon(state: OverlayState, isOpen: boolean, layout: Layout): OverlayState {
  if (layout === 'column') {
    return { ...state, isColumnSalonOpen: isOpen }
  }
  const changed = { ...state, isSheetSalonOpen: isOpen }
  if (isOpen) {
    changed.popover = null
    changed.isPickerOpen = false
  }
  return changed
}

function afterTogglePicker(state: OverlayState, layout: Layout): OverlayState {
  if (state.isPickerOpen) {
    return { ...state, isPickerOpen: false }
  }
  const opened = { ...state, isPickerOpen: true, popover: null }
  if (layout === 'sheet') {
    opened.isSheetSalonOpen = false
  }
  return opened
}

function afterTabLeft(state: OverlayState, leftMenu: boolean, leftSalon: boolean): OverlayState {
  const changed = { ...state }
  if (state.popover !== null && leftMenu) {
    changed.popover = null
  }
  if (state.isSheetSalonOpen && leftSalon) {
    changed.isSheetSalonOpen = false
  }
  return changed
}

// Whether the Salon shows in this layout.
export function isSalonOpen(state: OverlayState, layout: Layout): boolean {
  return layout === 'sheet' ? state.isSheetSalonOpen : state.isColumnSalonOpen
}

// The scrim covers the page under the top bar while a popover or the Salon
// sheet is open (sheet layout only). The picker has none.
export function isScrimShown(state: OverlayState, layout: Layout): boolean {
  return layout === 'sheet' && (state.popover !== null || isSalonOpen(state, layout))
}
