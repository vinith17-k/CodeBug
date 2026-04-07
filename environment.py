import json
import random
from grader import grade, GradeResult

class CodeReviewEnv:
    def __init__(self, episodes_path, answers_path):
        """Initialize the environment by loading the episodes and answers data."""
        with open(episodes_path, 'r') as f:
            self.episodes = json.load(f)
        with open(answers_path, 'r') as f:
            self.answers = json.load(f)
            
        # Clean data from potential \r to avoid terminal issues
        for ep in self.episodes:
            ep["code"] = ep["code"].replace("\r", "")
        for ans in self.answers:
            if "buggy_code" in ans:
                 ans["buggy_code"] = ans["buggy_code"].replace("\r", "")
        
        self.current_episode = None
        self.episode_index = 0
        self.total_reward = 0
        self.correct_count = 0
        self.best_score = -float('inf')
        self.worst_score = float('inf')

    def reset(self):
        """Pick a random episode and return the observation."""
        self.current_episode = random.choice(self.episodes)
        
        observation = {
            "code": self.current_episode["code"],
            "episode_id": self.current_episode["episode_id"],
            "snippet_id": self.current_episode["snippet_id"],
            "instructions": (
                "Review this code. Find bugs, security issues, or logic errors. "
                "Respond in JSON with keys: type (flag or approve), category (bug/security/style/ok), "
                "line_hint (brief description of where the issue is), comment (your explanation), "
                "severity (1-5)"
            )
        }
        return observation

    def step(self, ai_action):
        """Execute one step (one review) and return (reward, done, info)."""
        ground_truth = self._get_answer(self.current_episode["episode_id"])
        
        # Use grader module
        result = grade(ai_action, ground_truth)
        reward = result.reward
        
        self.total_reward += reward
        self.episode_index += 1
        
        if result.correct:
            self.correct_count += 1
            
        if reward > self.best_score:
            self.best_score = reward
        if reward < self.worst_score:
            self.worst_score = reward
            
        done = True
        
        # Determine truth string for metadata
        if ground_truth and "bug" in ground_truth:
             truth_str = f"{ground_truth['bug']['type']} severity {ground_truth['bug']['severity']}"
        else:
             truth_str = "None"

        info = {
            "episode_id": self.current_episode["episode_id"],
            "ai_said": f"{ai_action.get('type')} / {ai_action.get('category')}",
            "truth": truth_str,
            "correct": result.correct,
            "breakdown": result.breakdown
        }
        
        return reward, done, info

    def _get_answer(self, episode_id):
        """Helper to find the matching answer for an episode ID."""
        for ans in self.answers:
            if ans["episode_id"] == episode_id:
                return ans
        return None


    def get_stats(self):
        """Return summary statistics of the environment performance."""
        avg_reward = self.total_reward / self.episode_index if self.episode_index > 0 else 0
        accuracy = self.correct_count / self.episode_index if self.episode_index > 0 else 0
        return {
            "total_reward": self.total_reward,
            "episodes_run": self.episode_index,
            "average_reward": avg_reward,
            "accuracy": accuracy,
            "best_score": self.best_score if self.best_score != -float('inf') else 0,
            "worst_score": self.worst_score if self.worst_score != float('inf') else 0
        }

    def render(self, observation, ai_action, reward, info):
        """Print a summary of the turn to the terminal."""
        # Ensure we only show a few lines and escape any weirdness
        lines = observation["code"].splitlines()
        code_preview = ""
        for line in lines[:3]:
            code_preview += f"  {line}\n"
        
        print("\n" + "-" * 40)
        print(f"Episode: {observation['episode_id']}")
        print("Code snippet shown to AI:")
        print(code_preview, end="")
        print("  ...")
        print()
        print(f"AI said:    {info['ai_said']}")
        print(f"Truth was:  {info['truth']}")
        print(f"Correct:    {info['correct']}")
        print(f"Reward:     {reward:+d}")
        print(f"Total so far: {self.total_reward}")
        print("-" * 40)

# TEST BLOCK
if __name__ == "__main__":
    env = CodeReviewEnv("episodes.json", "answers.json")
    
    print("Starting simulation...")
    
    for i in range(5):
        obs = env.reset()
        
        # Simulate an AI action
        if i % 2 == 0:
            # Even episodes: "Great" AI action
            fake_action = {
                "type": "flag",
                "category": "security",
                "line_hint": "line 3",
                "comment": "This looks like a SQL injection vulnerability",
                "severity": 5
            }
        else:
            # Odd episodes: "Missed the bug" AI action
            fake_action = {
                "type": "approve",
                "category": "ok",
                "line_hint": "",
                "comment": "",
                "severity": 0
            }
            
        reward, done, info = env.step(fake_action)
        env.render(obs, fake_action, reward, info)
        
    print("\nSimulation Complete.")
    print("Final Stats:")
    print(env.get_stats())
