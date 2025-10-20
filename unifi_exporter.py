#!/usr/bin/env python3
"""
Unifi Network Information Exporter
Queries Unifi Controller using direct API calls and exports network topology, devices, and configuration
Works with Unifi Network Application 9.x and API keys
Windows-compatible version
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests
import urllib3
import yaml

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Fix Windows console encoding
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


class UnifiAPI:
    """Direct API wrapper for Unifi Network Application"""

    def __init__(self, host, port=443, site="default", verify_ssl=False):
        self.base_url = f"https://{host}:{port}"
        self.site = site
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.verify = verify_ssl

    def login_with_api_key(self, api_key):
        """Authenticate using API key"""
        self.session.headers.update(
            {"X-API-KEY": api_key, "Content-Type": "application/json"}
        )

        # Test the connection
        try:
            response = self.session.get(
                f"{self.base_url}/proxy/network/api/s/{self.site}/self"
            )
            if response.status_code == 401:
                return False, "API key authentication failed - invalid key"
            elif response.status_code == 404:
                # Try alternative endpoint structure
                response = self.session.get(f"{self.base_url}/api/s/{self.site}/self")
                if response.status_code != 200:
                    return (
                        False,
                        f"API endpoint not found (status: {response.status_code})",
                    )

            if response.status_code == 200:
                return True, "Connected successfully"
            else:
                return False, f"Unexpected response: {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}"

    def login_with_credentials(self, username, password):
        """Authenticate using username and password"""
        login_data = {"username": username, "password": password}

        try:
            # Try UniFi OS endpoint first
            response = self.session.post(
                f"{self.base_url}/api/auth/login", json=login_data
            )

            if response.status_code == 404:
                # Try legacy endpoint
                response = self.session.post(
                    f"{self.base_url}/api/login", json=login_data
                )

            if response.status_code == 200:
                return True, "Connected successfully"
            else:
                return False, f"Login failed - status code: {response.status_code}"
        except requests.exceptions.RequestException as e:
            return False, f"Connection error: {str(e)}"

    def _get(self, endpoint):
        """Make GET request to API"""
        # Try UniFi OS proxy endpoint first
        url = f"{self.base_url}/proxy/network/api/s/{self.site}/{endpoint}"
        response = self.session.get(url)

        if response.status_code == 404:
            # Fallback to legacy endpoint
            url = f"{self.base_url}/api/s/{self.site}/{endpoint}"
            response = self.session.get(url)

        if response.status_code == 200:
            data = response.json()
            return data.get("data", [])
        else:
            print(
                f"Warning: Failed to fetch {endpoint} (status: {response.status_code})",
                file=sys.stderr,
            )
            return []

    def get_devices(self):
        """Get all network devices"""
        return self._get("stat/device")

    def get_clients(self):
        """Get all active clients"""
        return self._get("stat/sta")

    def get_networks(self):
        """Get network configuration"""
        return self._get("rest/networkconf")

    def get_port_forward_rules(self):
        """Get port forwarding rules"""
        return self._get("rest/portforward")

    def get_firewall_rules(self):
        """Get firewall rules"""
        return self._get("rest/firewallrule")

    def get_site_settings(self):
        """Get site settings"""
        return self._get("get/setting")

    def get_routing(self):
        """Get routing configuration"""
        return self._get("rest/routing")


def gather_network_info(api):
    """Gather all network information"""
    info = {
        "export_timestamp": datetime.now().isoformat(),
        "networks": [],
        "devices": [],
        "clients": [],
        "port_forwarding": [],
        "firewall_rules": [],
        "routing": [],
        "site_settings": [],
    }

    try:
        # Get Networks/VLANs
        print("Fetching networks...", file=sys.stderr)
        info["networks"] = api.get_networks()

        # Get Devices
        print("Fetching devices...", file=sys.stderr)
        devices = api.get_devices()
        for device in devices:
            device_info = {
                "name": device.get("name", "Unknown"),
                "model": device.get("model", "Unknown"),
                "type": device.get("type", "Unknown"),
                "ip": device.get("ip", "Unknown"),
                "mac": device.get("mac", "Unknown"),
                "version": device.get("version", "Unknown"),
                "state": device.get("state", "Unknown"),
                "uptime": device.get("uptime", 0),
                "adopted": device.get("adopted", False),
            }

            # Add switch-specific info
            if device.get("type") == "usw":
                device_info["port_table"] = device.get("port_table", [])
                device_info["port_overrides"] = device.get("port_overrides", [])

            # Add AP-specific info
            if device.get("type") == "uap":
                device_info["essid"] = device.get("essid", "N/A")
                device_info["num_sta"] = device.get("num_sta", 0)

            # Add gateway-specific info
            if device.get("type") == "ugw" or device.get("type") == "udm":
                device_info["wan"] = device.get("wan1", {})
                device_info["speedtest_status"] = device.get("speedtest-status", {})

            info["devices"].append(device_info)

        # Get Active Clients
        print("Fetching clients...", file=sys.stderr)
        clients = api.get_clients()
        for client in clients:
            client_info = {
                "hostname": client.get("hostname", client.get("name", "Unknown")),
                "ip": client.get("ip", "Unknown"),
                "mac": client.get("mac", "Unknown"),
                "network": client.get("network", "Unknown"),
                "network_name": client.get("network_name", "Unknown"),
                "connected_device": client.get(
                    "sw_mac", client.get("ap_mac", "Unknown")
                ),
                "connected_port": client.get("sw_port", "N/A"),
                "uptime": client.get("uptime", 0),
                "last_seen": client.get("last_seen", 0),
                "is_wired": client.get("is_wired", False),
            }
            info["clients"].append(client_info)

        # Get Port Forwarding Rules
        print("Fetching port forwarding rules...", file=sys.stderr)
        info["port_forwarding"] = api.get_port_forward_rules()

        # Get Firewall Rules
        print("Fetching firewall rules...", file=sys.stderr)
        info["firewall_rules"] = api.get_firewall_rules()

        # Get Routing
        print("Fetching routing configuration...", file=sys.stderr)
        info["routing"] = api.get_routing()

        # Get Site Settings
        print("Fetching site settings...", file=sys.stderr)
        info["site_settings"] = api.get_site_settings()

    except Exception as e:
        print(f"ERROR: Failed to gather network info: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()

    return info


def generate_network_diagram(info):
    """Generate a markdown network diagram"""
    diagram = ["# Network Topology\n"]
    diagram.append(f"*Generated: {info['export_timestamp']}*\n")

    # Networks/VLANs
    diagram.append("\n## Networks/VLANs\n")
    for net in info["networks"]:
        name = net.get("name", "Unknown")
        vlan = net.get("vlan", "N/A")
        subnet = net.get("ip_subnet", "N/A")
        dhcp = "DHCP enabled" if net.get("dhcpd_enabled", False) else "DHCP disabled"

        diagram.append(f"### {name}\n")
        diagram.append(f"- **VLAN:** {vlan}\n")
        diagram.append(f"- **Subnet:** {subnet}\n")
        diagram.append(f"- **DHCP:** {dhcp}\n")

        if net.get("dhcpd_enabled"):
            start = net.get("dhcpd_start", "N/A")
            stop = net.get("dhcpd_stop", "N/A")
            diagram.append(f"- **DHCP Range:** {start} - {stop}\n")
        diagram.append("\n")

    # Devices
    diagram.append("\n## Network Devices\n")
    for device in info["devices"]:
        diagram.append(f"### {device['name']} ({device['model']})\n")
        diagram.append(f"- **Type:** {device['type']}\n")
        diagram.append(f"- **IP:** {device['ip']}\n")
        diagram.append(f"- **MAC:** {device['mac']}\n")
        diagram.append(f"- **State:** {device['state']}\n")
        diagram.append(f"- **Version:** {device['version']}\n")

        if "port_table" in device and device["port_table"]:
            active_ports = [p for p in device["port_table"] if p.get("up", False)]
            if active_ports:
                diagram.append(f"\n**Active Ports ({len(active_ports)}):**\n")
                for port in active_ports[:10]:  # Limit to first 10
                    port_num = port.get("port_idx", "Unknown")
                    speed = port.get("speed", 0)
                    name = port.get("name", "")
                    diagram.append(f"  - Port {port_num}: {speed}Mbps")
                    if name:
                        diagram.append(f" ({name})")
                    diagram.append("\n")
        diagram.append("\n")

    # Client Summary
    diagram.append("\n## Active Clients Summary\n")
    diagram.append(f"**Total Clients:** {len(info['clients'])}\n")

    wired = sum(1 for c in info["clients"] if c.get("is_wired", False))
    wireless = len(info["clients"]) - wired
    diagram.append(f"- **Wired:** {wired}\n")
    diagram.append(f"- **Wireless:** {wireless}\n\n")

    # Group clients by network
    clients_by_network = {}
    for client in info["clients"]:
        network = client.get("network_name", "Unknown")
        if network not in clients_by_network:
            clients_by_network[network] = []
        clients_by_network[network].append(client)

    for network, clients in clients_by_network.items():
        diagram.append(f"\n### {network} ({len(clients)} clients)\n")
        for client in clients[:10]:  # Limit to first 10 per network
            hostname = client["hostname"]
            ip = client["ip"]
            conn_type = "Wired" if client.get("is_wired") else "Wireless"
            diagram.append(f"- **{hostname}** - {ip} ({conn_type})\n")

        if len(clients) > 10:
            diagram.append(f"\n*... and {len(clients) - 10} more clients*\n")

    # Port Forwarding
    if info["port_forwarding"]:
        diagram.append("\n## Port Forwarding Rules\n")
        for rule in info["port_forwarding"]:
            if rule.get("enabled", False):
                name = rule.get("name", "Unnamed")
                fwd_port = rule.get("fwd_port", "N/A")
                dst_port = rule.get("dst_port", "N/A")
                fwd = rule.get("fwd", "N/A")
                diagram.append(f"- **{name}:** Port {fwd_port} -> {fwd}:{dst_port}\n")

    return "".join(diagram)


def main():
    parser = argparse.ArgumentParser(
        description="Export Unifi Network Information",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using API key
  %(prog)s --host 192.168.1.1 --api-key YOUR_KEY
  
  # Using username/password
  %(prog)s --host 192.168.1.1 --username admin --password pass123
  
  # Custom port and site
  %(prog)s --host 192.168.1.1 --api-key YOUR_KEY --port 8443 --site default
        """,
    )

    parser.add_argument("--host", required=True, help="Unifi Controller hostname/IP")

    # Authentication options
    auth_group = parser.add_mutually_exclusive_group(required=True)
    auth_group.add_argument("--api-key", help="API Key for authentication")
    auth_group.add_argument(
        "--username", help="Controller username (requires --password)"
    )

    parser.add_argument("--password", help="Controller password (used with --username)")
    parser.add_argument(
        "--port", default=443, type=int, help="Controller port (default: 443)"
    )
    parser.add_argument("--site", default="default", help="Site ID (default: default)")
    parser.add_argument(
        "--output-dir", default="./unifi_export", help="Output directory"
    )
    parser.add_argument(
        "--format",
        choices=["json", "yaml", "both"],
        default="both",
        help="Output format (default: both)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    # Validate authentication arguments
    if args.username and not args.password:
        parser.error("--username requires --password")

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.debug:
        print(f"Debug: Connecting with:", file=sys.stderr)
        print(f"  Host: {args.host}", file=sys.stderr)
        print(f"  Port: {args.port}", file=sys.stderr)
        print(f"  Site: {args.site}", file=sys.stderr)

    # Connect to controller
    print(
        f"Connecting to Unifi Controller at {args.host}:{args.port}...", file=sys.stderr
    )
    api = UnifiAPI(host=args.host, port=args.port, site=args.site)

    if args.api_key:
        success, message = api.login_with_api_key(args.api_key)
    else:
        success, message = api.login_with_credentials(args.username, args.password)

    if not success:
        print(f"ERROR: {message}", file=sys.stderr)
        print("\nTroubleshooting:", file=sys.stderr)
        print(
            "  - Verify the controller is accessible at https://{}:{}".format(
                args.host, args.port
            ),
            file=sys.stderr,
        )
        print("  - Check your API key or credentials", file=sys.stderr)
        print("  - Try port 443 (UniFi OS) or 8443 (legacy)", file=sys.stderr)
        print("  - Ensure the API key has sufficient permissions", file=sys.stderr)
        exit(1)

    print(f"SUCCESS: {message}", file=sys.stderr)

    # Gather information
    print("\nGathering network information...", file=sys.stderr)
    network_info = gather_network_info(api)

    # Save to files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if args.format in ["json", "both"]:
        json_file = output_dir / f"unifi_network_{timestamp}.json"
        print(f"Writing JSON to {json_file}...", file=sys.stderr)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(network_info, f, indent=2, default=str)

    if args.format in ["yaml", "both"]:
        yaml_file = output_dir / f"unifi_network_{timestamp}.yaml"
        print(f"Writing YAML to {yaml_file}...", file=sys.stderr)
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(network_info, f, default_flow_style=False, sort_keys=False)

    # Generate markdown diagram
    diagram_file = output_dir / f"network_diagram_{timestamp}.md"
    print(f"Generating network diagram to {diagram_file}...", file=sys.stderr)
    diagram = generate_network_diagram(network_info)
    with open(diagram_file, "w", encoding="utf-8") as f:
        f.write(diagram)

    print("\nExport complete!", file=sys.stderr)
    print(f"  Files saved to: {output_dir}", file=sys.stderr)
    print(f"  - Networks: {len(network_info['networks'])}", file=sys.stderr)
    print(f"  - Devices: {len(network_info['devices'])}", file=sys.stderr)
    print(f"  - Clients: {len(network_info['clients'])}", file=sys.stderr)
    print(
        f"  - Port Forwarding Rules: {len(network_info['port_forwarding'])}",
        file=sys.stderr,
    )
    print(f"  - Firewall Rules: {len(network_info['firewall_rules'])}", file=sys.stderr)


if __name__ == "__main__":
    main()
