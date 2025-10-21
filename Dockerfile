# Homelab MCP Servers - Docker Container
# Packages Docker and Ping MCP servers for easy distribution
# https://github.com/bjeans/homelab-mcp

FROM python:3.11-slim

# Metadata
LABEL maintainer="Barnaby Jeans <barnaby@bjeans.dev>"
LABEL description="MCP servers for homelab infrastructure management"
LABEL org.opencontainers.image.source="https://github.com/bjeans/homelab-mcp"
LABEL org.opencontainers.image.licenses="MIT"

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash mcpuser && \
    mkdir -p /config /app && \
    chown -R mcpuser:mcpuser /app /config

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY --chown=mcpuser:mcpuser requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server files
COPY --chown=mcpuser:mcpuser docker_mcp_podman.py .
COPY --chown=mcpuser:mcpuser ping_mcp_server.py .
COPY --chown=mcpuser:mcpuser mcp_config_loader.py .

# Copy entrypoint script
COPY --chown=mcpuser:mcpuser docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Switch to non-root user
USER mcpuser

# Environment variables with defaults
ENV PYTHONUNBUFFERED=1 \
    ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml \
    ENABLED_SERVERS=docker,ping

# Expose stdio for MCP communication
# MCP servers communicate over stdin/stdout, no ports needed

# Health check (checks if Python process is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "python.*mcp" || exit 1

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
