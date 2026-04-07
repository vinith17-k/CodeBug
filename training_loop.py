"""
training_loop.py — CLI training loop with checkpointing.

Key improvements:
  - Run outputs saved to runs/ (never committed to git)
  - Checkpoint saved after every episode: resumes across runs
  - Config-driven paths
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

from config import CHECKPOINT_FILE, RUNS_DIR
from agent import review
from environment import CodeReviewEnv


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


def _load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_reward": 0, "episodes_run": 0, "history": []}


def _save_checkpoint(data: dict) -> None:
    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def run_training(num_episodes: int = 5, verbose: bool = True, resume: bool = True) -> dict:
    """
    Run the training loop.

    Args:
        num_episodes: How many episodes to run this session.
        verbose:      Print progress to stdout.
        resume:       If True, load and continue from the last checkpoint.
    """
    checkpoint = _load_checkpoint() if resume else {"total_reward": 0, "episodes_run": 0, "history": []}

    if resume and checkpoint["episodes_run"] > 0:
        if verbose:
            print(f"Resuming from checkpoint: {checkpoint['episodes_run']} episodes already run.")

    env = CodeReviewEnv()
    history: list[dict] = checkpoint["history"]
    total_reward: int   = checkpoint["total_reward"]

    start_ep = checkpoint["episodes_run"]

    if verbose:
        print(f"--- Training Loop: {num_episodes} episodes (starting at ep {start_ep + 1}) ---")

    for i in range(1, num_episodes + 1):
        obs       = env.reset()
        ai_action = review(obs["code"])
        reward, done, info = env.step(ai_action)

        total_reward += reward

        record = {
            "episode_index": start_ep + i,
            "episode_id":    obs["episode_id"],
            "snippet_id":    obs["snippet_id"],
            "reward":        reward,
            "ai_said":       info["ai_said"],
            "truth":         info["truth"],
            "correct":       info["correct"],
            "breakdown":     info["breakdown"],
            "timestamp":     datetime.utcnow().isoformat() + "Z",
        }
        history.append(record)

        # Save checkpoint after every episode
        _save_checkpoint({
            "total_reward": total_reward,
            "episodes_run": start_ep + i,
            "history":      history,
        })

        if verbose:
            status = "✓ CORRECT" if info["correct"] else "✗ WRONG"
            print(
                f"Ep {start_ep + i:03d} | {obs['episode_id']} | "
                f"{info['ai_said']:22} | {status} | Reward: {reward:+3d} | "
                f"Cumulative: {total_reward}"
            )

    stats = env.get_stats()
    output_data = {"overall_stats": stats, "history": history}

    # Save timestamped run file in runs/
    os.makedirs(RUNS_DIR, exist_ok=True)
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_file = os.path.join(RUNS_DIR, f"run_{ts}.json")
    with open(run_file, "w") as f:
        json.dump(output_data, f, indent=2)

    if verbose:
        print(f"\n--- Training Complete ---")
        print(f"Total Reward:  {total_reward}")
        print(f"Session Acc.:  {stats['accuracy'] * 100:.1f}%")
        print(f"Run saved to:  {run_file}")
        print(f"Checkpoint:    {CHECKPOINT_FILE}")

    return output_data


def analyze_history() -> None:
    """Print a summary from the latest checkpoint."""
    checkpoint = _load_checkpoint()
    if not checkpoint["history"]:
        print("No checkpoint found. Run training first.")
        return

    stats   = checkpoint
    history = checkpoint["history"]

    print("\n--- PERFORMANCE ANALYSIS ---")
    print(f"Episodes run:  {stats['episodes_run']}")
    print(f"Total reward:  {stats['total_reward']}")

    correct = sum(1 for h in history if h["correct"])
    if history:
        print(f"Accuracy:      {correct / len(history) * 100:.1f}%")
        print(f"Best reward:   {max(h['reward'] for h in history)}")
        print(f"Worst reward:  {min(h['reward'] for h in history)}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "default"

    if mode == "short":
        run_training(num_episodes=10)
    elif mode == "analyze":
        analyze_history()
    elif mode == "fresh":
        run_training(num_episodes=5, resume=False)
    else:
        run_training(num_episodes=5)
