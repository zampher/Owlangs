"""
Entry point for `python -m backend.app`.

Delegates to the existing CLI launcher so that both commands behave
consistently (path setup, Redis handling, etc.).
"""

from backend.cli import main


def run():
    """Alias for CLI main."""
    main()


if __name__ == "__main__":
    run()

