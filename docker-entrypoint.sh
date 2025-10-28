#!/bin/bash
set -e

# Homelab MCP Container Entrypoint
# Supports two modes:
# 1. Unified mode (default): Runs homelab_unified_mcp.py with all servers
# 2. Legacy mode: Runs individual server specified in ENABLED_SERVERS
# NOTE: All diagnostic output goes to stderr to keep stdout clean for MCP protocol

echo "Starting Homelab MCP..." >&2

# Check if Ansible inventory is being used
if [ -f "$ANSIBLE_INVENTORY_PATH" ]; then
    echo "Using Ansible inventory: $ANSIBLE_INVENTORY_PATH" >&2
else
    echo "No Ansible inventory found at $ANSIBLE_INVENTORY_PATH, using environment variables" >&2
fi

# Determine mode: Unified (default) or Legacy
if [ -z "$ENABLED_SERVERS" ]; then
    # Unified mode - run all servers together
    echo "Mode: UNIFIED (all servers in one process)" >&2
    if [ -f "homelab_unified_mcp.py" ]; then
        echo "Starting Unified Homelab MCP Server..." >&2
        echo "Available tools: docker_*, ping_*, ollama_*, pihole_*, unifi_*" >&2
        exec python homelab_unified_mcp.py
    else
        echo "ERROR: homelab_unified_mcp.py not found" >&2
        exit 1
    fi
fi

# Legacy mode - run individual server
echo "Mode: LEGACY (individual server)" >&2
echo "Enabled servers: ${ENABLED_SERVERS}" >&2

# Parse ENABLED_SERVERS (comma-separated list)
IFS=',' read -ra SERVERS <<< "$ENABLED_SERVERS"

# Validate at least one server is specified
if [ ${#SERVERS[@]} -eq 0 ]; then
    echo "ERROR: No servers enabled. Set ENABLED_SERVERS environment variable." >&2
    echo "Example: ENABLED_SERVERS=docker,ping,ollama,pihole,unifi,ups,registry" >&2
    exit 1
fi

# Function to start MCP server
start_server() {
    local server=$1
    case $server in
        docker)
            if [ -f "docker_mcp_podman.py" ]; then
                echo "Starting Docker/Podman MCP server..." >&2
                exec python docker_mcp_podman.py
            else
                echo "ERROR: docker_mcp_podman.py not found" >&2
                exit 1
            fi
            ;;
        ping)
            if [ -f "ping_mcp_server.py" ]; then
                echo "Starting Ping MCP server..." >&2
                exec python ping_mcp_server.py
            else
                echo "ERROR: ping_mcp_server.py not found" >&2
                exit 1
            fi
            ;;
        ollama)
            if [ -f "ollama_mcp.py" ]; then
                echo "Starting Ollama MCP server..." >&2
                exec python ollama_mcp.py
            else
                echo "ERROR: ollama_mcp.py not found" >&2
                exit 1
            fi
            ;;
        pihole)
            if [ -f "pihole_mcp.py" ]; then
                echo "Starting Pi-hole MCP server..." >&2
                exec python pihole_mcp.py
            else
                echo "ERROR: pihole_mcp.py not found" >&2
                exit 1
            fi
            ;;
        unifi)
            if [ -f "unifi_mcp_optimized.py" ]; then
                echo "Starting Unifi MCP server..." >&2
                exec python unifi_mcp_optimized.py
            else
                echo "ERROR: unifi_mcp_optimized.py not found" >&2
                exit 1
            fi
            ;;
        registry)
            if [ -f "mcp_registry_inspector.py" ]; then
                echo "Starting MCP Registry Inspector server..." >&2
                exec python mcp_registry_inspector.py
            else
                echo "ERROR: mcp_registry_inspector.py not found" >&2
                exit 1
            fi
            ;;
        ups)
            if [ -f "ups_mcp_server.py" ]; then
                echo "Starting UPS Monitor MCP server..." >&2
                exec python ups_mcp_server.py
            else
                echo "ERROR: ups_mcp_server.py not found" >&2
                exit 1
            fi
            ;;
        *)
            echo "ERROR: Unknown server '$server'" >&2
            echo "Valid servers: docker, ping, ollama, pihole, unifi, ups, registry" >&2
            exit 1
            ;;
    esac
}

# For now, we only support running one server per container
# This is the MCP design pattern - one server per stdio connection
if [ ${#SERVERS[@]} -gt 1 ]; then
    echo "WARNING: Multiple servers specified. Only the first server will run." >&2
    echo "MCP servers communicate over stdio and can only run one per container." >&2
fi

# Start the first (and only) server
start_server "${SERVERS[0]}"
```
