"""server/app.py — OpenEnv multi-mode entry point."""
import uvicorn
from main import app


def main():
    """Start the CodeBug server."""
    uvicorn.run(app, host="0.0.0.0", port=7860)


if __name__ == "__main__":
    main()
