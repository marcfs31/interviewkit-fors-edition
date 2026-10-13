### Fixed
- A grading the AI returns without a valid result, feedback or card is now rejected with a retryable error instead of being saved as "partially correct" (50 XP) with canned feedback.
- A new session is no longer padded with generic "closures" or "array" questions when the AI returns too few: it fails and can be retried, so every question matches the chosen stack.
- Blank or non-text answers are rejected before reaching the AI, and resubmitting an answer clears its previous grade, so a failed re-grade can no longer earn XP for the old one.
