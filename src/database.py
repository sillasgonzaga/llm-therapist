import sqlite3
from pathlib import Path
from . import config
from loguru import logger
import datetime # Import datetime

DATABASE_FILE = Path(config.DATABASE_PATH)

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        # Ensure the directory exists before connecting
        DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row # Return rows as dict-like objects
        # Enable foreign key support
        conn.execute("PRAGMA foreign_keys = ON;")
        logger.info(f"Database connection established: {DATABASE_FILE}")
        return conn
    except sqlite3.Error as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def create_tables(conn: sqlite3.Connection):
    """Creates the necessary tables if they don't exist."""
    try:
        cursor = conn.cursor()
        # --- processed_posts table (llm_response removed) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT UNIQUE NOT NULL,
                post_url TEXT NOT NULL,
                post_title TEXT,
                post_body TEXT,
                created_utc TIMESTAMP,
                top_comment_id TEXT,
                top_comment_body TEXT,
                top_comment_score INTEGER,
                similarity_score REAL, -- Using REAL for floating point numbers
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_post_id ON processed_posts (post_id);
        """)

        # --- llm_data table (New table) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS llm_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL, -- Link to the processed post
                input_prompt TEXT NOT NULL,
                llm_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id), -- Assuming one LLM attempt per post in this table
                FOREIGN KEY (post_id) REFERENCES processed_posts(post_id) ON DELETE CASCADE
            );
        """)
        # Index for faster lookups if needed, post_id is already indexed via UNIQUE/FK
        # cursor.execute("""
        #     CREATE INDEX IF NOT EXISTS idx_llm_post_id ON llm_data (post_id);
        # """)

        conn.commit()
        logger.info("Database tables checked/created successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def check_post_processed(conn: sqlite3.Connection, post_id: str) -> bool:
    """Checks if a post_id already exists in the processed_posts table."""
    try:
        cursor = conn.cursor()
        # Check the main table to see if the core processing happened
        cursor.execute("SELECT 1 FROM processed_posts WHERE post_id = ?", (post_id,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Error checking if post {post_id} is processed: {e}")
        return False # Assume not processed if error occurs

# --- insert_processed_post (Updated: llm_response removed) ---
def insert_processed_post(conn: sqlite3.Connection, data: dict):
    """Inserts a processed post record into the database."""
    # Ensure 'created_utc' is a datetime object if present
    created_utc_val = data.get('created_utc')
    if created_utc_val and not isinstance(created_utc_val, datetime.datetime):
         try:
             # Attempt conversion assuming ISO format or timestamp
             if isinstance(created_utc_val, (int, float)):
                 created_utc_val = datetime.datetime.fromtimestamp(created_utc_val, tz=datetime.timezone.utc)
             else:
                 created_utc_val = datetime.datetime.fromisoformat(str(created_utc_val))
         except ValueError:
             logger.warning(f"Could not parse created_utc: {created_utc_val}. Setting to None.")
             created_utc_val = None


    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO processed_posts (
                post_id, post_url, post_title, post_body, created_utc,
                top_comment_id, top_comment_body, top_comment_score,
                similarity_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO NOTHING; -- Avoid errors if trying to re-insert somehow
        """, (
            data.get('post_id'), data.get('post_url'), data.get('post_title'),
            data.get('post_body'), created_utc_val, # Use potentially converted value
            data.get('top_comment_id'), data.get('top_comment_body'),
            data.get('top_comment_score'), data.get('similarity_score')
        ))
        conn.commit()
        # Check if insert happened (rowcount > 0)
        if cursor.rowcount > 0:
            logger.info(f"Inserted record into processed_posts for post_id: {data.get('post_id')}")
        else:
             logger.warning(f"processed_posts record for post_id: {data.get('post_id')} likely already existed. No insert performed.")
        # Return the id of the inserted row, or None if insertion didn't happen
        # return cursor.lastrowid if cursor.rowcount > 0 else None
    except sqlite3.IntegrityError as ie:
         # This might happen if ON CONFLICT wasn't used or another constraint failed
         logger.warning(f"Integrity Error inserting into processed_posts for post {data.get('post_id')}: {ie}")
    except sqlite3.Error as e:
        logger.error(f"Error inserting record into processed_posts for post {data.get('post_id')}: {e}")
        conn.rollback() # Rollback on error
    # We don't strictly need to return the ID for the current flow


# --- insert_llm_data (New function) ---
def insert_llm_data(conn: sqlite3.Connection, post_id: str, input_prompt: str, llm_response: str):
    """Inserts LLM interaction data into the llm_data table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO llm_data (
                post_id, input_prompt, llm_response
            ) VALUES (?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                input_prompt = excluded.input_prompt,
                llm_response = excluded.llm_response,
                created_at = CURRENT_TIMESTAMP;
        """, (post_id, input_prompt, llm_response))
        conn.commit()
        logger.info(f"Inserted/Updated record in llm_data for post_id: {post_id}")
    except sqlite3.IntegrityError as ie:
        # This might happen if the foreign key constraint fails (processed_post doesn't exist yet)
        logger.error(f"Integrity Error inserting LLM data for post {post_id}: {ie}. Does the processed_posts record exist?")
        conn.rollback()
    except sqlite3.Error as e:
        logger.error(f"Error inserting LLM data for post {post_id}: {e}")
        conn.rollback()