// Colour contrast measured in the page, for the browser tests of specs 014 and 035:
// the colour helpers, the contrast scan and the focus outline reader of spec 035's
// "Test harness". Both test files read this one file, so they always measure the
// same way. The file only declares; each test file wraps it in a function for
// `page.evaluate` that returns `scanTextContrast()` or `readFocusOutline()`.

// `parseColour` gives [r, g, b, alpha] from a computed colour (rgb() fast path, a
// canvas for any other CSS colour syntax), `over` composites a colour on an opaque
// one, `contrast` is the WCAG 2.x ratio.
const canvas = document.createElement('canvas');
canvas.width = 1;
canvas.height = 1;
const drawing = canvas.getContext('2d', { willReadFrequently: true });
function parseColour(text) {
  const match = text.match(/^rgba?\(([^)]*)\)$/);
  if (match) {
    const parts = match[1].split(/[\s,\/]+/).filter(part => part !== '');
    let alpha = 1;
    if (parts.length > 3) {
      alpha = parts[3].endsWith('%') ? parseFloat(parts[3]) / 100 : Number(parts[3]);
    }
    return [Number(parts[0]), Number(parts[1]), Number(parts[2]), alpha];
  }
  drawing.clearRect(0, 0, 1, 1);
  drawing.fillStyle = '#000000';
  drawing.fillStyle = text;
  drawing.fillRect(0, 0, 1, 1);
  const data = drawing.getImageData(0, 0, 1, 1).data;
  return [data[0], data[1], data[2], data[3] / 255];
}
function over(top, bottom) {
  const alpha = top[3];
  return [
    top[0] * alpha + bottom[0] * (1 - alpha),
    top[1] * alpha + bottom[1] * (1 - alpha),
    top[2] * alpha + bottom[2] * (1 - alpha),
    1,
  ];
}
function channel(value) {
  const scaled = value / 255;
  if (scaled <= 0.03928) {
    return scaled / 12.92;
  }
  return Math.pow((scaled + 0.055) / 1.055, 2.4);
}
function luminance(colour) {
  return 0.2126 * channel(colour[0]) + 0.7152 * channel(colour[1])
    + 0.0722 * channel(colour[2]);
}
function contrast(first, second) {
  const lighter = Math.max(luminance(first), luminance(second));
  const darker = Math.min(luminance(first), luminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}
const WHITE = [255, 255, 255, 1];

// The contrast scan of spec 035's "Test harness". For each element that has a
// direct non-empty text node and is visible (non-zero box, `visibility` `visible`,
// not inside a `visually-hidden` element, not a disabled control, not an
// `option`): the text colour, its alpha multiplied by the opacity of the element
// and of each ancestor, composited over the first non-transparent background among
// the element and its ancestors (white when none, itself composited over white).
// Each measurement also says which roster row (`rowState`) and which remove button
// (`removeFor`, the player id of its row) hold the element, so that a test can
// pick the elements it is about.
function scanTextContrast() {
  const skippedTags = new Set(
    ['SCRIPT', 'STYLE', 'NOSCRIPT', 'OPTION', 'TITLE', 'HEAD']
  );
  const measurements = [];
  for (const element of document.body.querySelectorAll('*')) {
    if (skippedTags.has(element.tagName)) {
      continue;
    }
    let ownText = '';
    for (const node of element.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        ownText += node.textContent;
      }
    }
    ownText = ownText.trim();
    if (ownText === '') {
      continue;
    }
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    if (box.width === 0 || box.height === 0 || style.visibility !== 'visible') {
      continue;
    }
    if (element.closest('.visually-hidden') || element.closest(':disabled')) {
      continue;
    }
    let opacity = 1;
    let background = null;
    for (let node = element; node; node = node.parentElement) {
      const nodeStyle = getComputedStyle(node);
      opacity *= parseFloat(nodeStyle.opacity);
      if (background === null) {
        const candidate = parseColour(nodeStyle.backgroundColor);
        if (candidate[3] > 0) {
          background = candidate;
        }
      }
    }
    const opaqueBackground = background === null ? WHITE : over(background, WHITE);
    const text = parseColour(style.color);
    text[3] = text[3] * opacity;
    const shown = over(text, opaqueBackground);
    const ratio = contrast(shown, opaqueBackground);
    const row = element.closest('[data-testid="roster-player"]');
    const removeButton = element.closest('[data-testid="remove-player"]');
    measurements.push({
      tag: element.tagName,
      testid: element.getAttribute('data-testid'),
      rowState: row === null ? null : row.getAttribute('data-state'),
      removeFor: removeButton === null || row === null
        ? null : row.getAttribute('data-player-id'),
      text: ownText,
      opacity: opacity,
      ratio: ratio,
    });
  }
  return measurements;
}

// The outline of the focused element: its computed style, its width in px and the
// contrast of its colour (composited over white) against white.
function readFocusOutline() {
  const element = document.activeElement;
  const style = getComputedStyle(element);
  const colour = over(parseColour(style.outlineColor), WHITE);
  return {
    style: style.outlineStyle,
    width: parseFloat(style.outlineWidth),
    ratio: contrast(colour, WHITE),
  };
}
