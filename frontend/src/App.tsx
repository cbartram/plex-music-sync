import { useState, useEffect, useRef } from 'react';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Music, Loader2, Terminal, CheckCircle, XCircle, Lock } from 'lucide-react';

interface JobStatus {
  status: 'processing' | 'completed' | 'failed';
  logs: string[];
  result?: string;
  error?: string;
}

export default function SpotifyPlexApp() {
  const [spotifyUrl, setSpotifyUrl] = useState('');
  const [authKey, setAuthKey] = useState('');
  const [loading, setLoading] = useState(false); // Controls the "Start" button state

  // Job State
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<JobStatus | null>(null);

  // UI Refs
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const savedKey = localStorage.getItem('plex_spotdl_auth_key');
    if (savedKey) setAuthKey(savedKey);
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [jobState?.logs]);

  // Polling Logic
  useEffect(() => {
    let intervalId: number;

    if (activeJobId && jobState?.status !== 'completed' && jobState?.status !== 'failed') {
      intervalId = setInterval(async () => {
        try {
          const response = await fetch(`/api/jobs/${activeJobId}`, {
            headers: { 'X-API-Key': authKey }
          });
          if (response.ok) {
            const data = await response.json();
            setJobState(data);

            // If finished, stop loading indicator on button
            if (data.status === 'completed' || data.status === 'failed') {
              setLoading(false);
            }
          }
        } catch (e) {
          console.error("Failed to poll job status");
        }
      }, 2000); // Poll every 2 seconds
    }

    return () => clearInterval(intervalId);
  }, [activeJobId, jobState?.status, authKey]);

  const handleAuthChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setAuthKey(value);
    localStorage.setItem('plex_spotdl_auth_key', value);
  };

  const handleSubmit = async (e: any) => {
    e.preventDefault();
    setLoading(true);
    setJobState(null);
    setActiveJobId(null);

    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accepts': 'application/json',
          'X-API-Key': authKey
        },
        body: JSON.stringify({ spotify_url: spotifyUrl }),
      });

      const data = await response.json();

      if (response.ok) {
        // Success: Store Job ID to start polling
        setActiveJobId(data.job_id);
        setSpotifyUrl('');
        setJobState({ status: 'processing', logs: ['Initializing job...'] });
      } else {
        setLoading(false);
        setJobState({
            status: 'failed',
            logs: [],
            error: data.detail || 'Failed to initiate download'
        });
      }
    } catch (error) {
      setLoading(false);
      setJobState({
          status: 'failed',
          logs: [],
          error: 'Failed to connect to backend service'
      });
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-2xl">
        <div className="bg-slate-800/50 backdrop-blur-lg rounded-2xl shadow-2xl p-8 border border-slate-700">
          <div className="flex items-center justify-center mb-8">
            <Music className="w-12 h-12 text-green-500 mr-3" />
            <h1 className="text-4xl font-bold text-white">
              Spotify Plex Sync
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Auth Key Input */}
            <div>
              <label htmlFor="auth-key" className="block text-sm font-medium text-slate-300 mb-2">
                Server Auth Key
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <Input
                  id="auth-key"
                  type="password"
                  placeholder="Enter secret API key..."
                  value={authKey}
                  onChange={handleAuthChange}
                  className="pl-9 bg-slate-700/50 border-slate-600 text-white placeholder:text-slate-400 focus:border-indigo-500 focus:ring-indigo-500"
                />
              </div>
            </div>

            {/* Spotify URL Input */}
            <div>
              <label htmlFor="spotify-url" className="block text-sm font-medium text-slate-300 mb-2">
                Spotify URL
              </label>
              <Input
                id="spotify-url"
                type="text"
                placeholder="https://open.spotify.com/track/..."
                value={spotifyUrl}
                onChange={(e) => setSpotifyUrl(e.target.value)}
                disabled={loading}
                className="bg-slate-700/50 border-slate-600 text-white placeholder:text-slate-400 focus:border-green-500 focus:ring-green-500"
              />
            </div>

            <Button
              type="submit"
              disabled={!spotifyUrl || !authKey || loading}
              className="w-full bg-green-600 hover:bg-green-700 text-white font-semibold py-6 text-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  <Music className="mr-2 h-5 w-5" />
                  Download to Plex
                </>
              )}
            </Button>
          </form>

          {/* STATUS & LOGS AREA */}
          {jobState && (
            <div className="mt-8 animate-in fade-in slide-in-from-bottom-4 duration-500">

                {/* Status Header */}
                <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center space-x-2">
                        <Terminal className="w-4 h-4 text-slate-400" />
                        <span className="text-sm font-medium text-slate-300">Live Logs</span>
                    </div>

                    <div className="flex items-center space-x-2">
                        {jobState.status === 'processing' && <span className="text-xs text-yellow-400 animate-pulse">Running...</span>}
                        {jobState.status === 'completed' && <span className="text-xs text-green-400 flex items-center"><CheckCircle className="w-3 h-3 mr-1"/> Done</span>}
                        {jobState.status === 'failed' && <span className="text-xs text-red-400 flex items-center"><XCircle className="w-3 h-3 mr-1"/> Failed</span>}
                    </div>
                </div>

                {/* Log Terminal Window */}
                <div className="bg-black/80 rounded-lg p-4 font-mono text-sm h-64 overflow-y-auto border border-slate-700 shadow-inner">
                    <div className="space-y-1">
                        {jobState.logs.map((log, i) => (
                            <div key={i} className="text-slate-300 break-all border-l-2 border-slate-800 pl-2 hover:border-slate-600 transition-colors">
                                <span className="text-green-500/50 mr-2">{'>'}</span>
                                {log}
                            </div>
                        ))}
                        {jobState.error && (
                            <div className="text-red-400 font-bold mt-2">
                                Error: {jobState.error}
                            </div>
                        )}
                        {/* Invisible element to auto-scroll to */}
                        <div ref={logsEndRef} />
                    </div>
                </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}