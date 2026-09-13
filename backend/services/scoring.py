import math


def points_for_answer(is_correct: bool, time_limit: int, response_time: float) -> int:
    """Server-side scoring: floor remaining seconds, plus 100 for a correct answer."""
    remaining = max(0.0, time_limit - max(0.0, response_time))
    speed_points = math.floor(remaining)
    return speed_points + (100 if is_correct else 0)


def ranking_key(participant):
    # Ascending tuple produces the requested winner ordering.
    last = participant.last_answer_at.isoformat() if participant.last_answer_at else "9999-12-31"
    return (-participant.total_score, -participant.correct_count, participant.total_response_time, last, participant.joined_at.isoformat())
