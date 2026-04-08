import uuid
from openenv.core.env_server import Environment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState


class CodeBugEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    TASKS = [
        {
            "difficulty": "easy",
            "snippet": (
                "def transfer(from_account, to_account, amount):\n"
                "    if from_account.balance > amount:\n"
                "        from_account.balance -= amount\n"
                "        to_account.balance += amount\n"
                "        return True\n"
                "    return False"
            ),
            "truth": {"category": "logic", "severity": 4, "line_hint": 2},
        },
        {
            "difficulty": "medium",
            "snippet": (
                "def find_max(numbers):\n"
                "    if not numbers:\n"
                "        return None\n"
                "    max_val = numbers[0]\n"
                "    for i in range(len(numbers) - 1):\n"
                "        if numbers[i] > max_val:\n"
                "            max_val = numbers[i]\n"
                "    return max_val"
            ),
            "truth": {"category": "logic", "severity": 3, "line_hint": 5},
        },
        {
            "difficulty": "hard",
            "snippet": (
                "def login(username, password):\n"
                "    query = f\"SELECT * FROM users WHERE username = '{username}'"
                " AND password = '{password}'\"\n"
                "    user = db.execute(query)\n"
                "    if user:\n"
                "        return True\n"
                "    return False"
            ),
            "truth": {"category": "security", "severity": 5, "line_hint": 2},
        },
    ]

    def __init__(self):
        self._state = CodeReviewState()

    def reset(self, seed=None, episode_id=None, **kwargs) -> CodeReviewObservation:
        """Reset environment to initial state. Called by POST /reset."""
        self._state = CodeReviewState(
            episode_id=str(episode_id) if episode_id else str(uuid.uuid4()),
            step_count=0,
            current_task_idx=0,
            total_score=0.0,
        )
        task = self.TASKS[0]
        return CodeReviewObservation(
            done=False,
            reward=0.0,
            code_snippet=task["snippet"],
            difficulty=task["difficulty"],
            feedback=(
                "Episode started. Review the code snippet: "
                "identify the bug category, severity (1-5), and line number."
            ),
        )

    def step(self, action: CodeReviewAction, timeout_s=None, **kwargs) -> CodeReviewObservation:
        """Grade the agent's action and advance to the next task."""
        self._state.step_count += 1

        idx   = self._state.current_task_idx
        task  = self.TASKS[idx]
        truth = task["truth"]

        # Reward: 0.0 → 1.0
        reward = 0.0
        if action.category.strip().lower() == truth["category"]:
            reward += 0.5
        sev_diff = abs(action.severity - truth["severity"])
        if sev_diff == 0:
            reward += 0.3
        elif sev_diff == 1:
            reward += 0.15
        if action.line_hint is not None and action.line_hint == truth["line_hint"]:
            reward += 0.2

        self._state.total_score += reward
        self._state.current_task_idx += 1

        done = self._state.current_task_idx >= len(self.TASKS)

        if done:
            return CodeReviewObservation(
                done=True,
                reward=reward,
                code_snippet="",
                difficulty="",
                feedback=(
                    f"Episode complete. "
                    f"Total score: {self._state.total_score:.2f} / {len(self.TASKS):.1f}"
                ),
            )

        next_task = self.TASKS[self._state.current_task_idx]
        return CodeReviewObservation(
            done=False,
            reward=reward,
            code_snippet=next_task["snippet"],
            difficulty=next_task["difficulty"],
            feedback=f"Step reward: {reward:.2f}. Now review the next snippet.",
        )

    @property
    def state(self) -> CodeReviewState:
        return self._state
