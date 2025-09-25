"""News Fetcher MCP Server - Main entry point."""

import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server.fastmcp import FastMCP
from news_fetcher import __version__
from news_fetcher.config import Config
from news_fetcher.tools import (
    search_feeds,
    fetch_article,
    rank_articles,
    summarize_collection,
    build_epub,
    publish_opds,
)
from news_fetcher.opds_server import create_opds_app

# Initialize FastMCP server
mcp = FastMCP("news-fetcher")

# Load configuration
config = Config()

# Register MCP tools
@mcp.tool()
def news_search_feeds(
    topic: Optional[str] = None,
    sources: Optional[List[str]] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Search and fetch RSS/Atom feeds based on topic or specific sources.
    
    Args:
        topic: Topic to search for (optional)
        sources: List of RSS/Atom feed URLs (optional)
        limit: Maximum number of articles to return (default: 10)
    
    Returns:
        Dict containing articles with metadata
    """
    return search_feeds(topic=topic, sources=sources, limit=limit, config=config)


@mcp.tool()
def news_fetch_article(url: str) -> Dict[str, Any]:
    """
    Fetch and extract full text content from a news article URL.
    Uses Trafilatura first, falls back to Readability if needed.
    
    Args:
        url: URL of the article to fetch
    
    Returns:
        Dict containing extracted article content and metadata
    """
    return fetch_article(url=url, config=config)


@mcp.tool()
def news_rank(items: List[Dict[str, Any]], topic: str) -> List[Dict[str, Any]]:
    """
    Rank articles by relevance to topic using heuristics and LLM reranking.
    
    Args:
        items: List of article dictionaries
        topic: Topic to rank articles against
    
    Returns:
        List of top-ranked articles (Top 5)
    """
    return rank_articles(items=items, topic=topic, config=config)


@mcp.tool()
def news_summarize(collection: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a front-page TL;DR summary of a collection of articles.
    
    Args:
        collection: List of article dictionaries
    
    Returns:
        Dict containing summary with bullets and key information
    """
    return summarize_collection(collection=collection, config=config)


@mcp.tool()
def news_build_epub(
    articles: List[Dict[str, Any]], 
    title: str,
    filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build an EPUB file from a collection of articles.
    
    Args:
        articles: List of article dictionaries
        title: Title for the EPUB
        filename: Optional filename (auto-generated if not provided)
    
    Returns:
        Dict containing EPUB file path and metadata
    """
    return build_epub(articles=articles, title=title, filename=filename, config=config)


@mcp.tool()
def news_publish_opds(file_path: str) -> Dict[str, Any]:
    """
    Publish EPUB file via OPDS catalog for KOReader access.
    
    Args:
        file_path: Path to the EPUB file to publish
    
    Returns:
        Dict containing OPDS URL and publication details
    """
    return publish_opds(file_path=file_path, config=config)


@mcp.tool()
def news_get_preferences() -> Dict[str, Any]:
    """
    Get current user preferences and configuration.
    
    Returns:
        Dict containing user preferences, sources, and interests
    """
    return config.get_preferences()


@mcp.tool()
def news_update_preferences(preferences: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user preferences and configuration.
    
    Args:
        preferences: Dictionary of preferences to update
    
    Returns:
        Dict containing updated preferences
    """
    return config.update_preferences(preferences)


async def start_opds_server():
    """Start the OPDS server in the background."""
    import uvicorn
    from news_fetcher.opds_server import create_opds_app
    
    app = create_opds_app(config)
    server_config = uvicorn.Config(
        app, 
        host="0.0.0.0", 
        port=config.opds_port,
        log_level="info"
    )
    server = uvicorn.Server(server_config)
    await server.serve()


def main():
    """Main entry point for the MCP server."""
    print(f"Starting News Fetcher MCP Server v{__version__}")
    print(f"Configuration loaded from: {config.config_dir}")
    print(f"OPDS server will be available at: http://localhost:{config.opds_port}/opds")
    
    # Start OPDS server in background
    asyncio.create_task(start_opds_server())
    
    # Run MCP server
    mcp.run()


if __name__ == "__main__":
    main()