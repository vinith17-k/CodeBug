import json
import logging
import os
import re
import time
import threading

from flask import Flask, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import (
    ALLOWED_EXTENSIONS,
    MAX_CONTENT_LENGTH_MB,
    RATE_LIMIT_AUTO_RUN,
    RATE_LIMIT_DEFAULT,
    RATE_LIMIT_REVIEW,
    RUNS_DIR,
)
from environment import CodeReviewEnv
from agent import review, call_llm
from grader import grade
from training_loop import run_training

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH_MB * 1024 * 1024

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[RATE_LIMIT_DEFAULT],
    headers_enabled=True,   # Adds Retry-After + X-RateLimit-* headers
)

# Ensure runs directory exists
os.makedirs(RUNS_DIR, exist_ok=True)
HISTORY_FILE = os.path.join(RUNS_DIR, "history.json")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Global State ---
STATE = {
    "total_reward": 0,
    "episode_count": 0,
    "current_episode_id": None,
    "history": [],
    "is_running": False
}

# Initialize environment
env = CodeReviewEnv("episodes.json", "answers.json")

# Helper to save history to file
def save_history_file():
    stats = {
        "total_reward": STATE["total_reward"],
        "episodes_run": STATE["episode_count"],
        "accuracy": calculate_accuracy(),
        "best_score": calculate_best_score()
    }
    data = {
        "overall_stats": stats,
        "history": STATE["history"]
    }
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)

def calculate_accuracy():
    if STATE["episode_count"] == 0: return 0
    correct = sum(1 for h in STATE["history"] if h["correct"])
    return correct / STATE["episode_count"]

def calculate_best_score():
    if not STATE["history"]: return 0
    return max(h["reward"] for h in STATE["history"])

def find_bug_lines(code, ai_action):
    lines = code.splitlines()
    highlighted = []
    line_hint = ai_action.get("line_hint", "").lower()
    category = ai_action.get("category", "ok")
    
    if ai_action.get("type") != "flag":
        return []
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        should_highlight = False
        
        # Security patterns
        if category == "security":
            if any(p in line_lower for p in [
                "f\"select", "f'select", "query =", "execute(",
                "password =", "hashed = password", "= password",
                "api_key =", "secret =", "token ="
            ]):
                should_highlight = True
        
        # Logic patterns  
        if category == "logic":
            if any(p in line_lower for p in [
                "range(len(", "> amount", "< amount",
                ">= amount", "if accounts", "return"
            ]):
                should_highlight = True
        
        # Match line hint keywords
        if line_hint:
            hint_words = [w for w in line_hint.split() if len(w) > 3]
            if any(word in line_lower for word in hint_words):
                should_highlight = True
        
        if should_highlight:
            highlighted.append({
                "line_number": i + 1,
                "content": line,
                "severity": ai_action.get("severity", 3)
            })
    
    return highlighted[:3]  # max 3 highlighted lines

def get_fix_suggestion(code, ai_action):
    if ai_action.get("type") != "flag": return None
    
    comment = ai_action.get('comment', '')
    category = ai_action.get('category', '')

    fix_prompt = f"""
    You are a senior engineer. A code reviewer found this issue:
    
    Bug type: {category}
    Issue: {comment}
    Location: {ai_action.get('line_hint', '')}
    
    Here is the original buggy code:
    {code}
    
    Provide a fixed version of the code.
    Respond with ONLY a JSON object:
    {{
        "fixed_code": "the complete fixed code here",
        "changes": ["list", "of", "what", "changed"],
        "explanation": "one sentence explaining the fix"
    }}
    No markdown, no backticks, just the JSON object.
    """
    
    raw = call_llm(fix_prompt)
    if raw:
        try:
            match = re.search(r'(\{.*\})', raw, re.DOTALL)
            if match:
                return json.loads(match.group(1))
        except:
            pass

    # Fallback logic
    if category == "security" and "sql" in comment.lower():
        return {
            "fixed_code": code.replace(
                "f\"SELECT * FROM users WHERE username='{username}'\"",
                "\"SELECT * FROM users WHERE username=?\""
            ),
            "changes": ["Replaced f-string with parameterized query",
                       "Added ? placeholder instead of variable interpolation"],
            "explanation": "Parameterized queries prevent SQL injection by separating code from data."
        }
    
    if category == "security" and "password" in comment.lower():
        return {
            "fixed_code": code.replace(
                "hashed = password",
                "import hashlib\n    hashed = hashlib.sha256(password.encode()).hexdigest()"
            ),
            "changes": ["Added hashlib import",
                       "Applied SHA-256 hashing before storing password"],
            "explanation": "Always hash passwords with a cryptographic function before storage."
        }
    
    if category == "logic" and "range(len(" in code:
         return {
            "fixed_code": code.replace("range(len(numbers) - 1)", 
                                        "range(len(numbers))"),
            "changes": ["Fixed loop range to include last element"],
            "explanation": "range(len(x)) iterates all items; range(len(x)-1) skips the last one."
        }
    
    return None

# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/next-episode", methods=["GET"])
def next_episode():
    # Reset env to get a new snippet
    obs = env.reset()
    STATE["current_episode_id"] = obs["episode_id"]
    return jsonify({
        "episode_id": obs["episode_id"],
        "snippet_id": obs["snippet_id"],
        "code": obs["code"],
        "episode_count": STATE["episode_count"]
    })

@app.route("/api/review", methods=["POST"])
@limiter.limit(RATE_LIMIT_REVIEW)
def perform_review():
    data = request.json
    code = data.get("code")
    episode_id = data.get("episode_id")
    snippet_id = data.get("snippet_id")
    
    # 1. Get AI Review
    ai_action = review(code)
    
    # 2. Get Ground Truth
    ground_truth = env._get_answer(episode_id)
    
    # 3. Grade the review
    res = grade(ai_action, ground_truth)
    reward = res.reward
    
    # 4. Update state
    STATE["total_reward"] += reward
    STATE["episode_count"] += 1
    
    record = {
        "episode_id": episode_id,
        "snippet_id": snippet_id,
        "ai_said": f"{ai_action.get('type')} / {ai_action.get('category')}",
        "reward": reward,
        "correct": res.correct,
        "breakdown": res.breakdown,
        "bug_type": res.bug_type
    }
    STATE["history"].append(record)
    save_history_file()
    
    return jsonify({
        "ai_action": ai_action,
        "reward": reward,
        "correct": res.correct,
        "breakdown": res.breakdown,
        "total_reward": STATE["total_reward"],
        "episode_count": STATE["episode_count"],
        "highlighted_lines": find_bug_lines(code, ai_action),
        "fix": get_fix_suggestion(code, ai_action)
    })

@app.route("/api/history", methods=["GET"])
def get_history():
    # If history is empty in state, try reading from file
    if not STATE["history"] and os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                data = json.load(f)
                STATE["history"] = data["history"]
                STATE["total_reward"] = data["overall_stats"]["total_reward"]
                STATE["episode_count"] = data["overall_stats"]["episodes_run"]
        except Exception as exc:
            logger.warning("Could not read history file: %s", exc)
            
    return jsonify({
        "history": STATE["history"],
        "total_reward": STATE["total_reward"],
        "episodes_run": STATE["episode_count"],
        "accuracy": calculate_accuracy(),
        "best_score": calculate_best_score()
    })

@app.route("/api/train", methods=["POST"])
@limiter.limit(RATE_LIMIT_AUTO_RUN)
def train():
    episodes = request.json.get("episodes", 10)
    
    # run synchronously to match frontend assumptions
    try:
        output_data = run_training(num_episodes=episodes, verbose=False, resume=True)
        stats = output_data["overall_stats"]
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "healthy",
        "has_anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "has_openai": bool(os.environ.get("OPENAI_API_KEY"))
    })

@app.route("/api/upload", methods=["POST"])
@limiter.limit(RATE_LIMIT_REVIEW)
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "File type not supported"}), 400
        
    code = file.read().decode('utf-8')
    note = None
    if len(code) > 10000:
        code = code[:10000]
        note = "User uploaded file — truncated to first 10,000 characters"
        
    return process_raw_code(code, file.filename, note)

@app.route("/api/review-text", methods=["POST"])
@limiter.limit(RATE_LIMIT_REVIEW)
def review_text():
    data = request.json
    code = data.get("code", "")
    filename = data.get("filename", "pasted_code.py")
    
    if not code:
        return jsonify({"error": "Empty code"}), 400
        
    note = None
    if len(code) > 10000:
        code = code[:10000]
        note = "Pasted code — truncated to first 10,000 characters"
        
    return process_raw_code(code, filename, note)

def process_raw_code(code, filename, note=None):
    # 1. Get AI Review
    ai_action = review(code)
    
    # 2. Build fake ground truth
    ground_truth = {
        "bug": {
            "type": ai_action["category"] if ai_action["type"] == "flag" else "none",
            "severity": ai_action.get("severity", 0),
            "description": "User uploaded file — no ground truth",
            "line_hint": ai_action.get("line_hint", "")
        }
    }
    
    # 3. Grade
    res = grade(ai_action, ground_truth)
    reward = res.reward
    
    # 4. Update state
    STATE["total_reward"] += reward
    STATE["episode_count"] += 1
    
    record = {
        "episode_id": f"upload_{STATE['episode_count']}",
        "snippet_id": filename,
        "ai_said": f"{ai_action.get('type')} / {ai_action.get('category')}",
        "reward": reward,
        "correct": res.correct,
        "breakdown": res.breakdown,
        "bug_type": res.bug_type
    }
    STATE["history"].append(record)
    save_history_file()
    
    return jsonify({
        "filename": filename,
        "code": code,
        "line_count": len(code.splitlines()),
        "ai_action": ai_action,
        "reward": reward,
        "correct": res.correct,
        "breakdown": res.breakdown,
        "total_reward": STATE["total_reward"],
        "episode_count": STATE["episode_count"],
        "summary": res.summary(),
        "note": note or "User uploaded file — reward based on AI confidence",
        "highlighted_lines": find_bug_lines(code, ai_action),
        "fix": get_fix_suggestion(code, ai_action)
    })

@app.route("/api/comparison", methods=["GET"])
def get_comparison():
    # Pick episode ep_001 (SQL injection — best visual example)
    code = ""
    for ep in env.episodes:
        if ep["episode_id"] == "ep_001":
            code = ep["code"]
            break
            
    truth = env._get_answer("ep_001")
    
    # Simulate untrained AI
    untrained_action = {
        "type": "approve",
        "category": "ok", 
        "line_hint": "",
        "comment": "Code looks fine, no issues found.",
        "severity": 0
    }
    
    trained_action = review(code)
    
    untrained_result = grade(untrained_action, truth)
    trained_result = grade(trained_action, truth)
    
    highlighted = find_bug_lines(code, trained_action)
    
    return jsonify({
        "code": code,
        "highlighted_lines": highlighted,
        "untrained": {
            "action": untrained_action,
            "reward": untrained_result.reward,
            "correct": untrained_result.correct,
            "breakdown": untrained_result.breakdown
        },
        "trained": {
            "action": trained_action,
            "reward": trained_result.reward,
            "correct": trained_result.correct,
            "breakdown": trained_result.breakdown
        },
        "ground_truth": truth.get("bug", {})
    })

@app.route("/api/stats", methods=["GET"])
def get_stats():
    return jsonify({
        "total_reward": STATE["total_reward"],
        "episode_count": STATE["episode_count"],
        "accuracy": calculate_accuracy(),
        "best_score": calculate_best_score(),
        "is_running": STATE["is_running"]
    })

@app.route("/api/reset", methods=["GET"])
def reset_state():
    STATE["total_reward"] = 0
    STATE["episode_count"] = 0
    STATE["history"] = []
    STATE["is_running"] = False
    if os.path.exists(HISTORY_FILE):
        os.remove(HISTORY_FILE)
    return jsonify({"status": "reset"})

if __name__ == "__main__":
    app.run(port=5000, threaded=True, debug=True)
