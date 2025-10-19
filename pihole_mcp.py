#!/usr/bin/env python3
"""
Pi-hole MCP Server v3
Provides DNS statistics from Pi-hole instances using session-based authentication
Supports Pi-hole v6 API with automatic session management and refresh
Reads host configuration from Ansible inventory
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import aiohttp
import yaml

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from mcp_config_loader import load_env_file, COMMON_ALLOWED_ENV_VARS

server = Server("pihole-info")

# Load .env with security hardening
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"

PIHOLE_ALLOWED_VARS = COMMON_ALLOWED_ENV_VARS | {
    'PIHOLE_*',  # Matches PIHOLE_HOST, PIHOLE_PASSWORD, etc.
}

load_env_file(ENV_FILE, allowed_vars=PIHOLE_ALLOWED_VARS, strict=True)

# Configuration
ANSIBLE_INVENTORY_PATH = os.getenv("ANSIBLE_INVENTORY_PATH", "")

logger.info(f"Ansible inventory: {ANSIBLE_INVENTORY_PATH}")

# Session cache: {hostname: {'sid': str, 'expires_at': datetime}}
SESSION_CACHE = {}


def load_pihole_hosts_from_ansible():
    """
    Load Pi-hole hosts from Ansible inventory
    Returns list of tuples: [(display_name, host, port, api_key), ...]
    """
    if not ANSIBLE_INVENTORY_PATH or not Path(ANSIBLE_INVENTORY_PATH).exists():
        logger.warning(f"Ansible inventory not found at: {ANSIBLE_INVENTORY_PATH}")
        logger.warning("Falling back to .env configuration")
        return load_pihole_hosts_from_env()
    
    try:
        with open(ANSIBLE_INVENTORY_PATH, 'r') as f:
            inventory = yaml.safe_load(f)
        
        pihole_hosts = []
        
        all_group = inventory.get('all', {})
        children = all_group.get('children', {})
        
        # Find pihole_servers group
        pihole_group = children.get('pihole_servers', {})
        
        # Process all children groups (pihole_docker, pihole_native, etc.)
        for group_name, group_data in pihole_group.get('children', {}).items():
            for hostname, host_vars in group_data.get('hosts', {}).items():
                display_name = hostname.split('.')[0].replace('-', ' ').title().replace(' ', '-')
                host = host_vars.get('ansible_host', hostname.split('.')[0])
                port = host_vars.get('pihole_port', 80)
                
                # Get API key from environment variable
                # Convert Server1 to PIHOLE_API_KEY_SERVER1
                env_key = f"PIHOLE_API_KEY_{display_name.replace('-', '_').upper()}"
                api_key = os.getenv(env_key, '')
                
                pihole_hosts.append((display_name, host, port, api_key))
                logger.info(f"Found Pi-hole host: {display_name} -> {host}:{port}")
        
        if not pihole_hosts:
            logger.warning("No Pi-hole hosts found in Ansible inventory")
            return load_pihole_hosts_from_env()
        
        return pihole_hosts
        
    except Exception as e:
        logger.error(f"Error loading Ansible inventory: {e}")
        logger.warning("Falling back to .env configuration")
        return load_pihole_hosts_from_env()


def load_pihole_hosts_from_env():
    """
    Fallback: Load Pi-hole hosts from environment variables
    Returns list of tuples: [(display_name, host, port, api_key), ...]
    """
    pihole_hosts = []
    
    # Look for PIHOLE_*_HOST environment variables
    processed_names = set()
    for key in os.environ.keys():
        if key.startswith('PIHOLE_') and key.endswith('_HOST'):
            # Extract name: PIHOLE_SERVER1_HOST -> SERVER1
            name_part = key.replace('PIHOLE_', '').replace('_HOST', '')
            
            if name_part in processed_names:
                continue
            processed_names.add(name_part)
            
            # Get corresponding values
            host = os.getenv(f'PIHOLE_{name_part}_HOST', '')
            port = int(os.getenv(f'PIHOLE_{name_part}_PORT', '80'))
            api_key = os.getenv(f'PIHOLE_API_KEY_{name_part}', '')
            
            # Format display name
            display_name = name_part.replace('_', '-').title()
            
            if host:
                pihole_hosts.append((display_name, host, port, api_key))
                logger.info(f"Loaded from env: {display_name} -> {host}:{port}")
    
    return pihole_hosts


# Load Pi-hole hosts on startup
PIHOLE_HOSTS = load_pihole_hosts_from_ansible()

if not PIHOLE_HOSTS:
    logger.error("No Pi-hole hosts configured!")
    logger.error("Please set ANSIBLE_INVENTORY_PATH or PIHOLE_*_HOST environment variables")


async def get_pihole_session(host: str, port: int, password: str) -> dict:
    """
    Get or refresh a Pi-hole session
    
    Returns:
        dict with 'sid' and 'expires_at', or {'error': str} on failure
    """
    url = f'http://{host}:{port}/api/auth'
    payload = {"password": password}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    session_data = data.get('session', {})
                    
                    if session_data.get('valid'):
                        # Calculate expiry time (session validity is in seconds)
                        validity_seconds = session_data.get('validity', 300)
                        # Refresh 30 seconds before expiry to be safe
                        expires_at = datetime.now() + timedelta(seconds=validity_seconds - 30)
                        
                        return {
                            'sid': session_data['sid'],
                            'expires_at': expires_at
                        }
                    else:
                        message = session_data.get('message', 'Authentication failed')
                        return {'error': f"Auth failed: {message}"}
                else:
                    text = await response.text()
                    return {'error': f"HTTP {response.status}: {text[:100]}"}
                    
    except asyncio.TimeoutError:
        return {'error': 'Connection timeout'}
    except aiohttp.ClientConnectorError:
        return {'error': 'Connection refused'}
    except Exception as e:
        return {'error': f"Exception: {str(e)}"}


async def get_cached_session(display_name: str, host: str, port: int, api_key: str) -> dict:
    """
    Get a valid session from cache or create a new one
    
    Returns:
        dict with 'sid', or {'error': str} on failure
    """
    if not api_key:
        return {'error': 'No API key configured'}
    
    # Check if we have a valid cached session
    cache_key = display_name
    if cache_key in SESSION_CACHE:
        cached = SESSION_CACHE[cache_key]
        if datetime.now() < cached['expires_at']:
            # Session still valid
            return {'sid': cached['sid']}
        else:
            logger.info(f"Session expired for {display_name}, refreshing...")
    
    # Get new session
    session_info = await get_pihole_session(host, port, api_key)
    
    if 'error' not in session_info:
        # Cache the new session
        SESSION_CACHE[cache_key] = session_info
        logger.info(f"New session obtained for {display_name}, expires at {session_info['expires_at']}")
        return {'sid': session_info['sid']}
    
    return session_info


async def pihole_api_request(host: str, port: int, endpoint: str, sid: str, timeout: int = 5):
    """
    Make an authenticated request to Pi-hole API using session ID
    
    Uses URL query parameter method: ?sid=<SID>
    """
    # URL-encode the SID
    encoded_sid = quote(sid)
    url = f'http://{host}:{port}{endpoint}?sid={encoded_sid}'
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"API request failed: HTTP {response.status} for {url}")
                    return None
    except asyncio.TimeoutError:
        logger.warning(f"Timeout requesting {url}")
        return None
    except Exception as e:
        logger.warning(f"Error requesting {url}: {str(e)}")
        return None


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Pi-hole tools"""
    return [
        types.Tool(
            name="get_pihole_stats",
            description="Get DNS statistics from all Pi-hole instances",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_pihole_status",
            description="Check which Pi-hole instances are online",
            inputSchema={"type": "object", "properties": {}}
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls"""
    try:
        if name == "get_pihole_stats":
            output = "=== PI-HOLE DNS STATISTICS ===\n\n"
            
            for display_name, host, port, api_key in PIHOLE_HOSTS:
                output += f"--- {display_name} ---\n"
                
                # Get session
                session_result = await get_cached_session(display_name, host, port, api_key)
                
                if 'error' in session_result:
                    output += f"Error: {session_result['error']}\n\n"
                    continue
                
                # Get stats using session
                sid = session_result['sid']
                data = await pihole_api_request(host, port, '/api/stats/summary', sid)
                
                if data:
                    # Extract stats from Pi-hole v6 API response
                    queries = data.get('queries', {})
                    clients = data.get('clients', {})
                    gravity = data.get('gravity', {})
                    
                    # Format numbers with commas
                    total_queries = queries.get('total', 0)
                    blocked_queries = queries.get('blocked', 0)
                    percent_blocked = queries.get('percent_blocked', 0)
                    unique_clients = clients.get('active', 0)
                    domains_blocked = gravity.get('domains_being_blocked', 0)
                    
                    output += f"Total Queries: {total_queries:,}\n"
                    output += f"Queries Blocked: {blocked_queries:,}\n"
                    output += f"Percent Blocked: {percent_blocked:.1f}%\n"
                    output += f"Unique Clients: {unique_clients:,}\n"
                    output += f"Domains on Blocklist: {domains_blocked:,}\n"
                else:
                    output += "Could not retrieve stats\n"
                
                output += "\n"
            
            return [types.TextContent(type="text", text=output)]
        
        elif name == "get_pihole_status":
            output = "=== PI-HOLE STATUS ===\n\n"
            online = 0
            
            for display_name, host, port, api_key in PIHOLE_HOSTS:
                # Try to get a session (which tests connectivity and auth)
                session_result = await get_cached_session(display_name, host, port, api_key)
                
                if 'error' in session_result:
                    output += f"✗ {display_name} ({host}:{port}): OFFLINE - {session_result['error']}\n"
                else:
                    online += 1
                    output += f"✓ {display_name} ({host}:{port}): ONLINE\n"
            
            output = f"Online: {online}/{len(PIHOLE_HOSTS)}\n\n" + output
            return [types.TextContent(type="text", text=output)]
        
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        logger.error(f"Error in tool {name}: {str(e)}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="pihole-info",
                server_version="3.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
