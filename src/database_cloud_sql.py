import os
import datetime
from contextlib import contextmanager # For session management alternative
from loguru import logger
from typing import Generator, Optional

# Third-party imports
import sqlalchemy
from sqlalchemy import create_engine, text, exc
from sqlalchemy.orm import sessionmaker, Session

# Google Cloud specific imports
from google.cloud.sql.connector import Connector, IPTypes

# Local imports
from . import config # Import necessary config variables

# --- Global Variables ---
connector: Optional[Connector] = None
engine: Optional[sqlalchemy.engine.Engine] = None
SessionLocal: Optional[sessionmaker[Session]] = None

def init_connection_pool() -> sqlalchemy.engine.Engine:
    """
    Initializes a connection pool for Cloud SQL based on configuration.
    Uses the Cloud SQL Python Connector.
    """
    global connector
    if connector is None:
        logger.info("Initializing Cloud SQL Connector...")
        connector = Connector()

    # Function to return database connection using connector
    def getconn() -> sqlalchemy.engine.interfaces.DBAPIConnection:
        conn = connector.connect(
            config.INSTANCE_CONNECTION_NAME,    # Cloud SQL Instance Connection Name
            config.DB_DRIVER.split('+')[1],     # "psycopg2" or "pg8000"
            user=config.DB_USER,
            password=config.DB_PASS,
            db=config.DB_NAME,
            ip_type=IPTypes.PRIVATE if os.getenv("GOOGLE_CLOUD_RUN_JOB") else IPTypes.PUBLIC, # Use Private IP within GCP VPC, Public for local dev/testing
            enable_iam_auth=config.ENABLE_IAM_AUTH # Use IAM DB Auth if enabled and running in Cloud Run
        )
        logger.debug("Cloud SQL connection established via Connector.")
        return conn

    try:
        logger.info(f"Creating SQLAlchemy engine for {config.DB_DRIVER}...")
        # Create the engine using the connector's connection function
        # pool_size, max_overflow, etc. can be configured here if needed
        # pool_timeout and pool_recycle are important for long-running apps, maybe less so for batch jobs
        db_engine = create_engine(
            f"{config.DB_DRIVER}://", # Use driver name from config
            creator=getconn,
            pool_size=5,        # Default pool size
            max_overflow=2,     # Default max overflow
            pool_timeout=30,    # Wait 30s for a connection
            pool_recycle=1800   # Recycle connections older than 30 mins
        )
        logger.info("SQLAlchemy engine created successfully.")
        return db_engine
    except Exception as e:
        logger.error(f"Error creating SQLAlchemy engine: {e}", exc_info=True)
        raise

def get_engine() -> sqlalchemy.engine.Engine:
    """Returns the SQLAlchemy engine, initializing it if necessary."""
    global engine
    if engine is None:
        engine = init_connection_pool()
    return engine

def get_session_local() -> sessionmaker[Session]:
    """Returns the SQLAlchemy SessionLocal factory, initializing it if necessary."""
    global SessionLocal
    if SessionLocal is None:
        db_engine = get_engine()
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
        logger.info("SQLAlchemy SessionLocal factory created.")
    return SessionLocal

# --- Context Manager for Sessions ---
@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session_factory = get_session_local()
    session = session_factory()
    try:
        yield session
        session.commit()
        logger.debug("Session committed.")
    except Exception as e:
        logger.error(f"Session rollback initiated due to error: {e}", exc_info=True)
        session.rollback()
        raise # Re-raise the exception after rollback
    finally:
        session.close()
        logger.debug("Session closed.")

# --- Database Operations ---

def create_tables():
    """Creates the necessary tables using raw SQL if they don't exist."""
    # Note: Using SQLAlchemy models and metadata.create_all(engine) is more robust
    # But sticking to raw SQL for minimal changes from original code.
    # Using TIMESTAMPTZ for PostgreSQL timezone support.
    # Using BOOLEAN native type.
    # Using REAL which maps to float4 in PostgreSQL.
    create_posts_sql = text("""
        CREATE TABLE IF NOT EXISTS processed_posts (
            id SERIAL PRIMARY KEY,
            post_id TEXT UNIQUE NOT NULL,
            post_url TEXT NOT NULL,
            post_title TEXT,
            post_body TEXT,
            created_utc TIMESTAMPTZ,
            processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );
    """)
    create_posts_idx_sql = text("CREATE INDEX IF NOT EXISTS idx_post_id ON processed_posts (post_id);")

    create_llm_sql = text("""
        CREATE TABLE IF NOT EXISTS llm_data (
            id SERIAL PRIMARY KEY,
            post_id TEXT NOT NULL UNIQUE,
            input_prompt TEXT NOT NULL,
            llm_response TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES processed_posts(post_id) ON DELETE CASCADE
        );
    """)
    # No separate index needed for llm_data.post_id due to UNIQUE constraint

    create_comments_sql = text("""
        CREATE TABLE IF NOT EXISTS post_comments (
            id SERIAL PRIMARY KEY,
            post_id TEXT NOT NULL,
            comment_id TEXT UNIQUE NOT NULL,
            comment_body TEXT,
            comment_score INTEGER,
            comment_rank INTEGER NOT NULL,
            is_actual_advice BOOLEAN,
            similarity_score REAL,
            fetched_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES processed_posts(post_id) ON DELETE CASCADE
        );
    """)
    create_comments_idx_post_sql = text("CREATE INDEX IF NOT EXISTS idx_comment_post_id ON post_comments (post_id);")
    create_comments_idx_rank_sql = text("CREATE INDEX IF NOT EXISTS idx_comment_rank ON post_comments (comment_rank);")
    create_comments_idx_advice_sql = text("CREATE INDEX IF NOT EXISTS idx_comment_is_advice ON post_comments (is_actual_advice);")

    logger.info("Attempting to create/verify database tables...")
    try:
        with get_db_session() as session:
            session.execute(create_posts_sql)
            session.execute(create_posts_idx_sql)
            session.execute(create_llm_sql)
            session.execute(create_comments_sql)
            session.execute(create_comments_idx_post_sql)
            session.execute(create_comments_idx_rank_sql)
            session.execute(create_comments_idx_advice_sql)
        logger.info("Database tables checked/created successfully.")
    except exc.SQLAlchemyError as e:
        logger.error(f"Error creating database tables: {e}", exc_info=True)
        raise


def check_post_processed(post_id: str) -> bool:
    """Checks if a post_id already exists in the processed_posts table."""
    query = text("SELECT 1 FROM processed_posts WHERE post_id = :post_id LIMIT 1")
    try:
        with get_db_session() as session:
            result = session.execute(query, {"post_id": post_id}).scalar_one_or_none()
            return result is not None
    except exc.SQLAlchemyError as e:
        logger.error(f"Error checking if post {post_id} is processed: {e}", exc_info=True)
        return False # Assume not processed on error

def insert_processed_post(data: dict):
    """Inserts a processed post record (post-level data only)."""
    created_utc_val = data.get('created_utc')
    # Basic type check, already handles datetime in scraper
    if created_utc_val and not isinstance(created_utc_val, datetime.datetime):
         logger.warning(f"Non-datetime value passed for created_utc: {created_utc_val}. Attempting insert anyway.")

    sql = text("""
        INSERT INTO processed_posts (
            post_id, post_url, post_title, post_body, created_utc
        ) VALUES (:post_id, :post_url, :post_title, :post_body, :created_utc)
        ON CONFLICT (post_id) DO NOTHING;
    """)
    params = {
        "post_id": data.get('post_id'),
        "post_url": data.get('post_url'),
        "post_title": data.get('post_title'),
        "post_body": data.get('post_body'),
        "created_utc": created_utc_val
    }
    try:
        with get_db_session() as session:
            result = session.execute(sql, params)
            if result.rowcount > 0:
                logger.info(f"Inserted record into processed_posts for post_id: {data.get('post_id')}")
            # No warning needed for rowcount == 0 due to ON CONFLICT DO NOTHING
    except exc.IntegrityError:
         # Should ideally not happen with ON CONFLICT DO NOTHING unless another constraint fails
         logger.warning(f"Integrity Error on insert into processed_posts for post {data.get('post_id')}. Might indicate unexpected issue.")
    except exc.SQLAlchemyError as e:
        logger.error(f"Error inserting record into processed_posts for post {data.get('post_id')}: {e}", exc_info=True)
        # Rollback is handled by context manager

def insert_llm_data(post_id: str, input_prompt: str, llm_response: str):
    """Inserts LLM interaction data into the llm_data table."""
    # PostgreSQL ON CONFLICT syntax
    sql = text("""
        INSERT INTO llm_data (post_id, input_prompt, llm_response)
        VALUES (:post_id, :input_prompt, :llm_response)
        ON CONFLICT (post_id) DO UPDATE SET
            input_prompt = EXCLUDED.input_prompt,
            llm_response = EXCLUDED.llm_response,
            created_at = CURRENT_TIMESTAMP;
    """)
    params = {
        "post_id": post_id,
        "input_prompt": input_prompt,
        "llm_response": llm_response
    }
    try:
        with get_db_session() as session:
            session.execute(sql, params)
            logger.debug(f"Inserted/Updated record in llm_data for post_id: {post_id}")
    except exc.IntegrityError as ie:
        logger.error(f"Integrity Error inserting LLM data for post {post_id}: {ie}. FK constraint failed?", exc_info=True)
    except exc.SQLAlchemyError as e:
        logger.error(f"Error inserting LLM data for post {post_id}: {e}", exc_info=True)

def insert_post_comment(comment_data: dict):
    """Inserts data for a single comment into the post_comments table."""
     # PostgreSQL ON CONFLICT syntax
    sql = text("""
        INSERT INTO post_comments (
            post_id, comment_id, comment_body, comment_score, comment_rank,
            is_actual_advice, similarity_score
        ) VALUES (
            :post_id, :comment_id, :comment_body, :comment_score, :comment_rank,
            :is_actual_advice, :similarity_score
        )
        ON CONFLICT (comment_id) DO UPDATE SET
            comment_score = EXCLUDED.comment_score,
            is_actual_advice = EXCLUDED.is_actual_advice,
            similarity_score = EXCLUDED.similarity_score,
            fetched_at = CURRENT_TIMESTAMP;
    """)
    params = {
        "post_id": comment_data.get('post_id'),
        "comment_id": comment_data.get('comment_id'),
        "comment_body": comment_data.get('comment_body'),
        "comment_score": comment_data.get('comment_score'),
        "comment_rank": comment_data.get('comment_rank'),
        "is_actual_advice": comment_data.get('is_actual_advice'),
        "similarity_score": comment_data.get('similarity_score')
    }
    try:
        with get_db_session() as session:
            session.execute(sql, params)
            logger.debug(f"Inserted/Updated comment {comment_data.get('comment_id')} for post {comment_data.get('post_id')}")
    except exc.IntegrityError as ie:
         logger.error(f"Integrity Error inserting comment {comment_data.get('comment_id')}: {ie}. FK constraint failed?", exc_info=True)
    except exc.SQLAlchemyError as e:
        logger.error(f"Error inserting comment {comment_data.get('comment_id')}: {e}", exc_info=True)


# --- Cleanup Function (Optional) ---
def close_connection_pool():
    """Closes the Cloud SQL connector and disposes the engine."""
    global engine, connector, SessionLocal
    logger.info("Attempting to close database connection pool...")
    if engine:
        engine.dispose()
        engine = None
        logger.info("SQLAlchemy engine disposed.")
    if connector:
        connector.close()
        connector = None
        logger.info("Cloud SQL Connector closed.")
    SessionLocal = None

# It's generally recommended to initialize the engine once when the application starts.
# For a script like this, calling get_engine() the first time a connection is needed works.
# Ensure close_connection_pool() is called on application shutdown if necessary,
# although for short-lived Cloud Run jobs, it might not be strictly required.