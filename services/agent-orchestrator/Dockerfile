FROM python:3.11-slim

WORKDIR /app

# System deps for Playwright + build tools
RUN apt-get update && apt-get install -y \
    wget curl gnupg ca-certificates \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 \
    libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set Playwright browser path
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Python deps using uv for faster & more reliable resolution
COPY requirements.txt .
RUN pip install uv && uv pip install --system --no-cache -r requirements.txt

# Install Playwright browsers to the shared path
RUN playwright install chromium

# App code
COPY . .

# Create non-root user and set permissions
RUN useradd -m aegis && chown -R aegis /app && mkdir -p /ms-playwright && chown -R aegis /ms-playwright
USER aegis

ENV PORT=8001
EXPOSE ${PORT}

# Default: Run the API server
# For ARQ worker (paid Background Worker), override CMD with:
#   arq worker.WorkerSettings
# For ARQ worker (FREE Web Service tier), override CMD with:
#   uvicorn worker_web:app --host 0.0.0.0 --port ${PORT}
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 2"]
