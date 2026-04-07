class GradeResult:
    def __init__(self, reward, breakdown, correct, bug_type="unknown", bug_severity=0):
        """Initialize the grade result with scoring data and metadata."""
        self.reward = reward
        self.breakdown = breakdown
        self.correct = correct
        self.bug_type = bug_type
        self.bug_severity = bug_severity

    def summary(self):
        """Return a formatted multi-line summary of the grading result."""
        lines = [
            "GRADE SUMMARY",
            "-" * 25,
            f"Reward:    {self.reward:+d}",
            f"Correct:   {'Yes' if self.correct else 'No'}",
            f"Bug was:   {self.bug_type} (severity {self.bug_severity})",
            "",
            "Breakdown:"
        ]
        for entry in self.breakdown:
            lines.append(f"  {entry}")
        lines.append("-" * 25)
        lines.append(f"Total: {self.reward:+d}")
        return "\n".join(lines)

    def to_dict(self):
        """Convert the grade result to a dictionary for batch processing."""
        return {
            "reward": self.reward,
            "correct": self.correct,
            "bug_type": self.bug_type,
            "bug_severity": self.bug_severity,
            "breakdown": self.breakdown
        }

def grade(ai_action, ground_truth):
    """
    Grades a single AI review against the ground truth.
    
    ai_action keys: type, category, line_hint, comment, severity
    ground_truth keys: bug (containing: type, severity, description, line_hint)
    """
    if ground_truth is None or "bug" not in ground_truth:
        return GradeResult(reward=0, breakdown=["No ground truth available"], correct=False)
    
    bug = ground_truth["bug"]
    reward = 0
    breakdown = []
    correct = False
    
    ai_type = ai_action.get("type", "approve")
    ai_category = ai_action.get("category", "ok")
    ai_comment = ai_action.get("comment", "")
    ai_severity = ai_action.get("severity", 3)
    ai_line_hint = ai_action.get("line_hint", "")

    # --- IF AI FLAGGED SOMETHING ---
    if ai_type == "flag":
        if ai_category == bug["type"]:
            correct = True
            
            # Category match bonus
            if bug["type"] == "security":
                reward += 25
                breakdown.append("+25: caught a security vulnerability")
            elif bug["type"] == "logic":
                reward += 15
                breakdown.append("+15: caught a logic bug")
            else:
                reward += 10
                breakdown.append("+10: caught a style/other issue")
            
            # Severity accuracy bonus
            severity_diff = abs(ai_severity - bug["severity"])
            if severity_diff == 0:
                reward += 5
                breakdown.append("+5: severity rating was exact")
            elif severity_diff == 1:
                reward += 3
                breakdown.append("+3: severity rating was close")
            else:
                breakdown.append("+0: severity rating was off")
            
            # Comment quality bonus
            if len(ai_comment) > 40:
                reward += 5
                breakdown.append("+5: detailed comment provided")
            elif len(ai_comment) > 15:
                reward += 2
                breakdown.append("+2: brief comment provided")
            else:
                breakdown.append("+0: comment too short or missing")
            
            # Line hint bonus
            if len(ai_line_hint) > 5:
                reward += 3
                breakdown.append("+3: line location was specified")
            else:
                breakdown.append("+0: no line location given")
        
        else:
            # Wrong category - false positive
            reward -= 10
            breakdown.append(f"-10: false positive — flagged as '{ai_category}' but was '{bug['type']}'")
            
    # --- IF AI APPROVED ---
    elif ai_type == "approve":
        if bug["severity"] >= 5:
            reward -= 25
            breakdown.append(f"-25: missed a critical severity-5 bug ({bug['type']})")
        elif bug["severity"] >= 4:
            reward -= 20
            breakdown.append(f"-20: missed a high severity-4 bug ({bug['type']})")
        elif bug["severity"] >= 3:
            reward -= 12
            breakdown.append(f"-12: missed a medium severity-3 bug ({bug['type']})")
        else:
            reward -= 5
            breakdown.append(f"-5: missed a low severity bug ({bug['type']})")
            
    # --- UNKNOWN ACTION ---
    else:
        reward -= 5
        breakdown.append("-5: unknown action type")
        
    return GradeResult(
        reward=reward, 
        breakdown=breakdown, 
        correct=correct, 
        bug_type=bug["type"], 
        bug_severity=bug["severity"]
    )

def batch_grade(episodes):
    """Summarizes grading across multiple episodes."""
    results_list = []
    total_reward = 0
    correct_count = 0
    best_score = -float('inf')
    worst_score = float('inf')
    
    caught_security = 0
    caught_logic = 0
    false_positives = 0
    missed_bugs = 0
    
    for ep in episodes:
        res = grade(ep["ai_action"], ep["ground_truth"])
        res_dict = res.to_dict()
        results_list.append(res_dict)
        
        reward = res_dict["reward"]
        total_reward += reward
        
        if res_dict["correct"]:
            correct_count += 1
            if res_dict["bug_type"] == "security":
                caught_security += 1
            elif res_dict["bug_type"] == "logic":
                caught_logic += 1
        else:
            ai_type = ep["ai_action"].get("type")
            if ai_type == "flag":
                false_positives += 1
            elif ai_type == "approve":
                missed_bugs += 1
                
        if reward > best_score:
            best_score = reward
        if reward < worst_score:
            worst_score = reward
            
    count = len(episodes)
    if count == 0:
        return {"error": "no episodes provided"}
        
    return {
        "results": results_list,
        "total_reward": total_reward,
        "average_reward": total_reward / count,
        "accuracy": correct_count / count,
        "best_score": best_score,
        "worst_score": worst_score,
        "caught_security": caught_security,
        "caught_logic": caught_logic,
        "false_positives": false_positives,
        "missed_bugs": missed_bugs
    }

# TEST BLOCK
if __name__ == "__main__":
    test_cases = [
        # 1. Perfect security catch
        {"ai_action": {"type": "flag", "category": "security", 
                        "line_hint": "line 3 query string", 
                        "comment": "SQL injection vulnerability — user input directly in query", 
                        "severity": 5},
         "ground_truth": {"bug": {"type": "security", "severity": 5, 
                                   "description": "SQL injection", "line_hint": "query line"}}},
        
        # 2. Correct logic catch, vague comment  
        {"ai_action": {"type": "flag", "category": "logic",
                        "line_hint": "loop",
                        "comment": "off by one",
                        "severity": 3},
         "ground_truth": {"bug": {"type": "logic", "severity": 3,
                                   "description": "off-by-one", "line_hint": "range call"}}},
        
        # 3. False positive (flags logic but it was security)
        {"ai_action": {"type": "flag", "category": "logic",
                        "line_hint": "line 5",
                        "comment": "this looks wrong",
                        "severity": 2},
         "ground_truth": {"bug": {"type": "security", "severity": 5,
                                   "description": "plain text password", "line_hint": "db.insert line"}}},
        
        # 4. Missed critical bug
        {"ai_action": {"type": "approve", "category": "ok",
                        "line_hint": "", "comment": "", "severity": 0},
         "ground_truth": {"bug": {"type": "security", "severity": 5,
                                   "description": "SQL injection", "line_hint": "query line"}}},
        
        # 5. Missed medium bug
        {"ai_action": {"type": "approve", "category": "ok",
                        "line_hint": "", "comment": "", "severity": 0},
         "ground_truth": {"bug": {"type": "logic", "severity": 3,
                                   "description": "off-by-one", "line_hint": "range call"}}},
        
        # 6. Perfect catch with full detail
        {"ai_action": {"type": "flag", "category": "security",
                        "line_hint": "db.insert line — password stored without hashing",
                        "comment": "Password is stored as plain text. Should use bcrypt or hashlib sha256 before inserting into the database.",
                        "severity": 5},
         "ground_truth": {"bug": {"type": "security", "severity": 5,
                                   "description": "plain text password", "line_hint": "db.insert line"}}}
    ]
    
    print("RUNNING GRADER TESTS...\n")
    
    for i, case in enumerate(test_cases, 1):
        print(f"CASE {i}:")
        result = grade(case["ai_action"], case["ground_truth"])
        print(result.summary())
        print()
        
    print("BATCH RESULTS:")
    import pprint
    pprint.pprint(batch_grade(test_cases))
