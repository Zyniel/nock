// The icons of Nock (specs/_design/foundation.md « Icons » and specs/_design/cells.md « Player icons », spec 041), as shapes.
//
// A component draws them in an SVG with the stroke attributes of specs/_design/foundation.md « Icons »
// (fill none, stroke currentColor, round caps and joins,
// aria-hidden). The grid draws the flag on a flagged clue and the player icons
// of the Accessibilité mode (spec 042, IconShapes.svelte).

export type IconName =
  | 'undo'
  | 'aide'
  | 'salon'
  | 'clavier'
  | 'menu'
  | 'crayon'
  | 'swap'
  | 'effacer'
  | 'chrono'
  | 'flag'
  | 'chevron-left'
  | 'chevron-right'
  | 'smile'

// One SVG element of an icon: a path, a rectangle, a circle or a polygon.
export type IconShape =
  | { kind: 'path'; d: string }
  | { kind: 'rect'; x: number; y: number; width: number; height: number; rx: number }
  | { kind: 'circle'; cx: number; cy: number; r: number }
  | { kind: 'polygon'; points: string }

// The shapes of specs/_design/foundation.md « Icons », in its order, in a 24 by 24 box.
export const ICONS: Record<IconName, readonly IconShape[]> = {
  undo: [
    { kind: 'path', d: 'M9 14 4 9l5-5' },
    { kind: 'path', d: 'M4 9h10a6 6 0 0 1 0 12h-3' },
  ],
  aide: [
    { kind: 'path', d: 'M9 18h6M10 22h4' },
    {
      kind: 'path',
      d: 'M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z',
    },
  ],
  salon: [{ kind: 'path', d: 'M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z' }],
  clavier: [
    { kind: 'rect', x: 2, y: 6, width: 20, height: 12, rx: 2 },
    { kind: 'path', d: 'M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10' },
  ],
  menu: [{ kind: 'path', d: 'M4 7h16M4 12h16M4 17h16' }],
  crayon: [
    { kind: 'path', d: 'M4 20h4L19 9l-4-4L4 16v4z' },
    { kind: 'path', d: 'M13.5 6.5l4 4' },
  ],
  swap: [{ kind: 'path', d: 'M4 8h14l-3-3M20 16H6l3 3' }],
  effacer: [
    { kind: 'path', d: 'M9 5h11v14H9l-6-7 6-7z' },
    { kind: 'path', d: 'M13 9l4 6M17 9l-4 6' },
  ],
  chrono: [
    { kind: 'circle', cx: 12, cy: 13.5, r: 7.5 },
    { kind: 'path', d: 'M12 10v3.5l2.5 2M9.5 3h5M12 3v3' },
  ],
  flag: [
    { kind: 'path', d: 'M6 21V4' },
    { kind: 'path', d: 'M6 4h12l-3 4.5 3 4.5H6z' },
  ],
  'chevron-left': [{ kind: 'path', d: 'M15 5l-7 7 7 7' }],
  'chevron-right': [{ kind: 'path', d: 'M9 5l7 7-7 7' }],
  smile: [
    { kind: 'circle', cx: 12, cy: 12, r: 9 },
    { kind: 'path', d: 'M8.5 14.5c1.8 2 5.2 2 7 0' },
    { kind: 'path', d: 'M9 9.5h.01M15 9.5h.01' },
  ],
}

// The player icons of the Accessibilité mode (specs/_design/cells.md « Player icons »), by join
// index 0 to 7, in a 10 by 10 box. A rect here has rx 0.
export const PLAYER_ICONS: readonly (readonly IconShape[])[] = [
  // 0, Rond.
  [{ kind: 'circle', cx: 5, cy: 5, r: 4.4 }],
  // 1, Carré.
  [{ kind: 'rect', x: 0.9, y: 0.9, width: 8.2, height: 8.2, rx: 0 }],
  // 2, Triangle.
  [{ kind: 'polygon', points: '5,0.4 9.7,9.3 0.3,9.3' }],
  // 3, Losange.
  [{ kind: 'polygon', points: '5,0.1 9.9,5 5,9.9 0.1,5' }],
  // 4, Étoile.
  [
    {
      kind: 'polygon',
      points: '5,0.2 6.3,3.6 9.9,3.7 7.1,6 8.1,9.6 5,7.5 1.9,9.6 2.9,6 0.1,3.7 3.7,3.6',
    },
  ],
  // 5, Croix.
  [
    {
      kind: 'polygon',
      points:
        '3.3,0.4 6.7,0.4 6.7,3.3 9.6,3.3 9.6,6.7 6.7,6.7 6.7,9.6 3.3,9.6 3.3,6.7 0.4,6.7 0.4,3.3 3.3,3.3',
    },
  ],
  // 6, Cœur.
  [{ kind: 'path', d: 'M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z' }],
  // 7, Sablier.
  [{ kind: 'polygon', points: '0.6,0.6 9.4,0.6 5.6,5 9.4,9.4 0.6,9.4 4.4,5' }],
]

// The Nock mark (the notch at the back of an arrow), filled, in a 10 by 14 box.
export const NOCK_MARK_POINTS: string = '0,0 10,0 10,14 5,10 0,14'
