"""
training_loop.py — RL training loop for CodeBug agent.

This simplified version trains the agent on code review tasks.
"""

import json
import os
from datetime import datetime
from config import CHECKPOINT_FILE, RUNS_DIR
from agent import review


# =========================================================================
# Checkpoint helpers
# =========================================================================

def _load_checkpoint() -> dict:
    """Load checkpoint from disk if it exists"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"total_reward": 0.0, "episodes_run": 0, "history": []}


def _save_checkpoint(data: dict) -> None:
    """Save checkpoint to disk"""
    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f, indent=2)


def run_training(num_episodes: int = 5, verbose: bool = True, resume: bool = True) -> dict:
    """
    Run simplified training loop for the agent.
    
    Args:
        num_episodes: How many episodes to run
        verbose: Print progress
        resume: Load checkpoint and resume
        
    Returns:
        Dictionary with training stats
    """
    checkpoint = _load_checkpoint() if resume else {"total_reward": 0.0, "episodes_run": 0, "history": []}
    
    if resume and checkpoint["episodes_run"] > 0 and verbose:
        print(f"Resuming from checkpoint: {checkpoint['episodes_run']} episodes already run.")
    
    # Training examples (code snippets with ground truth)
    training_snippets = [
        {
            "code": 'def get_user(uid):\n    q = f"SELECT * FROM users WHERE id={uid}"\n    cursor.execute(q)',
            "truth": {"category": "security", "severity": 5}
        },
        {
            "code": 'def find_max(nums):\n    for i in range(len(nums) - 1):\n        if nums[i] > mx: mx = nums[i]',
            "truth": {"category": "logic", "severity": 3}
        },
        {
            "code": 'password = "admin123"\ndb.save_user(user, password)',
            "truth": {"category": "security", "severity": 5}
        },
    ]
    
    history = checkpoint["history"]
    total_reward = checkpoint["total_reward"]
    start_ep = checkpoint["episodes_run"]
    
    if verbose:
        print(f"--- Training Loop: {num_episodes} episodes (starting at ep {start_ep + 1}) ---")
    
    for i in range(1, num_episodes + 1):
        # Pick a random snippet
        snippet = training_snippets[(start_ep + i) % len(training_snippets)]
        code = snippet["code"]
        truth = snippet["truth"]
        
        # Get AI review
        try:
            ai_bugs = review(code)
            if not ai_bugs:
                ai_bugs = []
            
            # Simple scoring: did the agent detect a bug?
            detected_bug = len(ai_bugs) > 0
            reward = 1.0 if detected_bug else 0.0
            
            # Check if it matches category
            if ai_bugs and ai_bugs[0].get("category") == truth["category"]:
                reward += 0.5
            # Check severity
            if ai_bugs and ai_bugs[0].get("severity") == truth["severity"]:
                reward += 0.5
                
        except Exception as e:
            if verbose:
                print(f"  Warning: Agent failed on episode {i}: {e}")
            ai_bugs = []
            reward = 0.0
        
        total_reward += reward
        
        # Save record
        record = {
            "episode": start_ep + i,
            "code_length": len(code),
            "bugs_detected": len(ai_bugs),
            "reward": reward,
            "truth_category": truth["category"],
            "truth_severity": truth["severity"],
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        history.append(record)
        
        # Save checkpoint
        _save_checkpoint({
            "total_reward": total_reward,
            "episodes_run": start_ep + i,
            "history": history,
        })
        
        if verbose:
            print(f"Ep {start_ep + i:02d} | Bugs: {len(ai_bugs):1d} | Reward: {reward:.1f} | Cumulative: {total_reward:.1f}")
    
    if verbose:
        print(f"\n--- Training Complete ---")
        print(f"Total Episodes: {len(history)}")
        print(f"Total Reward: {total_reward:.1f}")
        if history:
            avg_reward = total_reward / len(history)
            print(f"Average Reward: {avg_reward:.2f}")
    
    # Save run file
    os.makedirs(RUNS_DIR, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_file = os.path.join(RUNS_DIR, f"run_{ts}.json")
    with open(run_file, "w") as f:
        json.dump({"history": history, "total_reward": total_reward}, f, indent=2)
    
    return {
        "episodes_completed": num_episodes,
        "total_reward": float(total_reward),
        "average_reward": float(total_reward / num_episodes) if num_episodes > 0 else 0.0,
        "history_length": len(history),
        "checkpoint_file": CHECKPOINT_FILE
    }

