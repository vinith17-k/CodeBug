# RL Code Reviewer

An RL-trained AI agent that reviews code like a senior engineer.
Built for the Code With Antigravity Hackathon.

## What it does
- Reviews Python, JS, Java and other code files for bugs
- Catches security vulnerabilities (SQL injection, plain-text passwords)
- Finds logic errors (off-by-one, wrong operators)
- Suggests fixes with a before/after diff view
- Trained with Reinforcement Learning — gets smarter every episode

## Tech Stack
- Python + Flask backend
- Anthropic Claude API (claude-haiku) for AI reviews
- Vanilla JavaScript frontend
- RL environment with custom reward function
- Chart.js for training visualization

## How to run locally
1. Install dependencies: `pip install -r requirements.txt`
2. Set API keys: 
   - `set ANTHROPIC_API_KEY=your_key_here` (Windows)
   - `export ANTHROPIC_API_KEY=your_key_here` (Mac/Linux)
3. Run the server: `python app.py`
4. Open http://localhost:5000

## Project Structure
- `bug_bank.py`      — bug injection engine
- `environment.py`   — RL environment (exam room)
- `grader.py`        — reward function
- `agent.py`         — AI reviewer (calls Claude API)
- `training_loop.py` — training loop
- `app.py`           — Flask web server
- `templates/`       — HTML landing & dashboard

## Built with
Google Antigravity IDE + Claude AI

© 2025 RL Code Reviewer. Built with ♥ for Antigravity Hackathon.
