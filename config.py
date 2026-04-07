"""
config.py — Central configuration for CodeBug.

All tuneable constants live here so you never have to hunt through
multiple source files to change a model name or a reward value.
"""

import os

# ---------------------------------------------------------------------------
# API / Model
# ---------------------------------------------------------------------------

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
OPENAI_MODEL    = "gpt-4o-mini"
MAX_TOKENS      = 300         # Max tokens for review calls
FIX_MAX_TOKENS  = 600         # Max tokens for fix-suggestion calls

# ---------------------------------------------------------------------------
# Reward values
# ---------------------------------------------------------------------------

REWARD_SECURITY_CATCH   =  25    # Correctly flagged a security bug
REWARD_LOGIC_CATCH      =  15    # Correctly flagged a logic bug
REWARD_OTHER_CATCH      =  10    # Correctly flagged a style/other issue
REWARD_CLEAN_APPROVE    =   5    # Correctly approved clean code   ← NEW
REWARD_PARTIAL_CREDIT   =   5    # Right decision, wrong category  ← NEW

REWARD_SEVERITY_EXACT   =   5    # Severity matched exactly
REWARD_SEVERITY_CLOSE   =   3    # Severity off by 1

REWARD_COMMENT_LONG     =   5    # Comment longer than 40 chars
REWARD_COMMENT_SHORT    =   2    # Comment between 16-40 chars

REWARD_LINE_HINT        =   3    # Line location was specified

PENALTY_WRONG_CATEGORY  = -10    # Flagged but wrong category
PENALTY_MISS_CRITICAL   = -25    # Missed severity-5 bug
PENALTY_MISS_HIGH       = -20    # Missed severity-4 bug
PENALTY_MISS_MEDIUM     = -12    # Missed severity-3 bug
PENALTY_MISS_LOW        =  -5    # Missed severity ≤ 2 bug
PENALTY_UNKNOWN_ACTION  =  -5    # Unknown action type

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

EPISODES_FILE    = "episodes.json"
ANSWERS_FILE     = "answers.json"
RUNS_DIR         = "runs"          # All run outputs go here
CHECKPOINT_FILE  = os.path.join(RUNS_DIR, "checkpoint.json")

# ---------------------------------------------------------------------------
# Flask / Rate limiting
# ---------------------------------------------------------------------------

MAX_CONTENT_LENGTH_MB  = 1          # Max upload size in MB
RATE_LIMIT_DEFAULT     = "60 per minute"
RATE_LIMIT_REVIEW      = "20 per minute"  # Paid API — be conservative
RATE_LIMIT_AUTO_RUN    = "5 per minute"

ALLOWED_EXTENSIONS = {"py", "js", "ts", "java", "cpp", "c", "go", "rb", "php", "txt"}
