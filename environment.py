import uuid
from openenv.core.env_server import Environment
from models import CodeReviewAction, CodeReviewObservation, CodeReviewState

class CodeBugEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True
    
    # 3 minimum tasks: easy -> medium -> hard
    TASKS = [
        {
            "difficulty": "easy",
            "snippet": "def transfer(from_account, to_account, amount):\n    if from_account.balance > amount:\n        from_account.balance -= amount\n        to_account.balance += amount\n        return True\n    return False",
            "truth": {"category": "logic", "severity": 4, "line_hint": 2}
        },
        {
            "difficulty": "medium",
            "snippet": "def find_max(numbers):\n    if not numbers:\n        return None\n    max_val = numbers[0]\n    for i in range(len(numbers) - 1):\n        if numbers[i] > max_val:\n            max_val = numbers[i]\n    return max_val",
            "truth": {"category": "logic", "severity": 3, "line_hint": 5}
        },
        {
            "difficulty": "hard",
            "snippet": "def login(username, password):\n    query = f\"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'\"\n    user = db.execute(query)\n    if user:\n        return True\n    return False",
            "truth": {"category": "security", "severity": 5, "line_hint": 3}
        }
    ]

    def __init__(self):
        self._state = CodeReviewState()

    def reset(self, seed=None, episode_id=None, **kwargs) -> CodeReviewObservation:
        self._state = CodeReviewState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            current_task_idx=0,
            total_score=0.0
        )
        task = self.TASKS[0]
        return CodeReviewObservation(
            done=False,
            reward=None,
            code_snippet=task["snippet"],
            difficulty=task["difficulty"],
            feedback="Scan the snippet and provide your code review action (category, severity, line_hint)."
        )

    def step(self, action: CodeReviewAction, timeout_s=None, **kwargs) -> CodeReviewObservation:
        self._state.step_count += 1
        
        idx = self._state.current_task_idx
        task = self.TASKS[idx]
        truth = task["truth"]
        
        # Reward Scale 0.0 -> 1.0 (strict Hackathon requirement)
        reward = 0.0
        
        is_correct_category = action.category.strip().lower() == truth["category"]
        if is_correct_category:
            reward += 0.5
            
        severity_diff = abs(action.severity - truth["severity"])
        if severity_diff == 0:
            reward += 0.3
        elif severity_diff == 1:
            reward += 0.15
            
        if action.line_hint == truth["line_hint"]:
            reward += 0.2
            
        self._state.total_score += reward
        self._state.current_task_idx += 1
        
        done = self._state.current_task_idx >= len(self.TASKS)
        
        if done:
            next_snippet = ""
            next_diff = ""
            feedback = f"Final evaluation complete! Score for this run: {self._state.total_score:.2f} / {len(self.TASKS)}"
        else:
            next_task = self.TASKS[self._state.current_task_idx]
            next_snippet = next_task["snippet"]
            next_diff = next_task["difficulty"]
            feedback = f"Task graded! Reward received: {reward:.2f}. Proceed to the next snippet."

        return CodeReviewObservation(
            done=done,
            reward=reward,
            code_snippet=next_snippet,
            difficulty=next_diff,
            feedback=feedback
        )

    @property
    def state(self) -> CodeReviewState:
        return self._state
