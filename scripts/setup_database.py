import sys
import os

# Add src directory to Python path to allow importing modules from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database import get_db_connection, create_tables
from loguru import logger

def main():
    logger.info("Setting up database...")
    conn = None
    try:
        conn = get_db_connection()
        create_tables(conn)
        logger.info("Database setup complete.")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")

if __name__ == "__main__":
    main()