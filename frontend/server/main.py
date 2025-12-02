import os
import asyncio
import logging
import time
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from pydantic import BaseModel
from pathlib import Path
from spotdl import Spotdl
from spotdl.types.options import DownloaderOptions

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MUSIC_DIR = os.getenv("MUSIC_DIR", "./music")
STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")
COOKIES_FILE = os.getenv("COOKIES_FILE", "/app/cookies.txt")

_spotdl_client = None
_client_lock = asyncio.Lock()
app = FastAPI(title="Plex Sync API", version="1.0.0")

def register_log_filter() -> None:
    """
    Removes logs from healthiness/readiness endpoints so they don't spam
    and pollute application log flow
    """

    class EndpointFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return (
                    record.args
                    and len(record.args) >= 3
                    and record.args[2] not in ["/health", "/ready"]
            )

    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

register_log_filter()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SpotifyRequest(BaseModel):
    spotify_url: str


def get_or_create_spotdl_client():
    """Get or create a singleton Spotdl client"""
    global _spotdl_client

    with _client_lock:
        if _spotdl_client is None:
            cookies = read_cookies_files()
            if cookies is None:
                raise Exception("Failed to read cookies.txt file contents.")

            po_token = ""  # TODO Need to generate this

            _spotdl_client = Spotdl(
                client_id=os.getenv("SPOTIFY_CLIENT_ID"),
                client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
                downloader_settings=DownloaderOptions(
                    output=MUSIC_DIR + "/{artists}/{album}/{title}.{output-ext}",
                    threads=4,
                    cookie_file=cookies,
                    yt_dlp_args=f"--extractor-args \"youtube:player_client=web_music,default;po_token=web_music+{po_token}\""
                ),
            )

        return _spotdl_client


# API Routes
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
    }


@app.post("/api/download")
async def download_spotify(
        request: SpotifyRequest,
        background_tasks: BackgroundTasks
):
    """
    Download Spotify track or playlist to Plex music directory
    """
    if not ("spotify.com" in request.spotify_url):
        raise HTTPException(
            status_code=400,
            detail="Invalid Spotify URL. Must be a spotify.com link."
        )

    if not os.path.exists(MUSIC_DIR):
        try:
            Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cannot access music directory: {str(e)}"
            )

    background_tasks.add_task(download_spotify_content, request.spotify_url)

    return {
        "status": "started",
        "message": "Download started. Check logs for progress.",
        "spotify_url": request.spotify_url,
        "music_dir": MUSIC_DIR
    }


# Mount static files for assets (JS, CSS, images, etc.)
# This must come before the catch-all route
app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")

# If you have a docs directory
if os.path.exists(f"{STATIC_DIR}/docs"):
    app.mount("/docs", StaticFiles(directory=f"{STATIC_DIR}/docs", html=True), name="docs")


# Catch-all route for SPA - this must be last
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """
    Serve the React SPA for all non-API routes.
    This enables client-side routing.
    """
    # Try to serve the requested file if it exists
    file_path = Path(STATIC_DIR) / full_path

    # If it's a file and exists, serve it
    if file_path.is_file():
        return FileResponse(file_path)

    # Otherwise, serve index.html for SPA routing
    index_path = Path(STATIC_DIR) / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")

def read_cookies_files() -> None:
    try:
        with open(COOKIES_FILE, 'r') as file:
            return file.read()
    except FileNotFoundError:
        logger.error("Error: The /app/cookies.txt file was not found.")
    except Exception as e:
        logger.error(f"An error occurred while attempting to read the cookie file: {e}")
    return None


def download_spotify_content(spotify_url: str, max_attempts: int = 3):
    """Background task to download Spotify content with retry logic"""
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    client = get_or_create_spotdl_client()

    for attempt in range(max_attempts):
        try:
            logger.info(f"Starting download for: {spotify_url} (Attempt {attempt + 1}/{max_attempts})")
            Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)

            if attempt > 0:
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)

            songs = client.search([spotify_url])
            logger.info(f"Found {len(songs)} songs for URL: {spotify_url}")
            results = client.download_songs(songs)
            logger.info(f"Successfully downloaded {len(results)} songs")

            loop.close()
            return results
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Download error (attempt {attempt + 1}): {error_msg}")

            if "429" in error_msg or "rate" in error_msg.lower():
                if attempt < max_attempts - 1:
                    wait_time = 60 * (attempt + 1)
                    logger.info(f"Rate limit hit. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue

            if attempt == max_attempts - 1:
                loop.close()
                raise

    loop.close()
    return None


if __name__ == "__main__":
    if not os.getenv("SPOTIFY_CLIENT_ID") or not os.getenv("SPOTIFY_CLIENT_SECRET"):
        logger.error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in environment variables.")
        exit(1)

    logger.info("Starting API")
    uvicorn.run(app, host="0.0.0.0", port=8000)