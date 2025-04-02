import time
import sys
from pathlib import Path
from . import config, database, reddit_scraper, llm_interface, text_analyzer
from loguru import logger

# Delay between processing posts (in seconds)
POST_PROCESSING_DELAY = 5
# Delay between LLM calls within a single post's processing (in seconds)
INTRA_POST_LLM_DELAY = 3 # Increase if hitting rate limits

def run_pipeline():
    """Runs the main processing pipeline."""
    logger.info("Starting LLM Desabafos Analyzer pipeline run...")

    # --- Initialization ---
    conn = None
    try:
        reddit = reddit_scraper.get_reddit_instance()
        conn = database.get_db_connection()
        database.create_tables(conn)
        if not llm_interface.client:
             raise ConnectionError("LLM Client failed to initialize.")
        if not text_analyzer.similarity_model:
            raise RuntimeError("Similarity model failed to load.")
    except Exception as e:
        logger.error(f"Pipeline initialization failed: {e}")
        if conn: conn.close()
        return

    # --- Fetch Posts ---
    posts = reddit_scraper.get_subreddit_posts(reddit, config.SUBREDDIT_NAME, config.POST_LIMIT)
    if not posts:
        logger.warning("No posts fetched. Exiting pipeline.")
        if conn: conn.close()
        return

    # --- Process Posts ---
    processed_count = 0
    skipped_count = 0
    error_count = 0
    for submission in posts:
        post_id = submission.id
        main_llm_advice_response = None # Store the main advice for similarity calculation
        llm_call_successful = False # Track if main LLM call worked

        try:
            logger.info(f"--- Processing Post ID: {post_id} | Title: {submission.title[:60]}... ---")

            # 1. Check if already processed (basic check, might need refinement)
            if database.check_post_processed(conn, post_id):
                logger.info(f"Post {post_id} core data already exists. Skipping.")
                skipped_count += 1
                continue # Skip entire post processing if base record exists

            # 2. Extract Post Data
            post_data = reddit_scraper.extract_post_data(submission)
            post_title = post_data['post_title']
            post_body = post_data['post_body']

            # 3. Get Main LLM Advice for the Original Post
            logger.info(f"Getting main LLM advice for OP (Post {post_id})...")
            llm_op_result = llm_interface.get_llm_response(post_title, post_body)
            time.sleep(INTRA_POST_LLM_DELAY) # Delay after LLM call

            if llm_op_result:
                # Check if LLM call was successful
                main_llm_advice_response = llm_op_result['response']
                llm_call_successful = True
                # Insert LLM OP data (prompt + response) immediately after getting it
                database.insert_processed_post(conn, post_data)
                database.insert_llm_data(conn, post_id, llm_op_result['prompt'], main_llm_advice_response)
                logger.info(f"Main LLM advice for post {post_id} stored successfully.")
            else:
                logger.error(f"Failed to get LLM advice for post {post_id}. Cannot proceed with comments for this post.")
                # Insert core post data even if LLM fails? Or skip? Let's skip for now.
                error_count += 1
                
                time.sleep(POST_PROCESSING_DELAY) # Wait before next post
                continue

            # 4. Get Top Comments (if main LLM call was successful)
            logger.info(f"Fetching top comments for post {post_id}...")
            top_comments = reddit_scraper.get_top_comments(submission, limit=reddit_scraper.MAX_COMMENTS_TO_FETCH)
            time.sleep(1) # Small delay after Reddit API call

            if not top_comments:
                logger.warning(f"No suitable top comments found for post {post_id}. Storing post data only.")
                # Insert core post data even if no comments found
                #database.insert_processed_post(conn, post_data)
                processed_count += 1 # Count as processed (even without comments)
                time.sleep(POST_PROCESSING_DELAY) # Wait before next post
                continue

            # --- Process Each Top Comment ---
            logger.info(f"Processing {len(top_comments)} comments for post {post_id}...")
            comments_processed_count = 0
            for rank, comment in enumerate(top_comments, start=1):
                comment_id = comment.id
                comment_body = comment.body
                comment_score = comment.score
                is_actual_advice = None
                similarity_score = None

                # 5. Verify Comment using LLM
                logger.debug(f"Verifying comment rank {rank} (ID: {comment_id}) for post {post_id}...")
                is_actual_advice = llm_interface.verify_comment_advice(post_title, post_body, comment_body)
                time.sleep(INTRA_POST_LLM_DELAY) # Delay after *each* verification LLM call

                if is_actual_advice is None:
                     logger.warning(f"Verification failed or was ambiguous for comment {comment_id}.")

                # 6. Calculate Similarity (e.g., only for Rank 1 comment vs main LLM advice)
                if rank == 1 and main_llm_advice_response:
                    logger.debug(f"Calculating similarity for rank 1 comment {comment_id}...")
                    similarity_score = text_analyzer.calculate_similarity(
                        comment_body,
                        main_llm_advice_response
                    )
                    if similarity_score is None:
                         logger.warning(f"Could not calculate similarity for comment {comment_id}.")

                # 7. Store Comment Data
                comment_data = {
                    'post_id': post_id,
                    'comment_id': comment_id,
                    'comment_body': comment_body,
                    'comment_score': comment_score,
                    'comment_rank': rank,
                    'is_actual_advice': is_actual_advice,
                    'similarity_score': similarity_score
                }
                database.insert_post_comment(conn, comment_data)
                comments_processed_count += 1


            # 8. Store Core Post Data (after processing comments)
            # This ensures the post record exists before comments with FK are inserted
            # (Correction: Moved insert_llm_data earlier, insert post data here)
            database.insert_processed_post(conn, post_data)
            processed_count += 1
            logger.success(f"Finished processing post {post_id} with {comments_processed_count} comments.")

            # Delay before processing the next post
            time.sleep(POST_PROCESSING_DELAY)

        except KeyboardInterrupt:
            logger.warning("Pipeline interrupted by user.")
            break
        except Exception as e:
            logger.error(f"An unexpected error occurred processing post {post_id}: {e}", exc_info=True)
            error_count += 1
            time.sleep(POST_PROCESSING_DELAY * 2) # Longer delay after an error

    # --- Cleanup ---
    if conn:
        conn.close()
        logger.info("Database connection closed.")

    logger.info(f"Pipeline run finished. Posts processed: {processed_count}, Posts skipped: {skipped_count}, Post errors: {error_count}")


if __name__ == '__main__':
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file_path = log_dir / "pipeline_{time}.log"

    logger.remove()
    logger.add(log_file_path, rotation="1 day", retention="7 days", level=config.LOG_LEVEL, backtrace=True, diagnose=True) # Enhanced logging
    logger.add(sys.stderr, level="INFO") # Keep console INFO level clean

    run_pipeline()