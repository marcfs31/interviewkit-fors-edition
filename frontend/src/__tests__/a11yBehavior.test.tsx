import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { stubLayoutApis } from './jsdomLayout';
import CardEditor from '@/components/session/CardEditor';
import QuestionPhase from '@/components/session/QuestionPhase';
import StackSelector from '@/components/StackSelector';
import Navbar from '@/components/Navbar';
import { ChangeUsernameDialog } from '@/components/profile/ChangeUsernameDialog';
import { updateProfile } from '@/services/profileService';

const mocks = vi.hoisted(() => ({ pathname: '/dashboard' }));

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    user: 'marc',
    stats: null,
    logout: vi.fn(),
    updateUser: vi.fn(),
    refreshStats: vi.fn(),
  }),
}));
vi.mock('@/context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() }),
}));
vi.mock('@/services/profileService', () => ({ updateProfile: vi.fn() }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => mocks.pathname,
}));

beforeAll(stubLayoutApis);

const stacks = {
  rol: { Frontend: ['React', 'JavaScript'], Backend: ['Python'] },
  topic: { React: ['Hooks'] },
  level: ['Junior', 'Mid', 'Senior'],
};

describe('CardEditor form labels', () => {
  const card = { concept: 'c', definition: 'd', explanation: 'e', use_case: 'u', avoid_when: 'a', mnemonic: 'm', tags: ['uno', 'dos'] };

  function renderEditing() {
    render(<CardEditor card={card} onChange={vi.fn()} originalCard={card} />);
    fireEvent.click(screen.getByRole('button', { name: /Editar/ }));
    return screen.findByPlaceholderText('Nombre del concepto…');
  }

  it('associates every visible label with its control', async () => {
    await renderEditing();

    for (const name of [/^Concepto$/, /^Definición/, /^Explicación$/, /^Usar cuando$/, /^Evitar cuando/, /^Mnemotecnia/]) {
      expect(screen.getByLabelText(name)).toBeInTheDocument();
    }
    expect(screen.getByLabelText(/^Concepto$/)).toHaveValue('c');
  });

  it('names each tag input by its position', async () => {
    await renderEditing();

    expect(screen.getByRole('textbox', { name: 'Etiqueta 1' })).toHaveValue('uno');
    expect(screen.getByRole('textbox', { name: 'Etiqueta 2' })).toHaveValue('dos');
  });

  it('uses correctly accented copy', async () => {
    await renderEditing();

    expect(screen.getByText(/^Definición/)).toBeInTheDocument();
    expect(screen.getByText('Explicación')).toBeInTheDocument();
    expect(screen.getByText('Código')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Añadir tag' })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Definicion|Explicacion|Codigo|Anadir/);
  });
});

describe('toggle buttons expose their state', () => {
  it('Ver / Editar in CardEditor', () => {
    const card = { concept: 'c' };
    render(<CardEditor card={card} onChange={vi.fn()} originalCard={card} />);
    const ver = screen.getByRole('button', { name: /Ver/ });
    const editar = screen.getByRole('button', { name: /Editar/ });

    expect(ver).toHaveAttribute('aria-pressed', 'true');
    expect(editar).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(editar);

    expect(ver).toHaveAttribute('aria-pressed', 'false');
    expect(editar).toHaveAttribute('aria-pressed', 'true');
  });

  it('Texto / Código in QuestionPhase', () => {
    render(
      <QuestionPhase question="¿Qué es un closure?" questionType="theory" stack="JavaScript" answer="" onAnswerChange={vi.fn()} onSubmit={vi.fn()} />
    );
    const texto = screen.getByRole('button', { name: /Texto/ });
    const codigo = screen.getByRole('button', { name: /Código/ });

    expect(texto).toHaveAttribute('aria-pressed', 'true');
    expect(codigo).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(codigo);

    expect(texto).toHaveAttribute('aria-pressed', 'false');
    expect(codigo).toHaveAttribute('aria-pressed', 'true');
  });

  it('options in StackSelector mark only the chosen one', async () => {
    render(<StackSelector onSubmit={vi.fn()} stacks={stacks} />);

    fireEvent.click(screen.getByRole('button', { name: 'Frontend' }));
    await screen.findByRole('heading', { name: '¿Qué tecnología quieres practicar?' });
    fireEvent.click(screen.getByRole('button', { name: /Atrás/ }));

    expect(await screen.findByRole('button', { name: 'Frontend' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'Backend' })).toHaveAttribute('aria-pressed', 'false');
  });
});

describe('StackSelector focus management', () => {
  it('moves focus to the new step heading after choosing an option', async () => {
    render(<StackSelector onSubmit={vi.fn()} stacks={stacks} />);
    expect(document.body).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: 'Frontend' }));

    const heading = await screen.findByRole('heading', { name: '¿Qué tecnología quieres practicar?' });
    await waitFor(() => expect(heading).toHaveFocus());
    expect(heading).toHaveAttribute('tabindex', '-1');
  });

  it('moves focus to the previous step heading on Atrás', async () => {
    render(<StackSelector onSubmit={vi.fn()} stacks={stacks} />);
    fireEvent.click(screen.getByRole('button', { name: 'Frontend' }));
    await screen.findByRole('heading', { name: '¿Qué tecnología quieres practicar?' });

    fireEvent.click(screen.getByRole('button', { name: /Atrás/ }));

    const heading = await screen.findByRole('heading', { name: '¿Cuál es tu rol?' });
    await waitFor(() => expect(heading).toHaveFocus());
  });

  it('does not steal focus on first render', () => {
    render(<StackSelector onSubmit={vi.fn()} stacks={stacks} />);

    expect(screen.getByRole('heading', { name: '¿Cuál es tu rol?' })).not.toHaveFocus();
  });
});

describe('Navbar links', () => {
  it('renders real links and marks only the current route', () => {
    mocks.pathname = '/stats';
    render(<Navbar />);
    const nav = screen.getAllByRole('navigation')[0];

    const stats = Array.from(nav.querySelectorAll('a')).find((a) => a.textContent === 'Stats');
    const dashboard = Array.from(nav.querySelectorAll('a')).find((a) => a.textContent === 'Dashboard');
    expect(stats).toHaveAttribute('href', '/stats');
    expect(stats).toHaveAttribute('aria-current', 'page');
    expect(dashboard).toHaveAttribute('href', '/dashboard');
    expect(dashboard).not.toHaveAttribute('aria-current');
  });

  it('links the logo to the home page', () => {
    render(<Navbar />);

    expect(screen.getByRole('link', { name: 'InterviewKit, ir al inicio' })).toHaveAttribute('href', '/');
  });
});

describe('ChangeUsernameDialog', () => {
  it('labels the input and announces errors', async () => {
    vi.mocked(updateProfile).mockRejectedValueOnce(new Error('Ese nombre ya existe'));
    render(<ChangeUsernameDialog isOpenChangeUserName setIsOpenChangeUserName={vi.fn()} />);

    expect(screen.getByLabelText('Nombre de usuario')).toHaveValue('marc');
    fireEvent.click(screen.getByRole('button', { name: 'Guardar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Ese nombre ya existe');
  });

  it('shows no alert before anything fails', () => {
    render(<ChangeUsernameDialog isOpenChangeUserName setIsOpenChangeUserName={vi.fn()} />);

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
