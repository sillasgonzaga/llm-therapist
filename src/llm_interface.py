import openai
from . import config
from loguru import logger
from typing import Dict, Optional

LLM_NAME = 'gpt-4o-mini'

# Initialize OpenAI client
try:
    # Consider adding timeout configuration
    client = openai.OpenAI(
        api_key=config.OPENAI_API_KEY,
        timeout=30.0 # Example timeout
    )
    logger.info("OpenAI client initialized.")
except Exception as e:
    logger.error(f"Failed to initialize OpenAI client: {e}")
    client = None

def get_llm_response(post_title: str, post_body: str) -> Optional[Dict[str, str]]:
    """
    Gets advice/perspective from the LLM based on the original post content.

    Returns:
        A dictionary containing 'prompt' and 'response' on success, None on failure.
    """
    if not client:
        logger.error("LLM client (get_llm_response) is not initialized.")
        return None

    prompt = f"""
    O seguinte post foi feito no subreddit r/desabafos. Por favor, leia o título e o corpo do post e forneça um conselho ou uma perspectiva útil, empática e construtiva para o autor original (OP). Concentre-se em ser solidário e evite julgamentos.

    Título: {post_title}

    Corpo:
    {post_body}

    Seu conselho/perspectiva para o OP:
    """

    try:
        logger.debug(f"Sending OP advice prompt to LLM for post title: {post_title[:50]}...")
        response = client.chat.completions.create(
            model=LLM_NAME, # Consider cost/speed vs quality (maybe GPT-4 for main advice?)
            messages=[
                {"role": "system", "content": "Você é um assistente prestativo e empático que oferece conselhos construtivos e solidários para posts do r/desabafos."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=350, # Slightly increased tokens maybe
            temperature=0.7,
        )
        llm_answer = response.choices[0].message.content.strip()
        logger.info(f"Received LLM OP advice response for post title: {post_title[:50]}...")
        return {"prompt": prompt, "response": llm_answer}

    except openai.APITimeoutError:
        logger.error(f"OpenAI API request timed out (get_llm_response).")
    except openai.APIError as e:
        logger.error(f"OpenAI API error (get_llm_response): {e}")
    except Exception as e:
        logger.error(f"Error getting LLM response (get_llm_response): {e}", exc_info=True)

    return None

# --- New function for comment verification ---
def verify_comment_advice(post_title: str, post_body: str, comment_body: str) -> Optional[bool]:
    """
    Uses LLM to verify if a comment is actual advice/support for the OP.

    Args:
        post_title: Title of the original post.
        post_body: Body of the original post.
        comment_body: The text of the comment to verify.

    Returns:
        True if the comment is likely advice/support.
        False if it's likely not (e.g., mod post, unrelated question, meta).
        None if the verification fails or the answer is ambiguous.
    """
    if not client:
        logger.error("LLM client (verify_comment_advice) is not initialized.")
        return None

    # Limit comment body length to avoid excessive token usage/cost
    max_comment_len = 500
    truncated_comment_body = comment_body[:max_comment_len]
    if len(comment_body) > max_comment_len:
        logger.warning(f"Comment body truncated to {max_comment_len} chars for verification LLM call.")


    # Limit post body length as well for context
    max_post_body_len = 1000
    truncated_post_body = post_body[:max_post_body_len] if post_body else ""

    verification_prompt = f"""
    Contexto: Post Original no r/desabafos
    Título: {post_title}
    Corpo: {truncated_post_body}
    ---
    Comentário feito neste post:
    "{truncated_comment_body}"
    ---
    Pergunta: Este comentário está fornecendo conselho direto, apoio emocional, uma perspectiva relevante ou uma pergunta construtiva em resposta direta ao conteúdo e desabafo do post original? Foque em diferenciar conselhos/apoio de mensagens automáticas de MOD, perguntas genéricas não relacionadas ao desabafo (ex: "O que aconteceu?"), ou meta-comentários sobre o Reddit.

    Responda APENAS com "Sim" ou "Não".
    """

    try:
        logger.debug(f"Sending verification prompt to LLM for comment: {comment_body[:60]}...")
        response = client.chat.completions.create(
            model=LLM_NAME, # Use a cheaper/faster model if suitable for classification
            messages=[
                {"role": "system", "content": "Você é um classificador de comentários. Analise o comentário no contexto do post original e responda apenas 'Sim' ou 'Não' à pergunta feita."},
                {"role": "user", "content": verification_prompt}
            ],
            max_tokens=10, # Needs only a short answer ("Sim" or "Não")
            temperature=0.1, # Low temperature for consistent classification
            n=1, # Only one completion needed
        )
        verification_answer = response.choices[0].message.content.strip().lower()

        logger.info(f"Received verification response: '{verification_answer}' for comment: {comment_body[:60]}...")

        if verification_answer.startswith("sim"):
            return True
        elif verification_answer.startswith("não") or verification_answer.startswith("nao"):
             return False
        else:
            logger.warning(f"Ambiguous verification response: '{verification_answer}'. Could not determine Yes/No.")
            return None # Ambiguous answer

    except openai.APITimeoutError:
        logger.error(f"OpenAI API request timed out (verify_comment_advice).")
    except openai.APIError as e:
        logger.error(f"OpenAI API error (verify_comment_advice): {e}")
    except Exception as e:
        logger.error(f"Error during comment verification LLM call: {e}", exc_info=True)

    return None # Return None if any error occurred