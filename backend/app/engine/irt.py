"""
IRT Engine — 3-Parameter Logistic (3PL) model.

P(θ) = c + (1 - c) / (1 + exp(-a(θ - b)))

Default IRT params per question (can be calibrated from response data):
  a = discrimination = 1.0
  b = difficulty (mapped from band)
  c = guessing = 0.25 (4-option MCQ)
"""

import math
from typing import Tuple

# Difficulty band → b parameter mapping
DIFFICULTY_B_MAP = {
    "easy": -1.0,
    "medium": 0.0,
    "hard": 1.5,
}

DEFAULT_A = 1.0   # discrimination
DEFAULT_C = 0.25  # guessing (4-option MCQ)

# θ bounds
THETA_MIN = -4.0
THETA_MAX = 4.0
THETA_STEP_CORRECT = 0.4
THETA_STEP_INCORRECT = 0.3


def prob_correct(theta: float, a: float, b: float, c: float) -> float:
    """3PL probability of a correct response."""
    return c + (1.0 - c) / (1.0 + math.exp(-a * (theta - b)))


def get_irt_params(difficulty_band: str) -> Tuple[float, float, float]:
    """Return (a, b, c) for a given difficulty band."""
    b = DIFFICULTY_B_MAP.get(difficulty_band.lower(), 0.0)
    return DEFAULT_A, b, DEFAULT_C


def update_theta_mle(
    current_theta: float,
    is_correct: bool,
    difficulty_band: str,
    step_override: float = None,
) -> float:
    """
    Simple MLE-inspired θ update.

    A full MLE would iterate the Newton–Raphson update over the response
    vector; here we use a step-size heuristic calibrated to the difficulty
    band so that harder correct answers increase θ more than easy ones.
    """
    a, b, c = get_irt_params(difficulty_band)

    if is_correct:
        # Gain more θ from harder correct answers
        step = step_override or (THETA_STEP_CORRECT * (1.0 + b))
        new_theta = current_theta + max(step, 0.1)
    else:
        # Lose less θ from harder wrong answers (they're expected to be hard)
        step = step_override or (THETA_STEP_INCORRECT * (1.0 - b * 0.3))
        new_theta = current_theta - max(step, 0.1)

    return float(max(THETA_MIN, min(THETA_MAX, new_theta)))


def escalate_difficulty(current: str) -> str:
    order = ["easy", "medium", "hard"]
    idx = order.index(current) if current in order else 1
    return order[min(idx + 1, len(order) - 1)]


def reduce_difficulty(current: str) -> str:
    order = ["easy", "medium", "hard"]
    idx = order.index(current) if current in order else 1
    return order[max(idx - 1, 0)]
