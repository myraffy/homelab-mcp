# Docker Deployment Guide

This guide covers deploying the Homelab MCP servers using Docker containers.

> **For Docker MCP Marketplace:** This image is marketplace-ready! Configure it entirely via environment variables with no external dependencies. See [Configuration Methods](#configuration-methods) below.

## Quick Start

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+ (optional but recommended)
- Network access to your homelab services
- Ansible inventory file OR environment variables configured

### Build the Container
```bash
# Clone the repository
git clone https://github.com/bjeans/homelab-mcp.git
cd homelab-mcp

# Build the Docker image
docker build -t homelab-mcp:latest .
```

### Run with Docker Compose (Recommended)
```bash
# Copy the example environment file
cp .env.docker.example .env

# Edit .env with your configuration
nano .env

# Start the services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the services
docker-compose down
```

### Run with Docker CLI

#### Using Ansible Inventory
```bash
docker run -d \
  --name homelab-mcp-docker \
  --network host \
  -e ENABLED_SERVERS=docker \
  -e ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml \
  -v $(pwd)/ansible_hosts.yml:/config/ansible_hosts.yml:ro \
  --stdin \
  --tty \
  homelab-mcp:latest
```

#### Using Environment Variables
```bash
docker run -d \
  --name homelab-mcp-docker \
  --network host \
  -e ENABLED_SERVERS=docker \
  -e DOCKER_SERVER1_ENDPOINT=192.168.1.100:2375 \
  -e DOCKER_SERVER2_ENDPOINT=192.168.1.101:2375 \
  --stdin \
  --tty \
  homelab-mcp:latest
```

## Configuration

### Configuration Methods

The container supports two configuration methods:

#### Method 1: Ansible Inventory (Recommended)

Mount your Ansible inventory file as a volume:
```yaml
volumes:
  - ./ansible_hosts.yml:/config/ansible_hosts.yml:ro
environment:
  - ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml
```

**Advantages:**
- Centralized configuration
- Supports complex host groupings
- Better for multi-host environments
- Single source of truth

#### Method 2: Environment Variables

Pass configuration via environment variables:
```yaml
environment:
  - DOCKER_SERVER1_ENDPOINT=192.168.1.100:2375
  - DOCKER_SERVER2_ENDPOINT=192.168.1.101:2375
```

**Advantages:**
- Simple for basic setups
- No additional files needed
- Easy to test

### Available Servers

The `ENABLED_SERVERS` environment variable controls which MCP server runs:

- `docker` - Docker/Podman container management
- `ping` - Network ping utilities

**Important:** Only ONE server runs per container (MCP design pattern).
```bash
# Run Docker MCP server
-e ENABLED_SERVERS=docker

# Run Ping MCP server
-e ENABLED_SERVERS=ping
```

## Network Configuration

### Host Network Mode

The container uses `network_mode: host` to access homelab services:
```yaml
network_mode: host
```

**Why?** Your Docker/Podman APIs and ping targets are on your local network. Host mode provides direct access without port mapping complexity.

**Security Note:** Review firewall rules. See [SECURITY.md](SECURITY.md) for details.

### Alternative: Bridge Mode

For isolated networking:
```yaml
networks:
  - homelab
```

Requires additional configuration for service discovery.

## Security

### Running as Non-Root

The container runs as user `mcpuser` (UID 1000) for security:
```dockerfile
USER mcpuser
```

### Sensitive Data

**Never include sensitive data in the image:**
- ✅ Mount Ansible inventory as read-only volume
- ✅ Use environment variables for API keys
- ✅ Use Docker secrets in production
- ❌ Don't hardcode credentials in Dockerfile

### File Permissions

If using Ansible inventory:
```bash
# Restrict permissions (Linux/Mac)
chmod 600 ansible_hosts.yml
```

### Firewall Rules

Ensure Docker/Podman APIs are not exposed to internet:
```bash
# Example iptables rule (adjust for your setup)
iptables -A INPUT -p tcp --dport 2375 -s 192.168.1.0/24 -j ACCEPT
iptables -A INPUT -p tcp --dport 2375 -j DROP
```

## Integration with Claude Desktop

### Configuration Overview

The Docker containers can be configured two ways:

1. **Environment Variables (Recommended for Marketplace)** - No external files needed
2. **Ansible Inventory Volume Mount** - For advanced setups with many hosts

### Option 1: Environment Variables (Minimal Dependencies)

This approach requires no external files - everything is passed as environment variables. **Best for Docker MCP marketplace distribution.**

**Step 1: Start the container**

```bash
# Docker Compose approach
docker-compose up -d

# Or manually:
docker run -d --name homelab-mcp-docker --network host \
  -e ENABLED_SERVERS=docker \
  -e DOCKER_SERVER1_ENDPOINT=192.168.1.100:2375 \
  -e DOCKER_SERVER2_ENDPOINT=192.168.1.101:2375 \
  homelab-mcp:latest
```

**Step 2: Configure Claude Desktop**

Edit Claude Desktop config file:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "homelab-docker": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "homelab-mcp-docker",
        "python",
        "docker_mcp_podman.py"
      ]
    },
    "homelab-ping": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "homelab-mcp-ping",
        "python",
        "ping_mcp_server.py"
      ]
    }
  }
}
```

### Option 2: Ansible Inventory Volume Mount (Advanced)

For complex setups with many hosts, mount an Ansible inventory file:

```bash
docker run -d --name homelab-mcp-docker --network host \
  -e ENABLED_SERVERS=docker \
  -e ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml \
  -v $(pwd)/ansible_hosts.yml:/config/ansible_hosts.yml:ro \
  homelab-mcp:latest
```

See [Configuration section](#configuration) above for details.

### Important Notes

- **Use `docker exec -i`** (not `-it`) for proper MCP stdio communication
- Do NOT use `-t` (tty) as it interferes with MCP protocol
- Container must be running before Claude tries to connect
- Restart Claude Desktop completely after configuration changes

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs homelab-mcp-docker

# Common issues:
# 1. ENABLED_SERVERS not set
# 2. Invalid server name
# 3. Missing configuration
```

### Can't Connect to Docker API
```bash
# Test connectivity from container
docker exec homelab-mcp-docker curl http://192.168.1.100:2375/containers/json

# Check firewall rules
# Verify API is enabled on target hosts
```

### Ping Not Working
```bash
# Ensure NET_RAW capability is granted
docker run --cap-add=NET_RAW ...

# Or in docker-compose.yml:
cap_add:
  - NET_RAW
```

### MCP Communication Issues

**Symptoms:** Claude Desktop can't connect to server

**Solutions:**
1. Ensure container is running: `docker ps`
2. Check stdin/tty are enabled: `--stdin --tty`
3. Verify container logs: `docker logs <container>`
4. Test with `docker exec -i`: `docker exec -i <container> python <server>.py`

### Permission Denied
```bash
# If you see permission errors:
# 1. Check volume mount permissions
ls -la ansible_hosts.yml

# 2. Ensure file is readable
chmod 644 ansible_hosts.yml

# 3. Check container user
docker exec homelab-mcp-docker whoami
```

## Building Multi-Architecture Images

For ARM devices (Raspberry Pi, etc.):
```bash
# Setup buildx
docker buildx create --use

# Build for multiple architectures
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t bjeans/homelab-mcp:latest \
  --push \
  .
```

## Testing

### Quick Verification Test

Test the Docker image quickly with these commands:

**Test Ping Server:**

```bash
# PowerShell
docker run --rm --network host `
    -e ENABLED_SERVERS=ping `
    -e ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml `
    -v "$PWD/ansible_hosts.yml:/config/ansible_hosts.yml:ro" `
    homelab-mcp:latest

# Bash
docker run --rm --network host \
    -e ENABLED_SERVERS=ping \
    -e ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml \
    -v $(pwd)/ansible_hosts.yml:/config/ansible_hosts.yml:ro \
    homelab-mcp:latest
```

**Test Docker Server:**

```bash
# PowerShell
docker run --rm --network host `
    -e ENABLED_SERVERS=docker `
    -e ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml `
    -v "$PWD/ansible_hosts.yml:/config/ansible_hosts.yml:ro" `
    homelab-mcp:latest

# Bash
docker run --rm --network host \
    -e ENABLED_SERVERS=docker \
    -e ANSIBLE_INVENTORY_PATH=/config/ansible_hosts.yml \
    -v $(pwd)/ansible_hosts.yml:/config/ansible_hosts.yml:ro \
    homelab-mcp:latest
```

**Expected Output:**

- Server starts with "Starting Homelab MCP Servers..."
- Ansible inventory is loaded from `/config/ansible_hosts.yml`
- Hosts/endpoints are discovered (e.g., "Found Docker host:", "Loaded X hosts")
- No error messages

### Docker Compose Testing

Start all services and view logs:

```bash
docker-compose up -d
docker-compose logs -f homelab-mcp-docker
docker-compose logs -f homelab-mcp-ping
```

### Claude Desktop Integration Testing

1. Start containers with Docker Compose:

```bash
docker-compose up -d
```

1. Update Claude Desktop config (`%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "homelab-mcp-docker": {
      "command": "docker",
      "args": ["exec", "-i", "homelab-mcp-docker", "python", "docker_mcp_podman.py"]
    },
    "homelab-mcp-ping": {
      "command": "docker",
      "args": ["exec", "-i", "homelab-mcp-ping", "python", "ping_mcp_server.py"]
    }
  }
}
```

1. Restart Claude Desktop completely

1. Test in Claude:
   - Ask: "What tools are available from homelab-mcp-docker?"
   - Ask: "Can you list the Docker containers on my servers?"
   - Ask: "Ping 192.168.1.1 for me"

## Health Checks

The container includes health checks:

```bash
# Check container health
docker inspect homelab-mcp-docker | grep -A 10 Health

# Health check looks for Python MCP process
HEALTHCHECK CMD pgrep -f "python.*mcp" || exit 1
```

## Updating
```bash
# Pull latest changes
git pull

# Rebuild image
docker-compose build

# Restart services
docker-compose up -d
```

## Development

### Local Testing
```bash
# Build with different tag
docker build -t homelab-mcp:dev .

# Run with volume mounts for live code changes
docker run -it --rm \
  -v $(pwd):/app \
  homelab-mcp:dev \
  python docker_mcp_podman.py
```

### Debugging
```bash
# Run interactively with shell
docker run -it --rm \
  --entrypoint /bin/bash \
  homelab-mcp:latest

# Inside container, test servers manually:
python docker_mcp_podman.py
```

## Performance

### Resource Limits

Add resource constraints if needed:
```yaml
deploy:
  resources:
    limits:
      cpus: '0.5'
      memory: 256M
    reservations:
      cpus: '0.25'
      memory: 128M
```

### Caching

Docker build uses layer caching. Requirements install is cached separately:
```dockerfile
# Copy requirements first (cached unless changed)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code (changes more frequently)
COPY *.py .
```

## Next Steps

- Add more MCP servers (Ollama, Pi-hole, Unifi)
- Publish to Docker Hub
- Submit to MCP Registry
- Add automated testing

## Support

- Issues: https://github.com/bjeans/homelab-mcp/issues
- Discussions: https://github.com/bjeans/homelab-mcp/discussions
- Security: See [SECURITY.md](SECURITY.md)
