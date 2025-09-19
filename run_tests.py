#!/usr/bin/env python3
"""
Test runner script for the swarm-autoscaler project
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running {description}:")
        print(f"Return code: {e.returncode}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for swarm-autoscaler")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--cadvisor", action="store_true", help="Run cAdvisor tests only")
    parser.add_argument("--docker", action="store_true", help="Run Docker tests only")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--install", action="store_true", help="Install test dependencies first")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    # Change to project root
    project_root = Path(__file__).parent
    import os
    os.chdir(project_root)
    
    # Install dependencies if requested
    if args.install:
        print("Installing test dependencies...")
        if not run_command([sys.executable, "-m", "pip", "install", "-r", "tests/requirements.txt"], 
                          "Installing test dependencies"):
            return 1
    
    # Build test command
    cmd = [sys.executable, "-m", "pytest"]
    
    if args.verbose:
        cmd.append("-v")
    
    # Add markers based on arguments
    markers = []
    if args.unit:
        markers.append("unit")
    if args.integration:
        markers.append("integration")
    if args.cadvisor:
        markers.append("cadvisor")
    if args.docker:
        markers.append("docker")
    
    if markers:
        cmd.extend(["-m", " or ".join(markers)])
    elif not args.all:
        # Default to unit tests only
        cmd.extend(["-m", "unit"])
    
    # Add test directory
    cmd.append("tests/")
    
    # Run tests
    success = run_command(cmd, "Running tests")
    
    if success:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
