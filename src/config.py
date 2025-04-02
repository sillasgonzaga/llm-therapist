import os
from pathlib import Path
from loguru import logger

# Load .env only for local development, not needed in Cloud Run
if os.getenv("GOOGLE_CLOUD_RUN_JOB") is None: # Simple check if not in Cloud Run
     from dotenv import load_dotenv
     env_path = Path('.') / '.env'
     if env_path.exists():
         load_dotenv(dotenv_path=env_path)
     else:
         logger.warning(".env file not found for local development.")


# Reddit Config
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT", "llm_desabafos_analyzer_cloud_run")

# LLM Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Project Settings
SUBREDDIT_NAME = os.getenv("SUBREDDIT_NAME", "desabafos")
POST_LIMIT = int(os.getenv("POST_LIMIT", "50"))
SIMILARITY_MODEL = os.getenv("SIMILARITY_MODEL", "all-MiniLM-L6-v2")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Cloud SQL Configuration ---
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
# Instance Connection Name: 'project:region:instance-id'
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")
# Choose the DB driver dialect based on installation in pyproject.toml
# DB_DRIVER = "postgresql+psycopg2"
DB_DRIVER = os.getenv("DB_DRIVER", "postgresql+psycopg2") # Or postgresql+pg8000

# --- Basic Validation ---
missing_creds = []
if not REDDIT_CLIENT_ID: missing_creds.append("REDDIT_CLIENT_ID")
if not REDDIT_CLIENT_SECRET: missing_creds.append("REDDIT_CLIENT_SECRET")
if not OPENAI_API_KEY: missing_creds.append("OPENAI_API_KEY")
if missing_creds:
    logger.error(f"Missing required API credentials in environment variables: {', '.join(missing_creds)}")
    # raise ValueError(f"Missing required API credentials: {', '.join(missing_creds)}")

missing_db_config = []
if not DB_USER: missing_db_config.append("DB_USER")
if not DB_PASS: missing_db_config.append("DB_PASS")
if not DB_NAME: missing_db_config.append("DB_NAME")
if not INSTANCE_CONNECTION_NAME: missing_db_config.append("INSTANCE_CONNECTION_NAME")
if missing_db_config:
     logger.error(f"Missing database configuration in environment variables: {', '.join(missing_db_config)}")
     # raise ValueError(f"Missing database configuration: {', '.join(missing_db_config)}")

# Determine if running in Cloud Run for connector settings
# Use IAM AuthN by default if available and running in Cloud Run
ENABLE_IAM_AUTH = os.getenv("DB_ENABLE_IAM_AUTH", "true").lower() == "true" and os.getenv("GOOGLE_CLOUD_RUN_JOB") is not None


# --- Database URL (Optional, can be constructed if needed elsewhere) ---
# You might not need this if using the connector directly with SQLAlchemy engine
# if all([DB_USER, DB_PASS, DB_NAME, INSTANCE_CONNECTION_NAME]):
#     DATABASE_URL = f"{DB_DRIVER}://{DB_USER}:{DB_PASS}@/{DB_NAME}?host=/cloudsql/{INSTANCE_CONNECTION_NAME}"
# else:
#     DATABASE_URL = None