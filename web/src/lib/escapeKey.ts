// The Escape key of the room page's overlays: the Aide menu, the Menu, the
// Salon and the reaction picker each answer Escape pressed while the focus is
// inside them (specs 022, 043).

// Call `onEscape` when Escape is pressed while the focus is inside `element`.
// Returns a function that stops listening.
export function listenForEscape(element: HTMLElement, onEscape: () => void): () => void {
  const onKeyDown = (event: KeyboardEvent): void => {
    if (event.key === 'Escape') {
      event.preventDefault()
      onEscape()
    }
  }
  element.addEventListener('keydown', onKeyDown)
  return () => element.removeEventListener('keydown', onKeyDown)
}
