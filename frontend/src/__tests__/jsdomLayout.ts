// CodeMirror measures layout through APIs jsdom does not implement.
export function stubLayoutApis(): void {
  const emptyRect = {
    x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0,
    toJSON: () => ({}),
  } as DOMRect;
  const rects = () => ({ length: 0, item: () => null, [Symbol.iterator]: function* () {} }) as unknown as DOMRectList;
  Range.prototype.getBoundingClientRect = () => emptyRect;
  Range.prototype.getClientRects = rects;
  Element.prototype.getClientRects = rects;
}
