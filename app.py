"""
FastAPI entry point for Hugging Face Spaces and production deployment.
This file simply imports the main FastAPI application to ensure
consistent behavior across localhost and HF Spaces deployments.
"""

from main import app

__all__ = ["app"]

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
