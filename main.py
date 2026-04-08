from openenv.core.env_server import create_fastapi_app
from environment import CodeBugEnvironment

app = create_fastapi_app(CodeBugEnvironment)
