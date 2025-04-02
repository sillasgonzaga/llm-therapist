import sqlite3
from pathlib import Path
from . import config
from loguru import logger
import datetime

DATABASE_FILE = Path(config.DATABASE_PATH)
# TABLES CREATED:
# - processed_posts
# - llm_data
# - post_comments (new table for top comments)


def get_db_connection():
    """Establishes a connection to the SQLite database."""
    try:
        DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DATABASE_FILE, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        conn.row_factory = sqlite3.Row
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
        # --- processed_posts table (comment fields removed) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT UNIQUE NOT NULL,
                post_url TEXT NOT NULL,
                post_title TEXT,
                post_body TEXT,
                created_utc TIMESTAMP,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_post_id ON processed_posts (post_id);
        """)

        # --- llm_data table (No changes needed here for this request) ---
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

        # --- post_comments table (New table for top comments) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                comment_id TEXT UNIQUE NOT NULL, -- Reddit comment ID
                comment_body TEXT,
                comment_score INTEGER,
                comment_rank INTEGER NOT NULL, -- Rank 1-5 among top comments fetched
                is_actual_advice BOOLEAN, -- Result of verification LLM call
                similarity_score REAL, -- Similarity vs main LLM advice (e.g., only for rank 1)
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES processed_posts(post_id) ON DELETE CASCADE
            );
        """)
        # Add indices for faster querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_comment_post_id ON post_comments (post_id);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_comment_rank ON post_comments (comment_rank);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_comment_is_advice ON post_comments (is_actual_advice);
        """)


        conn.commit()
        logger.info("Database tables checked/created successfully.")
    except sqlite3.Error as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def check_post_processed(conn: sqlite3.Connection, post_id: str) -> bool:
    """Checks if a post_id already exists in the processed_posts table."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM processed_posts WHERE post_id = ?", (post_id,))
        return cursor.fetchone() is not None
    except sqlite3.Error as e:
        logger.error(f"Error checking if post {post_id} is processed: {e}")
        return False

# --- insert_processed_post (Updated: comment/similarity fields removed) ---
def insert_processed_post(conn: sqlite3.Connection, data: dict):
    """Inserts a processed post record (post-level data only)."""
    created_utc_val = data.get('created_utc')
    if created_utc_val and not isinstance(created_utc_val, datetime.datetime):
         try:
             if isinstance(created_utc_val, (int, float)):
                 created_utc_val = datetime.datetime.fromtimestamp(created_utc_val, tz=datetime.timezone.utc)
             else:
                 created_utc_val = datetime.datetime.fromisoformat(str(created_utc_val).replace('Z', '+00:00')) # Handle Z notation
         except ValueError:
             logger.warning(f"Could not parse created_utc: {created_utc_val}. Setting to None.")
             created_utc_val = None

    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO processed_posts (
                post_id, post_url, post_title, post_body, created_utc
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO NOTHING;
        """, (
            data.get('post_id'), data.get('post_url'), data.get('post_title'),
            data.get('post_body'), created_utc_val
        ))
        conn.commit()
        if cursor.rowcount > 0:
            logger.info(f"Inserted record into processed_posts for post_id: {data.get('post_id')}")
        else:
             logger.warning(f"processed_posts record for post_id: {data.get('post_id')} likely already existed. No insert performed.")
    except sqlite3.IntegrityError as ie:
         logger.warning(f"Integrity Error inserting into processed_posts for post {data.get('post_id')}: {ie}")
    except sqlite3.Error as e:
        logger.error(f"Error inserting record into processed_posts for post {data.get('post_id')}: {e}")
        conn.rollback()

# --- insert_llm_data (No changes needed here for this request) ---
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
        logger.error(f"Integrity Error inserting LLM data for post {post_id}: {ie}. Does the processed_posts record exist?")
        conn.rollback()
    except sqlite3.Error as e:
        logger.error(f"Error inserting LLM data for post {post_id}: {e}")
        conn.rollback()

# --- insert_post_comment (New function) ---
def insert_post_comment(conn: sqlite3.Connection, comment_data: dict):
    """Inserts data for a single comment into the post_comments table."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO post_comments (
                post_id, comment_id, comment_body, comment_score, comment_rank,
                is_actual_advice, similarity_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(comment_id) DO UPDATE SET
                comment_score = excluded.comment_score,
                is_actual_advice = excluded.is_actual_advice,
                similarity_score = excluded.similarity_score,
                fetched_at = CURRENT_TIMESTAMP;
                -- Note: We generally don't update rank or body on conflict
        """, (
            comment_data.get('post_id'),
            comment_data.get('comment_id'),
            comment_data.get('comment_body'),
            comment_data.get('comment_score'),
            comment_data.get('comment_rank'),
            comment_data.get('is_actual_advice'), # Should be bool or None
            comment_data.get('similarity_score') # Should be float or None
        ))
        conn.commit()
        logger.debug(f"Inserted/Updated comment {comment_data.get('comment_id')} for post {comment_data.get('post_id')}")
    except sqlite3.IntegrityError as ie:
         logger.error(f"Integrity Error inserting comment {comment_data.get('comment_id')}: {ie}. Does post {comment_data.get('post_id')} exist?")
         conn.rollback()
    except sqlite3.Error as e:
        logger.error(f"Error inserting comment {comment_data.get('comment_id')}: {e}")
        conn.rollback()