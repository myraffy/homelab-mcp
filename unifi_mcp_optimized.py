#!/usr/bin/env python3
"""
Unifi Network MCP Server - Optimized Version
Provides access to Unifi network devices and clients with better performance
Separates infrastructure (devices) from clients for faster queries
"""

import asyncio
import glob
import json
import logging
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

import mcp.server.stdio
import mcp.types as types
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from mcp_config_loader import load_env_file, COMMON_ALLOWED_ENV_VARS

server = Server("unifi-network")

# Configuration
SCRIPT_DIR = Path(__file__).parent
ENV_FILE = SCRIPT_DIR / ".env"

# Load .env with security hardening
UNIFI_ALLOWED_VARS = COMMON_ALLOWED_ENV_VARS | {
    "UNIFI_HOST",
    "UNIFI_API_KEY",
}

load_env_file(ENV_FILE, allowed_vars=UNIFI_ALLOWED_VARS, strict=True)

UNIFI_EXPORTER_PATH = SCRIPT_DIR / "unifi_exporter.py"
UNIFI_HOST = os.getenv("UNIFI_HOST", "192.168.1.1")
UNIFI_API_KEY = os.getenv("UNIFI_API_KEY", "")

# Cache configuration
CACHE_DIR = Path(tempfile.gettempdir()) / "unifi_mcp_cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_DURATION = timedelta(minutes=5)  # Cache data for 5 minutes


logger.info(f"Unifi host: {UNIFI_HOST}")
logger.info(f"API key configured: {'Yes' if UNIFI_API_KEY else 'No'}")
logger.info(f"Cache directory: {CACHE_DIR}")


def get_cached_data():
    """Get cached Unifi data if available and not expired"""
    cache_file = CACHE_DIR / "unifi_data.json"

    if not cache_file.exists():
        return None

    # Check if cache is still valid
    cache_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
    if datetime.now() - cache_time > CACHE_DURATION:
        logger.info("Cache expired")
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.info(f"Using cached data from {cache_time}")
            return data
    except Exception as e:
        logger.error(f"Error reading cache: {e}")
        return None


def save_cached_data(data):
    """Save Unifi data to cache"""
    cache_file = CACHE_DIR / "unifi_data.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        logger.info(f"Saved data to cache: {cache_file}")
    except Exception as e:
        logger.error(f"Error saving cache: {e}")


async def fetch_unifi_data():
    """Fetch fresh data from Unifi exporter"""
    if not UNIFI_EXPORTER_PATH.exists():
        raise FileNotFoundError(f"Exporter not found at {UNIFI_EXPORTER_PATH}")

    if not UNIFI_API_KEY:
        raise ValueError("UNIFI_API_KEY not set in .env file")

    with tempfile.TemporaryDirectory() as tmpdir:
        logger.info(f"Running Unifi exporter...")

        # Fix Windows console encoding issues
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        cmd = [
            "python",
            str(UNIFI_EXPORTER_PATH),
            "--host",
            UNIFI_HOST,
            "--api-key",
            UNIFI_API_KEY,
            "--format",
            "json",
            "--output-dir",
            tmpdir,
        ]

        # Use Popen with communicate() for proper subprocess handling
        import sys

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,  # Prevent stdin blocking
            text=True,
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        try:
            stdout, stderr = process.communicate(timeout=30)

            if process.returncode != 0:
                logger.error(f"Exporter failed: {stderr}")
                raise RuntimeError(f"Exporter failed with code {process.returncode}")

        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            logger.warning("Process timeout but checking for output files...")

        # Find the generated JSON file
        json_files = glob.glob(os.path.join(tmpdir, "unifi_network_*.json"))

        if not json_files:
            raise FileNotFoundError(
                f"No output file generated. STDOUT: {stdout}, STDERR: {stderr}"
            )

        # Read the most recent file
        latest_file = sorted(json_files)[-1]
        logger.info(f"Reading data from {latest_file}")

        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Save to cache
        save_cached_data(data)

        return data


async def get_unifi_data():
    """Get Unifi data from cache or fetch fresh"""
    # Try cache first
    data = get_cached_data()
    if data:
        return data

    # Fetch fresh data
    logger.info("Fetching fresh Unifi data...")
    return await fetch_unifi_data()


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available Unifi network tools"""
    return [
        types.Tool(
            name="get_network_devices",
            description="Get all Unifi network devices (switches, APs, gateways) with status and basic info. This is cached for better performance.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_network_clients",
            description="Get all active network clients and their connections. This is cached for better performance.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="get_network_summary",
            description="Get network overview: VLANs, device count, client count. Fast summary view.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        types.Tool(
            name="refresh_network_data",
            description="Force refresh network data from Unifi controller (bypasses cache).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls"""
    try:
        if name == "get_network_devices":
            data = await get_unifi_data()
            return format_network_devices(data)

        elif name == "get_network_clients":
            data = await get_unifi_data()
            return format_network_clients(data)

        elif name == "get_network_summary":
            data = await get_unifi_data()
            return format_network_summary(data)

        elif name == "refresh_network_data":
            logger.info("Force refreshing network data...")
            data = await fetch_unifi_data()
            return [
                types.TextContent(
                    type="text",
                    text=f"✓ Network data refreshed successfully\n\nDevices: {len(data.get('devices', []))}\nClients: {len(data.get('clients', []))}\nNetworks: {len(data.get('networks', []))}",
                )
            ]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        logger.error(f"Error in {name}: {str(e)}", exc_info=True)
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


def format_network_devices(data: dict) -> list[types.TextContent]:
    """Format network devices output"""
    devices = data.get("devices", [])

    output = "=== NETWORK DEVICES ===\n\n"
    output += f"Total: {len(devices)} devices\n\n"

    # Group by type
    by_type = {}
    for device in devices:
        device_type = device.get("type", "unknown")
        if device_type not in by_type:
            by_type[device_type] = []
        by_type[device_type].append(device)

    type_names = {
        "ugw": "Gateways",
        "usw": "Switches",
        "uap": "Access Points",
        "unknown": "Other",
    }

    for device_type, type_devices in sorted(by_type.items()):
        output += f"\n{type_names.get(device_type, device_type.upper())} ({len(type_devices)}):\n"

        for device in type_devices:
            name = device.get("name", "Unknown")
            model = device.get("model", "N/A")
            ip = device.get("ip", "N/A")
            state = device.get("state", 0)
            status = "✓ Online" if state == 1 else "✗ Offline"
            version = device.get("version", "N/A")

            output += f"  • {name} ({model})\n"
            output += f"    IP: {ip} | Status: {status} | Version: {version}\n"

            # Add client count for APs
            if device_type == "uap":
                num_sta = device.get("num_sta", 0)
                output += f"    Connected clients: {num_sta}\n"

            # Add port info for switches
            if device_type == "usw":
                port_table = device.get("port_table", [])
                ports_up = sum(1 for p in port_table if p.get("up", False))
                output += f"    Ports: {ports_up}/{len(port_table)} up\n"

    return [types.TextContent(type="text", text=output)]


def format_network_clients(data: dict) -> list[types.TextContent]:
    """Format network clients output"""
    clients = data.get("clients", [])
    networks = {n["_id"]: n for n in data.get("networks", [])}

    output = "=== NETWORK CLIENTS ===\n\n"
    output += f"Total: {len(clients)} active clients\n\n"

    # Group by VLAN/network
    by_network = {}
    for client in clients:
        network_id = client.get("network_id", "unknown")
        if network_id not in by_network:
            by_network[network_id] = []
        by_network[network_id].append(client)

    for network_id, network_clients in sorted(
        by_network.items(), key=lambda x: len(x[1]), reverse=True
    ):
        network_name = networks.get(network_id, {}).get("name", "Unknown")
        vlan = networks.get(network_id, {}).get("vlan", "N/A")

        output += f"\n{network_name} (VLAN {vlan}) - {len(network_clients)} clients:\n"

        # Show first 10 clients per network
        for client in network_clients[:10]:
            hostname = client.get("hostname", client.get("name", "Unknown"))
            ip = client.get("ip", "N/A")
            mac = client.get("mac", "N/A")
            is_wired = client.get("is_wired", False)
            conn_type = "Wired" if is_wired else "Wireless"

            output += f"  • {hostname} ({ip})\n"
            output += f"    MAC: {mac} | {conn_type}\n"

        if len(network_clients) > 10:
            output += f"  ... and {len(network_clients) - 10} more\n"

    return [types.TextContent(type="text", text=output)]


def format_network_summary(data: dict) -> list[types.TextContent]:
    """Format network summary output"""
    networks = data.get("networks", [])
    devices = data.get("devices", [])
    clients = data.get("clients", [])

    output = "=== NETWORK SUMMARY ===\n\n"

    # Overall stats
    output += f"Networks/VLANs: {len(networks)}\n"
    output += f"Network Devices: {len(devices)}\n"
    output += f"Active Clients: {len(clients)}\n\n"

    # Device breakdown
    online_devices = sum(1 for d in devices if d.get("state") == 1)
    output += f"DEVICES:\n"
    output += f"  Online: {online_devices}/{len(devices)}\n"

    # Count by type
    device_types = {}
    for d in devices:
        dtype = d.get("type", "unknown")
        device_types[dtype] = device_types.get(dtype, 0) + 1

    type_names = {"ugw": "Gateways", "usw": "Switches", "uap": "Access Points"}
    for dtype, count in device_types.items():
        output += f"  {type_names.get(dtype, dtype)}: {count}\n"

    # Client breakdown
    wired = sum(1 for c in clients if c.get("is_wired", False))
    output += f"\nCLIENTS:\n"
    output += f"  Wired: {wired}\n"
    output += f"  Wireless: {len(clients) - wired}\n"

    # Top networks by client count
    by_network = {}
    for client in clients:
        network_id = client.get("network_id", "unknown")
        by_network[network_id] = by_network.get(network_id, 0) + 1

    output += f"\nTOP NETWORKS:\n"
    networks_dict = {n["_id"]: n for n in networks}
    for network_id, count in sorted(
        by_network.items(), key=lambda x: x[1], reverse=True
    )[:5]:
        name = networks_dict.get(network_id, {}).get("name", "Unknown")
        vlan = networks_dict.get(network_id, {}).get("vlan", "N/A")
        output += f"  • {name} (VLAN {vlan}): {count} clients\n"

    return [types.TextContent(type="text", text=output)]


async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="unifi-network",
                server_version="2.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
