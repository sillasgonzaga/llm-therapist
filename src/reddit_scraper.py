import praw
from . import config
from loguru import logger
import datetime

def get_reddit_instance():
    """Initializes and returns a PRAW Reddit instance."""
    try:
        reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT,
            # Optional: Add username/password for actions requiring a user account
            # username="your_reddit_username",
            # password="your_reddit_password",
        )
        reddit.read_only = True # Set to False if you need to perform actions like commenting/voting
        logger.info(f"PRAW Reddit instance created. Read-only: {reddit.read_only}")
        return reddit
    except Exception as e:
        logger.error(f"Failed to create PRAW Reddit instance: {e}")
        raise

def get_subreddit_posts(reddit: praw.Reddit, subreddit_name: str, limit: int):
    """Fetches recent posts from a specified subreddit."""
    try:
        subreddit = reddit.subreddit(subreddit_name)
        # Fetching 'new' posts. You could also use 'hot' or 'top'.
        posts = list(subreddit.new(limit=limit))
        logger.info(f"Fetched {len(posts)} posts from r/{subreddit_name}")
        return posts
    except Exception as e:
        logger.error(f"Failed to fetch posts from r/{subreddit_name}: {e}")
        return []

def get_top_comment(submission: praw.models.Submission):
    """Finds the most upvoted, non-stickied, non-deleted comment in a submission."""
    try:
        submission.comments.replace_more(limit=0) # Load top-level comments only
        top_comment = None
        max_score = -1 # Initialize with a score lower than any possible comment score

        for comment in submission.comments.list():
            # Skip stickied comments, deleted comments, or moderator comments if desired
            if isinstance(comment, praw.models.Comment) and \
               not comment.stickied and \
               comment.author is not None and \
               comment.body != '[deleted]' and \
               comment.body != '[removed]':
                if comment.score > max_score:
                    max_score = comment.score
                    top_comment = comment

        if top_comment:
            logger.debug(f"Found top comment (ID: {top_comment.id}, Score: {top_comment.score}) for post {submission.id}")
            return top_comment
        else:
            logger.warning(f"No suitable top comment found for post {submission.id}")
            return None
    except Exception as e:
        logger.error(f"Error fetching top comment for post {submission.id}: {e}")
        return None

def extract_post_data(submission: praw.models.Submission) -> dict:
    """Extracts relevant data from a PRAW submission object."""
    return {
        "post_id": submission.id,
        "post_url": submission.permalink,
        "post_title": submission.title,
        "post_body": submission.selftext,
        "created_utc": datetime.datetime.fromtimestamp(submission.created_utc, tz=datetime.timezone.utc),
    }

def extract_comment_data(comment: praw.models.Comment) -> dict:
    """Extracts relevant data from a PRAW comment object."""
    if not comment:
        return {
            "top_comment_id": None,
            "top_comment_body": None,
            "top_comment_score": None,
        }
    return {
        "top_comment_id": comment.id,
        "top_comment_body": comment.body,
        "top_comment_score": comment.score,
    }