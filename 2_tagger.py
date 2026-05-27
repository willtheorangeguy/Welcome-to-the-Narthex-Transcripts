import os
import sys
import re
from email.utils import parsedate_to_datetime
from urllib.request import urlopen
import xml.etree.ElementTree as ET
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, TDRC, TRCK

PODCAST_NAME = "Welcome to the Narthex"

# Log file name
LOG_FILENAME = "tagged.log"

def normalize(text):
    """Normalize strings for reliable matching."""
    text = text.lower()
    text = re.sub(r"\.mp3$", "", text) # remove .mp3 extension
    text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
    text = re.sub(r"\s+", " ", text).strip() # collapse whitespace
    return text

def fetch_playlist_data(url):
    """Fetch episode titles and dates from RSS without loading a huge yt-dlp JSON payload."""
    title_map = {}
    channel_title = ""

    try:
        with urlopen(url, timeout=30) as response:
            xml_content = response.read()
    except Exception as e:
        print(f"Failed to fetch feed {url}: {e}")
        return title_map

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Failed to parse feed XML for {url}: {e}")
        return title_map, channel_title

    channel_node = root.find(".//channel/title")
    if channel_node is not None:
        channel_title = (channel_node.text or "").strip()

    # RSS item nodes are usually channel/item; 
    # .//item handles namespace-free feeds.
    for item in root.findall(".//item"):
        title_node = item.find("title")
        pub_date_node = item.find("pubDate")

        if title_node is None or pub_date_node is None:
            continue

        title = (title_node.text or "").strip()
        pub_date = (pub_date_node.text or "").strip()
        if not title or not pub_date:
            continue

        try:
            dt = parsedate_to_datetime(pub_date)
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            title_map[normalize(title)] = dt
        except (TypeError, ValueError):
            continue

    return title_map, channel_title

def process_year_folder(folder_path, year, title_map):
    """Process all MP3 files in the given folder, 
    matching them to playlist data and updating ID3 tags."""
    files_with_dates = []

    # Path to the log file
    log_path = os.path.join(folder_path, LOG_FILENAME)

    # Read already tagged files from log
    tagged_files = set()
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as log_file:
            for line in log_file:
                tagged_files.add(line.strip())

    # Gather all MP3 files and corresponding upload dates
    for file in os.listdir(folder_path):
        if not file.lower().endswith(".mp3"):
            continue
        # Normalize filename for matching
        norm_name = normalize(file)
        # Check for matching title in playlist data
        if norm_name not in title_map:
            print(f"Skipping (no match): {file}")
            continue
        # Store full path and upload date for sorting
        full_path = os.path.join(folder_path, file)
        files_with_dates.append((full_path, title_map[norm_name]))

    # Sort by upload date
    files_with_dates.sort(key=lambda x: x[1])

    # Update ID3 tags in sorted order
    with open(log_path, "a", encoding="utf-8") as log_file:
        for idx, (filepath, date) in enumerate(files_with_dates, start=1):
            filename = os.path.basename(filepath)

            if filename in tagged_files:
                print(f"Skipping (already tagged): {filename}")
                continue

            try:
                audio = EasyID3(filepath)
                audio["artist"] = PODCAST_NAME
                audio["albumartist"] = PODCAST_NAME
                audio["album"] = year
                audio["title"] = os.path.splitext(filename)[0]
                audio["tracknumber"] = str(idx)
                audio.save(filepath)
                id3 = ID3(filepath)

                # Album date = Jan 1 of year
                id3.delall("TDRC")
                id3.add(TDRC(encoding=3, text=f"{year}-01-01"))

                # Track number
                id3.delall("TRCK")
                id3.add(TRCK(encoding=3, text=str(idx)))
                id3.save(filepath)

                log_file.write(filename + "\n")
                log_file.flush()
                tagged_files.add(filename)

                print(f"Updated: {filename} → Track {idx}")
            except Exception as e:
                print(f"Error with {filepath}: {e}")

def process_year_subfolder(top_level_folder, year_folder, title_map):
    """Process one year folder inside the top-level folder."""
    # Validate year folder name
    if re.match(r"^(19|20)\d{2}$", year_folder) is None:
        print(f"Invalid year folder name: {year_folder}")
        return
    # Construct full path to year folder
    year_path = os.path.join(top_level_folder, year_folder)
    if not os.path.isdir(year_path):
        print(f"Year folder not found: {year_path}")
        return
    print(f"Processing folder: {year_path}")
    process_year_folder(year_path, year_folder, title_map)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python 2_tagger.py <year_folder>")
        sys.exit(1)

    year_folder = sys.argv[1]
    top_level_folder = os.path.dirname(os.path.abspath(__file__))
    playlist_url = "https://media.rss.com/narthexpodcast/feed.xml"

    print("Fetching playlist metadata...")
    title_map, feed_title = fetch_playlist_data(playlist_url)
    process_year_subfolder(top_level_folder, year_folder, title_map)
