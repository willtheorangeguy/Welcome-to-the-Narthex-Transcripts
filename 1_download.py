"""
This script uses yt-dlp to download audio, by year, from the
Welcome to the Narthex podcast.
"""

import yt_dlp

def download_playlist(playlist_url):
    """
    Downloads all audio from the podcast site.
    """
    ydl_opts = {
        "format": "bestaudio",
        "noplaylist": False,
        "ignoreerrors": True,
        "download_archive": "downloaded.log",
        "outtmpl": "%(upload_date>%Y)s/%(title)s.%(ext)s",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        ],
        'concurrent-fragments': True,
        'no-mtime': True,
        'playlistend': 10
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([playlist_url])


if __name__ == "__main__":
    playlist = "https://media.rss.com/narthexpodcast/feed.xml"
    download_playlist(playlist)
    print("Downloaded all audio from the Welcome to the Narthex podcast feed.")
