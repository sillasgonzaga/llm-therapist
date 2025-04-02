# LLM Therapista

A system that scrapes posts and comments from r/desabafos, asks a LLM on its answer about OP's post, compares it with the most upvoted answer and measures its closeness.

## Envrionment creation

uv venv
source .venv/bin/activate

uv pip install -e .
uv run python scripts/setup_database.py
uv run python -m src.pipeline

