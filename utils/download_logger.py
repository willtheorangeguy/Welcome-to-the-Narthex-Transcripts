"""Script to extract video IDs from a podcast feed using yt-dlp
and write them to a corresponding log file."""

import os
import sys
import yt_dlp

def get_playlist_video_ids(url):
    """Given a podcast feed URL, return 
    a list of podcasts in that feed."""
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,  # Don't resolve each video fully
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_ids = []

    # Playlist entries contain "id" field when extract_flat=True
    for entry in info.get("entries", []):
        if entry and entry.get("id"):
            video_ids.append(entry["id"])

    return video_ids


if __name__ == "__main__":
    if len(sys.argv) < 3:
        playlist_input = input("Enter the podcast feed URL: ").strip()
        folder = input("Enter the folder path to save the log file: ").strip()
    else: 
        playlist_input = sys.argv[1]
        folder = sys.argv[2]

    ids = get_playlist_video_ids(playlist_input)

    # Write video IDs to 'downloaded.log'
    log_file = "downloaded.log"
    folder_path = "../" + folder # move one directory up
    log_file_path = os.path.join(folder_path, log_file)
    with open(log_file_path, "w", encoding="utf-8") as f:
        for vid in ids:
            f.write(f"youtube {vid}\n")
            print("Wrote video ID:", vid)
