#!/usr/bin/env python3
"""
Test runner script for HoneyGrid.
Runs all tests and generates coverage reports.
"""

import sys
import subprocess
from pathlib import Path


def run_tests(test_path="tests/unit", coverage=True, verbose=True):
    """Run pytest with optional coverage."""
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add test path
    cmd.append(test_path)
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    
    # Add coverage
    if coverage:
        cmd.extend([
            "--cov=server",
            "--cov=agent",
            "--cov-report=term-missing",
            "--cov-report=html:coverage_html"
        ])
    
    # Run tests
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    return result.returncode


def main():
    """Main entry point."""
    # Check if pytest is available
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            check=True
        )
    except subprocess.CalledProcessError:
        print("ERROR: pytest is not installed!")
        print("Install with: pip install pytest pytest-cov")
        return 1
    
    # Run unit tests
    print("=" * 70)
    print("Running unit tests...")
    print("=" * 70)
    exit_code = run_tests("tests/unit", coverage=True)
    
    if exit_code == 0:
        print("\n" + "=" * 70)
        print("✓ All tests passed!")
        print("=" * 70)
        print("\nCoverage HTML report generated at: coverage_html/index.html")
    else:
        print("\n" + "=" * 70)
        print("✗ Some tests failed!")
        print("=" * 70)
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
