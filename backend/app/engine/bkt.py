"""
BKT Engine — Bayesian Knowledge Tracing.

Per-skill parameters:
  P(L0) = 0.10   initial mastery prior
  P(T)  = 0.30   learning/transition probability
  P(G)  = 0.20   lucky guess probability (tuned below 0.25 for 4-opt MCQ)
  P(S)  = 0.10   careless slip probability

Mastery threshold  : P(L) >= 0.95 → Mastered
Foundational gap   : P(L) <= 0.30 after >= 2 attempts → Gap
Lucky guess flag   : P(L) < 0.20 before a correct answer
"""

from typing import Tuple

# Default BKT parameters (can be overridden per skill if calibrated)
P_INIT = 0.10
P_TRANSIT = 0.30
P_GUESS = 0.20
P_SLIP = 0.10

MASTERY_THRESHOLD = 0.95
GAP_THRESHOLD = 0.30
LUCKY_GUESS_PRIOR = 0.20
MIN_ATTEMPTS_FOR_GAP = 2


def bkt_update(prior: float, is_correct: bool) -> float:
    """
    Update P(mastery) given a response.

    Returns the new posterior P(L).
    """
    prior = max(0.001, min(0.999, prior))   # numerical safety

    if is_correct:
        # P(L | correct) = P(L)*P(1-S) / [P(L)*(1-S) + (1-P(L))*P(G)]
        numerator = prior * (1.0 - P_SLIP)
        denominator = numerator + (1.0 - prior) * P_GUESS
        posterior = numerator / denominator if denominator > 0 else prior
        
        # Student answered correctly, so apply learning transition (chance of transition to learned state)
        new_p = posterior + (1.0 - posterior) * P_TRANSIT
        # On a correct answer, mastery must increase or stay the same
        new_p = max(prior, new_p)
    else:
        # P(L | incorrect) = P(L)*P(S) / [P(L)*P(S) + (1-P(L))*(1-P(G))]
        numerator = prior * P_SLIP
        denominator = numerator + (1.0 - prior) * (1.0 - P_GUESS)
        posterior = numerator / denominator if denominator > 0 else prior
        
        # Student answered incorrectly: they did NOT transition to the learned state,
        # so we do NOT apply P_TRANSIT. Mastery must decrease or stay the same.
        new_p = min(prior, posterior)

    return float(max(0.001, min(0.999, new_p)))


def is_mastered(p_mastery: float) -> bool:
    return p_mastery >= MASTERY_THRESHOLD


def is_foundational_gap(p_mastery: float, attempts: int) -> bool:
    return p_mastery <= GAP_THRESHOLD and attempts >= MIN_ATTEMPTS_FOR_GAP


def is_lucky_guess(prior_before_response: float, is_correct: bool) -> bool:
    """True if the student answered correctly but had a very low mastery prior."""
    return is_correct and prior_before_response < LUCKY_GUESS_PRIOR


def is_careless_slip(prior_before_response: float, is_correct: bool) -> bool:
    """True if the student answered incorrectly but had high mastery (likely a slip)."""
    return not is_correct and prior_before_response >= 0.70


def mastery_label(p: float) -> str:
    if p >= MASTERY_THRESHOLD:
        return "Mastered"
    elif p >= 0.50:
        return "Developing"
    else:
        return "Gap"
