from openenv.core.env_client import EnvClient
from openenv.core.client_types import StepResult
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState

class CodeBugClient(EnvClient[CodeReviewAction, CodeReviewObservation, CodeReviewState]):
    def _step_payload(self, action: CodeReviewAction) -> dict:
        return {
            "category": action.category,
            "severity": action.severity,
            "line_hint": action.line_hint,
            "comment": action.comment
        }

    def _parse_result(self, payload: dict) -> StepResult:
        obs_data = payload.get("observation", {})
        return StepResult(
            observation=CodeReviewObservation(
                done=payload.get("done", False),
                reward=payload.get("reward"),
                code_snippet=obs_data.get("code_snippet", ""),
                difficulty=obs_data.get("difficulty", ""),
                feedback=obs_data.get("feedback", "")
            ),
            reward=payload.get("reward"),
            done=payload.get("done", False)
        )

    def _parse_state(self, payload: dict) -> CodeReviewState:
        return CodeReviewState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            current_task_idx=payload.get("current_task_idx", 0),
            total_score=payload.get("total_score", 0.0)
        )
