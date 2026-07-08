FROM python:3.12-slim

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

# Copy only deps first (for Docker layer caching)
COPY pyproject.toml requirements.txt .env.example ./
RUN pip install --no-cache-dir -e ".[all]" 2>/dev/null || \
    pip install --no-cache-dir pandas numpy scipy statsmodels scikit-learn matplotlib seaborn requests

COPY . .

ENV PYTHONPATH=/workspace
ENV PIPELINE_ENV=codespaces
