"""Utility functions for the News Fetcher MCP Server."""

import re
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List
from urllib.parse import urlparse, urljoin
import unicodedata


def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Remove control characters
    text = ''.join(char for char in text if unicodedata.category(char)[0] != 'C' or char in '\n\r\t')
    
    # Decode HTML entities
    import html
    text = html.unescape(text)
    
    return text


def normalize_url(url: str) -> str:
    """Normalize URL for consistent handling."""
    if not url:
        return ""
    
    # Add protocol if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    return url


def extract_domain(url: str) -> str:
    """Extract domain from URL."""
    if not url:
        return ""
    
    try:
        parsed = urlparse(normalize_url(url))
        domain = parsed.netloc.lower()
        
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        
        return domain
    except:
        return ""


def generate_filename(title: str, max_length: int = 50) -> str:
    """Generate safe filename from title."""
    # Clean title
    filename = clean_text(title)
    
    # Remove or replace unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'[^\w\s-]', '', filename)
    filename = re.sub(r'[-\s]+', '-', filename)
    
    # Truncate if too long
    if len(filename) > max_length:
        filename = filename[:max_length].rsplit('-', 1)[0]
    
    # Remove leading/trailing hyphens
    filename = filename.strip('-')
    
    # Ensure it's not empty
    if not filename:
        filename = f"news-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    return filename


def deduplicate_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicate articles based on URL and title similarity."""
    if not articles:
        return articles
    
    seen_urls = set()
    seen_titles = set()
    deduped = []
    
    for article in articles:
        url = article.get('url', '')
        title = article.get('title', '')
        
        # Normalize for comparison
        normalized_url = normalize_url(url)
        normalized_title = clean_text(title).lower()
        
        # Skip if we've seen this URL
        if normalized_url and normalized_url in seen_urls:
            continue
        
        # Skip if we've seen a very similar title
        title_hash = hashlib.md5(normalized_title.encode()).hexdigest()
        if title_hash in seen_titles:
            continue
        
        # Check for similar titles (simple approach)
        is_similar = False
        for existing_title in seen_titles:
            # If titles are very similar (same first 50 chars), skip
            if len(normalized_title) > 20 and len(existing_title) > 20:
                if normalized_title[:50] == existing_title[:50]:
                    is_similar = True
                    break
        
        if is_similar:
            continue
        
        # Add to seen sets
        if normalized_url:
            seen_urls.add(normalized_url)
        if normalized_title:
            seen_titles.add(title_hash)
        
        deduped.append(article)
    
    return deduped


def is_recent(date_str: str, days: int = 7) -> bool:
    """Check if date string represents a recent date."""
    if not date_str:
        return False
    
    try:
        from dateutil import parser as date_parser
        article_date = date_parser.parse(date_str)
        cutoff_date = datetime.now() - timedelta(days=days)
        return article_date > cutoff_date
    except:
        return False


def calculate_reading_time(text: str) -> int:
    """Calculate estimated reading time in minutes."""
    if not text:
        return 0
    
    word_count = len(text.split())
    # Average reading speed: 200-250 words per minute
    reading_time = max(1, round(word_count / 225))
    return reading_time


def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """Extract keywords from text using simple frequency analysis."""
    if not text:
        return []
    
    # Simple keyword extraction
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    
    # Filter out common stop words
    stop_words = {
        'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
        'after', 'above', 'below', 'between', 'among', 'upon', 'against',
        'within', 'throughout', 'despite', 'towards', 'concerning',
        'this', 'that', 'these', 'those', 'they', 'them', 'their', 'there',
        'where', 'when', 'what', 'who', 'which', 'why', 'how', 'said', 'says',
        'can', 'could', 'will', 'would', 'should', 'may', 'might', 'must',
        'have', 'has', 'had', 'having', 'been', 'being', 'was', 'were', 'are',
        'more', 'most', 'much', 'many', 'some', 'all', 'any', 'each', 'every',
        'new', 'old', 'first', 'last', 'long', 'great', 'little', 'own', 'other',
        'right', 'big', 'high', 'different', 'small', 'large', 'next', 'early',
        'young', 'important', 'few', 'public', 'bad', 'same', 'able'
    }
    
    # Count word frequencies
    word_freq = {}
    for word in words:
        if word not in stop_words and len(word) > 3:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Sort by frequency and return top keywords
    keywords = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, freq in keywords[:max_keywords]]


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def validate_url(url: str) -> bool:
    """Validate if URL is properly formatted."""
    if not url:
        return False
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to specified length with suffix."""
    if not text or len(text) <= max_length:
        return text
    
    # Try to break at word boundary
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > max_length * 0.7:  # If we can break at word boundary without losing too much
        truncated = truncated[:last_space]
    
    return truncated + suffix


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage."""
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove or replace other problematic characters
    filename = re.sub(r'[<>:"|?*]', '', filename)
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250 - len(ext)] + ('.' + ext if ext else '')
    
    return filename.strip()


def merge_article_data(base_article: Dict[str, Any], additional_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge additional data into base article, preferring non-empty values."""
    merged = base_article.copy()
    
    for key, value in additional_data.items():
        if value and (key not in merged or not merged[key]):
            merged[key] = value
        elif key == 'tags' and isinstance(value, list) and isinstance(merged.get(key), list):
            # Merge tag lists
            merged[key] = list(set(merged[key] + value))
    
    return merged