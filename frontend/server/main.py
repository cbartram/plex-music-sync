import os
import asyncio
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path
from spotdl import Spotdl
from spotdl.types.options import DownloaderOptions
from virtualenv.discovery.windows.pep514 import LOGGER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Plex Sync API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
MUSIC_DIR = os.getenv("MUSIC_DIR", "./music")
STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")

client = Spotdl(
    client_id=os.getenv("SPOTIFY_CLIENT_ID", "DEFAULT_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET", "DEFAULT_CLIENT_SECRET"),
    downloader_settings=DownloaderOptions(
        output="{artists}/{album}/{title}.{output-ext}",
        threads=4,
        max_retries=5,
    )
)

class SpotifyRequest(BaseModel):
    spotify_url: str


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
                and record.args[2] not in ["/_/health", "/_/ready"]
            )

    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    from spotdl._version import __version__
    return {
        "status": "healthy",
        "music_dir": MUSIC_DIR,
        "music_dir_exists": os.path.exists(MUSIC_DIR),
        "spotdl_version": __version__
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


async def download_spotify_content(spotify_url: str, max_attempts=3):
    """Background task to download Spotify content with retry logic"""
    for attempt in range(max_attempts):
        try:
            logger.info(f"Starting download for: {spotify_url} (Attempt {attempt + 1}/{max_attempts})")

            # Ensure music directory exists
            Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)

            # Add delay between attempts to respect rate limits
            if attempt > 0:
                wait_time = 2 ** attempt  # Exponential backoff: 2, 4, 8 seconds
                logger.info(f"Waiting {wait_time} seconds before retry...")
                await asyncio.sleep(wait_time)

            # Run spotdl
            songs = client.search([spotify_url])
            logger.info(f"Found {len(songs)} songs for URL: {spotify_url}")

            # Download with the formatted output
            results, errors = client.download_songs(songs)

            logger.info(f"Successfully downloaded {len(results)} songs")
            if errors:
                logger.warning(f"Errors encountered: {errors}")

            return results

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Download error (attempt {attempt + 1}): {error_msg}")

            # Check if it's a rate limit error
            if "429" in error_msg or "rate" in error_msg.lower():
                if attempt < max_attempts - 1:
                    # Wait longer for rate limit errors
                    wait_time = 60 * (attempt + 1)  # 60, 120, 180 seconds
                    logger.info(f"Rate limit hit. Waiting {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                    continue

            # If it's the last attempt or not a rate limit error, raise
            if attempt == max_attempts - 1:
                raise
    return None


if __name__ == "__main__":
    import uvicorn

    if not os.getenv("SPOTIFY_CLIENT_ID") or not os.getenv("SPOTIFY_CLIENT_SECRET"):
        logger.error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set in environment variables.")
        exit(1)

    logger.info("Starting API")
    register_log_filter()
    uvicorn.run(app, host="0.0.0.0", port=8000)