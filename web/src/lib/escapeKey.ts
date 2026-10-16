// The Escape key of the room page's popovers: the chat panel and the reaction
// picker each close when Escape is pressed while the focus is inside them
// (spec 022).

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
