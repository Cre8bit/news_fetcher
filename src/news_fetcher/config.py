"""Configuration management for News Fetcher MCP Server."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict


@dataclass
class UserPreferences:
    """User preferences and settings."""
    interests: List[str]
    sources: List[str]
    language: str
    max_articles_per_feed: int
    enable_full_text: bool
    preferred_formats: List[str]
    exclude_domains: List[str]
    keywords_boost: List[str]
    keywords_filter: List[str]


@dataclass
class LLMConfig:
    """LLM configuration for ranking and summarization."""
    provider: str  # "openai", "anthropic", "local", etc.
    model: str
    api_key: Optional[str]
    base_url: Optional[str]
    max_tokens: int
    temperature: float


class Config:
    """Main configuration class for the News Fetcher MCP Server."""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent.parent.parent / "data" / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # File paths
        self.preferences_file = self.config_dir / "preferences.json"
        self.sources_file = self.config_dir / "sources.json"
        self.credentials_file = self.config_dir / "credentials.json"
        self.cache_dir = self.config_dir.parent / "cache"
        self.epubs_dir = self.config_dir.parent / "epubs"
        
        # Create directories
        self.cache_dir.mkdir(exist_ok=True)
        self.epubs_dir.mkdir(exist_ok=True)
        
        # Server settings
        self.opds_port = 8000
        self.cache_ttl = 3600  # 1 hour
        
        # Load configurations
        self._load_preferences()
        self._load_sources()
        self._load_credentials()
    
    def _load_preferences(self) -> None:
        """Load user preferences from file."""
        if self.preferences_file.exists():
            try:
                with open(self.preferences_file, 'r') as f:
                    data = json.load(f)
                    self.preferences = UserPreferences(**data)
            except (json.JSONDecodeError, TypeError) as e:
                print(f"Error loading preferences: {e}")
        else:
            raise FileNotFoundError(f"Preferences file not found: {self.preferences_file}")
        
    def _save_preferences(self) -> None:
        """Save user preferences to file."""
        with open(self.preferences_file, 'w') as f:
            json.dump(asdict(self.preferences), f, indent=2)
    
    def _load_sources(self) -> None:
        """Load RSS/Atom sources from file."""
        
        if self.sources_file.exists():
            try:
                with open(self.sources_file, 'r') as f:
                    self.sources = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error loading sources: {e}")
        else:
            raise FileNotFoundError(f"Sources file not found: {self.sources_file}")
        
    def _save_sources(self) -> None:
        """Save sources to file."""
        with open(self.sources_file, 'w') as f:
            json.dump(self.sources, f, indent=2)
    
    def _load_credentials(self) -> None:
        """Load credentials from file."""
        
        if self.credentials_file.exists():
            try:
                with open(self.credentials_file, 'r') as f:
                    self.credentials = json.load(f)
            except json.JSONDecodeError as e:
                print(f"Error loading credentials: {e}")
        else:
            raise FileNotFoundError(f"Credentials file not found: {self.credentials_file}")

    def _save_credentials(self) -> None:
        """Save credentials to file."""
        with open(self.credentials_file, 'w') as f:
            json.dump(self.credentials, f, indent=2)
    
    def get_preferences(self) -> Dict[str, Any]:
        """Get current user preferences."""
        return asdict(self.preferences)
    
    def update_preferences(self, new_preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Update user preferences."""
        # Update preferences
        for key, value in new_preferences.items():
            if hasattr(self.preferences, key):
                setattr(self.preferences, key, value)
        
        self._save_preferences()
        return self.get_preferences()
    
    def add_source(self, category: str, url: str) -> None:
        """Add a new RSS/Atom source."""
        if category not in self.sources:
            self.sources[category] = []
        
        if url not in self.sources[category]:
            self.sources[category].append(url)
            self._save_sources()
    
    def remove_source(self, category: str, url: str) -> None:
        """Remove an RSS/Atom source."""
        if category in self.sources and url in self.sources[category]:
            self.sources[category].remove(url)
            self._save_sources()
    
    def get_sources_for_topic(self, topic: str) -> List[str]:
        """Get RSS sources for a specific topic."""
        # Try exact match first
        if topic.lower() in self.sources:
            return self.sources[topic.lower()]
        
        # Try partial matches
        matches = []
        for category, urls in self.sources.items():
            if topic.lower() in category.lower() or category.lower() in topic.lower():
                matches.extend(urls)
        
        # If no matches, return general sources
        if not matches:
            return self.sources.get("general", [])
        
        return matches
    
    def get_llm_config(self) -> LLMConfig:
        """Get LLM configuration."""
        llm_creds = self.credentials.get("llm", {})
        return LLMConfig(
            provider=llm_creds.get("provider", "openai"),
            model=llm_creds.get("model", "gpt-3.5-turbo"),
            api_key=llm_creds.get("api_key"),
            base_url=llm_creds.get("base_url"),
            max_tokens=llm_creds.get("max_tokens", 1000),
            temperature=llm_creds.get("temperature", 0.7)
        )
    
    def update_credentials(self, provider: str, credentials: Dict[str, Any]) -> None:
        """Update credentials for a specific provider."""
        if provider not in self.credentials:
            self.credentials[provider] = {}
        
        self.credentials[provider].update(credentials)
        self._save_credentials()
    
    def get_cache_path(self, cache_key: str) -> Path:
        """Get cache file path for a given key."""
        return self.cache_dir / f"{cache_key}.json"
    
    def get_epub_path(self, filename: str) -> Path:
        """Get EPUB file path."""
        if not filename.endswith('.epub'):
            filename += '.epub'
        return self.epubs_dir / filename