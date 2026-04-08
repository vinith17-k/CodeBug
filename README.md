# CodeBug - OpenEnv Hackathon Submission

CodeBug is an RL environment designed to train agents to analyze and review Python code. The goal is to detect underlying issues within code snippets, determining category, severity, and the specific line where the bug resides.

## Action & Observation Spaces

### Observation Space (`CodeReviewObservation`)
Provides the agent with the contextual tools to analyze the bug:
- `code_snippet` (str): The snippet containing a logic, security, or syntax risk.
- `difficulty` (str): Represents the difficulty of the task (easy, medium, hard).
- `feedback` (str): Feedback string returned from the environment upon grading an action.

### Action Space (`CodeReviewAction`)
The agent's review and determination is returned:
- `category` (str): Type of the bug (logic, security, style, approve). 
- `severity` (int): Scale of 1 to 5.
- `line_hint` (int): Exact line number containing the vulnerability.
- `comment` (str): Short explanation of the bug found.

## Setup Instructions

### Installation

Install dependencies natively:
```bash
pip install -r requirements.txt
```

### Running the Server locally

Start the OpenEnv FastAPI backend server locally on port 7860:
```bash
uvicorn main:app --host 0.0.0.0 --port 7860
```

### Baseline Inference

You can run the baseline inference script strictly with an OpenAI compatible API:
```bash
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4o-mini"
export HF_TOKEN="sk-your-huggingface-or-openai-key"

python inference.py
```
