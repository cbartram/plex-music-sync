# Plex Stbc Downloader

A Kubernetes-native application that downloads Spotify songs and playlists to your Plex music library using SpotDL.
Architecture

- Frontend: React + Vite + ShadCN UI + Tailwind CSS
- Backend: Python FastAPI with SpotDL integration
- Deployment: Kubernetes with Helm charts
- Storage: Shared PVC with existing Plex server

## Prerequisites

Kubernetes cluster with existing Plex deployment
Helm 3.x
Docker for building images
Container registry (Docker Hub, Harbor, etc.)

# Check services

`kubectl get svc -n plex`

# Check ingress

`kubectl get ingress -n plex`

# Check backend health

```
kubectl port-forward -n plex svc/spotify-plex-backend 8000:8000
curl http://localhost:8000/health
```

## Usage

Access the web interface at your configured domain (e.g., https://spotify-plex.kraken-plugins.com)
Paste a Spotify track or playlist URL
Click "Download to Plex"
The backend will download the music to /music directory
Plex will automatically scan and add the new music

## Configuration
Backend Environment Variables

- MUSIC_DIR: Directory where music files are stored (default: /music)
- SPOTDL_PATH: Path to spotdl binary (default: spotdl)

## Frontend Proxy

The frontend nginx configuration proxies /api requests to the backend service.
Shared Storage
The backend deployment mounts the same PVC (plex-music-pvc) used by Plex:
Both Plex and the backend have read/write access to the /music directory.

## Troubleshooting
Backend Pod Not Starting

`kubectl logs -n plex deployment/spotify-plex-backend`

# Check if SpotDL is installed

`kubectl exec -n plex deployment/spotify-plex-backend -- spotdl --version`

Downloads Not Appearing in Plex
Check if files are being written:

`kubectl exec -n plex deployment/spotify-plex-backend -- ls -la /music`

Verify PVC is mounted correctly:

`kubectl describe pod -n plex <backend-pod-name>`

Manually trigger Plex library scan in Plex settings

## Permission Issues
Ensure the backend container has write permissions to the PVC:

`kubectl exec -n plex deployment/spotify-plex-backend -- touch /music/test.txt`

## Development
Run Frontend Locally
```
cd frontend
npm install
npm run dev
```

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
