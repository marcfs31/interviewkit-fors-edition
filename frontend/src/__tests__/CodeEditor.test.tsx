import { render, screen } from '@testing-library/react';
import { EditorView } from '@codemirror/view';
import CodeEditor from '@/components/CodeEditor';
import { stubLayoutApis } from './jsdomLayout';

beforeAll(stubLayoutApis);

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

describe('CodeEditor accessibility', () => {
  const HINT = 'Pulsa Esc y luego Tab para salir del editor';

  it('names the editing surface itself, with no wrapper textbox around it', () => {
    const { container } = render(<CodeEditor value="" onChange={vi.fn()} ariaLabel="Editor de prueba" />);

    const textbox = screen.getByRole('textbox', { name: 'Editor de prueba' });
    expect(textbox).toHaveClass('cm-content');
    expect(container.querySelectorAll('[role="textbox"]')).toHaveLength(1);
  });

  it('shows the keyboard-exit hint and links it to the editing surface', () => {
    render(<CodeEditor value="" onChange={vi.fn()} />);

    const hint = screen.getByText(HINT);
    expect(hint.id).not.toBe('');
    expect(screen.getByRole('textbox')).toHaveAttribute('aria-describedby', hint.id);
  });

  it('gives each editor its own hint id when several are on the page', () => {
    render(
      <>
        <CodeEditor value="" onChange={vi.fn()} ariaLabel="Uno" />
        <CodeEditor value="" onChange={vi.fn()} ariaLabel="Dos" />
      </>
    );

    const hints = screen.getAllByText(HINT);
    expect(hints[0].id).not.toBe(hints[1].id);
    expect(screen.getByRole('textbox', { name: 'Dos' })).toHaveAttribute('aria-describedby', hints[1].id);
  });

  const press = (target: HTMLElement, key: string, keyCode: number) => {
    const event = new KeyboardEvent('keydown', { key, keyCode, bubbles: true, cancelable: true });
    target.dispatchEvent(event);
    return event;
  };

  it('keeps Tab for indenting, but Esc then Tab leaves the editor', () => {
    const { container } = render(<CodeEditor value="x" onChange={vi.fn()} />);
    const content = viewOf(container).contentDOM;

    expect(press(content, 'Tab', 9).defaultPrevented).toBe(true);
    press(content, 'Escape', 27);
    expect(press(content, 'Tab', 9).defaultPrevented).toBe(false);
  });

  it('traps Tab again once another key is typed after Esc', () => {
    const { container } = render(<CodeEditor value="x" onChange={vi.fn()} />);
    const content = viewOf(container).contentDOM;

    press(content, 'Escape', 27);
    press(content, 'a', 65);
    expect(press(content, 'Tab', 9).defaultPrevented).toBe(true);
  });
});
