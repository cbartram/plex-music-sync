import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Music, Loader2, CheckCircle, XCircle } from 'lucide-react';

export default function SpotifyPlexApp() {
  const [spotifyUrl, setSpotifyUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ type: '', message: '' });

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    setLoading(true);
    setStatus({ type: '', message: '' });

    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ spotify_url: spotifyUrl }),
      });

      const data = await response.json();

      if (response.ok) {
        setStatus({
          type: 'success',
          message: data.message || 'Download started successfully!',
        });
        setSpotifyUrl('');
      } else {
        setStatus({
          type: 'error',
          message: data.detail || 'Failed to start download',
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: 'Failed to connect to backend service',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <div className="bg-slate-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-slate-700">
          <div className="flex items-center justify-center mb-8">
            <Music className="w-12 h-12 text-green-500 mr-3" />
            <h1 className="text-4xl font-bold text-white">
              Spotify to Plex
            </h1>
          </div>

          <p className="text-slate-300 text-center mb-8">
            Download Spotify songs and playlists directly to your Plex music library
          </p>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="spotify-url" className="block text-sm font-medium text-slate-300 mb-2">
                Spotify URL
              </label>
              <Input
                id="spotify-url"
                type="text"
                placeholder="https://open.spotify.com/track/... or playlist/..."
                value={spotifyUrl}
                onChange={(e) => setSpotifyUrl(e.target.value)}
                disabled={loading}
                className="bg-slate-700/50 border-slate-600 text-white placeholder:text-slate-400 focus:border-green-500 focus:ring-green-500"
              />
              <p className="text-xs text-slate-400 mt-2">
                Paste a Spotify track or playlist URL
              </p>
            </div>

            <Button
              type="submit"
              disabled={!spotifyUrl || loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-6 text-lg"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Downloading...
                </>
              ) : (
                <>
                  <Music className="mr-2 h-5 w-5" />
                  Download to Plex
                </>
              )}
            </Button>
          </form>

          {status.message && (
            <Alert
              className={`mt-6 ${
                status.type === 'success'
                  ? 'bg-green-900/30 border-green-700 text-green-300'
                  : 'bg-red-900/30 border-red-700 text-red-300'
              }`}
            >
              {status.type === 'success' ? (
                <CheckCircle className="h-4 w-4" />
              ) : (
                <XCircle className="h-4 w-4" />
              )}
              <AlertDescription>{status.message}</AlertDescription>
            </Alert>
          )}

          <div className="mt-8 pt-6 border-t border-slate-700">
            <h3 className="text-sm font-semibold text-slate-300 mb-3">How to use:</h3>
            <ol className="text-sm text-slate-400 space-y-2">
              <li>1. Copy a Spotify track or playlist URL</li>
              <li>2. Paste it in the input field above</li>
              <li>3. Click "Download to Plex"</li>
              <li>4. Wait for the download to complete</li>
              <li>5. Refresh your Plex library to see the new music</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}