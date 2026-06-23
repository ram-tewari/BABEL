"""
External metadata clients for fetching novel information from external sources.

This module provides clients for:
- NovelUpdates (https://www.novelupdates.com)
- RoyalRoad (https://www.royalroad.com)

Each client implements the MetadataClient abstract base class and provides
search and cover URL fetching capabilities.
"""

import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExternalMetadata(BaseModel):
    """Metadata fetched from external source."""
    
    title: str
    author: Optional[str] = None
    cover_url: Optional[str] = None
    synopsis: Optional[str] = None
    tags: List[str] = []
    status: str = "active"
    source: str
    
    def __init__(self, **data):
        super().__init__(**data)
        # Clean and deduplicate tags
        if self.tags:
            cleaned = []
            seen = set()
            for tag in self.tags:
                cleaned_tag = tag.strip()
                if cleaned_tag and cleaned_tag.lower() not in seen:
                    cleaned.append(cleaned_tag)
                    seen.add(cleaned_tag.lower())
            object.__setattr__(self, 'tags', cleaned)


class MetadataClient(ABC):
    """
    Abstract base class for external metadata clients.
    
    Provides interface for searching novels and fetching cover URLs
    from external sources like NovelUpdates and RoyalRoad.
    """
    
    BASE_URL: str = ""
    
    @abstractmethod
    async def search(self, title: str) -> Optional[ExternalMetadata]:
        """
        Search for a novel by title.
        
        Args:
            title: The novel title to search for.
            
        Returns:
            ExternalMetadata if found, None otherwise.
        """
        pass
    
    @abstractmethod
    async def get_cover_url(self, novel_id: str) -> Optional[str]:
        """
        Get the cover image URL for a novel.
        
        Args:
            novel_id: The external novel ID.
            
        Returns:
            Cover URL string if found, None otherwise.
        """
        pass
    
    @abstractmethod
    async def get_novel_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract the novel ID from a novel page URL.
        
        Args:
            url: The novel page URL.
            
        Returns:
            Novel ID string if extracted, None otherwise.
        """
        pass


class NovelUpdatesClient(MetadataClient):
    """
    Client for NovelUpdates API.
    
    NovelUpdates provides metadata for webnovels including:
    - Title and author
    - Synopsis
    - Cover images
    - Tags and genres
    - Status (ongoing, completed, etc.)
    
    Note: NovelUpdates doesn't have a public API, so this client
    scrapes the search results page.
    """
    
    BASE_URL = "https://www.novelupdates.com"
    SEARCH_URL = "https://www.novelupdates.com/?s={title}&post_type=series"
    
    # Mapping of status strings
    STATUS_MAP = {
        "ongoing": "active",
        "completed": "completed",
        "hiatus": "dropped",
        "discontinued": "dropped",
    }
    
    def __init__(self, timeout: float = 10.0):
        """
        Initialize the NovelUpdates client.
        
        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                follow_redirects=True,
            )
        return self._client
    
    async def search(self, title: str) -> Optional[ExternalMetadata]:
        """
        Search for a novel on NovelUpdates.
        
        Args:
            title: The novel title to search for.
            
        Returns:
            ExternalMetadata if found, None otherwise.
        """
        try:
            # URL encode the title
            search_url = self.SEARCH_URL.format(title=title.replace(" ", "+"))
            
            response = self.client.get(search_url)
            response.raise_for_status()
            
            # Parse the search results
            return self._parse_search_results(response.text, title)
            
        except httpx.HTTPError as e:
            logger.error(f"NovelUpdates search failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching NovelUpdates: {e}")
            return None
    
    def _parse_search_results(self, html: str, search_title: str) -> Optional[ExternalMetadata]:
        """
        Parse search results from NovelUpdates HTML.
        
        Args:
            html: The HTML response from search.
            search_title: The title we searched for.
            
        Returns:
            ExternalMetadata if found, None otherwise.
        """
        try:
            # Look for series list items
            # NovelUpdates uses .search_main_box for results
            import re
            
            # Find the first series result - match the full div with content
            series_pattern = r'<div class="search_main_box"[^>]*>(.*?)</div>'
            series_match = re.search(series_pattern, html, re.DOTALL)
            
            if not series_match:
                return None
            
            # Parse the first result
            series_html = series_match.group(0)
            
            # Extract title and link
            title_pattern = r'title="([^"]+)"[^>]*href="([^"]+)"'
            title_match = re.search(title_pattern, series_html)
            
            if not title_match:
                return None
            
            title = title_match.group(1)
            series_url = title_match.group(2)
            
            # Extract novel ID from URL
            novel_id = self.get_novel_id_from_url(series_url)
            
            # Extract author
            author_pattern = r'<div class="search_author">[^<]*<a[^>]*>([^<]+)</a>'
            author_match = re.search(author_pattern, series_html)
            author = author_match.group(1).strip() if author_match else None
            
            # Extract cover image
            img_pattern = r'<img[^>]*src="([^"]+)"[^>]*>'
            img_matches = re.findall(img_pattern, series_html)
            cover_url = None
            for img in img_matches:
                if "image" in img.lower() or "cover" in img.lower():
                    cover_url = img
                    break
            
            # Extract synopsis (limited from search page)
            synopsis_pattern = r'<div class="search_desc">([^<]+)'
            synopsis_match = re.search(synopsis_pattern, series_html)
            synopsis = synopsis_match.group(1).strip() if synopsis_match else None
            
            # Extract tags
            tags = []
            tag_pattern = r'<a[^>]*class="search_tags"[^>]*>([^<]+)</a>'
            tag_matches = re.findall(tag_pattern, html)
            tags = [tag.strip() for tag in tag_matches if tag.strip()][:10]  # Limit to 10 tags
            
            # Extract status
            status = "active"  # Default
            status_pattern = r'search_status[^>]*>([^<]+)'
            status_match = re.search(status_pattern, html)
            if status_match:
                status_text = status_match.group(1).strip().lower()
                status = self.STATUS_MAP.get(status_text, "active")
            
            return ExternalMetadata(
                title=title,
                author=author,
                cover_url=cover_url,
                synopsis=synopsis,
                tags=tags,
                status=status,
                source="novelupdates",
            )
            
        except Exception as e:
            logger.error(f"Error parsing NovelUpdates results: {e}")
            return None
    
    async def get_cover_url(self, novel_id: str) -> Optional[str]:
        """
        Get the cover image URL for a NovelUpdates novel.
        
        Args:
            novel_id: The NovelUpdates novel ID.
            
        Returns:
            Cover URL string if found, None otherwise.
        """
        try:
            # NovelUpdates series page
            series_url = f"{self.BASE_URL}/series/{novel_id}/"
            
            response = self.client.get(series_url)
            response.raise_for_status()
            
            # Parse cover image
            cover_pattern = r'<img[^>]*id="series_image"[^>]*src="([^"]+)"'
            cover_match = re.search(cover_pattern, response.text)
            
            if cover_match:
                return cover_match.group(1)
            
            # Alternative pattern
            alt_pattern = r'<div class="seriesimg">[^<]*<img[^>]*src="([^"]+)"'
            alt_match = re.search(alt_pattern, response.text)
            
            if alt_match:
                return alt_match.group(1)
            
            return None
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get cover URL from NovelUpdates: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting NovelUpdates cover URL: {e}")
            return None
    
    async def get_novel_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract the novel ID from a NovelUpdates URL.
        
        Args:
            url: The NovelUpdates series URL.
            
        Returns:
            Novel ID string if extracted, None otherwise.
        """
        return self._get_novel_id_from_url_sync(url)
    
    def _get_novel_id_from_url_sync(self, url: str) -> Optional[str]:
        """
        Extract the novel ID from a NovelUpdates URL (sync version).
        
        Args:
            url: The NovelUpdates series URL.
            
        Returns:
            Novel ID string if extracted, None otherwise.
        """
        # Pattern: https://www.novelupdates.com/series/novel-id/
        pattern = r"novelupdates\.com/series/([^/]+)/"
        match = re.search(pattern, url)
        
        if match:
            return match.group(1)
        
        return None
    
    async def get_metadata_by_id(self, novel_id: str) -> Optional[ExternalMetadata]:
        """
        Get full metadata for a novel by its ID.
        
        Args:
            novel_id: The NovelUpdates novel ID.
            
        Returns:
            ExternalMetadata if found, None otherwise.
        """
        try:
            series_url = f"{self.BASE_URL}/series/{novel_id}/"
            
            response = self.client.get(series_url)
            response.raise_for_status()
            
            return self._parse_series_page(response.text, novel_id)
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get metadata from NovelUpdates: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting NovelUpdates metadata: {e}")
            return None
    
    def _parse_series_page(self, html: str, novel_id: str) -> Optional[ExternalMetadata]:
        """
        Parse a series page for full metadata.
        
        Args:
            html: The HTML of the series page.
            novel_id: The novel ID.
            
        Returns:
            ExternalMetadata if parsed successfully, None otherwise.
        """
        try:
            # Extract title
            title_pattern = r'<h1[^>]*class="series-title"[^>]*>([^<]+)</h1>'
            title_match = re.search(title_pattern, html)
            title = title_match.group(1).strip() if title_match else None
            
            if not title:
                return None
            
            # Extract author
            author_pattern = r'<span[^>]*class="author"[^>]*><a[^>]*>([^<]+)</a></span>'
            author_match = re.search(author_pattern, html)
            author = author_match.group(1).strip() if author_match else None
            
            # Extract cover
            cover_pattern = r'<img[^>]*id="series_image"[^>]*src="([^"]+)"'
            cover_match = re.search(cover_pattern, html)
            cover_url = cover_match.group(1) if cover_match else None
            
            # Extract synopsis
            synopsis_pattern = r'<div[^>]*id="editdescription"[^>]*>([^<]+)'
            synopsis_match = re.search(synopsis_pattern, html, re.DOTALL)
            synopsis = None
            if synopsis_match:
                # Clean up HTML tags
                synopsis = re.sub(r'<[^>]+>', '', synopsis_match.group(1))
                synopsis = synopsis.strip()
            
            # Extract tags
            tags = []
            tag_pattern = r'<a[^>]*class="genre"[^>]*>([^<]+)</a>'
            tag_matches = re.findall(tag_pattern, html)
            tags = [tag.strip() for tag in tag_matches if tag.strip()][:10]
            
            # Extract status
            status = "active"
            status_pattern = r'<span[^>]*class="status"[^>]*>([^<]+)</span>'
            status_match = re.search(status_pattern, html)
            if status_match:
                status_text = status_match.group(1).strip().lower()
                status = self.STATUS_MAP.get(status_text, "active")
            
            return ExternalMetadata(
                title=title,
                author=author,
                cover_url=cover_url,
                synopsis=synopsis,
                tags=tags,
                status=status,
                source="novelupdates",
            )
            
        except Exception as e:
            logger.error(f"Error parsing NovelUpdates series page: {e}")
            return None
    
    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


class RoyalRoadClient(MetadataClient):
    """
    Client for RoyalRoad API.
    
    RoyalRoad provides metadata for webnovels including:
    - Title and author
    - Description
    - Cover images
    - Tags and genres
    - Status
    
    Uses the RoyalRoad public API.
    """
    
    BASE_URL = "https://www.royalroad.com"
    API_BASE = "https://www.royalroad.com/api"
    SEARCH_URL = f"{API_BASE}/fiction?keyword={{title}}"
    
    # Mapping of fiction status to our status
    STATUS_MAP = {
        "ONGOING": "active",
        "COMPLETED": "completed",
        "HIATUS": "dropped",
        "ABANDONED": "dropped",
        "UNKNOWN": "active",
    }
    
    def __init__(self, timeout: float = 10.0):
        """
        Initialize the RoyalRoad client.
        
        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self._client: Optional[httpx.Client] = None
    
    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "application/json",
                },
                follow_redirects=True,
            )
        return self._client
    
    async def search(self, title: str) -> Optional[ExternalMetadata]:
        """
        Search for a novel on RoyalRoad.
        
        Args:
            title: The novel title to search for.
            
        Returns:
            ExternalMetadata if found, None otherwise.
        """
        try:
            search_url = self.SEARCH_URL.format(title=title.replace(" ", "%20"))
            
            response = self.client.get(search_url)
            response.raise_for_status()
            
            data = response.json()
            
            if not data.get("data") or len(data["data"]) == 0:
                return None
            
            # Get the first result
            fiction = data["data"][0]
            
            return self._parse_fiction_data(fiction)
            
        except httpx.HTTPError as e:
            logger.error(f"RoyalRoad search failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching RoyalRoad: {e}")
            return None
    
    def _parse_fiction_data(self, fiction: dict) -> ExternalMetadata:
        """
        Parse fiction data from RoyalRoad API response.
        
        Args:
            fiction: The fiction data from API.
            
        Returns:
            ExternalMetadata parsed from the data.
        """
        # Extract cover URL
        cover_url = fiction.get("coverUrl")
        if cover_url and not cover_url.startswith("http"):
            cover_url = f"{self.BASE_URL}{cover_url}"
        
        # Extract tags
        tags = []
        genres = fiction.get("genres", [])
        if isinstance(genres, list):
            for genre in genres:
                if isinstance(genre, dict):
                    tags.append(genre.get("name", ""))
                else:
                    tags.append(str(genre))
        tags = [t.strip() for t in tags if t.strip()][:10]
        
        # Extract status
        fiction_status = fiction.get("status", "UNKNOWN")
        status = self.STATUS_MAP.get(fiction_status, "active")
        
        # Extract author
        author = fiction.get("author", {})
        if isinstance(author, dict):
            author = author.get("name", None)
        
        return ExternalMetadata(
            title=fiction.get("title", ""),
            author=author,
            cover_url=cover_url,
            synopsis=fiction.get("description", None),
            tags=tags,
            status=status,
            source="royalroad",
        )
    
    async def get_cover_url(self, novel_id: str) -> Optional[str]:
        """
        Get the cover image URL for a RoyalRoad novel.
        
        Args:
            novel_id: The RoyalRoad fiction ID.
            
        Returns:
            Cover URL string if found, None otherwise.
        """
        try:
            # Get fiction details
            fiction_url = f"{self.API_BASE}/fiction/{novel_id}"
            
            response = self.client.get(fiction_url)
            response.raise_for_status()
            
            data = response.json()
            cover_url = data.get("coverUrl")
            
            if cover_url and not cover_url.startswith("http"):
                return f"{self.BASE_URL}{cover_url}"
            
            return cover_url
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get cover URL from RoyalRoad: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting RoyalRoad cover URL: {e}")
            return None
    
    async def get_novel_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract the novel ID from a RoyalRoad URL.
        
        Args:
            url: The RoyalRoad fiction URL.
            
        Returns:
            Novel ID string if extracted, None otherwise.
        """
        return self._get_novel_id_from_url_sync(url)
    
    def _get_novel_id_from_url_sync(self, url: str) -> Optional[str]:
        """
        Extract the novel ID from a RoyalRoad URL (sync version).
        
        Args:
            url: The RoyalRoad fiction URL.
            
        Returns:
            Novel ID string if extracted, None otherwise.
        """
        # Pattern: https://www.royalroad.com/fiction/1234/novel-title
        pattern = r"royalroad\.com/fiction/(\d+)"
        match = re.search(pattern, url)
        
        if match:
            return match.group(1)
        
        return None
    
    async def get_metadata_by_id(self, novel_id: str) -> Optional[ExternalMetadata]:
        """
        Get full metadata for a novel by its ID.
        
        Args:
            novel_id: The RoyalRoad fiction ID.
            
        Returns:
            ExternalMetadata if found, None otherwise.
        """
        try:
            fiction_url = f"{self.API_BASE}/fiction/{novel_id}"
            
            response = self.client.get(fiction_url)
            response.raise_for_status()
            
            data = response.json()
            
            return self._parse_fiction_data(data)
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to get metadata from RoyalRoad: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting RoyalRoad metadata: {e}")
            return None
    
    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None


def get_metadata_client(source: str) -> MetadataClient:
    """
    Factory function to get a metadata client by source name.
    
    Args:
        source: The source name ("novelupdates" or "royalroad").
        
    Returns:
        The appropriate metadata client.
        
    Raises:
        ValueError: If the source is not recognized.
    """
    source = source.lower()
    
    if source == "novelupdates":
        return NovelUpdatesClient()
    elif source == "royalroad":
        return RoyalRoadClient()
    else:
        raise ValueError(f"Unknown metadata source: {source}")


async def download_cover_image(cover_url: str, save_path: Path) -> bool:
    """
    Download a cover image from a URL.
    
    Args:
        cover_url: The URL of the cover image.
        save_path: The path to save the image to.
        
    Returns:
        True if download succeeded, False otherwise.
    """
    try:
        # Ensure parent directory exists
        save_path.parent.mkdir(parents=True, exist_ok=True)
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(cover_url, follow_redirects=True)
            response.raise_for_status()
            
            # Verify it's an image
            content_type = response.headers.get("content-type", "")
            if "image" not in content_type:
                logger.warning(f"Cover URL does not return an image: {content_type}")
                return False
            
            # Save the image
            save_path.write_bytes(response.content)
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to download cover image: {e}")
        return False


def ensure_covers_directory() -> Path:
    """Ensure the covers directory exists."""
    covers_dir = Path("data/covers")
    covers_dir.mkdir(parents=True, exist_ok=True)
    return covers_dir