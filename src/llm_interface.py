import openai
from . import config
from loguru import logger
from typing import Dict, Optional # Added typing

LLM_NAME = 'gpt-4o-mini'

# Initialize OpenAI client
# Ensure OPENAI_API_KEY is set in your .env file
try:
    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    logger.info("OpenAI client initialized.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None # Set client to None if initialization fails

# --- Updated get_llm_response ---
def get_llm_response(post_title: str, post_body: str) -> Optional[Dict[str, str]]:
    """
    Gets a response from the LLM based on the post content.

    Returns:
        A dictionary containing 'prompt' and 'response' on success, None on failure.
    """
    if not client:
        logger.error("LLM client is not initialized. Cannot get response.")
        return None

    # Define the exact prompt being sent
    prompt = f"""
    O seguinte post foi feito no subreddit r/desabafos. Por favor, leia o título e o corpo do post e forneça um conselho ou uma perspectiva útil, empática e construtiva para o autor original (OP). Concentre-se em ser solidário e evite julgamentos.

    Título: {post_title}

    Corpo:
    {post_body}

    Seu conselho/perspectiva para o OP:
    """

    try:
        logger.debug(f"Sending prompt to LLM for post title: {post_title[:50]}...")
        response = client.chat.completions.create(
            model=LLM_NAME, # Or choose another model like gpt-4
            messages=[
                {"role": "system", "content": "Você é um assistente prestativo e empático que oferece conselhos construtivos."},
                {"role": "user", "content": prompt} # Use the defined prompt variable
            ],
            max_tokens=300, # Adjust token limit as needed
            temperature=0.7, # Adjust creativity/randomness
        )
        llm_answer = response.choices[0].message.content.strip()
        logger.info(f"Received LLM response for post title: {post_title[:50]}...")
        # Return both the prompt and the response
        return {"prompt": prompt, "response": llm_answer}

    except openai.APIError as e:
        logger.error(f"OpenAI API error: {e}")
    except Exception as e:
        logger.error(f"Error getting LLM response: {e}")

    return None # Return None if any error occurred

