import os
import json
from openai import OpenAI
from environment import CodeBugEnvironment
from models import CodeReviewAction

def run_inference():
    # Read required environment variables
    api_base = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
    model_name = os.environ.get("MODEL_NAME", "gpt-3.5-turbo")
    hf_token = os.environ.get("HF_TOKEN")
    
    # Initialize OpenEnv environment locally for baseline test
    env = CodeBugEnvironment()
    obs = env.reset()
    
    print(f"[START] Episode {env.state.episode_id}")
    
    client = OpenAI(
        api_key=hf_token, # HF_TOKEN acts as the API key per instructions
        base_url=api_base
    )
    
    total_reward = 0.0
    step_count = 0
    
    while not obs.done:
        step_count += 1
        
        prompt = f"""
        You are a code review agent. Difficulty: {obs.difficulty}.
        Given this code snippet:
        {obs.code_snippet}
        
        Output a valid JSON matching this schema exactly:
        {{
            "category": "logic | security | style | approve",
            "severity": 1-5 (int),
            "line_hint": line number where bug exists (int),
            "comment": "short description"
        }}
        """
        
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            raw_action = json.loads(response.choices[0].message.content)
            
            action = CodeReviewAction(
                category=raw_action.get("category", "style"),
                severity=int(raw_action.get("severity", 1)),
                line_hint=int(raw_action.get("line_hint", 0)) if raw_action.get("line_hint") else None,
                comment=raw_action.get("comment", "")
            )
        except Exception as e:
            # Fallback action on parsing failure
            action = CodeReviewAction(
                category="approve",
                severity=1,
                line_hint=None,
                comment="Failed to parse LLM output."
            )
            
        print(f"[STEP] Sending Action -> Category: {action.category}, Severity: {action.severity}")
        
        # Step environment
        obs = env.step(action)
        total_reward += obs.reward or 0.0
        
        print(f"[STEP] Result -> Reward: {obs.reward:.2f} | Info: {obs.feedback}")
        
    print(f"[END] Total Reward: {total_reward:.2f}")

if __name__ == "__main__":
    run_inference()
