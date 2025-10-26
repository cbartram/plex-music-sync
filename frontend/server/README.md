# Plex Spotify Downloader

A Kubernetes-native application that downloads Spotify songs and playlists to your Plex music library using SpotDL.
Architecture

- Frontend: React + Vite + ShadCN UI + Tailwind CSS
- Backend: Python FastAPI with SpotDL integration
- Deployment: Kubernetes with Helm charts
- Storage: Shared PVC with existing Plex server


## Building

```shell
docker build . -t cbartram/spotify-plex-sync:latest
docker push cbartram/spotify-plex-sync:latest
```

## Running Locally

```shell
SPOTDL_PATH=./bin/spotdl-4.4.3-win32.exe
STATIC_DIR=../dist

python3 -m main

# Server available on http://localhost:8000
````

Run Frontend Locally

```
cd frontend
npm install
npm run dev
```

## Configuration
Backend Environment Variables

- MUSIC_DIR: Directory where music files are stored (default: /music)
- SPOTDL_PATH: Path to spotdl binary (default: spotdl)

## Run Backend Locally

```
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

# License
MIT

## Credits

- SpotDL - Spotify downloader
- Plex - Media server
- ShadCN UI - UI components
