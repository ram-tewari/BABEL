"""
Metadata extraction module for multi-novel support.

Provides functions to extract novel metadata (title, author) from:
1. EPUB files (Dublin Core metadata from content.opf)
2. Filenames (fallback method)

The extraction strategy prioritizes EPUB internal metadata over filename parsing.
"""

import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict
import re
import logging

logger = logging.getLogger(__name__)


# XML namespaces for Dublin Core metadata in EPUB
NAMESPACES = {
    'dc': 'http://purl.org/dc/elements/1.1/',
    'opf': 'http://www.idpf.org/2007/opf'
}


def extract_metadata_from_epub(file_path: Path) -> Dict[str, Optional[str]]:
    """
    Extract metadata from EPUB file's content.opf.
    
    Reads Dublin Core metadata:
    - dc:title → novel title
    - dc:creator → author name
    
    Args:
        file_path: Path to EPUB file
        
    Returns:
        dict with 'title' and 'author' keys (None if not found)
    """
    result = {'title': None, 'author': None}
    
    try:
        with zipfile.ZipFile(file_path, 'r') as epub:
            # Find content.opf in META-INF/container.xml
            if 'META-INF/container.xml' not in epub.namelist():
                logger.warning(f"No META-INF/container.xml found in {file_path}")
                return result
            
            # Parse container.xml to find content.opf location
            container_xml = epub.read('META-INF/container.xml')
            root = ET.fromstring(container_xml)
            
            # The rootfile element is in no namespace, but has attributes in container namespace
            # Find all rootfile elements regardless of namespace
            rootfile = None
            for elem in root.iter():
                if elem.tag.endswith('rootfile'):
                    rootfile = elem
                    break
            
            if rootfile is None:
                logger.warning(f"No rootfile found in container.xml for {file_path}")
                return result
            
            content_opf_path = rootfile.get('full-path')
            if not content_opf_path:
                logger.warning(f"No full-path attribute in rootfile for {file_path}")
                return result
            
            # Parse content.opf
            if content_opf_path not in epub.namelist():
                logger.warning(f"content.opf not found at {content_opf_path} in {file_path}")
                return result
            
            content_opf = epub.read(content_opf_path)
            opf_root = ET.fromstring(content_opf)
            
            # Extract dc:title - search in all namespaces
            title_elem = None
            for elem in opf_root.iter():
                if elem.tag.endswith('title') and '{http://purl.org/dc/elements/1.1/}' in elem.tag:
                    title_elem = elem
                    break
                elif elem.tag == 'title' and not any('}' in str(parent.tag) for parent in opf_root.iter()):
                    # Check if parent is metadata element
                    parent = list(opf_root.iter())[1] if len(list(opf_root.iter())) > 1 else None
                    if parent is not None and parent.tag.endswith('metadata'):
                        title_elem = elem
                        break
            
            # Alternative: search by text content in all elements
            if title_elem is None or not title_elem.text:
                for elem in opf_root.iter():
                    if 'title' in elem.tag.lower() and elem.text:
                        title_elem = elem
                        break
            
            if title_elem is not None and title_elem.text:
                result['title'] = title_elem.text.strip()
            
            # Extract dc:creator (author) - search in all namespaces
            creator_elem = None
            for elem in opf_root.iter():
                if elem.tag.endswith('creator') and '{http://purl.org/dc/elements/1.1/}' in elem.tag:
                    creator_elem = elem
                    break
                elif elem.tag == 'creator' and not any('}' in str(parent.tag) for parent in opf_root.iter()):
                    parent = list(opf_root.iter())[1] if len(list(opf_root.iter())) > 1 else None
                    if parent is not None and parent.tag.endswith('metadata'):
                        creator_elem = elem
                        break
            
            # Alternative: search by text content in all elements
            if creator_elem is None or not creator_elem.text:
                for elem in opf_root.iter():
                    if 'creator' in elem.tag.lower() and elem.text:
                        creator_elem = elem
                        break
            
            if creator_elem is not None and creator_elem.text:
                result['author'] = creator_elem.text.strip()
                
    except zipfile.BadZipFile:
        logger.warning(f"Invalid EPUB file (not a valid zip): {file_path}")
    except ET.ParseError as e:
        logger.warning(f"XML parse error in EPUB metadata: {e}")
    except Exception as e:
        logger.warning(f"Error extracting EPUB metadata: {e}")
    
    return result


def extract_title_from_filename(filename: str) -> str:
    """
    Extract novel title from filename (fallback method).
    
    Handles common patterns:
    - "Lord of Mysteries - Book 1.epub" → "Lord of Mysteries"
    - "infinite_mage_chapter_1.txt" → "Infinite Mage Chapter 1"
    - "my-novel.epub" → "My Novel"
    
    Args:
        filename: The uploaded filename
        
    Returns:
        Cleaned title string
    """
    if not filename or not filename.strip():
        return "Untitled Novel"
    
    # Remove file extension
    name = filename
    for ext in ['.epub', '.txt', '.pdf', '.mobi']:
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
            break
    
    # Check for " - Book " pattern and extract text before it
    book_pattern = re.compile(r'\s*-\s*Book\s+\d+', re.IGNORECASE)
    match = book_pattern.search(name)
    if match:
        name = name[:match.start()]
    
    # Replace underscores with spaces
    name = name.replace('_', ' ')
    
    # Replace hyphens surrounded by spaces with spaces
    # This handles cases like "my - novel" → "my novel"
    name = re.sub(r'\s*-\s*', ' ', name)
    
    # Clean up multiple spaces
    name = re.sub(r'\s+', ' ', name)
    
    # Strip leading/trailing whitespace
    name = name.strip()
    
    # Remove special characters from start/end of each word
    # Keep alphanumeric characters and internal spaces/hyphens
    words = name.split()
    cleaned_words = []
    for word in words:
        # Strip non-alphanumeric from start and end
        cleaned_word = re.sub(r'^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$', '', word)
        if cleaned_word:
            cleaned_words.append(cleaned_word)
    
    if not cleaned_words:
        # Return filename without extension as fallback
        fallback = filename
        for ext in ['.epub', '.txt', '.pdf', '.mobi']:
            if fallback.lower().endswith(ext):
                fallback = fallback[:-len(ext)]
                break
        return fallback.strip() if fallback.strip() else "Untitled Novel"
    
    name = ' '.join(cleaned_words)
    
    # Title case the result for consistency
    # Handle special cases like "LOTM" or acronyms
    words = name.split()
    result_words = []
    for word in words:
        # Keep acronyms as-is (all caps, 2-4 chars)
        if len(word) <= 4 and word.isupper():
            result_words.append(word)
        else:
            # Use title() instead of capitalize() to preserve internal caps
            result_words.append(word.title())
    
    return ' '.join(result_words)


def extract_metadata(file_path: Path, filename: str) -> Dict[str, Optional[str]]:
    """
    Extract metadata with fallback strategy.
    
    Strategy:
    1. If EPUB, try reading internal Dublin Core metadata
    2. If metadata extraction fails or not EPUB, parse filename
    3. Return dict with 'title' and 'author'
    
    Args:
        file_path: Path to uploaded file
        filename: Original filename
        
    Returns:
        dict with 'title' and 'author' keys
    """
    result = {'title': None, 'author': None}
    
    # Check if file is EPUB
    is_epub = file_path.suffix.lower() == '.epub'
    
    if is_epub:
        # Try EPUB metadata extraction first
        epub_metadata = extract_metadata_from_epub(file_path)
        
        # Use EPUB metadata if we got a title
        if epub_metadata.get('title') and epub_metadata['title'].strip():
            result['title'] = epub_metadata['title']
            result['author'] = epub_metadata.get('author')
            return result
    
    # Fall back to filename extraction
    title = extract_title_from_filename(filename)
    result['title'] = title
    
    # Author is not extracted from filename
    result['author'] = None
    
    return result