from typing import Optional
from openenv.core.env_server import Action, Observation, State

class CodeReviewAction(Action):
    category: str      # E.g., 'security', 'logic', 'style', 'approve'
    severity: int      # 1 to 5 (5 is most severe)
    line_hint: Optional[int]
    comment: str       # Short explanation of the bug

class CodeReviewObservation(Observation):
    code_snippet: str
    difficulty: str    # 'easy', 'medium', 'hard'
    feedback: str      # Message to the agent

class CodeReviewState(State):
    current_task_idx: int = 0
    total_score: float = 0.0
