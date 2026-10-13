import { sessionReducer, initialState, type Card } from '@/reducers/sessionReducer';

type Action = Parameters<typeof sessionReducer>[1];

const QUESTIONS = [
  { question_id: 1, question: 'T1', type: 'theory' as const },
  { question_id: 2, question: 'T2', type: 'theory' as const },
  { question_id: 3, question: 'C1', type: 'code' as const },
  { question_id: 4, question: 'C2', type: 'code' as const },
  { question_id: 5, question: 'C3', type: 'code' as const },
];

const CARD = { concept: 'x' } as Card;

function run(actions: Action[]) {
  return actions.reduce(sessionReducer, initialState);
}

const start: Action = {
  type: 'INIT_SESSION',
  payload: { session_id: 1, stack: 'React', level: 'Básico', topic: 'Hooks', questions: QUESTIONS },
};

describe('sessionReducer with 5 questions (2 theory + 3 code)', () => {
  it('initializes the five questions in order, theory first', () => {
    const state = run([start]);
    expect(state.questions).toHaveLength(5);
    expect(state.questions.map((q) => q.type)).toEqual(['theory', 'theory', 'code', 'code', 'code']);
    expect(state.currentQuestionIndex).toBe(0);
    expect(state.currentPhase).toBe('answering');
  });

  it('advances through every question and completes only after the fifth', () => {
    let state = run([start]);
    for (let i = 0; i < 4; i++) {
      state = sessionReducer(state, { type: 'CARD_DISCARDED' });
      expect(state.currentQuestionIndex).toBe(i + 1);
      expect(state.currentPhase).toBe('answering');
    }
    state = sessionReducer(state, { type: 'CARD_DISCARDED' });
    expect(state.currentPhase).toBe('complete');
  });

  it('keeps the answer and feedback of each question separate', () => {
    let state = run([start]);
    for (let i = 0; i < 5; i++) {
      state = sessionReducer(state, { type: 'ANSWER_CHANGED', payload: `answer ${i}` });
      state = sessionReducer(state, { type: 'ANSWER_SUBMITTED' });
      state = sessionReducer(state, {
        type: 'FEEDBACK_RECEIVED',
        payload: { feedback: `feedback ${i}`, result: 'CORRECT', card: CARD },
      });
      state = sessionReducer(state, { type: 'CARD_SAVED' });
    }
    expect(state.currentPhase).toBe('complete');
    expect(state.questions.map((q) => q.answer)).toEqual([0, 1, 2, 3, 4].map((i) => `answer ${i}`));
    expect(state.questions.map((q) => q.feedback)).toEqual([0, 1, 2, 3, 4].map((i) => `feedback ${i}`));
  });
});

describe('sessionReducer error paths', () => {
  const toFeedback = (): ReturnType<typeof run> =>
    run([
      start,
      { type: 'ANSWER_CHANGED', payload: 'my answer' },
      { type: 'ANSWER_SUBMITTED' },
      { type: 'FEEDBACK_RECEIVED', payload: { feedback: 'fb', result: 'CORRECT', card: CARD } },
    ]);

  it('SUBMIT_FAILED returns to answering with the answer kept and the error set', () => {
    const state = run([
      start,
      { type: 'ANSWER_CHANGED', payload: 'my answer' },
      { type: 'ANSWER_SUBMITTED' },
      { type: 'SUBMIT_FAILED', payload: 'boom' },
    ]);
    expect(state.currentPhase).toBe('answering');
    expect(state.currentAnswer).toBe('my answer');
    expect(state.error).toBe('boom');
  });

  it('CARD_SAVE_FAILED keeps waiting_action with the edited card and feedback intact', () => {
    let state = toFeedback();
    state = sessionReducer(state, { type: 'UPDATE_CARD', payload: { concept: 'edited' } });
    state = sessionReducer(state, { type: 'CARD_SAVE_FAILED', payload: 'no se pudo guardar' });
    expect(state.currentPhase).toBe('waiting_action');
    expect(state.card?.concept).toBe('edited');
    expect(state.feedback).toBe('fb');
    expect(state.result).toBe('CORRECT');
    expect(state.currentQuestionIndex).toBe(0);
    expect(state.error).toBe('no se pudo guardar');
  });

  it('clears a card-save error once the card is saved or discarded', () => {
    const failed = sessionReducer(toFeedback(), { type: 'CARD_SAVE_FAILED', payload: 'x' });
    expect(sessionReducer(failed, { type: 'CARD_SAVED' }).error).toBeNull();
    expect(sessionReducer(failed, { type: 'CARD_DISCARDED' }).error).toBeNull();
  });

  it('clears a card-save error when the user edits the card again', () => {
    const failed = sessionReducer(toFeedback(), { type: 'CARD_SAVE_FAILED', payload: 'x' });
    expect(sessionReducer(failed, { type: 'UPDATE_CARD', payload: { concept: 'y' } }).error).toBeNull();
  });

  it('COMPLETE_FAILED stays in complete without inventing XP and COMPLETE_RETRYING clears it', () => {
    const complete = run([start, ...Array(5).fill({ type: 'CARD_DISCARDED' })]);
    expect(complete.currentPhase).toBe('complete');
    const failed = sessionReducer(complete, { type: 'COMPLETE_FAILED', payload: 'down' });
    expect(failed.currentPhase).toBe('complete');
    expect(failed.completeError).toBe('down');
    expect(failed.sessionCompleteLoaded).toBe(false);
    expect(failed.sessionXpEarned).toBe(0);
    const retrying = sessionReducer(failed, { type: 'COMPLETE_RETRYING' });
    expect(retrying.completeError).toBeNull();
    expect(retrying.sessionCompleteLoaded).toBe(false);
    const done = sessionReducer(retrying, { type: 'SESSION_COMPLETED', payload: { xp_earned: 120 } });
    expect(done.sessionCompleteLoaded).toBe(true);
    expect(done.completeError).toBeNull();
  });
});
