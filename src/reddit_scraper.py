import praw
import prawcore # Import prawcore for specific exceptions
from . import config
from loguru import logger
import datetime
from typing import List, Optional
import time
# Max comments to fetch and consider per post
MAX_COMMENTS_TO_FETCH = 5

def get_reddit_instance():
    """Initializes and returns a PRAW Reddit instance."""
    try:
        reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT,
        )
        reddit.read_only = True
        logger.info(f"PRAW Reddit instance created. Read-only: {reddit.read_only}")
        return reddit
    except Exception as e:
        logger.error(f"Failed to create PRAW Reddit instance: {e}")
        raise

def get_subreddit_posts(reddit: praw.Reddit, subreddit_name: str, limit: int):
    """Fetches recent posts from a specified subreddit."""
    try:
        subreddit = reddit.subreddit(subreddit_name)
        all_posts = list(subreddit.new(limit=limit*3))  # Fetch more to ensure we get enough recent posts
        # Filter posts to only include those from the last 24 hours
        twenty_four_hours_ago = time.time() - 24 * 60 * 60  # 24 hours in seconds
        posts = [submission for submission in all_posts if submission.created_utc >= twenty_four_hours_ago]

        # Limit to the specified number of posts
        posts = posts[:limit]
        # Log the number of posts fetched
        if len(posts) < limit:
            logger.warning(f"Fetched only {len(posts)} posts from r/{subreddit_name} instead of {limit}.")
        else:
            logger.info(f"Fetched {limit} posts from r/{subreddit_name}.")
        return posts
    except Exception as e:
        logger.error(f"Failed to fetch posts from r/{subreddit_name}: {e}")
        return []

# --- Renamed and modified from get_top_comment ---
def get_top_comments(submission: praw.models.Submission, limit: int = MAX_COMMENTS_TO_FETCH) -> List[praw.models.Comment]:
    """
    Finds the most upvoted, non-stickied, non-deleted, non-mod comments
    in a submission, up to a specified limit.
    """
    top_comments = []
    try:
        # Sort comments by 'score' (PRAW might internally use 'top' or requires manual sort after fetch)
        # It's safer to fetch and sort manually
        submission.comment_sort = "top" # Suggest sorting, but PRAW handling varies
        submission.comments.replace_more(limit=0) # Load top-level comments

        candidate_comments = []
        for comment in submission.comments.list():
             # Filter out unwanted comments
             if isinstance(comment, praw.models.Comment) and \
               not comment.stickied and \
               comment.author is not None and \
               comment.body not in ('[deleted]', '[removed]') and \
               comment.distinguished not in ('moderator', 'admin'): # Exclude mod/admin comments explicitly
                 candidate_comments.append(comment)

        # Sort the candidates by score descending
        candidate_comments.sort(key=lambda c: c.score, reverse=True)

        # Take the top 'limit' comments
        top_comments = candidate_comments[:limit]

        logger.info(f"Found {len(top_comments)} top comments for post {submission.id} (limit: {limit})")
        return top_comments

    except prawcore.exceptions.NotFound:
         logger.warning(f"Post {submission.id} might have been deleted, comments not accessible.")
         return []
    except Exception as e:
        logger.error(f"Error fetching comments for post {submission.id}: {e}", exc_info=True)
        return [] # Return empty list on error


def extract_post_data(submission: praw.models.Submission) -> dict:
    """Extracts relevant data from a PRAW submission object."""
    return {
        "post_id": submission.id,
        "post_url": f"https://www.reddit.com{submission.permalink}", # Ensure full URL
        "post_title": submission.title,
        "post_body": submission.selftext,
        # Ensure UTC timezone awareness
        "created_utc": datetime.datetime.fromtimestamp(submission.created_utc, tz=datetime.timezone.utc),
    }

# Removed extract_comment_data as it's handled differently now