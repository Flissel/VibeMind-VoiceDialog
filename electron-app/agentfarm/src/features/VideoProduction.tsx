import { useState, useEffect, useCallback } from 'react'
import type { VideoStatusResponse, VideoToolResult, VideoFileInfo, VideoListResponse } from '../types'

const api = () => (window as any).vibemindAgentFarm

const TEAM_STEPS = ['analyze', 'backgrounds', 'composite', 'build', 'split', 'final']

export function VideoProduction() {
  const [status, setStatus] = useState<VideoStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState<string | null>(null)
  const [result, setResult] = useState<VideoToolResult | null>(null)

  // Team inputs
  const [selectedStep, setSelectedStep] = useState('all')

  // Demo inputs
  const [demoFile, setDemoFile] = useState('')
  const [demoDuration, setDemoDuration] = useState('60')
  const [demoConfig, setDemoConfig] = useState('')

  // Lipsync / Voice inputs
  const [personName, setPersonName] = useState('')

  // Vision inputs
  const [visionMode, setVisionMode] = useState('all')

  useEffect(() => { loadStatus() }, [])

  async function loadStatus() {
    setLoading(true)
    try {
      const res = await api()?.videoStatus?.()
      setStatus(res || null)
    } catch {
      setStatus(null)
    }
    setLoading(false)
  }

  async function runAction(action: string, params?: Record<string, unknown>) {
    setRunning(action)
    setResult(null)
    try {
      let res: VideoToolResult
      switch (action) {
        case 'team_run':
          res = await api().videoTeamRun(params?.step || 'all')
          break
        case 'vision':
          res = await api().videoVision(params)
          break
        case 'demo_analyze':
          res = await api().videoDemoAnalyze(params?.input_file, params?.target_duration)
          break
        case 'demo_build':
          res = await api().videoDemoBuild(params?.config_path)
          break
        case 'lipsync':
          res = await api().videoLipsync(params?.person || undefined)
          break
        case 'lipsync_analyze':
          res = await api().videoLipsyncAnalyze()
          break
        case 'voice_clone':
          res = await api().videoVoiceClone()
          break
        case 'voice_tts':
          res = await api().videoVoiceTts(params?.person || undefined)
          break
        default:
          res = { success: false, message: `Unknown action: ${action}` }
      }
      setResult(res)
    } catch (e: any) {
      setResult({ success: false, message: e.message })
    }
    setRunning(null)
  }

  if (loading) {
    return <div style={{ color: 'var(--text-tertiary)', padding: 'var(--space-6)' }}>Loading video tools...</div>
  }

  const hasVibevideo = status?.vibevideo_installed ?? false
  const hasDeepfake = status?.deepfake_installed ?? false

  return (
    <div className="flex flex-col gap-4">
      {/* Status Header */}
      <div className="flex items-center gap-4" style={{ marginBottom: 'var(--space-2)' }}>
        <h2 style={{ fontSize: 'var(--text-title3)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', margin: 0 }}>
          Video Production
        </h2>
        <div className="flex gap-2">
          <StatusBadge ok={hasVibevideo} label="vibevideo" />
          <StatusBadge ok={hasDeepfake} label="deepfake" />
        </div>
        <div style={{ flex: 1 }} />
        <button onClick={loadStatus} style={linkBtnStyle}>Refresh</button>
      </div>

      {/* ── VIDEO GALLERY ─────────────────────────── */}
      <VideoGallery />

      {/* ── TEAM VIDEO PIPELINE ─────────────────────── */}
      <Section
        title="Team Video Pipeline"
        desc="Analyze, Sora Backgrounds, Composite, Build, Split-Screen, Final Cut"
        available={hasVibevideo}
      >
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Label>Step</Label>
            <select value={selectedStep} onChange={e => setSelectedStep(e.target.value)} style={selectStyle}>
              <option value="all">All Steps (full pipeline)</option>
              {TEAM_STEPS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <ActionButton
            label={`Run ${selectedStep === 'all' ? 'Full Pipeline' : selectedStep}`}
            running={running === 'team_run'}
            onClick={() => runAction('team_run', { step: selectedStep })}
          />
        </div>
      </Section>

      {/* ── VISION VIDEO ────────────────────────────── */}
      <Section
        title="Vision Video"
        desc="Her-style cinematic video — Sora AI scenes + Rachel dialog + TTS"
        available={hasVibevideo}
      >
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Label>Mode</Label>
            <select value={visionMode} onChange={e => setVisionMode(e.target.value)} style={selectStyle}>
              <option value="all">Full Pipeline (Sora + TTS + Build)</option>
              <option value="generate_sora">Generate Sora Scenes Only</option>
              <option value="generate_tts">Generate TTS Audio Only</option>
              <option value="build_only">Build Video Only (from existing assets)</option>
            </select>
          </div>
          <ActionButton
            label="Generate Vision Video"
            running={running === 'vision'}
            onClick={() => runAction('vision', { [visionMode]: true })}
          />
        </div>
      </Section>

      {/* ── PRODUCT DEMO ────────────────────────────── */}
      <Section
        title="Product Demo"
        desc="Auto-scene detection, AI labels, TTS voiceover from screenrecording"
        available={hasVibevideo}
      >
        <div className="flex flex-col gap-3">
          {/* Analyze */}
          <div style={{ borderBottom: '1px solid var(--separator)', paddingBottom: 'var(--space-3)' }}>
            <div style={{ fontSize: 'var(--text-caption1)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
              1. Analyze Screenrecording
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Label>Video File</Label>
                <input
                  value={demoFile}
                  onChange={e => setDemoFile(e.target.value)}
                  placeholder="C:\path\to\screenrecording.mp4"
                  style={inputStyle}
                />
              </div>
              <div className="flex items-center gap-2">
                <Label>Duration (s)</Label>
                <input
                  value={demoDuration}
                  onChange={e => setDemoDuration(e.target.value)}
                  placeholder="60"
                  type="number"
                  style={{ ...inputStyle, width: 80 }}
                />
              </div>
              <ActionButton
                label="Analyze"
                running={running === 'demo_analyze'}
                disabled={!demoFile.trim()}
                onClick={() => runAction('demo_analyze', { input_file: demoFile, target_duration: parseInt(demoDuration) || 60 })}
              />
            </div>
          </div>
          {/* Build */}
          <div>
            <div style={{ fontSize: 'var(--text-caption1)', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
              2. Build Demo Video
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Label>Scene Config</Label>
                <input
                  value={demoConfig}
                  onChange={e => setDemoConfig(e.target.value)}
                  placeholder="path/to/scenes.json (from analyze step)"
                  style={inputStyle}
                />
              </div>
              <ActionButton
                label="Build Demo"
                running={running === 'demo_build'}
                disabled={!demoConfig.trim()}
                onClick={() => runAction('demo_build', { config_path: demoConfig })}
              />
            </div>
          </div>
        </div>
      </Section>

      {/* ── LIP SYNC ────────────────────────────────── */}
      <Section
        title="Lip Sync (MuseTalk)"
        desc="AI lip sync on team videos — runs per person or all at once"
        available={hasDeepfake}
      >
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Label>Person</Label>
            <input
              value={personName}
              onChange={e => setPersonName(e.target.value)}
              placeholder="(leer = alle Personen)"
              style={inputStyle}
            />
          </div>
          <div className="flex gap-2">
            <ActionButton
              label={personName ? `Lip Sync: ${personName}` : 'Lip Sync All'}
              running={running === 'lipsync'}
              onClick={() => runAction('lipsync', { person: personName || undefined })}
            />
            <ActionButton
              label="Quality Analysis"
              running={running === 'lipsync_analyze'}
              onClick={() => runAction('lipsync_analyze')}
            />
          </div>
        </div>
      </Section>

      {/* ── VOICE CLONE ─────────────────────────────── */}
      <Section
        title="Voice Clone (ElevenLabs)"
        desc="Clone team member voices and generate TTS voiceover"
        available={hasDeepfake}
      >
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Label>Person</Label>
            <input
              value={personName}
              onChange={e => setPersonName(e.target.value)}
              placeholder="(leer = alle Personen)"
              style={inputStyle}
            />
          </div>
          <div className="flex gap-2">
            <ActionButton
              label="Clone Voices"
              running={running === 'voice_clone'}
              onClick={() => runAction('voice_clone')}
            />
            <ActionButton
              label={personName ? `TTS: ${personName}` : 'TTS All'}
              running={running === 'voice_tts'}
              onClick={() => runAction('voice_tts', { person: personName || undefined })}
            />
          </div>
        </div>
      </Section>

      {/* Result Output */}
      {result && (
        <div style={{
          background: result.success ? 'rgba(94,255,138,0.08)' : 'rgba(255,90,110,0.08)',
          border: `1px solid ${result.success ? 'var(--system-green)' : 'var(--system-red)'}`,
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-3)',
        }}>
          <div className="flex items-center justify-between">
            <span style={{ fontSize: 'var(--text-caption1)', fontWeight: 600, color: result.success ? 'var(--system-green)' : 'var(--system-red)' }}>
              {result.success ? 'Success' : 'Error'}
            </span>
            <button onClick={() => setResult(null)} style={linkBtnStyle}>Dismiss</button>
          </div>
          <pre style={{
            fontSize: 'var(--text-caption2)', color: 'var(--text-secondary)',
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: '4px 0 0',
            maxHeight: 300, overflow: 'auto',
          }}>
            {result.stdout || result.message}
          </pre>
          {result.stderr && (
            <pre style={{
              fontSize: 'var(--text-caption2)', color: 'var(--system-red)',
              whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: '4px 0 0',
              maxHeight: 100, overflow: 'auto', opacity: 0.7,
            }}>
              {result.stderr}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

// ── Shared Components ──────────────────────────────────────────

function Section({ title, desc, available, children }: {
  title: string; desc: string; available: boolean; children: React.ReactNode
}) {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)',
      opacity: available ? 1 : 0.5,
      pointerEvents: available ? 'auto' : 'none',
    }}>
      <div style={{ marginBottom: 'var(--space-3)' }}>
        <div style={{ fontSize: 'var(--text-body)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
          {title}
        </div>
        <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginTop: 2 }}>
          {desc}
        </div>
      </div>
      {available ? children : (
        <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
          Not installed — run git submodule update --init
        </span>
      )}
    </div>
  )
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)',
      minWidth: 80, fontWeight: 500,
    }}>
      {children}
    </span>
  )
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span style={{
      fontSize: 'var(--text-caption2)',
      padding: '2px 8px',
      borderRadius: 'var(--radius-sm)',
      background: ok ? 'rgba(94,255,138,0.12)' : 'rgba(255,90,110,0.12)',
      color: ok ? 'var(--system-green)' : 'var(--system-red)',
    }}>
      {ok ? '\u2713' : '\u2717'} {label}
    </span>
  )
}

function ActionButton({ label, running, onClick, disabled }: {
  label: string; running: boolean; onClick: () => void; disabled?: boolean
}) {
  const isDisabled = running || disabled
  return (
    <button
      onClick={onClick}
      disabled={isDisabled}
      style={{
        padding: '6px 14px',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--separator)',
        background: isDisabled ? 'var(--fill-tertiary)' : 'var(--accent)',
        color: isDisabled ? 'var(--text-tertiary)' : '#fff',
        fontSize: 'var(--text-caption1)',
        fontWeight: 600,
        cursor: isDisabled ? 'not-allowed' : 'pointer',
        opacity: isDisabled ? 0.5 : 1,
        width: 'fit-content',
      }}
    >
      {running ? 'Running...' : label}
    </button>
  )
}

// ── Video Gallery Components ──────────────────────────────────

function VideoGallery() {
  const [videos, setVideos] = useState<VideoFileInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [selectedVideo, setSelectedVideo] = useState<VideoFileInfo | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res: VideoListResponse = await api()?.videoList?.()
      setVideos(res?.videos ?? [])
    } catch {
      setVideos([])
    }
    setLoading(false)
  }, [])

  useEffect(() => { refresh() }, [refresh])

  // Auto-refresh every 30s
  useEffect(() => {
    const iv = setInterval(refresh, 30000)
    return () => clearInterval(iv)
  }, [refresh])

  const categories = ['all', ...Array.from(new Set(videos.map(v => v.category)))]
  const filtered = filter === 'all' ? videos : videos.filter(v => v.category === filter)

  if (loading && videos.length === 0) {
    return <div style={{ color: 'var(--text-tertiary)', padding: 'var(--space-4)' }}>Scanning videos...</div>
  }

  if (videos.length === 0) {
    return (
      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-6)',
        textAlign: 'center',
        color: 'var(--text-tertiary)',
      }}>
        <div style={{ fontSize: 32, marginBottom: 'var(--space-2)' }}>&#127909;</div>
        <div style={{ fontSize: 'var(--text-footnote)' }}>No videos found</div>
        <div style={{ fontSize: 'var(--text-caption2)', marginTop: 4 }}>
          Run a pipeline above to generate videos
        </div>
      </div>
    )
  }

  return (
    <>
      {selectedVideo && (
        <VideoPlayerModal video={selectedVideo} onClose={() => setSelectedVideo(null)} />
      )}

      <div style={{
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-4)',
      }}>
        {/* Header */}
        <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-3)' }}>
          <div>
            <div style={{ fontSize: 'var(--text-body)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
              My Videos
            </div>
            <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginTop: 2 }}>
              {videos.length} video{videos.length !== 1 ? 's' : ''} found
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select value={filter} onChange={e => setFilter(e.target.value)} style={selectStyle}>
              {categories.map(c => (
                <option key={c} value={c}>{c === 'all' ? 'All' : c}</option>
              ))}
            </select>
            <button onClick={refresh} style={linkBtnStyle}>Refresh</button>
          </div>
        </div>

        {/* Card Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
          gap: 'var(--space-3)',
        }}>
          {filtered.map(video => (
            <VideoCard key={video.path} video={video} onClick={() => setSelectedVideo(video)} />
          ))}
        </div>
      </div>
    </>
  )
}

function VideoCard({ video, onClick }: { video: VideoFileInfo; onClick: () => void }) {
  const videoSrc = `vibemind-video://video/${video.path.replace(/\\/g, '/')}`

  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--fill-quaternary)',
        border: '1px solid var(--separator)',
        borderRadius: 'var(--radius-md)',
        overflow: 'hidden',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'border-color 150ms ease, transform 150ms ease',
        padding: 0,
      }}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--separator)' }}
    >
      {/* Thumbnail */}
      <div style={{
        width: '100%',
        aspectRatio: '16/9',
        background: 'var(--fill-tertiary)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden',
      }}>
        <video
          src={videoSrc}
          preload="metadata"
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          onLoadedMetadata={e => {
            const v = e.target as HTMLVideoElement
            v.currentTime = 1
          }}
          muted
        />
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'rgba(0,0,0,0.3)',
        }}>
          <span style={{ fontSize: 28, color: '#fff', opacity: 0.9 }}>&#9654;</span>
        </div>
      </div>

      {/* Info */}
      <div style={{ padding: 'var(--space-3)', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{
          fontSize: 'var(--text-footnote)',
          fontWeight: 600,
          color: 'var(--text-primary)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}>
          {video.filename.replace('.mp4', '')}
        </div>
        <div className="flex items-center gap-2">
          <span style={{
            fontSize: 'var(--text-caption2)',
            padding: '1px 6px',
            borderRadius: 'var(--radius-sm)',
            background: 'rgba(100,140,255,0.15)',
            color: 'var(--accent)',
          }}>
            {video.category}
          </span>
          <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
            {video.size_human}
          </span>
        </div>
      </div>
    </button>
  )
}

function VideoPlayerModal({ video, onClose }: { video: VideoFileInfo; onClose: () => void }) {
  const videoSrc = `vibemind-video://video/${video.path.replace(/\\/g, '/')}`

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(0,0,0,0.88)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-6)',
      }}
    >
      <div onClick={e => e.stopPropagation()} style={{
        maxWidth: '90%',
        maxHeight: '90%',
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-3)',
      }}>
        {/* Header */}
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 'var(--text-body)', fontWeight: 600, color: '#fff' }}>
            {video.filename}
          </span>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: '#fff',
            fontSize: 20, cursor: 'pointer', padding: '4px 8px',
          }}>
            &#x2715;
          </button>
        </div>
        {/* Player */}
        <video
          src={videoSrc}
          controls
          autoPlay
          style={{
            maxWidth: '100%',
            maxHeight: 'calc(85vh - 60px)',
            borderRadius: 'var(--radius-md)',
            background: '#000',
          }}
        />
        {/* Meta */}
        <div className="flex gap-3" style={{ color: 'rgba(255,255,255,0.6)', fontSize: 'var(--text-caption1)' }}>
          <span>{video.category}</span>
          <span>{video.size_human}</span>
          <span>{new Date(video.modified_iso).toLocaleString()}</span>
        </div>
      </div>
    </div>
  )
}

// ── Shared Styles ──────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  flex: 1,
  background: 'var(--fill-tertiary)',
  color: 'var(--text-primary)',
  border: '1px solid var(--separator)',
  borderRadius: 'var(--radius-sm)',
  padding: '5px 10px',
  fontSize: 'var(--text-caption1)',
  outline: 'none',
}

const selectStyle: React.CSSProperties = {
  background: 'var(--fill-tertiary)',
  color: 'var(--text-primary)',
  border: '1px solid var(--separator)',
  borderRadius: 'var(--radius-sm)',
  padding: '5px 10px',
  fontSize: 'var(--text-caption1)',
}

const linkBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  color: 'var(--accent)',
  fontSize: 'var(--text-caption1)',
  cursor: 'pointer',
  padding: 0,
}
