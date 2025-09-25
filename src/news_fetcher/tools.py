"""MCP tools for news fetching, processing, and management."""

import asyncio
import hashlib
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from ebooklib import epub
from readability import Document

from news_fetcher.config import Config
from news_fetcher.llm_client import LLMClient
from news_fetcher.utils import (
    clean_text,
    deduplicate_articles,
    extract_domain,
    generate_filename,
    is_recent,
    normalize_url,
)


def search_feeds(
    topic: Optional[str] = None,
    sources: Optional[List[str]] = None,
    limit: int = 10,
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Search and fetch RSS/Atom feeds based on topic or specific sources.
    
    Args:
        topic: Topic to search for (optional)
        sources: List of RSS/Atom feed URLs (optional)
        limit: Maximum number of articles to return
        config: Configuration object
    
    Returns:
        Dict containing articles with metadata
    """
    if not config:
        config = Config()
    
    # Determine sources to use
    feed_urls = []
    if sources:
        feed_urls = sources
    elif topic:
        feed_urls = config.get_sources_for_topic(topic)
    else:
        # Use user's preferred sources from interests
        for interest in config.preferences.interests:
            feed_urls.extend(config.get_sources_for_topic(interest))
    
    if not feed_urls:
        return {
            "success": False,
            "error": "No sources found for the given topic or criteria",
            "articles": []
        }
    
    articles = []
    errors = []
    
    for feed_url in feed_urls[:5]:  # Limit to 5 feeds to avoid timeout
        try:
            # Check cache first
            cache_key = hashlib.md5(feed_url.encode()).hexdigest()
            cache_path = config.get_cache_path(f"feed_{cache_key}")
            
            cached_data = None
            if cache_path.exists():
                try:
                    with open(cache_path, 'r') as f:
                        cached_data = json.load(f)
                        cache_time = datetime.fromisoformat(cached_data['timestamp'])
                        
                        # Use cache if less than TTL
                        if datetime.now() - cache_time < timedelta(seconds=config.cache_ttl):
                            articles.extend(cached_data['articles'][:config.preferences.max_articles_per_feed])
                            continue
                except (json.JSONDecodeError, KeyError, ValueError):
                    pass
            
            # Fetch feed
            print(f"Fetching feed: {feed_url}")
            response = requests.get(feed_url, timeout=10, headers={
                'User-Agent': 'News-Fetcher-MCP/1.0'
            })
            response.raise_for_status()
            
            # Parse feed
            feed = feedparser.parse(response.content)
            
            if feed.bozo and not feed.entries:
                errors.append(f"Failed to parse feed: {feed_url}")
                continue
            
            feed_articles = []
            for entry in feed.entries[:config.preferences.max_articles_per_feed]:
                try:
                    # Extract article data
                    published = None
                    if hasattr(entry, 'published'):
                        try:
                            published = date_parser.parse(entry.published).isoformat()
                        except:
                            pass
                    
                    if hasattr(entry, 'updated') and not published:
                        try:
                            published = date_parser.parse(entry.updated).isoformat()
                        except:
                            pass
                    
                    article = {
                        'title': clean_text(entry.get('title', 'No title')),
                        'url': normalize_url(entry.get('link', '')),
                        'summary': clean_text(entry.get('summary', '')),
                        'published': published,
                        'author': entry.get('author', ''),
                        'source': feed.feed.get('title', extract_domain(feed_url)),
                        'source_url': feed_url,
                        'domain': extract_domain(entry.get('link', '')),
                        'tags': [tag.term for tag in getattr(entry, 'tags', [])],
                        'fetched_at': datetime.now().isoformat()
                    }
                    
                    # Filter by domain exclusions
                    if article['domain'] not in config.preferences.exclude_domains:
                        feed_articles.append(article)
                        
                except Exception as e:
                    errors.append(f"Error processing entry from {feed_url}: {str(e)}")
                    continue
            
            articles.extend(feed_articles)
            
            # Cache the results
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'articles': feed_articles
            }
            with open(cache_path, 'w') as f:
                json.dump(cache_data, f, indent=2)
                
        except Exception as e:
            errors.append(f"Error fetching feed {feed_url}: {str(e)}")
            continue
    
    # Remove duplicates
    articles = deduplicate_articles(articles)
    
    # Sort by publication date (newest first)
    articles.sort(key=lambda x: x.get('published', ''), reverse=True)
    
    # Apply limit
    articles = articles[:limit]
    
    return {
        "success": True,
        "articles": articles,
        "total_found": len(articles),
        "sources_used": feed_urls,
        "errors": errors,
        "topic": topic,
        "timestamp": datetime.now().isoformat()
    }


def fetch_article(url: str, config: Optional[Config] = None) -> Dict[str, Any]:
    """
    Fetch and extract full text content from a news article URL.
    Uses Trafilatura first, falls back to Readability if needed.
    
    Args:
        url: URL of the article to fetch
        config: Configuration object
    
    Returns:
        Dict containing extracted article content and metadata
    """
    if not config:
        config = Config()
    
    # Normalize URL
    url = normalize_url(url)
    
    # Check cache first
    cache_key = hashlib.md5(url.encode()).hexdigest()
    cache_path = config.get_cache_path(f"article_{cache_key}")
    
    if cache_path.exists():
        try:
            with open(cache_path, 'r') as f:
                cached_data = json.load(f)
                cache_time = datetime.fromisoformat(cached_data['timestamp'])
                
                # Use cache if less than TTL
                if datetime.now() - cache_time < timedelta(seconds=config.cache_ttl):
                    return cached_data
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    
    try:
        # Fetch the page
        print(f"Fetching article: {url}")
        response = requests.get(url, timeout=15, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        response.raise_for_status()
        
        html_content = response.text
        
        # Try Trafilatura first
        extracted_content = trafilatura.extract(
            html_content,
            output_format='json',
            include_comments=False,
            include_tables=True,
            include_images=True,
            url=url
        )
        
        article_data = None
        extraction_method = "trafilatura"
        
        if extracted_content:
            try:
                content_json = json.loads(extracted_content)
                
                # Check if we got good content
                text_length = len(content_json.get('text', ''))
                if text_length > 200:  # Minimum content threshold
                    article_data = {
                        'title': content_json.get('title', ''),
                        'text': content_json.get('text', ''),
                        'author': content_json.get('author', ''),
                        'published': content_json.get('date', ''),
                        'description': content_json.get('description', ''),
                        'url': url,
                        'domain': extract_domain(url),
                        'language': content_json.get('language', ''),
                        'word_count': len(content_json.get('text', '').split()),
                        'extraction_method': extraction_method
                    }
            except json.JSONDecodeError:
                pass
        
        # Fallback to Readability if Trafilatura didn't work well
        if not article_data:
            print("Trafilatura extraction insufficient, trying Readability...")
            extraction_method = "readability"
            
            doc = Document(html_content)
            
            # Parse with BeautifulSoup for additional metadata
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract metadata
            title = doc.title() or ""
            if not title:
                title_tag = soup.find('title')
                title = title_tag.get_text().strip() if title_tag else ""
            
            author = ""
            author_meta = soup.find('meta', attrs={'name': 'author'}) or soup.find('meta', attrs={'property': 'article:author'})
            if author_meta:
                author = author_meta.get('content', '')
            
            published = ""
            date_meta = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('meta', attrs={'name': 'date'})
            if date_meta:
                published = date_meta.get('content', '')
            
            description = ""
            desc_meta = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', attrs={'property': 'og:description'})
            if desc_meta:
                description = desc_meta.get('content', '')
            
            # Extract main content
            content_html = doc.summary()
            content_soup = BeautifulSoup(content_html, 'html.parser')
            text_content = content_soup.get_text(separator='\n', strip=True)
            
            article_data = {
                'title': clean_text(title),
                'text': clean_text(text_content),
                'author': clean_text(author),
                'published': published,
                'description': clean_text(description),
                'url': url,
                'domain': extract_domain(url),
                'language': '',
                'word_count': len(text_content.split()),
                'extraction_method': extraction_method
            }
        
        if article_data:
            # Add extraction metadata
            article_data.update({
                'fetched_at': datetime.now().isoformat(),
                'success': True,
                'error': None
            })
            
            # Cache the result
            with open(cache_path, 'w') as f:
                json.dump(article_data, f, indent=2)
            
            return article_data
        else:
            error_msg = "Failed to extract meaningful content from the article"
            return {
                'success': False,
                'error': error_msg,
                'url': url,
                'fetched_at': datetime.now().isoformat()
            }
    
    except Exception as e:
        error_msg = f"Error fetching article: {str(e)}"
        return {
            'success': False,
            'error': error_msg,
            'url': url,
            'fetched_at': datetime.now().isoformat()
        }


def rank_articles(
    items: List[Dict[str, Any]], 
    topic: str,
    config: Optional[Config] = None
) -> List[Dict[str, Any]]:
    """
    Rank articles by relevance to topic using heuristics and LLM reranking.
    
    Args:
        items: List of article dictionaries
        topic: Topic to rank articles against
        config: Configuration object
    
    Returns:
        List of top-ranked articles (Top 5)
    """
    if not config:
        config = Config()
    
    if not items:
        return []
    
    # First, apply heuristic pre-ranking
    scored_items = []
    
    for item in items:
        score = 0.0
        
        # Recency score (newer articles get higher scores)
        if item.get('published'):
            try:
                pub_date = date_parser.parse(item['published'])
                days_old = (datetime.now() - pub_date).days
                # Exponential decay: newer articles get much higher scores
                recency_score = max(0, 10 * (0.9 ** days_old))
                score += recency_score
            except:
                pass
        
        # Domain diversity (prefer different sources)
        domain_bonus = 2.0  # Base bonus for having content
        score += domain_bonus
        
        # Keyword matching in title and summary
        title = item.get('title', '').lower()
        summary = item.get('summary', '').lower()
        topic_lower = topic.lower()
        
        # Topic relevance
        if topic_lower in title:
            score += 15.0
        if topic_lower in summary:
            score += 10.0
        
        # Boost keywords
        for keyword in config.preferences.keywords_boost:
            keyword_lower = keyword.lower()
            if keyword_lower in title:
                score += 8.0
            if keyword_lower in summary:
                score += 5.0
        
        # Filter keywords (reduce score)
        for keyword in config.preferences.keywords_filter:
            keyword_lower = keyword.lower()
            if keyword_lower in title:
                score -= 20.0
            if keyword_lower in summary:
                score -= 10.0
        
        # Word count bonus (longer articles might be more substantial)
        word_count = item.get('word_count', len(item.get('summary', '').split()))
        if word_count > 200:
            score += 3.0
        elif word_count > 100:
            score += 1.0
        
        scored_items.append((item, score))
    
    # Sort by heuristic score
    scored_items.sort(key=lambda x: x[1], reverse=True)
    
    # Take top candidates for LLM reranking (more than 5 to give LLM options)
    top_candidates = [item for item, score in scored_items[:15]]
    
    # Use LLM for final reranking if available
    try:
        llm_client = LLMClient(config)
        if llm_client.is_available():
            print(f"Using LLM to rerank {len(top_candidates)} articles for topic: {topic}")
            reranked = llm_client.rank_articles(top_candidates, topic)
            if reranked:
                return reranked[:5]  # Return top 5
    except Exception as e:
        print(f"LLM ranking failed, using heuristic ranking: {e}")
    
    # Fallback to heuristic ranking
    return top_candidates[:5]


def summarize_collection(
    collection: List[Dict[str, Any]],
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Generate a front-page TL;DR summary of a collection of articles.
    
    Args:
        collection: List of article dictionaries
        config: Configuration object
    
    Returns:
        Dict containing summary with bullets and key information
    """
    if not config:
        config = Config()
    
    if not collection:
        return {
            "success": False,
            "error": "No articles provided for summarization"
        }
    
    # Try LLM summarization first
    try:
        llm_client = LLMClient(config)
        if llm_client.is_available():
            print(f"Using LLM to summarize {len(collection)} articles")
            summary = llm_client.summarize_articles(collection)
            if summary:
                return {
                    "success": True,
                    "summary": summary,
                    "article_count": len(collection),
                    "method": "llm",
                    "timestamp": datetime.now().isoformat()
                }
    except Exception as e:
        print(f"LLM summarization failed, using fallback: {e}")
    
    # Fallback to heuristic summarization
    print("Using heuristic summarization")
    
    # Group articles by domain for diversity
    by_domain = {}
    for article in collection:
        domain = article.get('domain', 'unknown')
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(article)
    
    # Extract key information
    bullet_points = []
    key_numbers = []
    dates = []
    sources = set()
    
    for article in collection[:10]:  # Limit for processing
        title = article.get('title', '')
        summary = article.get('summary', '')
        
        # Add title as bullet point
        if title:
            bullet_points.append(f"• {title}")
        
        # Add source
        source = article.get('source', article.get('domain', ''))
        if source:
            sources.add(source)
        
        # Extract dates
        if article.get('published'):
            try:
                pub_date = date_parser.parse(article['published'])
                dates.append(pub_date.strftime("%B %d, %Y"))
            except:
                pass
        
        # Simple number extraction from titles/summaries
        import re
        text = f"{title} {summary}"
        numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text)
        for num in numbers[:3]:  # Limit numbers per article
            if len(num) > 2:  # Only significant numbers
                key_numbers.append(num)
    
    # Generate summary text
    summary_text = f"Daily News Summary - {len(collection)} articles"
    
    if sources:
        source_list = ', '.join(list(sources)[:5])
        summary_text += f"\n\nSources: {source_list}"
    
    if dates:
        unique_dates = list(set(dates))
        if unique_dates:
            summary_text += f"\n\nCoverage from: {unique_dates[0]}"
            if len(unique_dates) > 1:
                summary_text += f" to {unique_dates[-1]}"
    
    summary_text += "\n\nTop Stories:"
    summary_text += "\n" + "\n".join(bullet_points[:10])
    
    if key_numbers:
        summary_text += f"\n\nKey figures mentioned: {', '.join(key_numbers[:5])}"
    
    return {
        "success": True,
        "summary": summary_text,
        "bullet_points": bullet_points[:10],
        "key_numbers": key_numbers[:5],
        "sources": list(sources),
        "date_range": dates,
        "article_count": len(collection),
        "method": "heuristic",
        "timestamp": datetime.now().isoformat()
    }


def build_epub(
    articles: List[Dict[str, Any]], 
    title: str,
    filename: Optional[str] = None,
    config: Optional[Config] = None
) -> Dict[str, Any]:
    """
    Build an EPUB file from a collection of articles.
    
    Args:
        articles: List of article dictionaries
        title: Title for the EPUB
        filename: Optional filename (auto-generated if not provided)
        config: Configuration object
    
    Returns:
        Dict containing EPUB file path and metadata
    """
    if not config:
        config = Config()
    
    if not articles:
        return {
            "success": False,
            "error": "No articles provided for EPUB generation"
        }
    
    try:
        # Generate filename if not provided
        if not filename:
            filename = generate_filename(title)
        
        epub_path = config.get_epub_path(filename)
        
        # Create EPUB book
        book = epub.EpubBook()
        
        # Set metadata
        book.set_identifier(f"news-fetcher-{int(time.time())}")
        book.set_title(title)
        book.set_language('en')
        book.add_author('News Fetcher MCP')
        book.add_metadata('DC', 'description', f'Collection of {len(articles)} news articles')
        book.add_metadata('DC', 'date', datetime.now().strftime('%Y-%m-%d'))
        
        # Add CSS style
        style = '''
        body { font-family: Arial, sans-serif; margin: 2em; }
        h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h2 { color: #34495e; margin-top: 2em; }
        .article-meta { color: #7f8c8d; font-size: 0.9em; margin-bottom: 1em; }
        .article-content { line-height: 1.6; }
        .source-link { color: #3498db; text-decoration: none; }
        .published-date { font-style: italic; }
        '''
        
        nav_css = epub.EpubItem(
            uid="nav_css",
            file_name="style/nav.css",
            media_type="text/css",
            content=style
        )
        book.add_item(nav_css)
        
        # Create table of contents
        toc_content = f"<h1>{title}</h1>\n"
        toc_content += f"<p>Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>\n"
        toc_content += f"<p>{len(articles)} articles</p>\n<ul>\n"
        
        chapters = []
        spine = ['nav']
        
        for i, article in enumerate(articles, 1):
            article_title = article.get('title', f'Article {i}')
            article_url = article.get('url', '')
            
            # Clean title for filename
            safe_title = ''.join(c for c in article_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            chapter_filename = f"chapter_{i:03d}.xhtml"
            
            # Add to TOC
            toc_content += f"<li><a href=\"{chapter_filename}\">{article_title}</a></li>\n"
            
            # Create chapter content
            chapter_html = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{article_title}</title>
    <link rel="stylesheet" type="text/css" href="../style/nav.css"/>
</head>
<body>
    <h1>{article_title}</h1>
    <div class="article-meta">
'''
            
            # Add metadata
            if article.get('author'):
                chapter_html += f'<p><strong>Author:</strong> {article["author"]}</p>\n'
            
            if article.get('published'):
                try:
                    pub_date = date_parser.parse(article['published'])
                    formatted_date = pub_date.strftime('%B %d, %Y at %I:%M %p')
                    chapter_html += f'<p class="published-date"><strong>Published:</strong> {formatted_date}</p>\n'
                except:
                    chapter_html += f'<p class="published-date"><strong>Published:</strong> {article["published"]}</p>\n'
            
            if article.get('source'):
                chapter_html += f'<p><strong>Source:</strong> {article["source"]}</p>\n'
            
            if article_url:
                chapter_html += f'<p><strong>Original:</strong> <a href="{article_url}" class="source-link">{article_url}</a></p>\n'
            
            chapter_html += '</div>\n<div class="article-content">\n'
            
            # Add content
            content = article.get('text', article.get('summary', ''))
            if not content:
                content = "No content available for this article."
            
            # Convert newlines to paragraphs
            paragraphs = content.split('\n\n')
            if not paragraphs or not any(p.strip() for p in paragraphs):
                paragraphs = [content]
            
            for para in paragraphs:
                para = para.strip()
                if para:
                    # Escape HTML characters
                    import html
                    para = html.escape(para)
                    chapter_html += f'<p>{para}</p>\n'
            
            chapter_html += '</div>\n</body>\n</html>'
            
            # Create chapter
            chapter = epub.EpubHtml(
                title=article_title,
                file_name=chapter_filename,
                lang='en'
            )
            chapter.content = chapter_html
            
            book.add_item(chapter)
            chapters.append(chapter)
            spine.append(chapter)
        
        toc_content += "</ul>\n"
        
        # Create introduction chapter
        intro = epub.EpubHtml(
            title="Table of Contents",
            file_name="intro.xhtml",
            lang='en'
        )
        intro.content = f'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Table of Contents</title>
    <link rel="stylesheet" type="text/css" href="style/nav.css"/>
</head>
<body>
{toc_content}
</body>
</html>'''
        
        book.add_item(intro)
        spine.insert(1, intro)
        
        # Define Table of Contents
        book.toc = (
            epub.Link("intro.xhtml", "Introduction", "intro"),
            (epub.Section("Articles"), chapters)
        )
        
        # Add navigation files
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Define spine
        book.spine = spine
        
        # Write EPUB file
        epub.write_epub(str(epub_path), book, {})
        
        print(f"EPUB created: {epub_path}")
        
        return {
            "success": True,
            "epub_path": str(epub_path),
            "filename": epub_path.name,
            "title": title,
            "article_count": len(articles),
            "file_size": epub_path.stat().st_size,
            "created_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to create EPUB: {str(e)}"
        }


def publish_opds(file_path: str, config: Optional[Config] = None) -> Dict[str, Any]:
    """
    Publish EPUB file via OPDS catalog for KOReader access.
    
    Args:
        file_path: Path to the EPUB file to publish
        config: Configuration object
    
    Returns:
        Dict containing OPDS URL and publication details
    """
    if not config:
        config = Config()
    
    try:
        epub_path = Path(file_path)
        
        if not epub_path.exists():
            return {
                "success": False,
                "error": f"EPUB file not found: {file_path}"
            }
        
        if not epub_path.suffix.lower() == '.epub':
            return {
                "success": False,
                "error": "File must be an EPUB file"
            }
        
        # Copy to epubs directory if not already there
        if epub_path.parent != config.epubs_dir:
            target_path = config.epubs_dir / epub_path.name
            import shutil
            shutil.copy2(epub_path, target_path)
            epub_path = target_path
        
        # OPDS server handles the actual publishing
        opds_url = f"http://localhost:{config.opds_port}/opds"
        download_url = f"http://localhost:{config.opds_port}/epubs/{epub_path.name}"
        
        return {
            "success": True,
            "opds_catalog_url": opds_url,
            "download_url": download_url,
            "filename": epub_path.name,
            "file_size": epub_path.stat().st_size,
            "published_at": datetime.now().isoformat(),
            "instructions": [
                "1. Ensure the OPDS server is running",
                f"2. Add OPDS catalog URL to KOReader: {opds_url}",
                "3. Browse and download the EPUB from KOReader",
                f"4. Direct download URL: {download_url}"
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to publish EPUB: {str(e)}"
        }