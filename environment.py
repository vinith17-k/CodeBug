import uuid
from openenv.core.env_server import Environment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState
from tasks.easy.grader import grade as grade_task_easy_001
from tasks.medium.grader import grade as grade_task_medium_002
from tasks.hard.grader import grade as grade_task_hard_003
from tasks.extra1.grader import grade as grade_task_extra_004
from tasks.extra2.grader import grade as grade_task_extra_005
from tasks.scoring import finalize_task_reward


class CodeBugEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    TASKS = [
        {
            "id": "task_easy_001",
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
            "id": "task_medium_002",
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
            "id": "task_hard_003",
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
        {
            "id": "task_extra_004",
            "difficulty": "hard",
            "snippet": (
                "API_KEY = \"sk-1234567890abcdef\"\n"
                "def process_data(data):\n"
                "    return data.upper()"
            ),
            "truth": {"category": "security", "severity": 5, "line_hint": 1},
        },
        {
            "id": "task_extra_005",
            "difficulty": "medium",
            "snippet": (
                "def divide(a, b):\n"
                "    # Potential bug here\n"
                "    return a / b"
            ),
            "truth": {"category": "logic", "severity": 3, "line_hint": 3},
        },
    ]

    _TASK_GRADERS = {
        "task_easy_001": grade_task_easy_001,
        "task_medium_002": grade_task_medium_002,
        "task_hard_003": grade_task_hard_003,
        "task_extra_004": grade_task_extra_004,
        "task_extra_005": grade_task_extra_005,
    }

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
            reward=0.01,  # Start with a baseline safe score
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
        task_id = task["id"]

        grader = self._TASK_GRADERS.get(task_id)
        if grader is None:
            reward = 0.5
        else:
            reward = float(grader(action))
        reward = finalize_task_reward(reward)
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
