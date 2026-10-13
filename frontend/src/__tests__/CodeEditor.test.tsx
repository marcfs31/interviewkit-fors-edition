import { render } from '@testing-library/react';
import { EditorView } from '@codemirror/view';
import CodeEditor from '@/components/CodeEditor';

// CodeMirror measures layout through APIs jsdom does not implement.
beforeAll(() => {
  const emptyRect = {
    x: 0, y: 0, top: 0, left: 0, right: 0, bottom: 0, width: 0, height: 0,
    toJSON: () => ({}),
  } as DOMRect;
  const rects = () => ({ length: 0, item: () => null, [Symbol.iterator]: function* () {} }) as unknown as DOMRectList;
  Range.prototype.getBoundingClientRect = () => emptyRect;
  Range.prototype.getClientRects = rects;
  Element.prototype.getClientRects = rects;
});

function viewOf(container: HTMLElement): EditorView {
  const dom = container.querySelector<HTMLElement>('.cm-editor');
  const view = dom && EditorView.findFromDOM(dom);
  if (!view) throw new Error('EditorView not mounted');
  return view;
}

describe('CodeEditor onChange', () => {
  it('calls the latest onChange after a rerender, not the first one', () => {
    const handlerA = vi.fn();
    const handlerB = vi.fn();
    const { container, rerender } = render(<CodeEditor value="" onChange={handlerA} />);
    rerender(<CodeEditor value="" onChange={handlerB} />);

    viewOf(container).dispatch({ changes: { from: 0, insert: 'const x = 1;' } });

    expect(handlerB).toHaveBeenCalledTimes(1);
    expect(handlerB).toHaveBeenCalledWith('const x = 1;');
    expect(handlerA).not.toHaveBeenCalled();
  });

  it('does not call onChange when the document is unchanged', () => {
    const handler = vi.fn();
    const { container } = render(<CodeEditor value="abc" onChange={handler} />);

    viewOf(container).dispatch({ selection: { anchor: 1 } });

    expect(handler).not.toHaveBeenCalled();
  });

  it('keeps the same editor view across rerenders', () => {
    const { container, rerender } = render(<CodeEditor value="" onChange={vi.fn()} />);
    const first = viewOf(container);
    rerender(<CodeEditor value="" onChange={vi.fn()} />);

    expect(viewOf(container)).toBe(first);
  });
});
