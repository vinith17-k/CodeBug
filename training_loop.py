import json
import sys
import os
from environment import CodeReviewEnv
from agent import review

def run_training(num_episodes=10, verbose=True):
    """
    Main training loop. Runs episodes where the AI reviews code and 
    records its performance to history.json.
    """
    if verbose:
        print(f"--- Starting Training Loop: {num_episodes} Episodes ---")
    
    # Initialize the code review environment
    env = CodeReviewEnv("episodes.json", "answers.json")
    history = []
    
    for i in range(1, num_episodes + 1):
        # 1. Reset for new episode
        obs = env.reset()
        
        # 2. Get AI review
        ai_action = review(obs["code"])
        
        # 3. Step the environment
        reward, done, info = env.step(ai_action)
        
        # Record metadata for this episode
        record = {
            "episode_index": i,
            "episode_id": obs["episode_id"],
            "snippet_id": obs["snippet_id"],
            "reward": reward,
            "ai_said": info["ai_said"],
            "truth": info["truth"],
            "correct": info["correct"],
            "breakdown": info["breakdown"]
        }
        history.append(record)
        
        if verbose:
            status = "✓ CORRECT" if info["correct"] else "✗ WRONG"
            print(f"Ep {i:02d} | ID: {obs['episode_id']} | {info['ai_said']:20} | {status} | Rewards: {reward:+3d}")

    # Generate summary statistics
    stats = env.get_stats()
    
    output_data = {
        "overall_stats": stats,
        "history": history
    }
    
    # Save training history
    with open("history.json", "w") as f:
        json.dump(output_data, f, indent=4)
        
    if verbose:
        print("\n--- Training Complete ---")
        print(f"Total Reward:   {stats['total_reward']}")
        print(f"Accuracy %:     {stats['accuracy'] * 100:.1f}%")
        print(f"Saved: history.json")
        
    return output_data

def analyze_history():
    """Prints a summary of the latest training history."""
    if not os.path.exists("history.json"):
        print("Error: history.json not found. Run training first.")
        return
        
    with open("history.json") as f:
        data = json.load(f)
        
    stats = data["overall_stats"]
    history = data["history"]
    
    print("\n--- PERFORMANCE ANALYSIS ---")
    print(f"Episodes:      {stats['episodes_run']}")
    print(f"Accuracy:      {stats['accuracy'] * 100:.1f}%")
    print(f"Total Reward:  {stats['total_reward']}")
    print(f"Avg Reward:    {stats['average_reward']:.2f}")
    print(f"Best Score:    {stats['best_score']}")
    
    sec_caught = stats.get("caught_security", 0)
    log_caught = stats.get("caught_logic", 0)
    print(f"Security Caught: {sec_caught}")
    print(f"Logic Caught:    {log_caught}")

if __name__ == "__main__":
    mode = "default"
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
    if mode == "short":
        run_training(num_episodes=10)
    elif mode == "analyze":
        analyze_history()
    else:
        # Default behavior: run 5 episodes
        run_training(num_episodes=5)
