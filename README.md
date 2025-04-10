# LLM Therapista

A system that scrapes posts and comments from r/desabafos, asks a LLM on its answer about OP's post, compares it with the most upvoted answer and measures its closeness.

## Envrionment creation

uv venv
source .venv/bin/activate

uv pip install -e .
uv run python scripts/setup_database.py
uv run python -m src.pipeline

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
