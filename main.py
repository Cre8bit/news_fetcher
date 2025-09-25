"""Main entry point for News Fetcher MCP Server."""

import sys
from pathlib import Path

# Add src to path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from news_fetcher.main import main

if __name__ == "__main__":
    main()
