import time
import sys # Import sys for logger configuration
import datetime # Import datetime
from pathlib import Path # Import Path
from . import config, database, reddit_scraper, llm_interface, text_analyzer
from loguru import logger

def run_pipeline():
    """Runs the main processing pipeline."""
    logger.info("Starting LLM Desabafos Analyzer pipeline run...")

    # --- Initialization ---
    conn = None
    try:
        reddit = reddit_scraper.get_reddit_instance()
        conn = database.get_db_connection()
        # Ensure tables exist
        database.create_tables(conn)
        # Ensure LLM and Similarity models are loaded (checked within modules)
        if not llm_interface.client:
             raise ConnectionError("LLM Client failed to initialize.")
        if not text_analyzer.similarity_model:
            raise RuntimeError("Similarity model failed to load.")

    except Exception as e:
        logger.error(f"Pipeline initialization failed: {e}")
        if conn:
            conn.close()
        return

    # --- Fetch Posts ---
    posts = reddit_scraper.get_subreddit_posts(reddit, config.SUBREDDIT_NAME, config.POST_LIMIT)
    if not posts:
        logger.warning("No posts fetched. Exiting pipeline.")
        if conn:
            conn.close()
        return

    # --- Process Posts ---
    processed_count = 0
    skipped_count = 0
    error_count = 0
    for submission in posts:
        post_id = submission.id # Get post_id early for logging
        try:
            logger.info(f"Processing post ID: {post_id} | Title: {submission.title[:60]}...")

            # 1. Check if already processed (in processed_posts)
            # We might still want to update LLM data even if processed,
            # but for simplicity, let's skip if the main record exists.
            if database.check_post_processed(conn, post_id):
                logger.info(f"Post {post_id} already processed. Skipping.")
                skipped_count += 1
                continue

            # 2. Extract Post Data
            post_data = reddit_scraper.extract_post_data(submission)

            # 3. Get Top Comment
            top_comment = reddit_scraper.get_top_comment(submission)
            comment_data = reddit_scraper.extract_comment_data(top_comment)

            if not top_comment or not comment_data.get("top_comment_body"):
                logger.warning(f"Skipping post {post_id} due to no valid top comment found.")
                skipped_count +=1
                time.sleep(2)
                continue

            # --- LLM Interaction and Storing ---
            # 4. Get LLM Response (returns dict with 'prompt' and 'response')
            llm_result = llm_interface.get_llm_response(post_data['post_title'], post_data['post_body'])

            llm_response_text = None # Initialize
            if llm_result:
                llm_prompt = llm_result['prompt']
                llm_response_text = llm_result['response']
                 # Insert LLM data first (or update if exists)
                 # Note: This insert happens *before* the main processed_posts insert.
                 # The FK constraint requires processed_posts record to exist first.
                 # Let's insert processed_posts first, then llm_data.

            else:
                logger.error(f"Failed to get LLM response for post {post_id}. Skipping LLM data storage and similarity.")
                # Decide if you still want to store the post data without LLM info
                # For now, let's skip the entire post if LLM fails
                error_count += 1
                time.sleep(5)
                continue # Skip to next post

            # --- Similarity Calculation ---
            # 5. Calculate Similarity (only if LLM response was successful)
            similarity_score = None
            if llm_response_text:
                 similarity_score = text_analyzer.calculate_similarity(
                     comment_data['top_comment_body'],
                     llm_response_text # Use the extracted response text
                 )
                 if similarity_score is None:
                     logger.warning(f"Could not calculate similarity for post {post_id}. Storing post without score.")


            # --- Store Results ---
            # 6. Store Core Post Data (without LLM response)
            # Ensure 'created_utc' is correctly formatted or handled in insert function
            processed_data = {
                **post_data,
                **comment_data,
                "similarity_score": similarity_score, # Store similarity here
            }
            # Insert into processed_posts first because llm_data has a FK constraint
            database.insert_processed_post(conn, processed_data)

            # 7. Store LLM Data (linked to the post_id)
            # Check again if llm_result was successful before inserting
            if llm_result:
                 database.insert_llm_data(conn, post_id, llm_result['prompt'], llm_result['response'])

            processed_count += 1

            # Add delay
            time.sleep(5)

        except KeyboardInterrupt:
            logger.warning("Pipeline interrupted by user.")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred processing post {post_id}: {e}", exc_info=True)
            error_count += 1
            time.sleep(10)

    # --- Cleanup ---
    if conn:
        conn.close()
        logger.info("Database connection closed.")

    logger.info(f"Pipeline run finished. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count}")


if __name__ == '__main__':
    # Configure Loguru
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True) # Ensure logs directory exists
    log_file_path = log_dir / "pipeline_{time}.log"

    # Remove default logger and add custom ones
    logger.remove()
    logger.add(log_file_path, rotation="1 day", retention="7 days", level=config.LOG_LEVEL) # Log to file
    logger.add(sys.stderr, level=config.LOG_LEVEL) # Log to console

    run_pipeline()