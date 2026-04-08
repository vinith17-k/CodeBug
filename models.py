from typing import Optional
from openenv.core.env_server import Action, Observation, State

class CodeReviewAction(Action):
    category: str          # 'security' | 'logic' | 'style' | 'approve'
    severity: int          # 1-5 (5 = most severe)
    line_hint: Optional[int] = None
    comment: str = ""      # Short explanation

class CodeReviewObservation(Observation):
    code_snippet: str = ""
    difficulty: str = ""   # 'easy' | 'medium' | 'hard'
    feedback: str = ""

class CodeReviewState(State):
    episode_id: str = ""
    step_count: int = 0
    current_task_idx: int = 0
    total_score: float = 0.0
