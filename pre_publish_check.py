#!/usr/bin/env python3
"""
Pre-Publication Security Checklist
Run this script before pushing to GitHub to verify no sensitive data is included
"""

import os
import re
import sys
from pathlib import Path

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_header(text):
    print(f"\n{BOLD}{'='*70}{RESET}")
    print(f"{BOLD}{text}{RESET}")
    print(f"{BOLD}{'='*70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✓{RESET} {text}")

def print_error(text):
    print(f"{RED}✗{RESET} {text}")

def print_warning(text):
    print(f"{YELLOW}⚠{RESET} {text}")

def check_file_exists(filepath):
    """Check if a file exists"""
    return Path(filepath).exists()

def check_file_in_gitignore(filename, gitignore_content):
    """Check if a filename is in gitignore"""
    return filename in gitignore_content

def scan_for_ips(content, filename):
    """Scan content for private IP addresses"""
    # Pattern for private IP addresses
    ip_pattern = r'\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3})\b'
    matches = re.findall(ip_pattern, content)
    
    # Filter out example IPs
    real_ips = [ip for ip in matches if not ip.startswith('192.168.1.') and not ip.startswith('10.0.1.')]
    return real_ips

def scan_for_api_keys(content, filename):
    """Scan content for potential API keys"""
    # Common patterns for API keys
    patterns = [
        r'api[_-]?key["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{20,})["\']',
        r'token["\']?\s*[:=]\s*["\']([a-zA-Z0-9]{20,})["\']',
        r'password["\']?\s*[:=]\s*["\']([^"\']{8,})["\']',
    ]
    
    found_keys = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        found_keys.extend(matches)
    
    return found_keys

def check_sensitive_files():
    """Check for sensitive files that shouldn't be committed"""
    print_header("Checking for Sensitive Files")
    
    script_dir = Path(__file__).parent
    issues = []
    
    # Read .gitignore
    gitignore_path = script_dir / '.gitignore'
    if gitignore_path.exists():
        with open(gitignore_path, 'r') as f:
            gitignore_content = f.read()
    else:
        print_error(".gitignore not found!")
        return False
    
    # Files that MUST be in .gitignore
    required_ignored = [
        '.env',
        'PROJECT_INSTRUCTIONS.md',
        'ansible_hosts.yml'
    ]
    
    for filename in required_ignored:
        if check_file_in_gitignore(filename, gitignore_content):
            print_success(f"{filename} is in .gitignore")
        else:
            print_error(f"{filename} is NOT in .gitignore!")
            issues.append(f"{filename} must be added to .gitignore")
    
    # Files that should exist but not be committed
    sensitive_files = [
        ('.env', '.env should exist but not be committed'),
        ('PROJECT_INSTRUCTIONS.md', 'Your customized instructions (not the .example)'),
        ('ansible_hosts.yml', 'Your real inventory (not the .example)')
    ]
    
    print()
    for filename, description in sensitive_files:
        filepath = script_dir / filename
        if filepath.exists():
            print_warning(f"{filename} exists - {description}")
            if not check_file_in_gitignore(filename, gitignore_content):
                issues.append(f"{filename} exists but is not in .gitignore!")
        else:
            print_success(f"{filename} does not exist (good for public repo)")
    
    # Example files that SHOULD exist
    print()
    example_files = [
        '.env.example',
        'PROJECT_INSTRUCTIONS.example.md',
        'ansible_hosts.example.yml'
    ]
    
    for filename in example_files:
        if check_file_exists(script_dir / filename):
            print_success(f"{filename} exists")
        else:
            print_error(f"{filename} is missing!")
            issues.append(f"{filename} should be included as template")
    
    return len(issues) == 0

def check_documentation_files():
    """Check that documentation files exist"""
    print_header("Checking Documentation Files")
    
    script_dir = Path(__file__).parent
    issues = []
    
    required_docs = {
        'README.md': 'Main documentation',
        'SECURITY.md': 'Security guidelines',
        '.env.example': 'Environment variables template',
        'requirements.txt': 'Python dependencies',
        'PROJECT_INSTRUCTIONS.example.md': 'Claude instructions template',
        'ansible_hosts.example.yml': 'Ansible inventory template'
    }
    
    for filename, description in required_docs.items():
        filepath = script_dir / filename
        if filepath.exists():
            print_success(f"{filename} - {description}")
        else:
            print_error(f"{filename} is MISSING - {description}")
            issues.append(f"Missing {filename}")
    
    return len(issues) == 0

def scan_python_files():
    """Scan Python files for potential issues"""
    print_header("Scanning Python Files for Sensitive Data")
    
    script_dir = Path(__file__).parent
    issues = []
    
    python_files = list(script_dir.glob('*.py'))
    
    for py_file in python_files:
        if py_file.name == 'pre_publish_check.py':
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for hardcoded IPs (in non-example contexts)
            ips = scan_for_ips(content, py_file.name)
            if ips:
                print_warning(f"{py_file.name}: Found IP addresses - {', '.join(ips)}")
                print_warning("  → Verify these are example IPs only")
            
            # Check for potential API keys (basic check)
            keys = scan_for_api_keys(content, py_file.name)
            if keys:
                print_error(f"{py_file.name}: Potential API keys found!")
                issues.append(f"{py_file.name} may contain hardcoded credentials")
            
            # Check for common mistakes
            if 'your-api-key' not in content.lower() and 'api' in content.lower():
                if 'getenv' not in content and 'os.environ' not in content:
                    print_warning(f"{py_file.name}: Check that API keys use environment variables")
            
        except Exception as e:
            print_error(f"Error scanning {py_file.name}: {e}")
    
    if not issues:
        print_success("No obvious sensitive data found in Python files")
    
    return len(issues) == 0

def scan_markdown_files():
    """Scan markdown files for real infrastructure details"""
    print_header("Scanning Markdown Files for Infrastructure Details")
    
    script_dir = Path(__file__).parent
    issues = []
    
    # Files to check (excluding the customized versions)
    md_files = [
        'README.md',
        'SECURITY.md',
        'PROJECT_INSTRUCTIONS.example.md',
        'ansible_hosts.example.yml'
    ]
    
    for filename in md_files:
        filepath = script_dir / filename
        if not filepath.exists():
            continue
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for private IPs that aren't examples
            ips = scan_for_ips(content, filename)
            suspicious_ips = [ip for ip in ips if not (
                ip.startswith('192.168.1.') or 
                ip.startswith('10.0.1.') or
                ip.startswith('172.16.')
            )]
            
            if suspicious_ips:
                print_error(f"{filename}: Found non-example IPs: {', '.join(suspicious_ips)}")
                issues.append(f"{filename} contains real IP addresses")
            else:
                print_success(f"{filename}: No real IP addresses found")
            
            # Check for common domain patterns
            if '.local' in content or 'home.' in content:
                # Count occurrences
                local_count = content.count('.local')
                home_count = content.count('home.')
                if filename == 'README.md' and (local_count > 3 or home_count > 0):
                    print_warning(f"{filename}: Contains .local or home. domains ({local_count + home_count} times)")
                    print_warning("  → Verify these are examples, not your real domains")
            
        except Exception as e:
            print_error(f"Error scanning {filename}: {e}")
    
    return len(issues) == 0

def final_reminders():
    """Print final reminders"""
    print_header("Final Pre-Publication Checklist")
    
    reminders = [
        "Review git history for accidentally committed secrets",
        "Ensure .env is NOT in git history (git rm --cached .env if needed)",
        "Test with a fresh clone in a new directory",
        "Verify .gitignore is working (git status should not show sensitive files)",
        "Double-check that PROJECT_INSTRUCTIONS.md is gitignored",
        "Review all commits for sensitive data before pushing",
        "Consider using 'git secrets' or similar tools",
        "Update GitHub repository description and tags",
        "Add topics/tags to GitHub repo for discoverability",
        "Consider adding LICENSE file if not present"
    ]
    
    for i, reminder in enumerate(reminders, 1):
        print(f"  {i}. {reminder}")
    
    print()

def main():
    """Run all checks"""
    print(f"{BOLD}Homelab MCP - Pre-Publication Security Check{RESET}")
    print(f"{BOLD}{'='*70}{RESET}")
    
    script_dir = Path(__file__).parent
    print(f"Checking directory: {script_dir}\n")
    
    all_passed = True
    
    # Run checks
    if not check_sensitive_files():
        all_passed = False
    
    if not check_documentation_files():
        all_passed = False
    
    if not scan_python_files():
        all_passed = False
    
    if not scan_markdown_files():
        all_passed = False
    
    # Final summary
    print_header("Summary")
    
    if all_passed:
        print_success("All checks passed! ✨")
        print_success("Review the warnings above and the final checklist before publishing.")
    else:
        print_error("Some checks FAILED! ⚠️")
        print_error("Fix the issues above before publishing to GitHub.")
    
    final_reminders()
    
    # Exit code
    sys.exit(0 if all_passed else 1)

if __name__ == '__main__':
    main()
