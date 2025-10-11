#!/usr/bin/env python3
"""
Ollama MCP Server
Provides access to Ollama instances and models
Reads host configuration from Ansible inventory
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import aiohttp
import yaml

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

server = Server("ollama-info")

# Load .env if exists
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"

if ENV_FILE.exists():
    logger.info(f"Loading configuration from {ENV_FILE}")
    with open(ENV_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Configuration
ANSIBLE_INVENTORY_PATH = os.getenv("ANSIBLE_INVENTORY_PATH", "")
OLLAMA_PORT = int(os.getenv("OLLAMA_PORT", "11434"))

# LiteLLM configuration
LITELLM_HOST = os.getenv("LITELLM_HOST", "localhost")
LITELLM_PORT = os.getenv("LITELLM_PORT", "4000")

logger.info(f"Ansible inventory: {ANSIBLE_INVENTORY_PATH}")
logger.info(f"LiteLLM endpoint: {LITELLM_HOST}:{LITELLM_PORT}")


def load_ollama_endpoints_from_ansible():
    """
    Load Ollama endpoints from Ansible inventory
    Returns dict of {display_name: ip_address}
    """
    if not ANSIBLE_INVENTORY_PATH or not Path(ANSIBLE_INVENTORY_PATH).exists():
        logger.warning(f"Ansible inventory not found at: {ANSIBLE_INVENTORY_PATH}")
        logger.warning("Falling back to .env configuration")
        return load_ollama_endpoints_from_env()
    
    try:
        with open(ANSIBLE_INVENTORY_PATH, 'r') as f:
            inventory = yaml.safe_load(f)
        
        endpoints = {}
        
        # Navigate through the inventory structure to find ollama_servers group
        all_group = inventory.get('all', {})
        children = all_group.get('children', {})
        
        # Find ollama_servers group
        ollama_group = children.get('ollama_servers', {})
        ollama_children = ollama_group.get('children', {})
        
        # Process each OS-specific group
        for os_group_name, os_group_data in ollama_children.items():
            # Get hosts directly or from children
            hosts = os_group_data.get('hosts', {})
            
            # Also check for nested children (like ollama_ubuntu_servers)
            for child_name, child_data in os_group_data.get('children', {}).items():
                hosts.update(child_data.get('hosts', {}))
            
            # Extract hostname and IP
            for hostname, host_vars in hosts.items():
                # Clean up hostname for display (remove domain suffix)
                display_name = hostname.split('.')[0]
                # Capitalize and clean up for display
                display_name = display_name.replace('-', ' ').title().replace(' ', '-')
                
                # Try to get IP from ansible_host var, or resolve hostname
                ip = host_vars.get('ansible_host', hostname.split('.')[0])
                
                endpoints[display_name] = ip
                logger.info(f"Found Ollama host: {display_name} -> {ip}")
        
        if not endpoints:
            logger.warning("No Ollama hosts found in Ansible inventory")
            return load_ollama_endpoints_from_env()
        
        return endpoints
        
    except Exception as e:
        logger.error(f"Error loading Ansible inventory: {e}")
        logger.warning("Falling back to .env configuration")
        return load_ollama_endpoints_from_env()


def load_ollama_endpoints_from_env():
    """
    Fallback: Load Ollama endpoints from environment variables
    Returns dict of {display_name: ip_address}
    """
    endpoints = {}
    
    # Look for OLLAMA_* environment variables
    for key, value in os.environ.items():
        if key.startswith('OLLAMA_') and key not in ['OLLAMA_PORT']:
            # Convert OLLAMA_SERVER1 to Server1
            display_name = key.replace('OLLAMA_', '').replace('_', '-').title()
            endpoints[display_name] = value
            logger.info(f"Loaded from env: {display_name} -> {value}")
    
    return endpoints


# Load Ollama endpoints on startup
OLLAMA_ENDPOINTS = load_ollama_endpoints_from_ansible()

if not OLLAMA_ENDPOINTS:
    logger.error("No Ollama endpoints configured!")
    logger.error("Please set ANSIBLE_INVENTORY_PATH or OLLAMA_* environment variables")


async def ollama_request(host_ip: str, endpoint: str, timeout: int = 5):
    """Make request to Ollama API"""
    url = f"http://{host_ip}:{OLLAMA_PORT}{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    return await response.json()
                return None
    except Exception as e:
        logger.debug(f"Ollama request failed for {host_ip}: {e}")
        return None


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Ollama tools"""
    return [
        types.Tool(
            name="get_ollama_status",
            description="Check status of all Ollama instances",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_ollama_models",
            description="Get models on a specific Ollama host",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": f"Host: {', '.join(OLLAMA_ENDPOINTS.keys())}"
                    }
                },
                "required": ["host"]
            }
        ),
        types.Tool(
            name="get_litellm_status",
            description="Check LiteLLM proxy status",
            inputSchema={"type": "object", "properties": {}}
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls"""
    try:
        if name == "get_ollama_status":
            output = "=== OLLAMA STATUS ===\n\n"
            total_models = 0
            online = 0
            
            for host_name, ip in OLLAMA_ENDPOINTS.items():
                data = await ollama_request(ip, "/api/tags", timeout=3)
                
                if data:
                    models = data.get('models', [])
                    count = len(models)
                    total_models += count
                    online += 1
                    
                    output += f"✓ {host_name} ({ip}): {count} models\n"
                    for model in models[:3]:
                        name = model.get('name', 'Unknown')
                        size = model.get('size', 0) / (1024**3)
                        output += f"    - {name} ({size:.1f}GB)\n"
                    if count > 3:
                        output += f"    ... and {count-3} more\n"
                    output += "\n"
                else:
                    output += f"✗ {host_name} ({ip}): OFFLINE\n\n"
            
            output = f"Summary: {online}/{len(OLLAMA_ENDPOINTS)} online, {total_models} models\n\n" + output
            return [types.TextContent(type="text", text=output)]
        
        elif name == "get_ollama_models":
            host = arguments.get("host")
            if host not in OLLAMA_ENDPOINTS:
                return [types.TextContent(type="text", text=f"Invalid host: {host}")]
            
            ip = OLLAMA_ENDPOINTS[host]
            data = await ollama_request(ip, "/api/tags", timeout=5)
            
            if not data:
                return [types.TextContent(type="text", text=f"{host} is offline")]
            
            models = data.get('models', [])
            output = f"=== {host} ({ip}) ===\n\n"
            output += f"Models: {len(models)}\n\n"
            
            for model in models:
                name = model.get('name', 'Unknown')
                size = model.get('size', 0) / (1024**3)
                modified = model.get('modified_at', 'Unknown')
                output += f"• {name}\n"
                output += f"  Size: {size:.2f}GB\n"
                output += f"  Modified: {modified}\n\n"
            
            return [types.TextContent(type="text", text=output)]
        
        elif name == "get_litellm_status":
            url = f'http://{LITELLM_HOST}:{LITELLM_PORT}/health/liveliness'
            logger.info(f"Checking LiteLLM at {url}")
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        logger.info(f"LiteLLM response status: {response.status}")
                        if response.status == 200:
                            data = await response.text()  # Liveliness returns text, not JSON
                            output = f"✓ LiteLLM Proxy: ONLINE\n"
                            output += f"Endpoint: {LITELLM_HOST}:{LITELLM_PORT}\n\n"
                            output += f"Liveliness Check: {data}"
                            return [types.TextContent(type="text", text=output)]
                        else:
                            return [types.TextContent(
                                type="text",
                                text=f"✗ LiteLLM Proxy: HTTP {response.status}\nEndpoint: {url}"
                            )]
            except asyncio.TimeoutError:
                return [types.TextContent(
                    type="text",
                    text=f"✗ LiteLLM Proxy: TIMEOUT\nEndpoint: {url}\nConnection timed out after 5 seconds"
                )]
            except aiohttp.ClientConnectorError as e:
                return [types.TextContent(
                    type="text",
                    text=f"✗ LiteLLM Proxy: CONNECTION REFUSED\nEndpoint: {url}\nError: {str(e)}"
                )]
            except Exception as e:
                logger.error(f"LiteLLM check error: {e}", exc_info=True)
                return [types.TextContent(
                    type="text",
                    text=f"✗ LiteLLM Proxy: ERROR\nEndpoint: {url}\nError: {str(e)}"
                )]
        
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ollama-info",
                server_version="2.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
