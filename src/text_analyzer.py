from sentence_transformers import SentenceTransformer, util
from . import config
from loguru import logger
import torch # Or tensorflow, depending on your installation

# Load the sentence transformer model globally for efficiency
# This might take a few seconds the first time it's run
try:
    # Check for GPU availability
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    logger.info(f"Using device: {device} for sentence transformer model.")
    similarity_model = SentenceTransformer(config.SIMILARITY_MODEL, device=device)
    logger.info(f"Sentence transformer model '{config.SIMILARITY_MODEL}' loaded successfully.")
except Exception as e:
    logger.error(f"Failed to load sentence transformer model '{config.SIMILARITY_MODEL}': {e}")
    similarity_model = None

def calculate_similarity(text1: str, text2: str) -> float | None:
    """Calculates cosine similarity between two texts using sentence embeddings."""
    if not similarity_model:
        logger.error("Similarity model not loaded. Cannot calculate similarity.")
        return None
    if not text1 or not text2:
        logger.warning("One or both texts are empty. Cannot calculate similarity.")
        return 0.0 # Or None, depending on how you want to handle empty inputs

    try:
        # Encode the texts into embeddings
        embedding1 = similarity_model.encode(text1, convert_to_tensor=True)
        embedding2 = similarity_model.encode(text2, convert_to_tensor=True)

        # Calculate cosine similarity
        cosine_scores = util.pytorch_cos_sim(embedding1, embedding2)
        similarity_score = cosine_scores.item() # Get the single score value

        # Clamp score between 0 and 1 (sometimes scores can be slightly outside due to float precision)
        similarity_score = max(0.0, min(1.0, similarity_score))

        logger.debug(f"Calculated similarity score: {similarity_score:.4f}")
        return similarity_score

    except Exception as e:
        logger.error(f"Error calculating text similarity: {e}")
        return None