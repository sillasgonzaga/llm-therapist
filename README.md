# LLM Therapist

LLM Therapist is a system designed to analyze posts and comments from the subreddit `r/desabafos`. It uses a Language Learning Model (LLM) to provide empathetic and constructive advice for original posts (OPs) and compares the LLM's responses with the most upvoted comments from the subreddit. The system also calculates the semantic similarity between the LLM's advice and the top comments.

## Project Structure

The project is organized into the following directories and files:

- **`src/`**: Contains the core application logic.
  - `pipeline.py`: The main pipeline that orchestrates the scraping, LLM interaction, and database operations.
  - `reddit_scraper.py`: Handles Reddit API interactions to fetch posts and comments.
  - `llm_interface.py`: Manages interactions with the LLM (e.g., OpenAI GPT).
  - `text_analyzer.py`: Provides utilities for calculating semantic similarity between texts.
  - `database.py`: Handles SQLite database operations.
  - `database_cloud_sql.py`: Manages database interactions for Google Cloud SQL.
  - `config.py`: Centralized configuration for environment variables and project settings.

- **`scripts/`**: Contains utility scripts.
  - `setup_database.py`: Initializes the database by creating necessary tables.

- **`notebooks/`**: Jupyter notebooks for data exploration and analysis.
  - `explore_results.ipynb`: Used to query and analyze data stored in the database.

- **`data/`**: Stores local data files.
  - `desabafos_data.db`: SQLite database file.
  - `queries.sql`: SQL queries for data analysis.

- **`logs/`**: Stores log files generated during pipeline execution.

- **`.github/`**: Contains GitHub-specific configurations.
  - `copilot-instructions.md`: Guidelines for using GitHub Copilot.

- **Configuration Files**:
  - `Dockerfile`: Defines the containerization setup for the project.
  - `.dockerignore`: Specifies files and directories to exclude from the Docker image.
  - `.gitignore`: Specifies files and directories to exclude from version control.
  - `pyproject.toml`: Defines project dependencies and build configurations.
  - `config.yaml`: Placeholder for runtime configuration.

## Features

1. **Reddit Scraping**: Fetches posts and comments from the subreddit `r/desabafos`.
2. **LLM Integration**: Uses OpenAI's GPT model to generate advice for posts.
3. **Semantic Analysis**: Compares LLM-generated advice with top comments using sentence embeddings.
4. **Database Storage**: Stores processed posts, LLM responses, and comments in a database.
5. **Cloud Deployment**: Supports deployment on Google Cloud Run with Cloud SQL integration.

## Environment Setup

To set up the project locally, follow these steps:

1. Create a virtual environment using `uv`:
   ```bash
   uv venv
   source .venv/bin/activate
   ```

2. Install the project dependencies:
   ```bash
   uv pip install -e .
   ```

3. Initialize the database:
   ```bash
   uv run python scripts/setup_database.py
   ```

4. Run the pipeline:
   ```bash
   uv run python -m src.pipeline
   ```

## Cloud Deployment
* GCP project created

### Create Artifact Registry Repository:
Go to Artifact Registry in the GCP Console.  
Click "Create Repository".  
Give it a name (e.g., llm-desabafos-repo).  
Select "Docker" as the format.  
Choose a Region (e.g., southamerica-east1 for São Paulo, or another region close to you/your users). Note this region.
Click "Create".

### Cloud Run setup
Go to Cloud Run in the GCP Console.
Click "Create Service" (or "Create Job" if it only runs periodically and doesn't need an HTTP endpoint). Let's assume "Service" for now, which can also be triggered periodically.
Choose "Deploy one revision from an existing container image". You can use a placeholder public image initially (like hello-world or python:slim) just to create the service. You'll replace it via CI/CD later.
Give the service a name (e.g., llm-desabafos-analyzer).
Select the same Region as your Artifact Registry.
Under "Authentication", choose "Allow unauthenticated invocations" if you need to trigger it via HTTP publicly (less likely for a batch job) or "Require authentication" (more common for background jobs triggered internally or via Cloud Scheduler).
Configure CPU, Memory, Timeout etc. under "Container(s), Volumes, Networking, Security". Pay attention to the timeout if your pipeline runs long.
Click "Create". Note the service name and region.
