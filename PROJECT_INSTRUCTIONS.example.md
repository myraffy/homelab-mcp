# Homelab MCP Context - Project Instructions (EXAMPLE)

**⚠️ IMPORTANT: This is an example template. Copy this to `PROJECT_INSTRUCTIONS.md` and customize with your actual infrastructure details.**

## Overview
You are assisting with a comprehensive homelab infrastructure that includes multiple servers, network devices, containers, and automation tools. You have access to specialized MCP (Model Context Protocol) servers that provide real-time access to all infrastructure components.

## Available MCP Servers & Capabilities

### 1. Ansible Inventory MCP (`ansible-inventory`)
**Purpose:** Query Ansible infrastructure inventory
**Use for:** Understanding host configurations, groups, and infrastructure layout

**Key Capabilities:**
- `get_all_hosts` - List all hosts in the infrastructure
- `get_all_groups` - View all defined groups
- `get_host_details` - Deep dive into specific host configuration
- `get_group_details` - Examine group structure and variables
- `search_hosts` - Find hosts by pattern or variable values
- `get_inventory_summary` - Quick overview of entire infrastructure

**When to use:** Before making infrastructure changes, when understanding relationships between hosts, when planning deployments

### 2. Docker/Podman MCP (`docker`)
**Purpose:** Monitor and inspect Docker and Podman containers across all hosts
**Use for:** Container health checks, deployment verification, troubleshooting

**Hosts monitored:**
- server1 (192.168.1.100) - Docker
- server2 (192.168.1.101) - Docker
- server3 (192.168.1.102) - Podman
- [Add your hosts here]

**Key Capabilities:**
- `get_docker_containers` - View containers on specific host
- `get_all_containers` - See all containers across infrastructure
- `get_container_stats` - CPU/memory usage for containers
- `check_container` - Verify if specific container is running

**When to use:** Checking service status, verifying deployments, troubleshooting container issues, monitoring resource usage

### 3. Ollama AI MCP (`ollama`)
**Purpose:** Monitor Ollama AI model instances and LiteLLM proxy
**Use for:** AI infrastructure management, model availability checks

**Hosts monitored:**
- server1 (192.168.1.100)
- server2 (192.168.1.101)
- workstation (192.168.1.150)
- [Add your hosts here]

**Key Capabilities:**
- `get_ollama_status` - Check all Ollama instances
- `get_ollama_models` - List models on specific host
- `get_litellm_status` - Verify LiteLLM proxy health

**When to use:** Checking AI service availability, verifying model deployments, troubleshooting LiteLLM proxy

### 4. Pi-hole DNS MCP (`pihole`)
**Purpose:** Monitor Pi-hole DNS filtering and statistics
**Use for:** DNS health checks, blocking statistics, network client monitoring

**Hosts monitored:**
- pihole-primary (192.168.1.10:80)
- pihole-secondary (192.168.1.11:80)
- [Add your hosts here]

**Key Capabilities:**
- `get_pihole_status` - Check which Pi-holes are online
- `get_pihole_stats` - DNS query stats, blocking percentages, client counts

**When to use:** Checking DNS health, investigating network issues, monitoring blocking effectiveness

### 5. Unifi Network MCP (`unifi`)
**Purpose:** Monitor Unifi network infrastructure
**Use for:** Network health, device status, client monitoring

**Infrastructure:**
- Network devices (switches, APs, gateways)
- VLANs
- Active clients
- [Add your infrastructure details here]

**Key Capabilities:**
- `get_network_devices` - View all switches, APs, gateways with status
- `get_network_clients` - See all active clients and connections
- `get_network_summary` - Quick overview of network health
- `refresh_network_data` - Force refresh from Unifi controller

**When to use:** Network troubleshooting, checking device status, monitoring client connections

### 6. n8n Workflow MCP (`n8n-mcp`)
**Purpose:** Interact with n8n workflow automation platform
**Use for:** Workflow management, automation tasks

**Endpoint:** https://n8n.your-domain.com

**Key Capabilities:**
- Full n8n workflow operations (525 nodes available)
- 263 AI-optimized tools
- Workflow creation, validation, and execution
- Access to templates and documentation

**When to use:** Creating automation workflows, integrating services, building complex automation chains

### 7. MCP Registry Inspector (`mcp-registry-inspector`)
**Purpose:** Self-inspection and file management for MCP development
**Use for:** Managing MCP server code, configuration updates

**Key Capabilities:**
- `get_claude_config` - View Claude Desktop MCP configuration
- `list_mcp_servers` - See all registered MCP servers
- `list_mcp_directory` - Browse MCP development directory
- `read_mcp_file` - Read MCP server source code
- `write_mcp_file` - **Update MCP server files directly**
- `search_mcp_files` - Find files by name or extension

**When to use:** Updating MCP servers, reviewing configuration, modifying code, managing the MCP ecosystem

## Infrastructure Configuration

### Configuration Hierarchy
1. **Ansible Inventory** (Primary) - `/path/to/ansible_hosts.yml`
2. **Environment Variables** (Fallback) - `.env` file in MCP directory
3. **Defaults** (Last resort)

### Key Network Information
- **Network:** 192.168.1.0/24 (customize with your network)
- **DNS:** Pi-hole instances at configured addresses
- **Gateway:** Your router/firewall address
- **Primary NAS:** Your NAS hostname/IP
- [Add your network details here]

### Main Servers
- **server1** (192.168.1.100) - Description, OS, services
- **server2** (192.168.1.101) - Description, OS, services
- **server3** (192.168.1.102) - Description, OS, services
- [Add your servers here]

## Best Practices

### When Starting Work
1. **Check infrastructure status first** - Use relevant MCP tools to understand current state
2. **Query Ansible inventory** - Understand host relationships and groups
3. **Verify services are running** - Use Docker and service-specific MCPs

### When Making Changes
1. **Use MCP Registry Inspector** - Write updated code directly to files
2. **Update Ansible inventory** - Keep it as single source of truth
3. **Test after changes** - Verify with appropriate MCP tools
4. **Document in .md files** - Use write_mcp_file to create documentation

### When Troubleshooting
1. **Start with service-specific MCP** - Check if service is actually down
2. **Check Docker containers** - Verify container health and status
3. **Review network** - Use Unifi MCP to check connectivity
4. **Check DNS** - Pi-hole MCP for DNS issues
5. **Verify Ansible config** - Ensure inventory is correct

### Important Notes
- **Always check before assuming** - Don't assume services are down, verify with MCPs
- **Use Ansible inventory** - It's the source of truth for infrastructure
- **Write files directly** - You can update MCP code using write_mcp_file
- **Test thoroughly** - After making changes, verify with relevant MCP tools
- **Configuration in Ansible** - Host IPs, ports, and infrastructure details live in Ansible inventory

## Common Workflows

### Checking Infrastructure Health
```
1. Get Ollama status (AI services)
2. Get all containers (application services)
3. Get Pi-hole status (DNS)
4. Get network summary (network health)
```

### Updating MCP Server
```
1. Read current MCP file
2. Make modifications
3. Write updated file using write_mcp_file
4. User restarts Claude Desktop
5. Test updated functionality
```

### Investigating Issues
```
1. Check specific service with relevant MCP
2. If containerized, check with Docker MCP
3. Verify host in Ansible inventory
4. Check network connectivity with Unifi MCP
5. Review DNS with Pi-hole MCP
```

### Adding New Infrastructure
```
1. Update Ansible inventory with new host
2. Deploy services via Ansible (if applicable)
3. Verify with Docker MCP (if containers)
4. Test specific service with relevant MCP
5. Update documentation
```

## Security Reminders

- **Never expose sensitive information** in responses
- **API keys and passwords** are in environment variables only
- **IP addresses** in this file are your private infrastructure
- **This file contains your network topology** - treat as confidential

## Remember
- You have **7 powerful MCP servers** at your disposal
- You can **read AND write files** directly
- Infrastructure state is **live and real-time**
- **Ansible inventory** is the authoritative source
- When in doubt, **query the relevant MCP** rather than guessing

This homelab is production-grade with redundancy, monitoring, and automation. Treat it as a professional infrastructure and always verify changes with the appropriate MCP tools.
