// Initial open state for side panels: open only when the window is wide enough.
export function isWiderThan(px) {
  return window.matchMedia(`(min-width: ${px}px)`).matches;
}
