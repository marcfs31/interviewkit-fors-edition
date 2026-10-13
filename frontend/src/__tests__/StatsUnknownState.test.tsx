import { render, screen, fireEvent } from '@testing-library/react';
import StatsPage from '../../app/(app)/(protected)/stats/page';
import ProfilePage from '../../app/(app)/(protected)/profile/page';
import Navbar from '@/components/Navbar';

const mockRefreshStats = vi.fn();
let authValue: Record<string, unknown>;

vi.mock('@/context/AuthContext', () => ({ useAuth: () => authValue }));
vi.mock('@/components/profile/ChangeUsernameDialog', () => ({ ChangeUsernameDialog: () => null }));
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }));
vi.mock('@/components/stats/ResultsDonut', () => ({ default: () => null }));
vi.mock('@/components/stats/StackBars', () => ({ default: () => null }));

const STATS = {
  total_xp: 1234, level: 3, xp_to_next_level: 266, progress_in_level: 234, xp_per_level: 500,
  results_summary: { correct: 1, partially_correct: 0, incorrect: 0 },
  stacks_stats: [], sessions_count: 4, recent_sessions: [], cards_summary: { total: 0, top_tags: [] },
};

function auth(stats: unknown, statsStatus: string) {
  authValue = { user: 'Marc', stats, statsStatus, refreshStats: mockRefreshStats, logout: vi.fn() };
}

const PAGES = [
  ['Stats page', StatsPage],
  ['Profile page', ProfilePage],
] as const;

describe.each(PAGES)('%s with unknown stats', (_name, Page) => {
  beforeEach(() => vi.clearAllMocks());

  it('on error shows an alert with a working Reintentar and no default numbers', () => {
    auth(null, 'error');
    render(<Page />);

    expect(screen.getByRole('alert')).toHaveTextContent('No se pudieron cargar tus estadísticas.');
    expect(document.body.textContent).not.toMatch(/Nv 1|\b0 XP|Aún no tienes/);
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(mockRefreshStats).toHaveBeenCalledTimes(1);
  });

  it('while loading shows a busy placeholder, no alert and no numbers', () => {
    auth(null, 'loading');
    render(<Page />);

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByText('Cargando estadísticas…')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Nv 1|\b0 XP/);
  });

  it('with real stats renders the values and no error', () => {
    auth(STATS, 'ok');
    render(<Page />);

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(document.body.textContent).toMatch(/1.?234/);
  });
});

describe('Navbar XP chip', () => {
  it.each([['loading'], ['error']])('is hidden while stats are %s', (status) => {
    auth(null, status);
    render(<Navbar />);
    expect(document.body.textContent).not.toMatch(/Nv \d|\bXP\b/);
  });

  it('shows level and XP once stats are known', () => {
    auth(STATS, 'ok');
    render(<Navbar />);
    expect(screen.getAllByText('Nv 3').length).toBeGreaterThan(0);
  });
});
