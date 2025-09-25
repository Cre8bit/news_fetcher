"""OPDS server for serving EPUB files to KOReader and other compatible readers."""

import os
from datetime import datetime
from pathlib import Path
from typing import List
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from news_fetcher.config import Config


def create_opds_app(config: Config) -> FastAPI:
    """Create FastAPI app for OPDS catalog."""
    app = FastAPI(
        title="News Fetcher OPDS Catalog",
        description="OPDS catalog for news articles converted to EPUB",
        version="1.0.0"
    )
    
    # Mount static files for EPUB downloads
    app.mount("/epubs", StaticFiles(directory=str(config.epubs_dir)), name="epubs")
    
    @app.get("/")
    async def root():
        """Root endpoint with basic info."""
        return {
            "title": "News Fetcher OPDS Catalog",
            "description": "OPDS catalog for news articles converted to EPUB",
            "opds_url": "/opds",
            "epub_count": len(list(config.epubs_dir.glob("*.epub")))
        }
    
    @app.get("/opds")
    async def opds_catalog():
        """Main OPDS catalog feed."""
        # Create OPDS XML
        feed = Element("feed")
        feed.set("xmlns", "http://www.w3.org/2005/Atom")
        feed.set("xmlns:opds", "http://opds-spec.org/2010/catalog")
        
        # Feed metadata
        id_elem = SubElement(feed, "id")
        id_elem.text = "urn:uuid:news-fetcher-opds"
        
        title = SubElement(feed, "title")
        title.text = "News Fetcher EPUB Catalog"
        
        updated = SubElement(feed, "updated")
        updated.text = datetime.now().isoformat() + "Z"
        
        author = SubElement(feed, "author")
        author_name = SubElement(author, "name")
        author_name.text = "News Fetcher MCP"
        
        # Self link
        self_link = SubElement(feed, "link")
        self_link.set("rel", "self")
        self_link.set("href", "/opds")
        self_link.set("type", "application/atom+xml;profile=opds-catalog;kind=navigation")
        
        # Start link
        start_link = SubElement(feed, "link")
        start_link.set("rel", "start")
        start_link.set("href", "/opds")
        start_link.set("type", "application/atom+xml;profile=opds-catalog;kind=navigation")
        
        # Get EPUB files
        epub_files = list(config.epubs_dir.glob("*.epub"))
        epub_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Add entries for each EPUB
        for epub_file in epub_files:
            entry = SubElement(feed, "entry")
            
            # Entry ID
            entry_id = SubElement(entry, "id")
            entry_id.text = f"urn:uuid:epub-{epub_file.stem}"
            
            # Entry title
            entry_title = SubElement(entry, "title")
            entry_title.text = epub_file.stem.replace('-', ' ').replace('_', ' ').title()
            
            # Entry updated time
            entry_updated = SubElement(entry, "updated")
            mtime = datetime.fromtimestamp(epub_file.stat().st_mtime)
            entry_updated.text = mtime.isoformat() + "Z"
            
            # Entry content
            content = SubElement(entry, "content")
            content.set("type", "text")
            content.text = f"News articles compiled on {mtime.strftime('%B %d, %Y')}"
            
            # Download link
            download_link = SubElement(entry, "link")
            download_link.set("rel", "http://opds-spec.org/acquisition")
            download_link.set("href", f"/epubs/{epub_file.name}")
            download_link.set("type", "application/epub+zip")
            download_link.set("title", "Download EPUB")
            
            # File size
            file_size = epub_file.stat().st_size
            download_link.set("length", str(file_size))
            
            # Category
            category = SubElement(entry, "category")
            category.set("scheme", "http://www.bisg.org/standards/bisac_subject/index.html")
            category.set("term", "NEWS")
            category.set("label", "News")
        
        # Convert to string
        xml_str = tostring(feed, encoding='unicode')
        
        return Response(
            content=xml_str,
            media_type="application/atom+xml;profile=opds-catalog;kind=navigation"
        )
    
    @app.get("/opds/recent")
    async def recent_entries():
        """Recent entries feed."""
        feed = Element("feed")
        feed.set("xmlns", "http://www.w3.org/2005/Atom")
        feed.set("xmlns:opds", "http://opds-spec.org/2010/catalog")
        
        # Feed metadata
        id_elem = SubElement(feed, "id")
        id_elem.text = "urn:uuid:news-fetcher-recent"
        
        title = SubElement(feed, "title")
        title.text = "Recent News EPUBs"
        
        updated = SubElement(feed, "updated")
        updated.text = datetime.now().isoformat() + "Z"
        
        # Links
        self_link = SubElement(feed, "link")
        self_link.set("rel", "self")
        self_link.set("href", "/opds/recent")
        self_link.set("type", "application/atom+xml;profile=opds-catalog;kind=acquisition")
        
        up_link = SubElement(feed, "link")
        up_link.set("rel", "up")
        up_link.set("href", "/opds")
        up_link.set("type", "application/atom+xml;profile=opds-catalog;kind=navigation")
        
        # Get recent EPUB files (last 30 days)
        cutoff_time = datetime.now().timestamp() - (30 * 24 * 60 * 60)  # 30 days
        epub_files = [
            f for f in config.epubs_dir.glob("*.epub")
            if f.stat().st_mtime > cutoff_time
        ]
        epub_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        
        # Add entries
        for epub_file in epub_files[:20]:  # Limit to 20 recent files
            entry = SubElement(feed, "entry")
            
            entry_id = SubElement(entry, "id")
            entry_id.text = f"urn:uuid:epub-{epub_file.stem}"
            
            entry_title = SubElement(entry, "title")
            entry_title.text = epub_file.stem.replace('-', ' ').replace('_', ' ').title()
            
            entry_updated = SubElement(entry, "updated")
            mtime = datetime.fromtimestamp(epub_file.stat().st_mtime)
            entry_updated.text = mtime.isoformat() + "Z"
            
            summary = SubElement(entry, "summary")
            summary.text = f"News collection from {mtime.strftime('%B %d, %Y')}"
            
            download_link = SubElement(entry, "link")
            download_link.set("rel", "http://opds-spec.org/acquisition")
            download_link.set("href", f"/epubs/{epub_file.name}")
            download_link.set("type", "application/epub+zip")
            download_link.set("length", str(epub_file.stat().st_size))
        
        xml_str = tostring(feed, encoding='unicode')
        return Response(
            content=xml_str,
            media_type="application/atom+xml;profile=opds-catalog;kind=acquisition"
        )
    
    @app.get("/epub/{filename}")
    async def download_epub(filename: str):
        """Download specific EPUB file."""
        epub_path = config.epubs_dir / filename
        
        if not epub_path.exists():
            raise HTTPException(status_code=404, detail="EPUB file not found")
        
        if not epub_path.suffix.lower() == '.epub':
            raise HTTPException(status_code=400, detail="File is not an EPUB")
        
        return FileResponse(
            path=str(epub_path),
            media_type="application/epub+zip",
            filename=filename
        )
    
    @app.get("/catalog.xml")
    async def catalog_xml():
        """Alternative OPDS catalog endpoint."""
        return await opds_catalog()
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        epub_count = len(list(config.epubs_dir.glob("*.epub")))
        return {
            "status": "healthy",
            "epub_count": epub_count,
            "epubs_dir": str(config.epubs_dir),
            "timestamp": datetime.now().isoformat()
        }
    
    return app


def start_opds_server(config: Config, host: str = "0.0.0.0", port: int = 8000):
    """Start the OPDS server."""
    import uvicorn
    
    app = create_opds_app(config)
    
    print(f"Starting OPDS server at http://{host}:{port}")
    print(f"OPDS catalog available at: http://{host}:{port}/opds")
    print(f"For KOReader, add catalog URL: http://{host}:{port}/opds")
    
    uvicorn.run(app, host=host, port=port)