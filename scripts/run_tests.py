#!/usr/bin/env python3
"""
Test runner script for HoneyGrid.
Runs all tests and generates coverage reports.
"""

import sys
import subprocess

from utils.env_loader import load_env

# Load environment variables from .env if available
load_env()


def run_tests(test_paths=None, coverage=True, verbose=True, html=True):
    """
    Run pytest with optional coverage.

    Args:
        test_paths: List of test paths or single path (default: all tests)
        coverage: Enable coverage reporting
        verbose: Enable verbose output
        html: Generate HTML coverage report
    """
    cmd = [sys.executable, "-m", "pytest"]

    # Add test paths
    if test_paths:
        if isinstance(test_paths, str):
            test_paths = [test_paths]
        cmd.extend(test_paths)
    else:
        cmd.append("tests/")

    # Add verbosity
    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add coverage
    if coverage:
        cmd.extend(["--cov=agent", "--cov=server", "--cov=gui_tk", "--cov-report=term"])

        if html:
            cmd.append("--cov-report=html:coverage_html")

    # Run tests
    print(f"Running: {' '.join(cmd)}")
    print()
    result = subprocess.run(cmd)

    return result.returncode


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run HoneyGrid tests with coverage reporting"
    )
    parser.add_argument(
        "paths", nargs="*", default=None, help="Test paths (default: all tests)"
    )
    parser.add_argument(
        "--no-coverage", action="store_true", help="Disable coverage reporting"
    )
    parser.add_argument(
        "--no-html", action="store_true", help="Disable HTML coverage report"
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Quiet output (less verbose)"
    )
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument(
        "--integration", action="store_true", help="Run only integration tests"
    )

    args = parser.parse_args()

    # Check if pytest is available
    try:
        subprocess.run(
            [sys.executable, "-m", "pytest", "--version"],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        print("ERROR: pytest is not installed!")
        print("Install with: pip install pytest pytest-cov")
        return 1

    # Determine test paths
    test_paths = args.paths if args.paths else None

    if args.unit:
        test_paths = ["tests/unit/"]
    elif args.integration:
        test_paths = ["tests/integration/"]

    # Run tests
    print("=" * 70)
    if test_paths:
        print(f"Running tests: {', '.join(test_paths)}")
    else:
        print("Running all tests...")
    print("=" * 70)
    print()

    exit_code = run_tests(
        test_paths=test_paths,
        coverage=not args.no_coverage,
        verbose=not args.quiet,
        html=not args.no_html,
    )

    print()
    if exit_code == 0:
        print("=" * 70)
        print("✓ All tests passed!")
        print("=" * 70)
        if not args.no_coverage and not args.no_html:
            print("\nCoverage HTML report: coverage_html/index.html")
    else:
        print("=" * 70)
        print("✗ Some tests failed!")
        print("=" * 70)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
