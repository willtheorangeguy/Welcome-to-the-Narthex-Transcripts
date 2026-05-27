"""Script to sort downloaded podcast files into year-based folders.

This script parses podcast RSS/XML feeds to extract episode metadata (title, date, URL)
and moves already-downloaded podcast files into subdirectories organized by year.

Usage:
    python download_sorter.py <xml_feed_path> <podcast_folder_path>

Example:
    python download_sorter.py "The Changelog.xml" "The Changelog"
"""

import argparse
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_rss_feed(xml_path: str) -> List[Dict]:
    """Parse RSS/XML feed and extract episode information.
    
    Args:
        xml_path: Path to the XML feed file
        
    Returns:
        List of dictionaries containing episode metadata:
        - title: Episode title
        - pub_date: Publication date (datetime object)
        - year: Publication year (int)
        - url: Episode URL or identifier
        - guid: Episode GUID (if available)
        - enclosure_url: Direct media file URL (if available)
    """
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        episodes = []
        
        # Try RSS 2.0 format first
        for item in root.findall('.//item'):
            title_elem = item.find('title')
            pubdate_elem = item.find('pubDate')
            link_elem = item.find('link')
            guid_elem = item.find('guid')
            enclosure_elem = item.find('enclosure')
            
            if title_elem is None or pubdate_elem is None:
                continue
                
            title = title_elem.text.strip() if title_elem.text else ""
            pub_date_str = pubdate_elem.text.strip() if pubdate_elem.text else ""
            
            # Parse publication date
            try:
                # Common RSS date formats
                for date_format in [
                    "%a, %d %b %Y %H:%M:%S %z",  # RFC 822
                    "%a, %d %b %Y %H:%M:%S %Z",
                    "%Y-%m-%dT%H:%M:%S%z",       # ISO 8601
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d",
                ]:
                    try:
                        pub_date = datetime.strptime(pub_date_str, date_format)
                        break
                    except ValueError:
                        continue
                else:
                    # If all formats fail, try parsing with a more flexible approach
                    pub_date = datetime.fromisoformat(pub_date_str.replace(' GMT', '+0000').replace(' +0000', '+0000'))
            except (ValueError, AttributeError) as e:
                print(f"Warning: Could not parse date '{pub_date_str}' for episode '{title}': {e}")
                continue
                
            episode_data = {
                'title': title,
                'pub_date': pub_date,
                'year': pub_date.year,
                'url': link_elem.text.strip() if link_elem is not None and link_elem.text else "",
                'guid': guid_elem.text.strip() if guid_elem is not None and guid_elem.text else "",
                'enclosure_url': enclosure_elem.get('url', '') if enclosure_elem is not None else ""
            }
            
            episodes.append(episode_data)
        
        print(f"Successfully parsed {len(episodes)} episodes from feed")
        return episodes
        
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        sys.exit(1)
    except (FileNotFoundError, OSError) as e:
        print(f"Error reading feed file: {e}")
        sys.exit(1)


def normalize_filename(filename: str) -> str:
    """Normalize filename for matching by removing special characters and lowercasing.
    
    Args:
        filename: Original filename
        
    Returns:
        Normalized filename string
    """
    # Remove file extension
    name = os.path.splitext(filename)[0]
    # Convert to lowercase and remove special characters
    name = re.sub(r'[^\w\s-]', '', name.lower())
    # Replace multiple spaces with single space
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def extract_url_identifier(url: str) -> str:
    """Extract a unique identifier from a podcast URL.
    
    Args:
        url: Episode URL (e.g., 'changelog.com/1/2677')
        
    Returns:
        Identifier string (e.g., 'changelog.com/1/2677')
    """
    # Remove protocol and 'www.'
    url = re.sub(r'^https?://(www\.)?', '', url)
    # Remove trailing slashes
    url = url.rstrip('/')
    return url


def match_file_to_episode(filename: str, episodes: List[Dict]) -> Optional[Dict]:
    """Match a downloaded file to an episode in the feed.
    
    Args:
        filename: Name of the downloaded file
        episodes: List of episode metadata dictionaries
        
    Returns:
        Matching episode dictionary or None if no match found
    """
    # Try to extract URL identifier from filename
    # Changelog format: [Title] (Type) [changelog.com/1/123].mp3
    # Also handles special characters like ⧸ (instead of /) and ： (instead of :)
    url_match = re.search(r'\[([^\]]+)\]\.(mp3|m4a|opus|ogg|wav|flac)$', filename, re.IGNORECASE)
    
    if url_match:
        file_url_id = url_match.group(1).replace('⧸', '/').replace('：', ':')
        
        # Try to match by URL identifier
        for episode in episodes:
            # Check guid first (most reliable for Changelog feeds)
            if episode.get('guid'):
                guid_normalized = episode['guid'].replace('⧸', '/').replace('：', ':')
                if file_url_id == guid_normalized or file_url_id in guid_normalized or guid_normalized in file_url_id:
                    return episode
            
            # Check URL
            episode_url_id = extract_url_identifier(episode['url'])
            if file_url_id in episode_url_id or episode_url_id in file_url_id:
                return episode
                
            # Also check enclosure URL if available
            if episode.get('enclosure_url'):
                enclosure_url_id = extract_url_identifier(episode['enclosure_url'])
                if file_url_id in enclosure_url_id or enclosure_url_id in file_url_id:
                    return episode
    
    # Fallback: Try to match by title (less reliable)
    normalized_filename = normalize_filename(filename)
    
    best_match = None
    best_score = 0
    
    for episode in episodes:
        normalized_title = normalize_filename(episode['title'])
        
        # Calculate similarity score (simple word overlap)
        file_words = set(normalized_filename.split())
        title_words = set(normalized_title.split())
        
        if title_words:
            overlap = len(file_words & title_words)
            score = overlap / len(title_words)
            
            if score > best_score and score > 0.5:  # At least 50% overlap
                best_score = score
                best_match = episode
    
    return best_match


def organize_podcasts(xml_path: str, podcast_folder: str, dry_run: bool = False) -> None:
    """Organize podcast files into year-based subdirectories.
    
    Args:
        xml_path: Path to the XML feed file
        podcast_folder: Path to the folder containing downloaded podcasts
        dry_run: If True, only print what would be done without moving files
    """
    # Parse the feed
    print(f"Parsing feed: {xml_path}")
    episodes = parse_rss_feed(xml_path)
    
    if not episodes:
        print("No episodes found in feed")
        sys.exit(1)
    
    # Get list of files in podcast folder
    podcast_path = Path(podcast_folder)
    if not podcast_path.exists():
        print(f"Error: Podcast folder '{podcast_folder}' does not exist")
        sys.exit(1)
    
    # Get all audio files (not in subdirectories)
    audio_extensions = {'.mp3', '.m4a', '.opus', '.ogg', '.wav', '.flac'}
    files = [f for f in podcast_path.iterdir() 
             if f.is_file() and f.suffix.lower() in audio_extensions]
    
    print(f"Found {len(files)} audio files in folder")
    
    # Match files to episodes and organize by year
    year_files: Dict[int, List[Tuple[Path, Dict]]] = defaultdict(list)
    unmatched_files = []
    
    for file in files:
        episode = match_file_to_episode(file.name, episodes)
        
        if episode:
            year_files[episode['year']].append((file, episode))
        else:
            unmatched_files.append(file)
    
    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total files to organize: {len(files)}")
    print(f"Matched files: {len(files) - len(unmatched_files)}")
    print(f"Unmatched files: {len(unmatched_files)}")
    
    if year_files:
        print("\nFiles by year:")
        for year in sorted(year_files.keys()):
            print(f"  {year}: {len(year_files[year])} files")
    
    if unmatched_files:
        print("\nUnmatched files (will not be moved):")
        for file in unmatched_files[:10]:  # Show first 10
            print(f"  - {file.name}")
        if len(unmatched_files) > 10:
            print(f"  ... and {len(unmatched_files) - 10} more")
    
    # Move files
    if not dry_run:
        print("\n" + "=" * 70)
        print("MOVING FILES")
        print("=" * 70)
        
        moved_count = 0
        error_count = 0
        
        for year, file_list in sorted(year_files.items()):
            year_folder = podcast_path / str(year)
            year_folder.mkdir(exist_ok=True)
            print(f"\nProcessing year {year}...")
            
            for file, episode in file_list:
                dest_path = year_folder / file.name
                
                try:
                    # Check if destination already exists
                    if dest_path.exists():
                        print(f"  Skipping {file.name} (already exists in {year}/)")
                        continue
                    
                    shutil.move(str(file), str(dest_path))
                    moved_count += 1
                    print(f"  Moved: {file.name} -> {year}/")
                    
                except (OSError, PermissionError, shutil.Error) as e:
                    print(f"  Error moving {file.name}: {e}")
                    error_count += 1
        
        print("\n" + "=" * 70)
        print(f"Completed: {moved_count} files moved, {error_count} errors")
        print("=" * 70)
    else:
        print("\n[DRY RUN] No files were actually moved.")
        print("Run without --dry-run to perform the actual file moves.")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Organize podcast files into year-based folders using XML feed data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python download_sorter.py feed.xml "Podcast Folder"
  python download_sorter.py --dry-run changelog.xml "The Changelog"
        """
    )
    
    parser.add_argument(
        'xml_feed',
        help='Path to the podcast RSS/XML feed file'
    )
    
    parser.add_argument(
        'podcast_folder',
        help='Path to the folder containing downloaded podcast files'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without actually moving files'
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.xml_feed):
        print(f"Error: XML feed file '{args.xml_feed}' not found")
        sys.exit(1)
    
    if not os.path.exists(args.podcast_folder):
        print(f"Error: Podcast folder '{args.podcast_folder}' not found")
        sys.exit(1)
    
    # Run the organizer
    try:
        organize_podcasts(args.xml_feed, args.podcast_folder, args.dry_run)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(0)
    except (RuntimeError, ValueError) as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

