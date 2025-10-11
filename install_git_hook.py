#!/usr/bin/env python3
"""
Install Git Pre-Push Hook
Automatically runs security checks before every git push

Usage:
  python install_git_hook.py

To bypass security checks on a specific push:
  git push --no-verify

To uninstall:
  Remove .git/hooks/pre-push file
"""

import os
import shutil
import sys
from pathlib import Path


def main():
    """Install the pre-push git hook"""
    
    # Find git directory
    git_dir = Path(".git")
    if not git_dir.exists():
        print("❌ Error: Not a git repository")
        print("   Run this script from the repository root")
        sys.exit(1)
    
    # Verify pre_publish_check.py exists
    check_script = Path("pre_publish_check.py")
    if not check_script.exists():
        print("❌ Error: pre_publish_check.py not found")
        print("   Make sure you're in the correct directory")
        sys.exit(1)
    
    # Create hooks directory if it doesn't exist
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    
    # Path to the hook file
    hook_file = hooks_dir / "pre-push"
    
    # Check if hook already exists
    if hook_file.exists():
        print("⚠️  Pre-push hook already exists!")
        response = input("   Overwrite? (y/N): ").strip().lower()
        if response != 'y':
            print("   Cancelled.")
            sys.exit(0)
        print()
    
    # Hook script content
    hook_content = '''#!/usr/bin/env python3
"""
Git pre-push hook - Runs security checks before allowing push
Installed by install_git_hook.py
"""

import sys
import subprocess
import os
from pathlib import Path

def main():
    """Run pre-publish check before push"""
    # Get the repository root (two levels up from .git/hooks/)
    hook_dir = Path(__file__).parent
    git_dir = hook_dir.parent
    repo_root = git_dir.parent
    
    check_script = repo_root / "pre_publish_check.py"
    
    if not check_script.exists():
        print(f"Warning: pre_publish_check.py not found at {check_script}")
        print("Skipping security check")
        print("Run: python install_git_hook.py to reinstall")
        sys.exit(0)
    
    print("🔒 Running security checks before push...")
    print("=" * 70)
    
    try:
        result = subprocess.run(
            [sys.executable, str(check_script)],
            cwd=str(repo_root),
            capture_output=False,
            text=True
        )
        
        if result.returncode != 0:
            print("\\n" + "=" * 70)
            print("❌ Security checks FAILED!")
            print("=" * 70)
            print("\\nYour push has been blocked to protect sensitive data.")
            print("\\nOptions:")
            print("  1. Fix the issues reported above")
            print("  2. Force push (NOT recommended): git push --no-verify")
            print("\\n⚠️  Only use --no-verify if you're absolutely sure it's safe!")
            sys.exit(1)
        else:
            print("\\n" + "=" * 70)
            print("✅ All security checks passed!")
            print("=" * 70)
            print("\\nProceeding with push...")
            sys.exit(0)
            
    except Exception as e:
        print(f"\\n⚠️  Error running security check: {e}")
        print("Push blocked as a precaution.")
        print("Use --no-verify to bypass (not recommended)")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
    
    # Write the hook file
    with open(hook_file, 'w', encoding='utf-8', newline='\n') as f:
        f.write(hook_content)
    
    # Make it executable (Unix/Mac only)
    if os.name != 'nt':
        os.chmod(hook_file, 0o755)
        print("✅ Hook installed and made executable")
    else:
        print("✅ Hook installed")
        print("   (On Windows, git will execute it with Python automatically)")
    
    print()
    print("=" * 70)
    print("🎉 Git pre-push hook installed successfully!")
    print("=" * 70)
    print()
    print("What this does:")
    print("  • Runs pre_publish_check.py before every git push")
    print("  • Blocks push if security issues are found")
    print("  • Protects against accidentally pushing sensitive data")
    print()
    print("To bypass on a specific push (use with caution):")
    print("  git push --no-verify")
    print()
    print("To uninstall:")
    print(f"  Remove: {hook_file}")
    print()
    print("Test it now:")
    print("  python pre_publish_check.py")
    print()

if __name__ == "__main__":
    main()
