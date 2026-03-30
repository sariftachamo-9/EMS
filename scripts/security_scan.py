import os
import subprocess
import sys

def run_pip_audit():
    print("--- Security Audit: Dependency Vulnerability Scan ---")
    try:
        # Check if pip-audit is installed
        subprocess.run(["pip-audit", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Error: pip-audit is not installed. Run 'pip install pip-audit' first.")
        return

    try:
        # Run pip-audit on the current environment
        result = subprocess.run(["pip-audit"], capture_output=True, text=True)
        if result.returncode == 0:
            print("SUCCESS: No known vulnerabilities found in dependencies.")
        else:
            print("WARNING: Vulnerabilities found!")
            print(result.stdout)
            print(result.stderr)
    except Exception as e:
        print(f"Error running pip-audit: {e}")

if __name__ == "__main__":
    run_pip_audit()
