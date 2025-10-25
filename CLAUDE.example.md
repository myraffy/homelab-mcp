# Claude Development Guide for Homelab MCP

## Project Overview

**Repository:** <https://github.com/bjeans/homelab-mcp>  
**Version:** 1.0.0 (Released: 2025-10-11)  
**License:** MIT  
**Purpose:** Open-source MCP servers for homelab infrastructure management through Claude Desktop

This project provides real-time monitoring and control of homelab infrastructure including Docker/Podman containers, Ollama AI models, Pi-hole DNS, Unifi networks, and Ansible inventory through the Model Context Protocol.

## Core Philosophy

1. **Security First** - Never commit credentials, IPs, or sensitive data
2. **Configuration as Code** - All settings via environment variables or Ansible inventory
3. **User Privacy** - All example files use placeholder data
4. **Production-Grade** - Code quality suitable for critical infrastructure
5. **Open Source** - Community-friendly, well-documented, MIT licensed

## Project Structure

```text
homelab-mcp/
├── ansible_mcp_server.py          # Ansible inventory queries
├── docker_mcp_podman.py           # Docker/Podman container monitoring
├── ollama_mcp.py                  # Ollama AI model management
├── pihole_mcp.py                  # Pi-hole DNS monitoring
├── unifi_mcp_optimized.py         # Unifi network device monitoring
├── ping_mcp_server.py             # Network connectivity testing (ICMP ping)
├── mcp_registry_inspector.py      # MCP server file management
├── unifi_exporter.py              # Unifi data export utility
├── .env.example                   # Configuration template
├── ansible_hosts.example.yml      # Ansible inventory example
├── PROJECT_INSTRUCTIONS.example.md # AI assistant guide
├── CLAUDE.example.md              # This file (rename to CLAUDE.md)
├── README.md                      # User documentation
├── SECURITY.md                    # Security guidelines
├── CONTRIBUTING.md                # Contribution guide
├── CHANGELOG.md                   # Version history
├── CONTEXT_AWARE_SECURITY.md      # Context-aware security scanning
├── CI_CD_CHECKS.md                # CI/CD automation documentation
├── LICENSE                        # MIT License
├── .gitignore                     # Git ignore rules
└── helpers/                       # Utility and setup scripts
    ├── install_git_hook.py        # Git pre-push hook installer
    ├── pre_publish_check.py       # Security validation script
    ├── run_checks.py              # CI/CD check runner
    └── requirements-dev.txt       # Development dependencies
```

## Setup Instructions

To use this file:

1. Copy `CLAUDE.example.md` to `CLAUDE.md`
2. Update any personal URLs or infrastructure details with your actual values
3. Never commit your customized `CLAUDE.md` - it's in `.gitignore` for security

**Note:** This example includes the actual homelab-mcp GitHub repository URLs for reporting issues and contributing.

## Architecture Patterns

### MCP Server Pattern

All servers follow this structure:

```python
@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [...]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls with proper error handling"""
    try:
        # Input validation
        # API call with timeout
        # Error handling
        # Structured JSON response
    except Exception as e:
        return error_response(...)
```

### Configuration Hierarchy

1. **Ansible Inventory** (Primary) - Single source of truth for infrastructure
2. **Environment Variables** (.env) - Service-specific credentials
3. **Defaults** - Fallback values in code

### Error Handling

- Always use try/except blocks
- Return structured error responses
- Log to stderr for debugging
- Never expose internal details to users

## Development Workflows

### Adding a New MCP Server

1. **Create server file** following naming: `{service}_mcp_server.py`
2. **Follow MCP pattern** from existing servers
3. **Add to .env.example** with placeholder values
4. **Update README.md** with server documentation
5. **Update PROJECT_INSTRUCTIONS.example.md** with usage patterns
6. **Test with real infrastructure**
7. **Run security check** before commit

### Modifying Existing Server

1. **Read current implementation** fully
2. **Maintain backward compatibility** unless major version
3. **Update error handling** if changing API calls
4. **Test all tool functions** after changes
5. **Update documentation** in README and docstrings
6. **Run pre_publish_check.py** before commit

### Security Checklist

Before any commit:

- [ ] No hardcoded IPs, hostnames, or credentials
- [ ] All sensitive data uses environment variables
- [ ] Example files use placeholder data (example.com, 192.0.2.x)
- [ ] Error messages don't expose internal details
- [ ] `pre_publish_check.py` passes
- [ ] Git pre-push hook installed (`install_git_hook.py`)

## Key Technical Decisions

### Why Ansible Inventory as Primary Config?

- Users already manage infrastructure with Ansible
- Single source of truth for all host details
- Reduces duplication across MCP servers
- Easier to keep configuration in sync

### Why Individual Server Files?

- Easier to maintain and debug
- Users can enable only what they need
- Clearer separation of concerns
- Simpler dependency management

### Why Python?

- Native MCP SDK support
- Strong async/await support
- Rich ecosystem for API clients
- Familiar to sysadmins and developers

### Why No Database?

- All data fetched in real-time from services
- Reduces complexity and maintenance
- Ensures data is always current
- No state synchronization issues

## Common AI Assistant Tasks

### "Add feature X to server Y"

1. Read the server file completely
2. Understand current tool structure
3. Add new tool following existing patterns
4. Update docstrings and error handling
5. Test thoroughly with real service
6. Update README.md documentation

### "Debug connection issue"

1. Check .env.example for required variables
2. Verify error handling in server code
3. Test API endpoint independently
4. Check firewall/network access
5. Validate credentials format

### "Improve error messages"

1. Review all error_response() calls
2. Make messages user-friendly
3. Don't expose internal details
4. Include actionable suggestions
5. Test each error path

### "Update documentation"

1. Update inline docstrings first
2. Update README.md server section
3. Update PROJECT_INSTRUCTIONS.example.md if workflow changes
4. Update CHANGELOG.md with changes
5. Consider if SECURITY.md needs updates

### "Create task reminder for user"

When user asks to remember something or track an issue:

1. Create GitHub issues in the homelab-mcp repository for bugs or feature requests
2. Use your preferred task management system (if configured)
3. Include detailed content with context and steps to reproduce
4. Add appropriate labels and assign if working on the project

**Examples of reminder requests:**

- "Remind me to reboot Server-01 to test auto-start"
- "Add upgrading Pi-hole to my todo list"
- "Don't forget to check that certificate renewal"
- "Track this workflow issue"
- "Report this bug in the homelab-mcp repository"

**Always help users track important tasks** - suggest appropriate tools.

## Testing Strategy

### Manual Testing

```bash
# Set up test environment
cp .env.example .env
# Edit .env with test credentials

# Test individual server
python ansible_mcp_server.py

# Test with Claude Desktop
# Add to claude_desktop_config.json
# Restart Claude Desktop
# Try commands in chat
```

### Security Testing

```bash
# Before every commit
python pre_publish_check.py

# Install git hook (one time)
python install_git_hook.py

# Hook will run automatically on git push
```

## Red Flags to Watch For

⚠️ **Never do these:**

- Hardcoding IPs, hostnames, or credentials
- Exposing API keys or tokens in logs
- Committing .env or other config files
- Using real infrastructure details in examples
- Skipping error handling in network calls
- Assuming services are always available

✅ **Always do these:**

- Use environment variables for all config
- Validate inputs before API calls
- Handle network timeouts gracefully
- Return structured JSON responses
- Log errors to stderr for debugging
- Run pre_publish_check.py before commits

## Working with Issues and PRs

### Good Issue Reports Include

- MCP server name and version
- Claude Desktop version
- Operating system
- Error messages (sanitized)
- Steps to reproduce
- Expected vs actual behavior

### Good Pull Requests Include

- Clear description of problem solved
- Testing performed
- Documentation updates
- Security considerations
- Breaking changes noted
- Screenshots/examples if applicable

## Task Management Integration

### GitHub Issues (Recommended)

Use the homelab-mcp GitHub repository for project-related tasks:

- **Bugs**: Report issues with MCP servers or infrastructure problems
- **Feature Requests**: Suggest new MCP servers or enhancements
- **Documentation**: Improvements to guides, examples, or clarity
- **Security**: Report security concerns or improvement suggestions

### Personal Task Management (Optional)

You may also integrate with your preferred task management system for personal homelab tasks:

- Infrastructure maintenance reminders
- Upgrade schedules
- Testing checklists
- Configuration changes

**Task Categories (for GitHub issues):**

- `bug` - Something isn't working
- `enhancement` - New feature or request  
- `documentation` - Improvements or additions to docs
- `security` - Security-related improvements
- `help wanted` - Extra attention is needed
- `good first issue` - Good for newcomers

## Links and Resources

- **Repository:** <https://github.com/bjeans/homelab-mcp>
- **Issues:** <https://github.com/bjeans/homelab-mcp/issues>
- **Discussions:** <https://github.com/bjeans/homelab-mcp/discussions>
- **Security:** <https://github.com/bjeans/homelab-mcp/security/advisories>
- **Pull Requests:** <https://github.com/bjeans/homelab-mcp/pulls>
- **Releases:** <https://github.com/bjeans/homelab-mcp/releases>
- **MCP Docs:** <https://modelcontextprotocol.io/>
- **Claude Desktop:** <https://claude.ai/download>

## Quick Commands Reference

```bash
# Security check
python pre_publish_check.py

# Install git hook
python install_git_hook.py

# Test server
python {server}_mcp_server.py

# Create example configs
cp .env.example .env
cp ansible_hosts.example.yml ansible_hosts.yml
cp PROJECT_INSTRUCTIONS.example.md PROJECT_INSTRUCTIONS.md
cp CLAUDE.example.md CLAUDE.md

# Report issues or request features
# Visit: https://github.com/bjeans/homelab-mcp/issues
```

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

---

**Remember:** This project manages critical infrastructure. Security and reliability are paramount. Always test thoroughly and never commit sensitive data.
