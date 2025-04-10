# Stage 1: Builder - Install dependencies using uv
FROM python:3.11-slim as builder

# Install uv
# Use a recent version of uv
ENV UV_VERSION=0.1.16 
RUN pip install --no-cache-dir uv==${UV_VERSION}

WORKDIR /app

# Copy only necessary files for dependency installation
COPY pyproject.toml ./

# Install dependencies into a virtual environment using uv
# Using sync ensures only specified dependencies are installed
# This creates a venv at /app/.venv
RUN uv venv && \
    uv pip sync pyproject.toml

# ---

# Stage 2: Runtime - Create the final image
FROM python:3.11-slim

WORKDIR /app

# Set environment variables for Python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create a non-root user and group
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /.venv

# Copy application code
COPY ./src ./src
COPY ./scripts ./scripts
# Copy config loading related files if needed at runtime (or handle via env vars)
# COPY .env . # Avoid copying .env into image; use environment variables in AWS instead

# Activate the virtual environment path for subsequent commands
ENV PATH="/app/.venv/bin:$PATH"

# Ensure scripts are executable (if needed)
RUN chmod +x scripts/*.py

# Change ownership to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Command to run the application using uv run within the activated venv
# Using -m src.pipeline ensures Python runs it as a module
CMD ["uv", "run", "python", "-m", "src.pipeline"]