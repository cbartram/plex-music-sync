import os
import asyncio
import logging
import time
# Added Security, Depends, status
from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends, status
from fastapi.security import APIKeyHeader  # Added APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from pydantic import BaseModel
from pathlib import Path
from spotdl import Spotdl
from spotdl.types.options import DownloaderOptions
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MUSIC_DIR = os.getenv("MUSIC_DIR", "./music")
STATIC_DIR = os.getenv("STATIC_DIR", "/app/static")
COOKIES_FILE = os.getenv("COOKIES_FILE", "/app/cookies.txt")
APP_AUTH_KEY = os.getenv("APP_AUTH_KEY", "DEFAULT_APP_AUTH_KEY_WILL_NOT_WORK_IN_PROD")
API_KEY_NAME = "X-API-Key"

_spotdl_client = None
_client_lock = threading.Lock()

app = FastAPI(title="Plex Sync API", version="1.0.0")
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == APP_AUTH_KEY:
        return api_key_header
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate credentials"
    )


def register_log_filter() -> None:
    class EndpointFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return (
                    record.args
                    and len(record.args) >= 3
                    and record.args[2] not in ["/health", "/ready"]
            )

    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


register_log_filter()

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
    global _spotdl_client
    with _client_lock:
        if _spotdl_client is None:
            cookies = read_cookies_files()
            if cookies is None:
                raise Exception("Failed to read cookies.txt file contents.")
            po_token = ""
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


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/download", dependencies=[Depends(get_api_key)])
async def download_spotify(
        request: SpotifyRequest,
        background_tasks: BackgroundTasks
):
    """
    Download Spotify track or playlist to Plex music directory
    """
    if not ("spotify.com" in request.spotify_url):
        logger.error(f"Invalid Spotify URL received: {request.spotify_url}")
        pass

    if not ("spotify.com" in request.spotify_url):
        raise HTTPException(status_code=400, detail="Invalid Spotify URL.")

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


# Mount static files
app.mount("/assets", StaticFiles(directory=f"{STATIC_DIR}/assets"), name="assets")
if os.path.exists(f"{STATIC_DIR}/docs"):
    app.mount("/docs", StaticFiles(directory=f"{STATIC_DIR}/docs", html=True), name="docs")


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    file_path = Path(STATIC_DIR) / full_path
    if file_path.is_file():
        return FileResponse(file_path)
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
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    client = get_or_create_spotdl_client()

    for attempt in range(max_attempts):
        try:
            logger.info(f"Starting download for: {spotify_url} (Attempt {attempt + 1}/{max_attempts})")
            Path(MUSIC_DIR).mkdir(parents=True, exist_ok=True)

            if attempt > 0:
                time.sleep(2 ** attempt)

            songs = client.search([spotify_url])
            logger.info(f"Found {len(songs)} songs for URL: {spotify_url}")
            results = client.download_songs(songs)
            logger.info(f"Successfully downloaded {len(results)} songs")
            loop.close()
            return results
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Download error: {error_msg}")
            if "429" in error_msg or "rate" in error_msg.lower():
                if attempt < max_attempts - 1:
                    time.sleep(60 * (attempt + 1))
                    continue
            if attempt == max_attempts - 1:
                loop.close()
                raise
    loop.close()
    return None


if __name__ == "__main__":
    if not os.getenv("SPOTIFY_CLIENT_ID") or not os.getenv("SPOTIFY_CLIENT_SECRET"):
        logger.error("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set")
        exit(1)

    logger.info("Starting API")
    uvicorn.run(app, host="0.0.0.0", port=8000)