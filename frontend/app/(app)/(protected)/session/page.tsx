"use client";

import { useState, useReducer, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence } from "framer-motion";
import { useAuth } from "@/context/AuthContext";
import { sessionReducer, initialState, type Card } from "@/reducers/sessionReducer";
import {
  createSession,
  submitAnswer,
  saveCard,
  completeSession,
} from "@/services/sessionService";

import { PageContainer } from "@/components/layout/PageContainer";
import SessionSetup from "@/components/session/SessionSetup";
import ProgressIndicator from "@/components/session/ProgressIndicator";
import QuestionPhase from "@/components/session/QuestionPhase";
import FeedbackLoading from "@/components/session/FeedbackLoading";
import FeedbackPhase from "@/components/session/FeedbackPhase";
import SessionComplete from "@/components/session/SessionComplete";

export default function SessionPage() {
  const { user, refreshStats } = useAuth();
  const router = useRouter();
  const [state, dispatch] = useReducer(sessionReducer, initialState);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Guards against calling /complete more than once per session
  const completeCalledRef = useRef(false);

  const handleCreateSession = async (select: { rol: string; stack: string; topic: string; level: string }) => {
    setLoading(true);
    setError(null);

    try {
      const data = await createSession(select);
      dispatch({ type: "INIT_SESSION", payload: data });
      completeCalledRef.current = false;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitAnswer = async () => {
    dispatch({ type: "ANSWER_SUBMITTED" });

    const question = state.questions[state.currentQuestionIndex];

    try {
      const data = await submitAnswer(
        state.session_id as number,
        question.question_id,
        state.currentAnswer
      );
      dispatch({ type: "FEEDBACK_RECEIVED", payload: data });
    } catch (err) {
      dispatch({ type: "SUBMIT_FAILED", payload: err instanceof Error ? err.message : String(err) });
    }
  };

  const handleCardChange = (updatedCard: Card) => {
    dispatch({ type: "UPDATE_CARD", payload: updatedCard });
  };

  const handleSaveCard = async () => {
    const question = state.questions[state.currentQuestionIndex];
    const card = state.card as Card;

    try {
      await saveCard({
        question_id: question.question_id,
        session_id: state.session_id as number,
        concept: card.concept,
        definition: card.definition,
        explanation: card.explanation,
        use_case: card.use_case,
        avoid_when: card.avoid_when,
        mnemonic: card.mnemonic,
        tags: card.tags,
        code: card.code,
        code_language: card.code_language,
      });
    } catch (err) {
      dispatch({ type: "CARD_SAVE_FAILED", payload: "Error al guardar la card: " + (err instanceof Error ? err.message : String(err)) });
      return;
    }

    dispatch({ type: "CARD_SAVED" });
  };

  const sessionId = state.session_id;
  const mountedRef = useRef(true);
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // A late /complete response must not land in a session the user already left
  // ("Nueva sesión" resets session_id while the request is still in flight).
  const sessionIdRef = useRef(sessionId);
  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const runComplete = useCallback(async () => {
    const requestedFor = sessionId;
    const isStale = () => !mountedRef.current || sessionIdRef.current !== requestedFor;
    try {
      const data = await completeSession(requestedFor as number);
      if (isStale()) return;
      dispatch({ type: "SESSION_COMPLETED", payload: data });
      refreshStats();
    } catch (err) {
      if (isStale()) return;
      // Re-arm the guard so the retry button can call /complete again; no XP
      // is invented, the complete screen shows an explicit error instead.
      completeCalledRef.current = false;
      dispatch({ type: "COMPLETE_FAILED", payload: err instanceof Error ? err.message : String(err) });
    }
  }, [sessionId, refreshStats]);

  const handleRetryComplete = () => {
    if (completeCalledRef.current) return;
    completeCalledRef.current = true;
    dispatch({ type: "COMPLETE_RETRYING" });
    runComplete();
  };

  // When the session reaches the "complete" phase, calculate XP and refresh stats
  useEffect(() => {
    if (state.currentPhase !== "complete") return;
    if (completeCalledRef.current || state.completeError) return;
    completeCalledRef.current = true;
    runComplete();
  }, [state.currentPhase, state.completeError, runComplete]);

  if (!state.session_id) {
    return (
      <SessionSetup
        loading={loading}
        error={error}
        onSubmit={handleCreateSession}
      />
    );
  }

  const currentQuestion = state.questions[state.currentQuestionIndex];

  return (
    <PageContainer max="3xl">
        <ProgressIndicator
          currentIndex={state.currentQuestionIndex}
          total={state.questions.length}
          stack={state.stack as string}
          level={state.level as string}
          topic={state.topic ?? undefined}
          questionType={currentQuestion?.type}
        />

        <AnimatePresence mode="wait">
          {state.currentPhase === "answering" && (
            <QuestionPhase
              question={currentQuestion.question}
              questionType={currentQuestion.type}
              stack={state.stack as string}
              answer={state.currentAnswer}
              error={state.error}
              onAnswerChange={(value) =>
                dispatch({ type: "ANSWER_CHANGED", payload: value })
              }
              onSubmit={handleSubmitAnswer}
            />
          )}

          {state.currentPhase === "loading_feedback" && <FeedbackLoading />}

          {state.currentPhase === "waiting_action" && (
            <FeedbackPhase
              feedback={state.feedback}
              result={state.result}
              card={state.card}
              originalCard={state.originalCard}
              onCardChange={handleCardChange}
              onDiscard={() => dispatch({ type: "CARD_DISCARDED" })}
              onSave={handleSaveCard}
              error={state.error}
            />
          )}

          {state.currentPhase === "complete" && (
            <SessionComplete
              totalQuestions={state.questions.length}
              stack={state.stack as string}
              onDashboard={() => router.push("/dashboard")}
              onNewSession={() => {
                completeCalledRef.current = false;
                dispatch({ type: "RESET_SESSION" });
              }}
              xpEarned={state.sessionXpEarned}
              totalXp={state.sessionTotalXp}
              level={state.sessionLevel}
              xpToNextLevel={state.sessionXpToNextLevel}
              xpPerLevel={state.sessionXpPerLevel}
              progressInLevel={state.sessionProgressInLevel}
              bonusApplied={state.sessionBonusApplied}
              loading={!state.sessionCompleteLoaded}
              error={state.completeError}
              onRetry={handleRetryComplete}
            />
          )}
        </AnimatePresence>
    </PageContainer>
  );
}
