"""
environment.py — Code-review RL environment.

Key improvements:
  - reset() uses a shuffled queue that exhausts all episodes before cycling,
    preventing repeated sampling of the same snippet within an epoch.
  - Episode/answer paths come from config.py.
  - Type annotations on all public methods.
"""

from __future__ import annotations

import json
import random
from typing import Any

from config import ANSWERS_FILE, EPISODES_FILE
from grader import GradeResult, grade


class CodeReviewEnv:
    def __init__(
        self,
        episodes_path: str = EPISODES_FILE,
        answers_path: str = ANSWERS_FILE,
    ) -> None:
        with open(episodes_path, "r") as f:
            self.episodes: list[dict] = json.load(f)
        with open(answers_path, "r") as f:
            self.answers: list[dict] = json.load(f)

        # Strip \r artifacts that cause terminal issues on Windows
        for ep in self.episodes:
            ep["code"] = ep["code"].replace("\r", "")
        for ans in self.answers:
            if "buggy_code" in ans:
                ans["buggy_code"] = ans["buggy_code"].replace("\r", "")

        self.current_episode: dict | None = None
        self.episode_index   = 0
        self.total_reward    = 0
        self.correct_count   = 0
        self.best_score      = -float("inf")
        self.worst_score     = float("inf")

        # Shuffled queue — exhausted before refilling (deduplication)
        self._queue: list[dict] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _refill_queue(self) -> None:
        """Shuffle a fresh copy of all episodes into the queue."""
        self._queue = list(self.episodes)
        random.shuffle(self._queue)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reset(self) -> dict[str, Any]:
        """
        Pick the next unseen episode from this epoch's shuffled queue.
        Once all episodes have been seen, reshuffle and start a new epoch.
        """
        if not self._queue:
            self._refill_queue()

        self.current_episode = self._queue.pop()

        return {
            "code":         self.current_episode["code"],
            "episode_id":   self.current_episode["episode_id"],
            "snippet_id":   self.current_episode["snippet_id"],
            "instructions": (
                "Review this code. Find bugs, security issues, or logic errors. "
                "Respond in JSON with keys: type (flag or approve), "
                "category (security/logic/style/ok), "
                "line_hint (brief description of where the issue is), "
                "comment (your explanation), severity (1-5)"
            ),
        }

    def step(self, ai_action: dict) -> tuple[int, bool, dict]:
        """Execute one review step and return (reward, done, info)."""
        ground_truth = self._get_answer(self.current_episode["episode_id"])

        result = grade(ai_action, ground_truth)
        reward = result.reward

        self.total_reward  += reward
        self.episode_index += 1

        if result.correct:
            self.correct_count += 1

        if reward > self.best_score:
            self.best_score = reward
        if reward < self.worst_score:
            self.worst_score = reward

        if ground_truth and "bug" in ground_truth:
            truth_str = f"{ground_truth['bug']['type']} severity {ground_truth['bug']['severity']}"
        else:
            truth_str = "None"

        info = {
            "episode_id": self.current_episode["episode_id"],
            "ai_said":    f"{ai_action.get('type')} / {ai_action.get('category')}",
            "truth":      truth_str,
            "correct":    result.correct,
            "breakdown":  result.breakdown,
        }

        return reward, True, info

    def _get_answer(self, episode_id: str) -> dict | None:
        for ans in self.answers:
            if ans["episode_id"] == episode_id:
                return ans
        return None

    def get_stats(self) -> dict:
        avg_r    = self.total_reward / self.episode_index if self.episode_index > 0 else 0
        accuracy = self.correct_count / self.episode_index if self.episode_index > 0 else 0
        return {
            "total_reward":   self.total_reward,
            "episodes_run":   self.episode_index,
            "average_reward": avg_r,
            "accuracy":       accuracy,
            "best_score":     self.best_score  if self.best_score  != -float("inf") else 0,
            "worst_score":    self.worst_score if self.worst_score !=  float("inf") else 0,
        }

    def render(self, observation: dict, ai_action: dict, reward: int, info: dict) -> None:
        lines = observation["code"].splitlines()
        code_preview = "".join(f"  {l}\n" for l in lines[:3])

        print("\n" + "-" * 40)
        print(f"Episode: {observation['episode_id']}")
        print("Code snippet:")
        print(code_preview, end="")
        print("  ...")
        print(f"\nAI said:    {info['ai_said']}")
        print(f"Truth was:  {info['truth']}")
        print(f"Correct:    {info['correct']}")
        print(f"Reward:     {reward:+d}")
        print(f"Total so far: {self.total_reward}")
        print("-" * 40)


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    env = CodeReviewEnv()
    print("Starting 5-episode simulation (shuffled queue)...\n")

    for i in range(5):
        obs = env.reset()
        fake_action = (
            {"type": "flag", "category": "security", "line_hint": "line 3",
             "comment": "Possible SQL injection vulnerability", "severity": 5}
            if i % 2 == 0
            else {"type": "approve", "category": "ok", "line_hint": "", "comment": "", "severity": 0}
        )
        reward, done, info = env.step(fake_action)
        env.render(obs, fake_action, reward, info)

    print("\nFinal Stats:")
    import pprint
    pprint.pprint(env.get_stats())
