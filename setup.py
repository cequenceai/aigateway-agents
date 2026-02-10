#!/usr/bin/env python3
"""
Unified Setup Script

Installs all dependencies for the project.
Run this once during initial setup.
"""

import subprocess
import sys
from pathlib import Path


def print_header(text):
    """Print formatted header."""
    print(f"\n{'='*60}")
    print(f"{text}")
    print(f"{'='*60}\n")


def run_command(cmd, description, check=True):
    """Run a command and handle errors."""
    print(f"→ {description}...")
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=check,
            capture_output=True,
            text=True
        )
        if result.stdout:
            print(result.stdout)
        if result.stderr and result.returncode != 0:
            print(f"⚠️  {result.stderr}")
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        return False


def install_from_requirements(requirements_path, project_name):
    """Install from a requirements.txt file."""
    req_path = Path(requirements_path)
    if not req_path.exists():
        print(f"⚠️  requirements.txt not found for {project_name}")
        return False
    
    cmd = f"{sys.executable} -m pip install -r \"{req_path}\""
    return run_command(cmd, f"Installing {project_name} dependencies")


def verify_imports():
    """Verify that key packages can be imported."""
    print_header("Verifying Installations")
    
    packages = {
        "langchain": "langchain",
        "langgraph": "langgraph",
        "langchain_mcp_adapters": "langchain-mcp-adapters",
        "langchain_anthropic": "langchain-anthropic",
        "langchain_openai": "langchain-openai",
        "anthropic": "anthropic",
        "cryptography": "cryptography",
        "rich": "rich",
        "mcp": "mcp",
    }
    
    results = []
    for module_name, package_name in packages.items():
        try:
            __import__(module_name)
            print(f"✓ {package_name}")
            results.append(True)
        except ImportError:
            print(f"✗ {package_name} - NOT INSTALLED")
            results.append(False)
    
    return all(results)


def main():
    """Main setup function."""
    print_header("Project Setup - Installing Dependencies")
    
    base_dir = Path(__file__).parent
    
    # Install MCP_AGENT dependencies
    mcp_requirements = base_dir / "MCP_AGENT" / "mcp_agent" / "requirements.txt"
    install_from_requirements(mcp_requirements, "MCP_AGENT")
    
    # Install ANTHROPIC_AGENT dependencies
    anthropic_requirements = base_dir / "ANTHROPIC_AGENT" / "requirements.txt"
    install_from_requirements(anthropic_requirements, "ANTHROPIC_AGENT")
    
    # Install core packages individually to ensure everything is there
    print_header("Installing Core Packages")
    
    packages = [
        "langchain>=0.3.0",
        "langgraph>=0.2.0",
        "langchain-mcp-adapters==0.2.1",
        "langchain-anthropic>=0.2.0",
        "langchain-openai>=0.2.0",
        "langchain-core==1.2.6",
        "httpx>=0.27.0",
        "rich>=13.0.0",
        "mcp>=1.0.0",
        "anthropic>=0.34.0",
        "cryptography>=42.0.0",
    ]
    
    for package in packages:
        cmd = f"{sys.executable} -m pip install '{package}'"
        run_command(cmd, f"Installing {package}", check=False)
    
    # Verify
    all_ok = verify_imports()
    
    print_header("Setup Complete!" if all_ok else "Setup Complete (with warnings)")
    
    if not all_ok:
        print("\n⚠️  Some packages may not be installed correctly.")
        print("   Check the output above for details.\n")
    else:
        print("\n✓ All dependencies installed successfully!\n")


if __name__ == "__main__":
    main()
