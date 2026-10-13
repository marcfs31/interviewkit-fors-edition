import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import SessionPage from '../../app/(app)/(protected)/session/page';

const mockRefreshStats = vi.fn();
const mockCreateSession = vi.fn();
const mockSubmitAnswer = vi.fn();
const mockSaveCard = vi.fn();
const mockCompleteSession = vi.fn();

vi.mock('@/context/AuthContext', () => ({
  useAuth: () => ({ user: 'tester', refreshStats: mockRefreshStats }),
}));

vi.mock('@/services/sessionService', () => ({
  createSession: (...a: unknown[]) => mockCreateSession(...a),
  submitAnswer: (...a: unknown[]) => mockSubmitAnswer(...a),
  saveCard: (...a: unknown[]) => mockSaveCard(...a),
  completeSession: (...a: unknown[]) => mockCompleteSession(...a),
}));

// Thin stubs: the phases are covered elsewhere; here only the page wiring matters.
vi.mock('@/components/session/SessionSetup', () => ({
  default: ({ onSubmit }: { onSubmit: (s: object) => void }) => (
    <button onClick={() => onSubmit({ rol: 'r', stack: 's', topic: 't', level: 'l' })}>start</button>
  ),
}));
vi.mock('@/components/session/QuestionPhase', () => ({
  default: ({ onSubmit, error }: { onSubmit: () => void; error?: string | null }) => (
    <div data-testid="phase-answering">
      <button onClick={onSubmit}>send</button>
      {error && <p role="alert">{error}</p>}
    </div>
  ),
}));
vi.mock('@/components/session/FeedbackPhase', () => ({
  default: ({ onSave, onDiscard, error }: { onSave: () => void; onDiscard: () => void; error?: string | null }) => (
    <div data-testid="phase-feedback">
      <button onClick={onSave}>save</button>
      <button onClick={onDiscard}>discard</button>
      {error && <p role="alert">{error}</p>}
    </div>
  ),
}));

const CARD = {
  concept: 'c', definition: 'd', explanation: 'e', use_case: 'u',
  avoid_when: 'a', mnemonic: 'm', code: '', code_language: '', tags: [],
};

async function reachFeedback() {
  render(<SessionPage />);
  fireEvent.click(screen.getByText('start'));
  fireEvent.click(await screen.findByText('send'));
  await screen.findByTestId('phase-feedback');
}

describe('SessionPage error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCreateSession.mockResolvedValue({
      session_id: 7, stack: 'React', level: 'Básico', topic: 'Hooks',
      questions: [{ question_id: 1, question: 'Q1', type: 'theory' }],
    });
    mockSubmitAnswer.mockResolvedValue({ feedback: 'fb', result: 'CORRECT', card: CARD });
  });

  it('keeps the feedback screen and shows an alert when saving the card fails', async () => {
    mockSaveCard.mockRejectedValue(new Error('sin conexión'));
    await reachFeedback();

    fireEvent.click(screen.getByText('save'));

    expect(await screen.findByRole('alert')).toHaveTextContent('sin conexión');
    expect(screen.getByTestId('phase-feedback')).toBeInTheDocument();
    expect(screen.queryByTestId('phase-answering')).not.toBeInTheDocument();
    expect(mockSubmitAnswer).toHaveBeenCalledTimes(1);
  });

  it('returns to the question with the error when submitting the answer fails', async () => {
    mockSubmitAnswer.mockRejectedValue(new Error('IA caída'));
    render(<SessionPage />);
    fireEvent.click(screen.getByText('start'));
    fireEvent.click(await screen.findByText('send'));

    expect(await screen.findByRole('alert')).toHaveTextContent('IA caída');
    expect(screen.getByTestId('phase-answering')).toBeInTheDocument();
  });

  it('shows an explicit error, never made-up XP, when completing the session fails, and retries', async () => {
    mockCompleteSession.mockRejectedValueOnce(new Error('500'));
    await reachFeedback();

    fireEvent.click(screen.getByText('discard'));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('No se pudo calcular tu XP.');
    expect(screen.queryByText(/\+0/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\b0 XP/);
    expect(mockRefreshStats).not.toHaveBeenCalled();

    mockCompleteSession.mockResolvedValueOnce({
      xp_earned: 120, total_xp: 620, level: 2, xp_to_next_level: 380,
      progress_in_level: 120, xp_per_level: 500, bonus_applied: false,
    });
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    await waitFor(() => expect(screen.getByText('+120')).toBeInTheDocument());
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(mockCompleteSession).toHaveBeenCalledTimes(2);
    expect(mockRefreshStats).toHaveBeenCalledTimes(1);
  });

  it('ignores a /complete response that arrives after the user started a new session', async () => {
    let resolveComplete: (v: object) => void = () => {};
    mockCompleteSession.mockReturnValueOnce(new Promise((r) => { resolveComplete = r; }));
    await reachFeedback();

    fireEvent.click(screen.getByText('discard'));
    fireEvent.click(await screen.findByRole('button', { name: /Nueva sesión/ }));
    expect(await screen.findByText('start')).toBeInTheDocument();

    resolveComplete({
      xp_earned: 120, total_xp: 620, level: 2, xp_to_next_level: 380,
      progress_in_level: 120, xp_per_level: 500, bonus_applied: false,
    });

    await waitFor(() => expect(mockCompleteSession).toHaveBeenCalledTimes(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.getByText('start')).toBeInTheDocument();
    expect(screen.queryByText('+120')).not.toBeInTheDocument();
    expect(mockRefreshStats).not.toHaveBeenCalled();
  });
});
