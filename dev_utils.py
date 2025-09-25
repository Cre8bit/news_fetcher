#!/usr/bin/env python3
"""
Development utilities for News Fetcher MCP Server
"""

import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from news_fetcher.config import Config


def add_source(category: str, url: str):
    """Add a new RSS source."""
    config = Config()
    config.add_source(category, url)
    print(f"Added {url} to {category} category")


def list_sources():
    """List all configured sources."""
    config = Config()
    print("Configured RSS Sources:")
    print("=" * 30)
    
    for category, urls in config.sources.items():
        print(f"\n{category.upper()}:")
        for url in urls:
            print(f"  - {url}")


def update_llm_config(provider: str, api_key: str, model: str = None):
    """Update LLM configuration."""
    config = Config()
    
    llm_config = {
        "provider": provider,
        "api_key": api_key
    }
    
    if model:
        llm_config["model"] = model
    
    config.update_credentials("llm", llm_config)
    print(f"Updated LLM configuration for {provider}")


def clear_cache():
    """Clear all cached data."""
    config = Config()
    
    # Clear cache files
    cache_files = list(config.cache_dir.glob("*.json"))
    for cache_file in cache_files:
        cache_file.unlink()
    
    print(f"Cleared {len(cache_files)} cache files")


def list_epubs():
    """List all generated EPUBs."""
    config = Config()
    
    epub_files = list(config.epubs_dir.glob("*.epub"))
    
    if not epub_files:
        print("No EPUB files found")
        return
    
    print("Generated EPUB files:")
    print("=" * 25)
    
    for epub_file in sorted(epub_files, key=lambda x: x.stat().st_mtime, reverse=True):
        size = epub_file.stat().st_size
        mtime = epub_file.stat().st_mtime
        
        from datetime import datetime
        date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        
        print(f"  {epub_file.name}")
        print(f"    Size: {size:,} bytes")
        print(f"    Modified: {date_str}")
        print()


def export_config():
    """Export current configuration to JSON."""
    config = Config()
    
    export_data = {
        "preferences": config.get_preferences(),
        "sources": config.sources,
        "version": "1.0"
    }
    
    export_file = Path("config_export.json")
    with open(export_file, 'w') as f:
        json.dump(export_data, f, indent=2)
    
    print(f"Configuration exported to {export_file}")


def import_config(config_file: str):
    """Import configuration from JSON file."""
    config_path = Path(config_file)
    
    if not config_path.exists():
        print(f"Configuration file not found: {config_file}")
        return
    
    with open(config_path, 'r') as f:
        import_data = json.load(f)
    
    config = Config()
    
    # Update preferences
    if "preferences" in import_data:
        config.update_preferences(import_data["preferences"])
        print("✓ Preferences updated")
    
    # Update sources
    if "sources" in import_data:
        config.sources = import_data["sources"]
        config._save_sources()
        print("✓ Sources updated")
    
    print(f"Configuration imported from {config_file}")


def show_help():
    """Show available commands."""
    print("News Fetcher MCP Server - Development Utilities")
    print("=" * 50)
    print()
    print("Available commands:")
    print("  list-sources           List all RSS sources")
    print("  add-source <cat> <url> Add RSS source to category")
    print("  update-llm <prov> <key> [model] Update LLM config")
    print("  clear-cache            Clear all cached data")
    print("  list-epubs             List generated EPUB files")
    print("  export-config          Export config to JSON")
    print("  import-config <file>   Import config from JSON")
    print("  help                   Show this help")
    print()
    print("Examples:")
    print("  python dev_utils.py list-sources")
    print("  python dev_utils.py add-source tech https://example.com/feed.xml")
    print("  python dev_utils.py update-llm openai sk-your-key-here gpt-4")
    print("  python dev_utils.py clear-cache")


def main():
    """Main CLI interface."""
    if len(sys.argv) < 2:
        show_help()
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "help":
            show_help()
        elif command == "list-sources":
            list_sources()
        elif command == "add-source":
            if len(sys.argv) < 4:
                print("Usage: add-source <category> <url>")
                return
            add_source(sys.argv[2], sys.argv[3])
        elif command == "update-llm":
            if len(sys.argv) < 4:
                print("Usage: update-llm <provider> <api_key> [model]")
                return
            model = sys.argv[4] if len(sys.argv) > 4 else None
            update_llm_config(sys.argv[2], sys.argv[3], model)
        elif command == "clear-cache":
            clear_cache()
        elif command == "list-epubs":
            list_epubs()
        elif command == "export-config":
            export_config()
        elif command == "import-config":
            if len(sys.argv) < 3:
                print("Usage: import-config <file>")
                return
            import_config(sys.argv[2])
        else:
            print(f"Unknown command: {command}")
            show_help()
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()