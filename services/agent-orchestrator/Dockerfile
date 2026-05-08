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

# Python deps
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Install Playwright browsers to the shared path
RUN playwright install chromium

# App code
COPY . .

# Create non-root user and set permissions
RUN useradd -m aegis && chown -R aegis /app && mkdir -p /ms-playwright && chown -R aegis /ms-playwright
USER aegis

EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
