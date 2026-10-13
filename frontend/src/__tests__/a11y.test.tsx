import { render, screen, fireEvent } from '@testing-library/react';
import { expectNoA11yViolations } from './a11y';
import { stubLayoutApis } from './jsdomLayout';
import CodeEditor from '@/components/CodeEditor';
import CardEditor from '@/components/session/CardEditor';
import StackSelector from '@/components/StackSelector';
import Navbar from '@/components/Navbar';
import { ChangeUsernameDialog } from '@/components/profile/ChangeUsernameDialog';
import LoginPage from '../../app/(app)/login/page';

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({
    user: 'marc',
    stats: { level: 2, total_xp: 120, xp_to_next_level: 80 },
    logout: vi.fn(),
    login: vi.fn(),
    updateUser: vi.fn(),
    refreshStats: vi.fn(),
  }),
}));
vi.mock('@/context/ThemeContext', () => ({
  useTheme: () => ({ theme: 'dark', toggleTheme: vi.fn() }),
}));
vi.mock('@/services/profileService', () => ({ updateProfile: vi.fn() }));
vi.mock('@/services/authService', () => ({ loginUser: vi.fn() }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
  usePathname: () => '/dashboard',
}));

beforeAll(stubLayoutApis);

const stacks = {
  rol: { Frontend: ['React', 'JavaScript'], Backend: ['Python'] },
  topic: { React: ['Hooks'] },
  level: ['Junior', 'Mid', 'Senior'],
};

const card = {
  concept: 'useEffect',
  definition: 'Hook de efectos',
  explanation: 'Sincroniza un componente con un sistema externo.',
  use_case: 'Suscripciones',
  avoid_when: 'Derivar estado',
  mnemonic: 'Efecto = fuera',
  code: 'useEffect(() => {}, [])',
  code_language: 'javascript',
  tags: ['react', 'hooks'],
};

describe('axe: no accessibility violations', () => {
  it('CardEditor in view mode', async () => {
    const { container } = render(<CardEditor card={card} onChange={vi.fn()} originalCard={card} />);
    await expectNoA11yViolations(container);
  });

  it('CardEditor in edit mode', async () => {
    const { container } = render(<CardEditor card={card} onChange={vi.fn()} originalCard={card} />);
    fireEvent.click(screen.getByRole('button', { name: /Editar/ }));
    await screen.findByPlaceholderText('Nombre del concepto…');
    await expectNoA11yViolations(container);
  });

  it('StackSelector', async () => {
    const { container } = render(<StackSelector onSubmit={vi.fn()} stacks={stacks} />);
    await expectNoA11yViolations(container);
  });

  it('Navbar', async () => {
    const { container } = render(<Navbar />);
    await expectNoA11yViolations(container);
  });

  it('ChangeUsernameDialog', async () => {
    render(<ChangeUsernameDialog isOpenChangeUserName setIsOpenChangeUserName={vi.fn()} />);
    await screen.findByRole('dialog');
    await expectNoA11yViolations(document.body);
  });

  it('login page', async () => {
    const { container } = render(<LoginPage />);
    await expectNoA11yViolations(container);
  });

  it('CodeEditor', async () => {
    const { container } = render(<CodeEditor value="const a = 1;" onChange={vi.fn()} />);
    await expectNoA11yViolations(container);
  });

  it('the helper reports a violation instead of passing silently (negative case)', async () => {
    const { container } = render(<input />);
    await expect(expectNoA11yViolations(container)).rejects.toThrow(/label/);
  });
});
