import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# Reddit Config
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "llm_desabafos_analyzer_v0.1")

# LLM Config (Example for OpenAI)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# Add other LLM configs if needed (e.g., GOOGLE_API_KEY)

# Project Settings
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/desabafos_data.db")
SUBREDDIT_NAME = os.getenv("SUBREDDIT_NAME", "desabafos")
POST_LIMIT = int(os.getenv("POST_LIMIT", "20"))
SIMILARITY_MODEL = os.getenv("SIMILARITY_MODEL", "all-MiniLM-L6-v2")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Create data directory if it doesn't exist
Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)

# Basic validation
if not all([REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, OPENAI_API_KEY]):
    raise ValueError("Missing required API credentials in .env file.")