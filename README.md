# News Fetcher MCP Server

A comprehensive Model Context Protocol (MCP) server for fetching, processing, and serving news content with EPUB generation and OPDS support for KOReader.

## Features

- **RSS/Atom Feed Processing**: Intelligent feed parsing with support for multiple sources
- **Full-Text Extraction**: Uses Trafilatura (primary) and Readability (fallback) for clean article extraction
- **LLM-Powered Ranking**: Smart article ranking and summarization using configurable LLM providers
- **EPUB Generation**: Convert article collections to EPUB format using EbookLib
- **OPDS Catalog**: Serve EPUBs via OPDS for wireless access from KOReader and other compatible readers
- **Configurable Preferences**: Manage interests, sources, credentials, and filtering preferences
- **Caching System**: Intelligent caching to reduce API calls and improve performance
- **Multiple LLM Support**: OpenAI, Anthropic, and local LLM support (Ollama, LocalAI)

## Architecture

```
news_fetcher/
├── src/news_fetcher/
│   ├── __init__.py          # Package metadata
│   ├── main.py              # MCP server and main entry point
│   ├── config.py            # Configuration management
│   ├── tools.py             # MCP tool implementations
│   ├── llm_client.py        # LLM integration for ranking/summarization
│   ├── opds_server.py       # OPDS server for KOReader
│   └── utils.py             # Utility functions
├── data/
│   ├── config/              # Configuration files
│   │   ├── preferences.json # User preferences and interests
│   │   ├── sources.json     # RSS/Atom feed sources
│   │   └── credentials.json # API keys and credentials
│   ├── cache/               # Cached feed and article data
│   └── epubs/               # Generated EPUB files
├── static/                  # Static files for OPDS server
├── main.py                  # Entry point
├── pyproject.toml           # Project configuration
└── README.md               # This file
```

## Installation

1. Clone or set up the repository:

```bash
cd /path/to/news_fetcher
```

2. Install dependencies using uv:

```bash
uv install
```

3. Configure your preferences and credentials:
   - Edit `data/config/preferences.json` for your interests and preferences
   - Edit `data/config/sources.json` to add/modify RSS sources
   - Edit `data/config/credentials.json` to add API keys for LLM providers

## MCP Tools

The server provides the following MCP tools:

### Core Tools

1. **`news_search_feeds`**

   - Search and fetch RSS/Atom feeds
   - Parameters: `topic` (optional), `sources` (optional), `limit` (default: 10)
   - Returns: Articles with metadata

2. **`news_fetch_article`**

   - Extract full text from article URL
   - Parameters: `url` (required)
   - Returns: Extracted article content and metadata

3. **`news_rank`**

   - Rank articles by topic relevance using heuristics + LLM
   - Parameters: `items` (article list), `topic` (string)
   - Returns: Top 5 ranked articles

4. **`news_summarize`**

   - Generate front-page TL;DR summary
   - Parameters: `collection` (article list)
   - Returns: Summary with bullets and key information

5. **`news_build_epub`**

   - Create EPUB from article collection
   - Parameters: `articles` (list), `title` (string), `filename` (optional)
   - Returns: EPUB file path and metadata

6. **`news_publish_opds`**
   - Publish EPUB via OPDS catalog
   - Parameters: `file_path` (string)
   - Returns: OPDS URLs and instructions

### Configuration Tools

7. **`news_get_preferences`**

   - Get current user preferences
   - Returns: Current configuration

8. **`news_update_preferences`**
   - Update user preferences
   - Parameters: `preferences` (dict)
   - Returns: Updated preferences

## Configuration

### User Preferences (`data/config/preferences.json`)

```json
{
  "interests": ["technology", "science", "world news"],
  "sources": [],
  "language": "en",
  "max_articles_per_feed": 20,
  "enable_full_text": true,
  "preferred_formats": ["epub", "html"],
  "exclude_domains": ["example.com"],
  "keywords_boost": ["AI", "technology", "innovation"],
  "keywords_filter": ["spam", "advertisement"]
}
```

### LLM Configuration (`data/config/credentials.json`)

```json
{
  "llm": {
    "provider": "openai",
    "api_key": "your-api-key-here",
    "model": "gpt-3.5-turbo",
    "base_url": null,
    "max_tokens": 1000,
    "temperature": 0.7
  }
}
```

Supported LLM providers:

- **OpenAI**: Set `provider` to `"openai"`, add your API key
- **Anthropic**: Set `provider` to `"anthropic"`, add your API key
- **Local LLM**: Set `provider` to `"local"`, set `base_url` to your local server (e.g., `"http://localhost:11434"` for Ollama)

## Usage

### Running the MCP Server

```bash
# Using uv
uv run python main.py

# Or directly
python main.py
```

The server will:

1. Start the MCP server with all tools registered
2. Launch the OPDS server on port 8000 (configurable)
3. Load configuration from `data/config/`

### Using with KOReader

1. Ensure the OPDS server is running
2. In KOReader, go to "File manager" → "Add OPDS catalog"
3. Add the catalog URL: `http://localhost:8000/opds`
4. Browse and download EPUBs wirelessly

### Example Workflow

1. **Search for articles**:

   ```python
   # Via MCP tool
   result = news_search_feeds(topic="artificial intelligence", limit=20)
   ```

2. **Rank articles by relevance**:

   ```python
   top_articles = news_rank(result["articles"], "machine learning developments")
   ```

3. **Generate summary**:

   ```python
   summary = news_summarize(top_articles)
   ```

4. **Create EPUB**:

   ```python
   epub_result = news_build_epub(
       articles=top_articles,
       title="AI News Digest - Today"
   )
   ```

5. **Publish via OPDS**:
   ```python
   opds_result = news_publish_opds(epub_result["epub_path"])
   ```

## RSS Sources

The server comes with curated RSS sources for various topics. You can:

- Add sources via `data/config/sources.json`
- Use the MCP tools to add sources programmatically
- Organize sources by topic/category

### Default Categories

- **Technology**: TechCrunch, Ars Technica, Wired, The Verge
- **Science**: Nature, Science Magazine, New Scientist
- **AI**: AI News, Artificial Intelligence News
- **Business**: Bloomberg, WSJ, Fortune
- **General**: CNN, BBC, Reuters, NPR

## Development

### Adding New Tools

1. Implement the tool function in `src/news_fetcher/tools.py`
2. Register it in `src/news_fetcher/main.py` using `@mcp.tool()`
3. Add any required utility functions to `src/news_fetcher/utils.py`

### Testing

```bash
# Run tests (when implemented)
uv run pytest

# Code formatting
uv run black src/
uv run isort src/

# Type checking
uv run mypy src/
```

## Troubleshooting

### Common Issues

1. **LLM not working**: Check your API keys in `data/config/credentials.json`
2. **Feeds not loading**: Verify RSS URLs in `data/config/sources.json`
3. **OPDS not accessible**: Check if port 8000 is available and firewall settings
4. **EPUB generation fails**: Check write permissions in `data/epubs/`

### Logs and Debugging

The server prints verbose logs to help with debugging:

- Feed fetching progress
- Article extraction methods used
- LLM API calls and responses
- EPUB generation steps
- OPDS server status

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is open source. See LICENSE file for details.

## Dependencies

Key dependencies:

- **MCP**: Model Context Protocol framework
- **feedparser**: RSS/Atom feed parsing
- **trafilatura**: Web content extraction
- **readability-lxml**: Fallback content extraction
- **ebooklib**: EPUB generation
- **fastapi**: OPDS server
- **requests**: HTTP client
- **beautifulsoup4**: HTML parsing
- **pydantic**: Data validation
