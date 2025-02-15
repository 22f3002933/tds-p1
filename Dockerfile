FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NODE_VERSION=22.x
ENV PIP_ROOT_USER_ACTION=ignore

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    python3.11-venv \
    python3.11-dev \
    git \
    nodejs \
    npm \
    curl \
    wget \
    imagemagick \
    build-essential \
    libpq-dev  \
    ffmpeg \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN apt-get remove -y libnode-dev nodejs && \
    curl -fsSL https://deb.nodesource.com/setup_${NODE_VERSION} | bash - && \
    apt-get update && apt-get install -y nodejs && \
    node -v && npm install -g prettier@3.4.2

# Create and set the working directory
WORKDIR /app

# Create data directory
RUN mkdir -p /data

# Copy requirements.txt first
COPY requirements.txt .

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Upgrade pip and install python packages
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Set environment variables (can be overridden at runtime)
ARG AIPROXY_TOKEN
ENV AIPROXY_TOKEN=${AIPROXY_TOKEN}

# Copy application code
COPY . .

# Expose the port your application will run on
EXPOSE 8000

# Command to run the application
ENTRYPOINT ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]