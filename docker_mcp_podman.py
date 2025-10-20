#!/usr/bin/env python3
"""
Docker/Podman MCP Server
Provides access to Docker and Podman containers via HTTP API
Reads host configuration from Ansible inventory
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

import aiohttp
import yaml

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from mcp_config_loader import load_env_file, COMMON_ALLOWED_ENV_VARS

server = Server("docker-info")

# Load .env with security hardening
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"

DOCKER_ALLOWED_VARS = COMMON_ALLOWED_ENV_VARS | {
    "DOCKER_*",  # Matches DOCKER_HOST, DOCKER_PORT, etc.
    "PODMAN_*",  # Matches PODMAN_HOST, PODMAN_PORT, etc.
}

load_env_file(ENV_FILE, allowed_vars=DOCKER_ALLOWED_VARS, strict=True)

# Configuration
ANSIBLE_INVENTORY_PATH = os.getenv("ANSIBLE_INVENTORY_PATH", "")

logger.info(f"Ansible inventory: {ANSIBLE_INVENTORY_PATH}")


def load_container_hosts_from_ansible():
    """
    Load container hosts from Ansible inventory
    Returns dict of {hostname: {'endpoint': 'ip:port', 'runtime': 'docker|podman'}}
    """
    if not ANSIBLE_INVENTORY_PATH or not Path(ANSIBLE_INVENTORY_PATH).exists():
        logger.warning(f"Ansible inventory not found at: {ANSIBLE_INVENTORY_PATH}")
        logger.warning("Falling back to .env configuration")
        return load_container_hosts_from_env()

    try:
        with open(ANSIBLE_INVENTORY_PATH, "r") as f:
            inventory = yaml.safe_load(f)

        container_hosts = {}

        all_group = inventory.get("all", {})
        children = all_group.get("children", {})

        # Process Docker hosts
        docker_group = children.get("docker_hosts", {})
        for hostname, host_vars in docker_group.get("hosts", {}).items():
            display_name = hostname.split(".")[0]
            ip = host_vars.get("ansible_host", hostname.split(".")[0])
            port = host_vars.get("docker_api_port", 2375)

            container_hosts[display_name] = {
                "endpoint": f"{ip}:{port}",
                "runtime": "docker",
            }
            logger.info(f"Found Docker host: {display_name} -> {ip}:{port}")

        # Process Podman hosts
        podman_group = children.get("podman_hosts", {})
        for hostname, host_vars in podman_group.get("hosts", {}).items():
            display_name = hostname.split(".")[0]
            ip = host_vars.get("ansible_host", hostname.split(".")[0])
            port = host_vars.get("podman_api_port", 8080)

            container_hosts[display_name] = {
                "endpoint": f"{ip}:{port}",
                "runtime": "podman",
            }
            logger.info(f"Found Podman host: {display_name} -> {ip}:{port}")

        if not container_hosts:
            logger.warning("No container hosts found in Ansible inventory")
            return load_container_hosts_from_env()

        return container_hosts

    except Exception as e:
        logger.error(f"Error loading Ansible inventory: {e}")
        logger.warning("Falling back to .env configuration")
        return load_container_hosts_from_env()


def load_container_hosts_from_env():
    """
    Fallback: Load container hosts from environment variables
    Returns dict of {hostname: {'endpoint': 'ip:port', 'runtime': 'docker|podman'}}
    """
    container_hosts = {}

    # Look for DOCKER_* environment variables
    for key, value in os.environ.items():
        if key.startswith("DOCKER_") and key.endswith("_ENDPOINT"):
            # Convert DOCKER_SERVER1_ENDPOINT to server1
            display_name = key.replace("DOCKER_", "").replace("_ENDPOINT", "").lower()
            container_hosts[display_name] = {"endpoint": value, "runtime": "docker"}
            logger.info(f"Loaded Docker from env: {display_name} -> {value}")

        elif key.startswith("PODMAN_") and key.endswith("_ENDPOINT"):
            # Convert PODMAN_SERVER1_ENDPOINT to server1
            display_name = key.replace("PODMAN_", "").replace("_ENDPOINT", "").lower()
            container_hosts[display_name] = {"endpoint": value, "runtime": "podman"}
            logger.info(f"Loaded Podman from env: {display_name} -> {value}")

    return container_hosts


# Load container hosts on startup
CONTAINER_HOSTS = load_container_hosts_from_ansible()

if not CONTAINER_HOSTS:
    logger.error("No container hosts configured!")
    logger.error(
        "Please set ANSIBLE_INVENTORY_PATH or DOCKER_/PODMAN_*_ENDPOINT environment variables"
    )


async def container_api_request(
    host: str, endpoint: str, timeout: int = 5
) -> Optional[Dict]:
    """
    Make a request to Docker or Podman API

    Args:
        host: Hostname from CONTAINER_HOSTS
        endpoint: API endpoint (e.g., '/containers/json')
        timeout: Request timeout in seconds

    Returns:
        JSON response dict or None on error
    """
    if host not in CONTAINER_HOSTS:
        logger.error(f"Unknown host: {host}")
        return None

    config = CONTAINER_HOSTS[host]
    runtime = config["runtime"]

    # Podman API uses /v4.0.0/libpod prefix for some endpoints
    # Docker uses standard Docker API
    if runtime == "podman":
        # Convert Docker-style endpoints to Podman libpod endpoints
        if endpoint.startswith("/containers"):
            endpoint = f"/v4.0.0/libpod{endpoint}"

    url = f"http://{config['endpoint']}{endpoint}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(
                        f"{runtime.capitalize()} API returned HTTP {response.status} for {host} ({url})"
                    )
                    return None
    except asyncio.TimeoutError:
        logger.error(
            f"Timeout connecting to {runtime} API on {host} (timeout={timeout}s)"
        )
        return None
    except aiohttp.ClientError as e:
        logger.error(f"Connection error to {runtime} API on {host}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to {runtime} API on {host}: {e}")
        return None


def normalize_container_info(container: Dict, runtime: str) -> Dict:
    """
    Normalize container information between Docker and Podman formats

    Args:
        container: Raw container dict from API
        runtime: 'docker' or 'podman'

    Returns:
        Normalized container dict with common fields
    """
    if runtime == "podman":
        # Podman uses different field names
        return {
            "Id": container.get("Id", ""),
            "Names": [
                (
                    container.get("Names", ["Unknown"])[0]
                    if isinstance(container.get("Names"), list)
                    else container.get("Name", "Unknown")
                )
            ],
            "Image": container.get("Image", "Unknown"),
            "ImageID": container.get("ImageID", ""),
            "Command": container.get("Command", []),
            "Created": container.get("Created", 0),
            "State": container.get("State", "unknown"),
            "Status": container.get("Status", "Unknown"),
            "Ports": container.get("Ports", []),
            "Labels": container.get("Labels", {}),
            "runtime": "podman",
        }
    else:
        # Docker format (already normalized)
        container["runtime"] = "docker"
        return container


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available container management tools"""
    return [
        types.Tool(
            name="get_docker_containers",
            description="Get containers on a specific host (works with both Docker and Podman)",
            inputSchema={
                "type": "object",
                "properties": {
                    "hostname": {
                        "type": "string",
                        "description": f"Host: {', '.join(CONTAINER_HOSTS.keys())}",
                        "enum": list(CONTAINER_HOSTS.keys()),
                    }
                },
                "required": ["hostname"],
            },
        ),
        types.Tool(
            name="get_all_containers",
            description="Get all containers across all hosts",
            inputSchema={"type": "object", "properties": {}},
        ),
        types.Tool(
            name="get_container_stats",
            description="Get CPU and memory stats for containers on a host",
            inputSchema={
                "type": "object",
                "properties": {
                    "hostname": {
                        "type": "string",
                        "description": f"Host: {', '.join(CONTAINER_HOSTS.keys())}",
                        "enum": list(CONTAINER_HOSTS.keys()),
                    }
                },
                "required": ["hostname"],
            },
        ),
        types.Tool(
            name="check_container",
            description="Check if a specific container is running on a host",
            inputSchema={
                "type": "object",
                "properties": {
                    "hostname": {
                        "type": "string",
                        "description": f"Host: {', '.join(CONTAINER_HOSTS.keys())}",
                        "enum": list(CONTAINER_HOSTS.keys()),
                    },
                    "container": {
                        "type": "string",
                        "description": "Container name to check",
                    },
                },
                "required": ["hostname", "container"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    """Handle tool execution requests"""

    logger.info(f"Tool called: {name} with args: {arguments}")

    try:
        if name == "get_docker_containers":
            default_hostname = (
                list(CONTAINER_HOSTS.keys())[0]
                if CONTAINER_HOSTS
                else "no-hosts-configured"
            )
            hostname = (
                arguments.get("hostname", default_hostname)
                if arguments
                else default_hostname
            )

            if hostname not in CONTAINER_HOSTS:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error: Unknown host '{hostname}'. Valid hosts: {', '.join(CONTAINER_HOSTS.keys())}",
                    )
                ]

            runtime = CONTAINER_HOSTS[hostname]["runtime"]
            containers = await container_api_request(hostname, "/containers/json")

            if containers is None:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error: Could not connect to {runtime.capitalize()} API on {hostname}",
                    )
                ]

            output = f"=== {hostname.upper()} ({runtime.upper()}) ===\n\n"

            if not containers:
                output += "No containers running\n"
            else:
                for container in containers:
                    norm = normalize_container_info(container, runtime)

                    name_str = (
                        norm["Names"][0].lstrip("/") if norm["Names"] else "Unknown"
                    )
                    image = norm["Image"]
                    state = norm["State"]
                    status = norm["Status"]

                    # Format ports
                    port_str = ""
                    ports = norm.get("Ports", [])
                    if ports:
                        port_mappings = []
                        for port in ports:
                            if "PublicPort" in port:
                                port_mappings.append(
                                    f"{port.get('PublicPort', '?')}->{port.get('PrivatePort', '?')}"
                                )
                        if port_mappings:
                            port_str = f" | Ports: {', '.join(port_mappings)}"

                    output += f"• {name_str} ({image})\n"
                    output += f"  Status: {status}{port_str}\n\n"

            return [types.TextContent(type="text", text=output)]

        elif name == "get_all_containers":
            output = f"Total: ? containers\n\n=== ALL CONTAINER HOSTS ===\n\n"
            total_containers = 0
            results = []

            for hostname, config in CONTAINER_HOSTS.items():
                runtime = config["runtime"]
                containers = await container_api_request(hostname, "/containers/json")

                host_output = f"--- {hostname.upper()} ---\n"

                if containers is not None:
                    total_containers += len(containers)
                    if containers:
                        for container in containers:
                            norm = normalize_container_info(container, runtime)
                            name_str = (
                                norm["Names"][0].lstrip("/")
                                if norm["Names"]
                                else "Unknown"
                            )
                            image = norm["Image"]
                            host_output += f"  • {name_str} ({image})\n"
                    else:
                        host_output += "  No containers\n"
                else:
                    host_output += f"  Error\n"

                results.append(host_output)

            # Update total count
            output = (
                f"Total: {total_containers} containers\n\n=== ALL CONTAINER HOSTS ===\n\n"
                + "\n".join(results)
            )
            return [types.TextContent(type="text", text=output)]

        elif name == "get_container_stats":
            default_hostname = (
                list(CONTAINER_HOSTS.keys())[0]
                if CONTAINER_HOSTS
                else "no-hosts-configured"
            )
            hostname = (
                arguments.get("hostname", default_hostname)
                if arguments
                else default_hostname
            )

            if hostname not in CONTAINER_HOSTS:
                return [
                    types.TextContent(
                        type="text", text=f"Error: Unknown host '{hostname}'"
                    )
                ]

            runtime = CONTAINER_HOSTS[hostname]["runtime"]
            containers = await container_api_request(hostname, "/containers/json")

            if containers is None:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error: Could not connect to {runtime.capitalize()} API on {hostname}",
                    )
                ]

            output = f"=== STATS: {hostname.upper()} ===\n\n"

            # Stats endpoint differs between Docker and Podman
            stats_endpoint_template = "/containers/{}/stats?stream=false"

            for container in containers[:10]:  # Limit to 10 for performance
                norm = normalize_container_info(container, runtime)
                container_id = norm["Id"]
                name = norm["Names"][0].lstrip("/") if norm["Names"] else "Unknown"

                stats = await container_api_request(
                    hostname, stats_endpoint_template.format(container_id), timeout=10
                )

                if stats:
                    # Calculate CPU percentage
                    cpu_percent = 0.0
                    try:
                        cpu_stats = stats.get("cpu_stats", {})
                        precpu_stats = stats.get("precpu_stats", {})

                        cpu_delta = cpu_stats.get("cpu_usage", {}).get(
                            "total_usage", 0
                        ) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                        system_delta = cpu_stats.get(
                            "system_cpu_usage", 0
                        ) - precpu_stats.get("system_cpu_usage", 0)

                        num_cpus = len(
                            cpu_stats.get("cpu_usage", {}).get("percpu_usage", [])
                        )
                        if num_cpus == 0:
                            num_cpus = 1

                        if system_delta > 0 and cpu_delta > 0:
                            cpu_percent = (cpu_delta / system_delta) * num_cpus * 100.0
                    except Exception as e:
                        logger.debug(f"Error calculating CPU for {name}: {e}")

                    # Calculate memory usage
                    mem_usage = 0.0
                    mem_limit = 0.0
                    mem_percent = 0.0
                    try:
                        mem_stats = stats.get("memory_stats", {})
                        mem_usage = mem_stats.get("usage", 0) / (
                            1024**3
                        )  # Convert to GB
                        mem_limit = mem_stats.get("limit", 0) / (1024**3)

                        if mem_limit > 0:
                            mem_percent = (
                                mem_stats.get("usage", 0) / mem_stats.get("limit", 1)
                            ) * 100.0
                    except Exception as e:
                        logger.debug(f"Error calculating memory for {name}: {e}")

                    output += f"• {name}\n"
                    output += f"  CPU: {cpu_percent:.1f}%\n"
                    output += f"  Memory: {mem_usage:.2f}GB / {mem_limit:.2f}GB ({mem_percent:.1f}%)\n\n"
                else:
                    output += f"• {name}\n  Stats unavailable\n\n"

            return [types.TextContent(type="text", text=output)]

        elif name == "check_container":
            hostname = arguments.get("hostname", "") if arguments else ""
            container_name = arguments.get("container", "") if arguments else ""

            if not hostname or not container_name:
                return [
                    types.TextContent(
                        type="text",
                        text="Error: Both hostname and container name are required",
                    )
                ]

            runtime = CONTAINER_HOSTS.get(hostname, {}).get("runtime", "docker")
            containers = await container_api_request(hostname, "/containers/json")

            if containers is None:
                return [
                    types.TextContent(
                        type="text",
                        text=f"Error: Could not connect to {runtime.capitalize()} API on {hostname}",
                    )
                ]

            for container in containers:
                norm = normalize_container_info(container, runtime)
                names = norm["Names"]

                # Check if container name matches (with or without leading /)
                for name in names:
                    clean_name = name.lstrip("/")
                    if clean_name == container_name or name == container_name:
                        return [
                            types.TextContent(
                                type="text",
                                text=f"✓ Container '{container_name}' is RUNNING on {hostname}\n"
                                f"  Image: {norm['Image']}\n"
                                f"  Status: {norm['Status']}\n"
                                f"  Runtime: {runtime}",
                            )
                        ]

            return [
                types.TextContent(
                    type="text",
                    text=f"✗ Container '{container_name}' is NOT running on {hostname}",
                )
            ]

        else:
            return [
                types.TextContent(type="text", text=f"Error: Unknown tool '{name}'")
            ]

    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}", exc_info=True)
        return [
            types.TextContent(type="text", text=f"Error executing {name}: {str(e)}")
        ]


async def main():
    """Run the MCP server"""
    logger.info("Starting Docker/Podman MCP Server...")
    logger.info(f"Configured hosts: {', '.join(CONTAINER_HOSTS.keys())}")

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="docker-info",
                server_version="2.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
