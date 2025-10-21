#!/bin/bash
set -e

# Homelab MCP Container Entrypoint
# Launches specified MCP servers based on ENABLED_SERVERS environment variable

echo "Starting Homelab MCP Servers..."
echo "Enabled servers: ${ENABLED_SERVERS}"

# Parse ENABLED_SERVERS (comma-separated list)
IFS=',' read -ra SERVERS <<< "$ENABLED_SERVERS"

# Validate at least one server is specified
if [ ${#SERVERS[@]} -eq 0 ]; then
    echo "ERROR: No servers enabled. Set ENABLED_SERVERS environment variable."
    echo "Example: ENABLED_SERVERS=docker,ping"
    exit 1
fi

# Check if Ansible inventory is being used
if [ -f "$ANSIBLE_INVENTORY_PATH" ]; then
    echo "Using Ansible inventory: $ANSIBLE_INVENTORY_PATH"
else
    echo "No Ansible inventory found at $ANSIBLE_INVENTORY_PATH, using environment variables"
fi

# Function to start MCP server
start_server() {
    local server=$1
    case $server in
        docker)
            if [ -f "docker_mcp_podman.py" ]; then
                echo "Starting Docker/Podman MCP server..."
                exec python docker_mcp_podman.py
            else
                echo "ERROR: docker_mcp_podman.py not found"
                exit 1
            fi
            ;;
        ping)
            if [ -f "ping_mcp_server.py" ]; then
                echo "Starting Ping MCP server..."
                exec python ping_mcp_server.py
            else
                echo "ERROR: ping_mcp_server.py not found"
                exit 1
            fi
            ;;
        *)
            echo "ERROR: Unknown server '$server'"
            echo "Valid servers: docker, ping"
            exit 1
            ;;
    esac
}

# For now, we only support running one server per container
# This is the MCP design pattern - one server per stdio connection
if [ ${#SERVERS[@]} -gt 1 ]; then
    echo "WARNING: Multiple servers specified. Only the first server will run."
    echo "MCP servers communicate over stdio and can only run one per container."
fi

# Start the first (and only) server
start_server "${SERVERS[0]}"
```
