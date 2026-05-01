import { useState, useEffect, useCallback, useRef } from 'react'
import type {
  VideoStatusResponse, VideoToolResult, VideoFileInfo, VideoListResponse,
  VideoProject, PipelineMatrix, PipelineStepInfo, PipelineStepStatus, ReferencePipeline,
} from '../types'

const api = () => (window as any).vibemindVideo

/** Convert a local file path to a playable video URL */
const toVideoURL = (filePath: string) => {
  const a = api()
  if (a?.toVideoURL) return a.toVideoURL(filePath)
  // Fallback: custom protocol
  return `vibemind-video://video/${filePath.replace(/\\/g, '/')}`
}

// ── Wizard Configuration ──────────────────────────────────────

type WizardId = 'team' | 'vision' | 'demo' | 'lipsync' | 'voice' | 'project'
type StepType = 'choice' | 'dropzone' | 'input' | 'progress' | 'done'

interface StepConfig {
  label: string
  type: StepType
  options?: { value: string; label: string }[]
  dataKey?: string
  placeholder?: string
  inputType?: string
  defaultValue?: string
}

interface WizardConfig {
  title: string
  icon: string
  desc: string
  color: string
  requires: 'vibevideo' | 'deepfake'
  steps: StepConfig[]
}

const WIZARDS: Record<WizardId, WizardConfig> = {
  team: {
    title: 'Team Video',
    icon: '\u{1F3AC}',
    desc: 'Team-Praesentation erstellen',
    color: '#4488ff',
    requires: 'vibevideo',
    steps: [
      {
        label: 'Pipeline-Schritt waehlen',
        type: 'choice',
        dataKey: 'step',
        options: [
          { value: 'all', label: 'Full Pipeline' },
          { value: 'analyze', label: 'Analyze' },
          { value: 'backgrounds', label: 'Sora Backgrounds' },
          { value: 'composite', label: 'Composite' },
          { value: 'build', label: 'Build' },
          { value: 'split', label: 'Split-Screen' },
          { value: 'final', label: 'Final Cut' },
        ],
      },
      { label: 'Team Pipeline laeuft...', type: 'progress' },
      { label: 'Fertig', type: 'done' },
    ],
  },
  vision: {
    title: 'Vision Video',
    icon: '\u2728',
    desc: 'KI Vision mit Sora AI',
    color: '#8866ff',
    requires: 'vibevideo',
    steps: [
      {
        label: 'Modus waehlen',
        type: 'choice',
        dataKey: 'mode',
        options: [
          { value: 'all', label: 'Full Pipeline (Sora + TTS + Build)' },
          { value: 'generate_sora', label: 'Nur Sora-Szenen' },
          { value: 'generate_tts', label: 'Nur TTS Audio' },
          { value: 'build_only', label: 'Nur Video bauen' },
        ],
      },
      { label: 'Vision wird generiert...', type: 'progress' },
      { label: 'Fertig', type: 'done' },
    ],
  },
  demo: {
    title: 'Product Demo',
    icon: '\u{1F5A5}',
    desc: 'Demo aus Screenrecording',
    color: '#22ccaa',
    requires: 'vibevideo',
    steps: [
      { label: 'Video-Datei waehlen', type: 'dropzone', dataKey: 'file' },
      { label: 'Ziel-Dauer (Sekunden)', type: 'input', dataKey: 'duration', placeholder: '60', inputType: 'number', defaultValue: '60' },
      { label: 'Screenrecording wird analysiert...', type: 'progress' },
      { label: 'Demo-Video wird gebaut...', type: 'progress' },
      { label: 'Fertig', type: 'done' },
    ],
  },
  lipsync: {
    title: 'Lipsync',
    icon: '\u{1F444}',
    desc: 'KI Lipsync auf Videos',
    color: '#ff5a6e',
    requires: 'deepfake',
    steps: [
      { label: 'Person waehlen', type: 'input', dataKey: 'person', placeholder: 'Leer = alle Personen' },
      { label: 'Lipsync laeuft...', type: 'progress' },
      { label: 'Qualitaets-Check...', type: 'progress' },
      { label: 'Fertig', type: 'done' },
    ],
  },
  voice: {
    title: 'Voice Clone',
    icon: '\u{1F399}',
    desc: 'Stimmen klonen & TTS',
    color: '#ffc145',
    requires: 'deepfake',
    steps: [
      {
        label: 'Aktion waehlen',
        type: 'choice',
        dataKey: 'action',
        options: [
          { value: 'clone', label: 'Stimmen klonen' },
          { value: 'tts', label: 'TTS generieren' },
        ],
      },
      { label: 'Person waehlen', type: 'input', dataKey: 'person', placeholder: 'Leer = alle Personen' },
      { label: 'Wird ausgefuehrt...', type: 'progress' },
      { label: 'Fertig', type: 'done' },
    ],
  },
  project: {
    title: 'Neues Projekt',
    icon: '\u{1F4C1}',
    desc: 'Video-Projekt erstellen',
    color: '#22cc88',
    requires: 'vibevideo',
    steps: [
      { label: 'Projekt-Name', type: 'input', dataKey: 'projectName', placeholder: 'z.B. Team Intro 2025' },
      { label: 'Projekt wird erstellt...', type: 'progress' },
      { label: 'Fertig', type: 'done' },
    ],
  },
}

// ── Root Component ────────────────────────────────────────────

export function VideoProduction() {
  const [status, setStatus] = useState<VideoStatusResponse | null>(null)
  const [loading, setLoading] = useState(true)

  // Wizard state
  const [activeWizard, setActiveWizard] = useState<WizardId | null>(null)
  const [wizardStep, setWizardStep] = useState(0)
  const [wizardData, setWizardData] = useState<Record<string, string>>({})
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<VideoToolResult | null>(null)

  // Project / Pipeline state
  const [viewMode, setViewMode] = useState<'pipeline' | 'gallery' | 'live'>('pipeline')
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const res = await api()?.videoStatus?.()
        setStatus(res || null)
      } catch { setStatus(null) }
      setLoading(false)
    })()
  }, [])

  const startWizard = (id: WizardId) => {
    setActiveWizard(id)
    setWizardStep(0)
    setWizardData({})
    setResult(null)
    setRunning(false)
  }

  const exitWizard = () => {
    setActiveWizard(null)
    setWizardStep(0)
    setWizardData({})
    setResult(null)
    setRunning(false)
  }

  if (loading) {
    return <div style={{ color: 'var(--text-tertiary)', padding: 'var(--space-6)' }}>Lade Video Studio...</div>
  }

  const hasVibevideo = status?.vibevideo_installed ?? false
  const hasDeepfake = status?.deepfake_installed ?? false

  return (
    <div className="flex flex-col gap-4">
      {activeWizard ? (
        <WizardView
          wizardId={activeWizard}
          step={wizardStep}
          setStep={setWizardStep}
          data={wizardData}
          setData={setWizardData}
          running={running}
          setRunning={setRunning}
          result={result}
          setResult={setResult}
          onExit={exitWizard}
        />
      ) : (
        <QuickActionGrid
          hasVibevideo={hasVibevideo}
          hasDeepfake={hasDeepfake}
          onSelect={startWizard}
        />
      )}

      {/* View Toggle */}
      <div className="flex items-center gap-2" style={{ marginTop: 'var(--space-1)' }}>
        <button
          onClick={() => setViewMode('pipeline')}
          style={{
            ...tabBtnStyle,
            ...(viewMode === 'pipeline' ? tabBtnActiveStyle : {}),
          }}
        >
          Pipeline
        </button>
        <button
          onClick={() => setViewMode('gallery')}
          style={{
            ...tabBtnStyle,
            ...(viewMode === 'gallery' ? tabBtnActiveStyle : {}),
          }}
        >
          Gallery
        </button>
        <button
          onClick={() => setViewMode('live')}
          style={{
            ...tabBtnStyle,
            ...(viewMode === 'live' ? tabBtnActiveStyle : {}),
          }}
        >
          Live
        </button>
      </div>

      {viewMode === 'pipeline' && (
        <>
          <PipelineReferenceView />
          <ProjectList
            selectedId={selectedProjectId}
            onSelect={setSelectedProjectId}
          />
          {selectedProjectId && (
            <ProjectPipelineMatrix projectId={selectedProjectId} />
          )}
        </>
      )}
      {viewMode === 'gallery' && <VideoGallery />}
      {viewMode === 'live' && <LiveCapture />}
    </div>
  )
}

// ── Quick Action Grid ─────────────────────────────────────────

function QuickActionGrid({ hasVibevideo, hasDeepfake, onSelect }: {
  hasVibevideo: boolean; hasDeepfake: boolean; onSelect: (id: WizardId) => void
}) {
  const cards: { id: WizardId; available: boolean }[] = [
    { id: 'team', available: hasVibevideo },
    { id: 'vision', available: hasVibevideo },
    { id: 'demo', available: hasVibevideo },
    { id: 'lipsync', available: hasDeepfake },
    { id: 'voice', available: hasDeepfake },
  ]

  // "Neues Projekt" pseudo-wizard entry
  const PROJECT_CARD = { title: 'Neues Projekt', icon: '\u{1F4C1}', desc: 'Video-Projekt erstellen', color: '#22cc88' }

  return (
    <div>
      <div className="flex items-center gap-3" style={{ marginBottom: 'var(--space-4)' }}>
        <span style={{ fontSize: 'var(--text-title3)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
          Video Studio
        </span>
        <StatusBadge ok={hasVibevideo} label="vibevideo" />
        <StatusBadge ok={hasDeepfake} label="deepfake" />
      </div>
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
        gap: 'var(--space-3)',
      }}>
        {cards.map(({ id, available }) => {
          const cfg = WIZARDS[id]
          return (
            <button
              key={id}
              onClick={() => available && onSelect(id)}
              disabled={!available}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-5) var(--space-4)',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--separator)',
                borderRadius: 'var(--radius-lg)',
                cursor: available ? 'pointer' : 'not-allowed',
                opacity: available ? 1 : 0.4,
                transition: 'border-color 200ms ease, transform 200ms ease',
                textAlign: 'center',
              }}
              onMouseEnter={e => { if (available) (e.currentTarget.style.borderColor = cfg.color) }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--separator)' }}
            >
              <span style={{ fontSize: 36 }}>{cfg.icon}</span>
              <span style={{ fontSize: 'var(--text-body)', fontWeight: 600, color: 'var(--text-primary)' }}>
                {cfg.title}
              </span>
              <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>
                {cfg.desc}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// ── Wizard View ───────────────────────────────────────────────

function WizardView({ wizardId, step, setStep, data, setData, running, setRunning, result, setResult, onExit }: {
  wizardId: WizardId
  step: number
  setStep: (s: number) => void
  data: Record<string, string>
  setData: (d: Record<string, string>) => void
  running: boolean
  setRunning: (r: boolean) => void
  result: VideoToolResult | null
  setResult: (r: VideoToolResult | null) => void
  onExit: () => void
}) {
  const cfg = WIZARDS[wizardId]
  const steps = cfg.steps
  const current = steps[step]

  // Skip voice person step if action is 'clone'
  const effectiveStep = (wizardId === 'voice' && step === 1 && data.action === 'clone') ? 2 : step
  const effectiveCurrent = steps[effectiveStep] || current

  const canNext = () => {
    if (effectiveCurrent.type === 'choice') return !!data[effectiveCurrent.dataKey || '']
    if (effectiveCurrent.type === 'dropzone') return !!data[effectiveCurrent.dataKey || '']
    if (effectiveCurrent.type === 'input') return true // optional fields
    return false
  }

  const goNext = () => {
    let next = effectiveStep + 1
    // Voice: skip person step for clone
    if (wizardId === 'voice' && next === 1 && data.action === 'clone') next = 2
    setStep(next)
  }

  const goBack = () => {
    if (effectiveStep === 0) { onExit(); return }
    let prev = effectiveStep - 1
    if (wizardId === 'voice' && prev === 1 && data.action === 'clone') prev = 0
    setStep(prev)
  }

  return (
    <div style={{
      background: 'var(--bg-secondary)',
      borderRadius: 'var(--radius-lg)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div className="flex items-center gap-3" style={{
        padding: 'var(--space-3) var(--space-4)',
        borderBottom: '1px solid var(--separator)',
      }}>
        <button onClick={goBack} disabled={running} style={{
          background: 'none', border: 'none', color: 'var(--text-secondary)',
          fontSize: 18, cursor: running ? 'not-allowed' : 'pointer', padding: '2px 6px',
        }}>
          &#8592;
        </button>
        <span style={{ fontSize: 20 }}>{cfg.icon}</span>
        <span style={{ fontSize: 'var(--text-body)', fontWeight: 600, color: 'var(--text-primary)', flex: 1 }}>
          {cfg.title}
        </span>
        {/* Step dots */}
        <div className="flex gap-1">
          {steps.map((s, i) => (
            <div key={i} style={{
              width: 8, height: 8, borderRadius: '50%',
              background: i < effectiveStep ? 'var(--system-green)'
                : i === effectiveStep ? cfg.color
                : 'var(--fill-tertiary)',
              transition: 'background 200ms ease',
            }} />
          ))}
        </div>
      </div>

      {/* Step content */}
      <div style={{ padding: 'var(--space-5)' }}>
        <div style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-3)' }}>
          Schritt {effectiveStep + 1} von {steps.length}: {effectiveCurrent.label}
        </div>

        {effectiveCurrent.type === 'choice' && (
          <ChoiceStep
            options={effectiveCurrent.options || []}
            value={data[effectiveCurrent.dataKey || ''] || ''}
            onChange={v => setData({ ...data, [effectiveCurrent.dataKey || '']: v })}
            color={cfg.color}
          />
        )}

        {effectiveCurrent.type === 'dropzone' && (
          <DropZoneStep
            value={data[effectiveCurrent.dataKey || ''] || ''}
            onChange={v => setData({ ...data, [effectiveCurrent.dataKey || '']: v })}
          />
        )}

        {effectiveCurrent.type === 'input' && (
          <InputStep
            value={data[effectiveCurrent.dataKey || ''] || effectiveCurrent.defaultValue || ''}
            onChange={v => setData({ ...data, [effectiveCurrent.dataKey || '']: v })}
            placeholder={effectiveCurrent.placeholder || ''}
            inputType={effectiveCurrent.inputType || 'text'}
          />
        )}

        {effectiveCurrent.type === 'progress' && (
          <ProgressStep
            wizardId={wizardId}
            step={effectiveStep}
            data={data}
            running={running}
            setRunning={setRunning}
            result={result}
            setResult={setResult}
            onComplete={() => setStep(effectiveStep + 1)}
            color={cfg.color}
          />
        )}

        {effectiveCurrent.type === 'done' && (
          <DoneStep result={result} onExit={onExit} />
        )}
      </div>

      {/* Footer */}
      {effectiveCurrent.type !== 'progress' && effectiveCurrent.type !== 'done' && (
        <div className="flex items-center justify-between" style={{
          padding: 'var(--space-3) var(--space-4)',
          borderTop: '1px solid var(--separator)',
        }}>
          <button onClick={onExit} style={linkBtnStyle}>Abbrechen</button>
          <button
            onClick={goNext}
            disabled={!canNext()}
            style={{
              padding: '8px 24px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: canNext() ? cfg.color : 'var(--fill-tertiary)',
              color: canNext() ? '#fff' : 'var(--text-tertiary)',
              fontSize: 'var(--text-caption1)',
              fontWeight: 600,
              cursor: canNext() ? 'pointer' : 'not-allowed',
            }}
          >
            {steps[effectiveStep + 1]?.type === 'progress' ? 'Starten' : 'Weiter'}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Step Components ───────────────────────────────────────────

function ChoiceStep({ options, value, onChange, color }: {
  options: { value: string; label: string }[]
  value: string
  onChange: (v: string) => void
  color: string
}) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
      gap: 'var(--space-2)',
    }}>
      {options.map(opt => {
        const selected = value === opt.value
        return (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            style={{
              padding: 'var(--space-3) var(--space-4)',
              background: selected ? `${color}18` : 'var(--fill-quaternary)',
              border: `2px solid ${selected ? color : 'transparent'}`,
              borderRadius: 'var(--radius-md)',
              color: 'var(--text-primary)',
              fontSize: 'var(--text-footnote)',
              fontWeight: selected ? 600 : 400,
              cursor: 'pointer',
              textAlign: 'left',
              transition: 'all 150ms ease',
            }}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}

function DropZoneStep({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file && file.name.toLowerCase().endsWith('.mp4')) {
      onChange((file as any).path || file.name)
    }
  }

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) onChange((file as any).path || file.name)
  }

  if (value) {
    return (
      <div className="flex items-center gap-3" style={{
        padding: 'var(--space-4)',
        background: 'rgba(94,255,138,0.06)',
        border: '2px solid var(--system-green)',
        borderRadius: 'var(--radius-lg)',
      }}>
        <span style={{ fontSize: 24 }}>&#127909;</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 'var(--text-footnote)', fontWeight: 600, color: 'var(--text-primary)' }}>
            {value.split(/[/\\]/).pop()}
          </div>
          <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
            {value}
          </div>
        </div>
        <button onClick={() => onChange('')} style={linkBtnStyle}>Entfernen</button>
      </div>
    )
  }

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      style={{
        minHeight: 180,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 'var(--space-2)',
        border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--separator)'}`,
        borderRadius: 'var(--radius-lg)',
        background: dragOver ? 'var(--accent-fill)' : 'transparent',
        cursor: 'pointer',
        transition: 'all 200ms ease',
      }}
    >
      <span style={{ fontSize: 40, opacity: 0.5 }}>&#8681;</span>
      <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-secondary)' }}>
        {dragOver ? 'Loslassen zum Hinzufuegen' : '.mp4 Datei hierher ziehen'}
      </span>
      <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
        oder klicken zum Durchsuchen
      </span>
      <input
        ref={inputRef}
        type="file"
        accept=".mp4"
        onChange={handleFile}
        style={{ display: 'none' }}
      />
    </div>
  )
}

function InputStep({ value, onChange, placeholder, inputType }: {
  value: string; onChange: (v: string) => void; placeholder: string; inputType: string
}) {
  return (
    <div style={{ maxWidth: 400 }}>
      <input
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        type={inputType}
        style={{
          width: '100%',
          background: 'var(--fill-tertiary)',
          color: 'var(--text-primary)',
          border: '1px solid var(--separator)',
          borderRadius: 'var(--radius-md)',
          padding: 'var(--space-3) var(--space-4)',
          fontSize: 'var(--text-body)',
          outline: 'none',
        }}
      />
    </div>
  )
}

function ProgressStep({ wizardId, step, data, running, setRunning, result, setResult, onComplete, color }: {
  wizardId: WizardId; step: number; data: Record<string, string>
  running: boolean; setRunning: (r: boolean) => void
  result: VideoToolResult | null; setResult: (r: VideoToolResult | null) => void
  onComplete: () => void; color: string
}) {
  const [elapsed, setElapsed] = useState(0)
  const [showDetails, setShowDetails] = useState(false)
  const started = useRef(false)

  // Elapsed timer
  useEffect(() => {
    if (!running) return
    const start = Date.now()
    const iv = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000)
    return () => clearInterval(iv)
  }, [running])

  // Run IPC action on mount
  useEffect(() => {
    if (started.current) return
    started.current = true
    ;(async () => {
      setRunning(true)
      setResult(null)
      try {
        let res: VideoToolResult
        if (wizardId === 'team') {
          res = await api().videoTeamRun(data.step || 'all')
        } else if (wizardId === 'vision') {
          res = await api().videoVision({ [data.mode || 'all']: true })
        } else if (wizardId === 'demo' && step === 2) {
          res = await api().videoDemoAnalyze(data.file, parseInt(data.duration) || 60)
        } else if (wizardId === 'demo' && step === 3) {
          res = await api().videoDemoBuild(data.configPath || '')
        } else if (wizardId === 'lipsync' && step === 1) {
          res = await api().videoLipsync(data.person || undefined)
        } else if (wizardId === 'lipsync' && step === 2) {
          res = await api().videoLipsyncAnalyze()
        } else if (wizardId === 'voice' && data.action === 'clone') {
          res = await api().videoVoiceClone()
        } else if (wizardId === 'voice') {
          res = await api().videoVoiceTts(data.person || undefined)
        } else {
          res = { success: false, message: 'Unknown action' }
        }
        setResult(res)
      } catch (e: any) {
        setResult({ success: false, message: e.message })
      }
      setRunning(false)
    })()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-advance when done
  useEffect(() => {
    if (!running && result) {
      const t = setTimeout(onComplete, 800)
      return () => clearTimeout(t)
    }
  }, [running, result, onComplete])

  const mins = Math.floor(elapsed / 60)
  const secs = elapsed % 60
  const timeStr = `${mins}:${String(secs).padStart(2, '0')}`

  return (
    <div className="flex flex-col gap-4">
      {/* Shimmer bar */}
      <div style={{
        height: 6,
        borderRadius: 3,
        background: 'var(--fill-quaternary)',
        overflow: 'hidden',
        position: 'relative',
      }}>
        {running && (
          <div style={{
            position: 'absolute',
            inset: 0,
            width: '40%',
            borderRadius: 3,
            background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
            animation: 'shimmer 1.5s infinite ease-in-out',
          }} />
        )}
        {!running && result && (
          <div style={{
            width: '100%', height: '100%', borderRadius: 3,
            background: result.success ? 'var(--system-green)' : 'var(--system-red)',
            transition: 'width 300ms ease',
          }} />
        )}
      </div>

      {/* Status */}
      <div className="flex items-center justify-between">
        <span style={{
          fontSize: 'var(--text-footnote)',
          color: running ? 'var(--text-secondary)' : (result?.success ? 'var(--system-green)' : 'var(--system-red)'),
          fontWeight: 500,
        }}>
          {running ? 'Pipeline laeuft...' : (result?.success ? 'Erfolgreich!' : 'Fehler')}
        </span>
        <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', fontFamily: 'monospace' }}>
          {timeStr}
        </span>
      </div>

      {/* Details toggle */}
      {(result?.stdout || result?.stderr) && (
        <div>
          <button onClick={() => setShowDetails(!showDetails)} style={{
            ...linkBtnStyle,
            fontSize: 'var(--text-caption2)',
          }}>
            {showDetails ? 'Details ausblenden \u25B2' : 'Details anzeigen \u25BC'}
          </button>
          {showDetails && (
            <pre style={{
              marginTop: 'var(--space-2)',
              fontSize: 'var(--text-caption2)',
              color: 'var(--text-secondary)',
              background: 'var(--fill-quaternary)',
              borderRadius: 'var(--radius-sm)',
              padding: 'var(--space-3)',
              maxHeight: 200,
              overflow: 'auto',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {result.stdout || result.message}
              {result.stderr && `\n\n--- stderr ---\n${result.stderr}`}
            </pre>
          )}
        </div>
      )}
    </div>
  )
}

function DoneStep({ result, onExit }: { result: VideoToolResult | null; onExit: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4" style={{ padding: 'var(--space-6) 0' }}>
      <div style={{
        width: 56, height: 56, borderRadius: '50%',
        background: result?.success ? 'rgba(94,255,138,0.15)' : 'rgba(255,90,110,0.15)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 28,
      }}>
        {result?.success ? '\u2713' : '\u2717'}
      </div>
      <div style={{
        fontSize: 'var(--text-body)', fontWeight: 600,
        color: result?.success ? 'var(--system-green)' : 'var(--system-red)',
      }}>
        {result?.success ? 'Pipeline abgeschlossen' : 'Fehler aufgetreten'}
      </div>
      <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', textAlign: 'center', maxWidth: 400 }}>
        {result?.message}
      </div>
      <div className="flex gap-3" style={{ marginTop: 'var(--space-2)' }}>
        <button onClick={onExit} style={{
          padding: '8px 24px',
          borderRadius: 'var(--radius-sm)',
          border: 'none',
          background: 'var(--accent)',
          color: '#fff',
          fontSize: 'var(--text-caption1)',
          fontWeight: 600,
          cursor: 'pointer',
        }}>
          Zurueck zum Studio
        </button>
      </div>
    </div>
  )
}

// ── Status Badge ──────────────────────────────────────────────

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

// ── Video Upload Dropzone ─────────────────────────────────────

function UploadDropzone({ onUploaded }: { onUploaded: () => void }) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [personName, setPersonName] = useState('')
  const [status, setStatus] = useState('')

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const files = Array.from(e.dataTransfer.files).filter(f =>
      /\.(mp4|mov|avi|mkv|webm)$/i.test(f.name)
    )
    if (files.length === 0) { setStatus('Keine Video-Dateien gefunden'); return }

    setUploading(true)
    for (const file of files) {
      const name = personName || file.name.replace(/\.[^.]+$/, '')
      // Electron 32+ with contextIsolation: file.path is always empty.
      // Use the preload bridge to resolve the absolute filesystem path.
      const filePath = api()?.getPathForFile?.(file) || (file as any).path || ''
      if (!filePath) {
        setStatus(`Fehler: Pfad nicht auflösbar für ${file.name}`)
        continue
      }
      setStatus(`Uploade ${file.name}...`)
      try {
        const res = await api()?.videoUpload?.(filePath, name)
        if (res?.success) {
          setStatus(`${file.name} hochgeladen`)
        } else {
          setStatus(`Fehler: ${res?.message || 'Upload fehlgeschlagen'}`)
        }
      } catch (err: any) {
        setStatus(`Fehler: ${err.message}`)
      }
    }
    setUploading(false)
    setPersonName('')
    onUploaded()
  }, [personName, onUploaded])

  return (
    <div style={{ marginBottom: 'var(--space-4)' }}>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        style={{
          border: `2px dashed ${dragging ? 'var(--accent)' : 'var(--separator)'}`,
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--space-5)',
          textAlign: 'center',
          background: dragging ? 'rgba(100,140,255,0.08)' : 'var(--bg-secondary)',
          transition: 'all 150ms ease',
          cursor: 'pointer',
        }}
      >
        <div style={{ fontSize: 28, marginBottom: 'var(--space-2)', opacity: 0.6 }}>
          {uploading ? '\u23F3' : '\u{1F4E5}'}
        </div>
        <div style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-secondary)', marginBottom: 'var(--space-2)' }}>
          {uploading ? 'Wird hochgeladen...' : 'Video hierher ziehen'}
        </div>
        <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
          MP4, MOV, AVI, MKV, WebM
        </div>
        {!uploading && (
          <input
            type="text"
            placeholder="Person (optional)"
            value={personName}
            onChange={e => setPersonName(e.target.value)}
            onClick={e => e.stopPropagation()}
            style={{
              marginTop: 'var(--space-3)', padding: '6px 12px',
              background: 'var(--fill-quaternary)', border: '1px solid var(--separator)',
              borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
              fontSize: 'var(--text-caption1)', textAlign: 'center', width: 180,
              outline: 'none',
            }}
          />
        )}
        {status && (
          <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--text-caption2)', color: 'var(--accent)' }}>
            {status}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Video Gallery ─────────────────────────────────────────────

function VideoGallery() {
  const [videos, setVideos] = useState<VideoFileInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [selectedVideo, setSelectedVideo] = useState<VideoFileInfo | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res: VideoListResponse = await api()?.videoList?.()
      setVideos(res?.videos ?? [])
    } catch { setVideos([]) }
    setLoading(false)
  }, [])

  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const iv = setInterval(refresh, 30000)
    return () => clearInterval(iv)
  }, [refresh])

  const categories = ['all', ...Array.from(new Set(videos.map(v => v.category)))]
  const filtered = filter === 'all' ? videos : videos.filter(v => v.category === filter)

  if (loading && videos.length === 0) {
    return <div style={{ color: 'var(--text-tertiary)', padding: 'var(--space-4)' }}>Videos werden geladen...</div>
  }

  return (
    <>
      {selectedVideo && <VideoPlayerModal video={selectedVideo} onClose={() => setSelectedVideo(null)} onDelete={() => {
        const v = selectedVideo
        setSelectedVideo(null)
        api()?.videoDelete?.(v.id, true).then((res: any) => { if (res?.success) refresh() })
      }} />}

      <UploadDropzone onUploaded={refresh} />

      <div style={{ background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)', padding: 'var(--space-4)' }}>
        <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-3)' }}>
          <div>
            <div style={{ fontSize: 'var(--text-body)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
              Meine Videos
            </div>
            <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginTop: 2 }}>
              {videos.length} Video{videos.length !== 1 ? 's' : ''} gefunden
            </div>
          </div>
          <div className="flex items-center gap-2">
            <select value={filter} onChange={e => setFilter(e.target.value)} style={selectStyle}>
              {categories.map(c => <option key={c} value={c}>{c === 'all' ? 'Alle' : c}</option>)}
            </select>
            <button onClick={refresh} style={linkBtnStyle}>Aktualisieren</button>
          </div>
        </div>
        {videos.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-tertiary)', padding: 'var(--space-4)' }}>
            <div style={{ fontSize: 'var(--text-footnote)' }}>Keine Videos gefunden</div>
            <div style={{ fontSize: 'var(--text-caption2)', marginTop: 4 }}>Ziehe ein Video in die Dropzone oben</div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 'var(--space-3)' }}>
            {filtered.map(video => <VideoCard key={video.path} video={video} onClick={() => setSelectedVideo(video)} />)}
          </div>
        )}
      </div>
    </>
  )
}

function VideoCard({ video, onClick }: { video: VideoFileInfo; onClick: () => void }) {
  const videoSrc = toVideoURL(video.path)
  return (
    <button onClick={onClick} style={{
      display: 'flex', flexDirection: 'column',
      background: 'var(--fill-quaternary)', border: '1px solid var(--separator)',
      borderRadius: 'var(--radius-md)', overflow: 'hidden', cursor: 'pointer',
      textAlign: 'left', transition: 'border-color 150ms ease', padding: 0,
    }}
      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)' }}
      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = 'var(--separator)' }}
    >
      <div style={{
        width: '100%', aspectRatio: '16/9', background: 'var(--fill-tertiary)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative', overflow: 'hidden',
      }}>
        <video src={videoSrc} preload="metadata" muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          onLoadedMetadata={e => { (e.target as HTMLVideoElement).currentTime = 1 }}
        />
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'rgba(0,0,0,0.3)' }}>
          <span style={{ fontSize: 28, color: '#fff', opacity: 0.9 }}>&#9654;</span>
        </div>
      </div>
      <div style={{ padding: 'var(--space-3)', display: 'flex', flexDirection: 'column', gap: 4 }}>
        <div style={{ fontSize: 'var(--text-footnote)', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {video.filename.replace('.mp4', '')}
        </div>
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 'var(--text-caption2)', padding: '1px 6px', borderRadius: 'var(--radius-sm)', background: 'rgba(100,140,255,0.15)', color: 'var(--accent)' }}>
            {video.category}
          </span>
          <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>{video.size_human}</span>
        </div>
      </div>
    </button>
  )
}

function VideoPlayerModal({ video, onClose, onDelete }: { video: VideoFileInfo; onClose: () => void; onDelete?: () => void }) {
  const videoSrc = toVideoURL(video.path)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [showFaceswap, setShowFaceswap] = useState(false)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (confirmDelete) setConfirmDelete(false)
        else if (showFaceswap) setShowFaceswap(false)
        else onClose()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose, confirmDelete, showFaceswap])

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.88)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--space-6)',
    }}>
      {showFaceswap && (
        <FaceswapDialog
          video={video}
          onClose={() => setShowFaceswap(false)}
        />
      )}
      <div onClick={e => e.stopPropagation()} style={{ maxWidth: '90%', maxHeight: '90%', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 'var(--text-body)', fontWeight: 600, color: '#fff' }}>{video.filename}</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowFaceswap(true)} style={{
              background: 'rgba(120,80,255,0.15)', border: '1px solid rgba(120,80,255,0.5)', color: '#b9a4ff',
              fontSize: 'var(--text-caption1)', cursor: 'pointer', padding: '4px 12px', borderRadius: 'var(--radius-sm)',
              fontWeight: 600,
            }}>🎭 Face Swap</button>
            {onDelete && !confirmDelete && (
              <button onClick={() => setConfirmDelete(true)} style={{
                background: 'none', border: '1px solid rgba(255,80,80,0.4)', color: 'rgba(255,80,80,0.8)',
                fontSize: 'var(--text-caption1)', cursor: 'pointer', padding: '4px 10px', borderRadius: 'var(--radius-sm)',
              }}>Loeschen</button>
            )}
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#fff', fontSize: 20, cursor: 'pointer', padding: '4px 8px' }}>&#x2715;</button>
          </div>
        </div>
        {confirmDelete && (
          <div style={{
            background: 'rgba(255,60,60,0.12)', border: '1px solid rgba(255,80,80,0.3)',
            borderRadius: 'var(--radius-md)', padding: 'var(--space-3)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ color: 'rgba(255,180,180,0.9)', fontSize: 'var(--text-caption1)' }}>Wirklich loeschen? Datei wird von der Festplatte entfernt.</span>
            <div className="flex items-center gap-2">
              <button onClick={() => onDelete?.()} style={{
                background: 'rgba(255,40,40,0.3)', border: '1px solid rgba(255,60,60,0.5)', color: '#ff6666',
                fontSize: 'var(--text-caption1)', cursor: 'pointer', padding: '4px 10px', borderRadius: 'var(--radius-sm)', fontWeight: 600,
              }}>Ja, loeschen</button>
              <button onClick={() => setConfirmDelete(false)} style={{
                background: 'none', border: '1px solid rgba(255,255,255,0.2)', color: 'rgba(255,255,255,0.6)',
                fontSize: 'var(--text-caption1)', cursor: 'pointer', padding: '4px 10px', borderRadius: 'var(--radius-sm)',
              }}>Abbrechen</button>
            </div>
          </div>
        )}
        <video src={videoSrc} controls autoPlay style={{ maxWidth: '100%', maxHeight: 'calc(85vh - 60px)', borderRadius: 'var(--radius-md)', background: '#000' }} />
        <div className="flex gap-3" style={{ color: 'rgba(255,255,255,0.6)', fontSize: 'var(--text-caption1)' }}>
          <span>{video.category}</span>
          <span>{video.size_human}</span>
          <span>{new Date(video.modified_iso).toLocaleString()}</span>
        </div>
      </div>
    </div>
  )
}

// ── Face Swap Dialog ──────────────────────────────────────────

interface FaceswapPreset { id: string; name: string }

interface FaceswapJob {
  id: string
  state: 'starting' | 'running' | 'done' | 'failed'
  percent: number
  frame: number
  total_frames: number
  fps: number
  eta_s: number
  output_path: string
  error?: string | null
  log_tail?: string[]
}

const VIDEO_API_BASE =
  (typeof window !== 'undefined' && (window as any).VIBEMIND_BACKEND_URL) ||
  'http://localhost:8007'

function FaceswapDialog({ video, onClose }: { video: VideoFileInfo; onClose: () => void }) {
  const [presets, setPresets] = useState<FaceswapPreset[]>([])
  const [target, setTarget] = useState<string>('__random__')
  const [keepAudio, setKeepAudio] = useState(true)
  const [job, setJob] = useState<FaceswapJob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const pollRef = useRef<number | null>(null)

  // Load presets once
  useEffect(() => {
    fetch(`${VIDEO_API_BASE}/api/video/presets`)
      .then(r => r.json())
      .then(data => setPresets(data.presets || []))
      .catch(e => setError(`Cannot load presets: ${e.message}`))
  }, [])

  // Poll job status while running
  useEffect(() => {
    if (!job?.id) return
    if (job.state === 'done' || job.state === 'failed') {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null }
      return
    }
    pollRef.current = window.setInterval(async () => {
      try {
        const r = await fetch(`${VIDEO_API_BASE}/api/video/job/${job.id}`)
        if (!r.ok) return
        const j: FaceswapJob = await r.json()
        setJob(j)
      } catch { /* ignore transient */ }
    }, 1000)
    return () => {
      if (pollRef.current) { window.clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [job?.id, job?.state])

  const startSwap = async () => {
    setError(null)
    let chosenTarget = target
    if (chosenTarget === '__random__') {
      if (presets.length === 0) {
        setError('No presets available')
        return
      }
      chosenTarget = presets[Math.floor(Math.random() * presets.length)].id
    }
    try {
      const r = await fetch(`${VIDEO_API_BASE}/api/video/faceswap`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input_path: video.path,
          target: chosenTarget,
          no_audio: !keepAudio,
        }),
      })
      if (!r.ok) {
        const txt = await r.text().catch(() => '')
        setError(`HTTP ${r.status}: ${txt.slice(0, 200)}`)
        return
      }
      const data = await r.json()
      // Pre-populate job stub so polling kicks in
      setJob({
        id: data.job_id,
        state: 'starting',
        percent: 0,
        frame: 0,
        total_frames: 0,
        fps: 0,
        eta_s: 0,
        output_path: data.output_path,
      })
    } catch (e: any) {
      setError(`Request failed: ${e?.message ?? e}`)
    }
  }

  const isRunning = job && (job.state === 'starting' || job.state === 'running')
  const isDone = job?.state === 'done'
  const isFailed = job?.state === 'failed'

  return (
    <div onClick={e => e.stopPropagation()} style={{
      position: 'fixed', inset: 0, zIndex: 1100, background: 'rgba(0,0,0,0.92)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 'var(--space-6)',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-5)', maxWidth: 520, width: '100%',
        display: 'flex', flexDirection: 'column', gap: 'var(--space-3)',
        border: '1px solid rgba(120,80,255,0.3)',
      }}>
        <div className="flex items-center justify-between">
          <div style={{ fontSize: 'var(--text-body)', fontWeight: 600, color: 'var(--text-primary)' }}>
            🎭 Face Swap
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', fontSize: 18, cursor: 'pointer' }}>✕</button>
        </div>

        <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
          Input: <code style={{ color: 'var(--accent)' }}>{video.filename}</code>
        </div>

        {/* Target selection */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <label style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
            Target face
          </label>
          <select
            value={target}
            onChange={e => setTarget(e.target.value)}
            disabled={isRunning || isDone}
            style={{
              padding: '6px 10px', fontSize: 'var(--text-footnote)',
              background: 'var(--bg-primary)', color: 'var(--text-primary)',
              border: '1px solid var(--separator)', borderRadius: 'var(--radius-sm)',
            }}
          >
            <option value="__random__">🎲 Random</option>
            {presets.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
          <input
            type="checkbox"
            checked={keepAudio}
            onChange={e => setKeepAudio(e.target.checked)}
            disabled={isRunning || isDone}
          />
          Audio aus Original übernehmen
        </label>

        {error && (
          <div style={{ background: 'rgba(255,60,60,0.1)', color: '#ff8080', padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)', fontSize: 'var(--text-caption1)' }}>
            {error}
          </div>
        )}

        {/* Progress */}
        {job && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <div className="flex items-center justify-between" style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
              <span>{job.state === 'starting' ? 'Initialisiere...' :
                     job.state === 'running' ? `Frame ${job.frame}/${job.total_frames} · ${job.fps.toFixed(1)} fps · eta ${Math.round(job.eta_s)}s` :
                     job.state === 'done' ? '✓ Fertig' : '✗ Fehlgeschlagen'}</span>
              <span>{job.percent.toFixed(1)}%</span>
            </div>
            <div style={{ height: 6, background: 'var(--fill-quaternary)', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${Math.max(2, Math.min(100, job.percent))}%`,
                background: isFailed ? '#ff5555' : (isDone ? '#22cc88' : '#7e5cff'),
                transition: 'width 300ms ease',
              }} />
            </div>
            {isDone && (
              <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginTop: 4 }}>
                Output: <code>{job.output_path.split(/[/\\]/).pop()}</code> — taucht in 30s in der Gallery auf
              </div>
            )}
            {isFailed && job.error && (
              <div style={{ fontSize: 'var(--text-caption2)', color: '#ff8080', marginTop: 4 }}>
                {job.error}
              </div>
            )}
          </div>
        )}

        <div className="flex items-center justify-end gap-2" style={{ marginTop: 'var(--space-2)' }}>
          {isDone || isFailed ? (
            <button onClick={onClose} style={{
              padding: '6px 14px', fontSize: 'var(--text-footnote)',
              background: 'var(--accent)', color: '#fff', border: 'none',
              borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600,
            }}>Schließen</button>
          ) : (
            <>
              <button onClick={onClose} disabled={!!isRunning} style={{
                padding: '6px 12px', fontSize: 'var(--text-footnote)',
                background: 'none', color: 'var(--text-secondary)',
                border: '1px solid var(--separator)', borderRadius: 'var(--radius-sm)',
                cursor: isRunning ? 'not-allowed' : 'pointer', opacity: isRunning ? 0.5 : 1,
              }}>Abbrechen</button>
              <button onClick={startSwap} disabled={!!isRunning} style={{
                padding: '6px 14px', fontSize: 'var(--text-footnote)',
                background: '#7e5cff', color: '#fff', border: 'none',
                borderRadius: 'var(--radius-sm)', cursor: isRunning ? 'wait' : 'pointer', fontWeight: 600,
                opacity: isRunning ? 0.7 : 1,
              }}>
                {isRunning ? 'Läuft...' : '🎭 Swap starten'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Live Capture (eyeTerm webcam → MP4) ──────────────────────

interface LiveRecState {
  active: boolean
  duration_s?: number
  output_path?: string
  size_mb?: number
  source?: string
}

function LiveCapture() {
  const [streamOk, setStreamOk] = useState<boolean | null>(null)
  const [rec, setRec] = useState<LiveRecState>({ active: false })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [hint, setHint] = useState('')
  const [tick, setTick] = useState(0)

  // Probe eyeTerm status on mount
  useEffect(() => {
    fetch('http://127.0.0.1:8099/status', { signal: AbortSignal.timeout(2000) })
      .then(r => setStreamOk(r.ok))
      .catch(() => setStreamOk(false))
  }, [])

  // Poll recording status while active
  useEffect(() => {
    if (!rec.active) return
    const iv = window.setInterval(async () => {
      try {
        const r = await fetch(`${VIDEO_API_BASE}/api/video/live-record/status`)
        if (!r.ok) return
        const data: LiveRecState = await r.json()
        setRec(data)
        setTick(t => t + 1)
      } catch { /* ignore */ }
    }, 1000)
    return () => window.clearInterval(iv)
  }, [rec.active])

  // Stream cache-buster to force refresh on remount
  const streamSrc = `http://127.0.0.1:8099/stream?t=${tick}`

  const startRec = async () => {
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${VIDEO_API_BASE}/api/video/live-record/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source: 'eyeterm', name_hint: hint || null }),
      })
      if (!r.ok) {
        const txt = await r.text().catch(() => '')
        setError(`HTTP ${r.status}: ${txt.slice(0, 200)}`)
        return
      }
      const data = await r.json()
      setRec({ active: true, ...data })
    } catch (e: any) {
      setError(`Request failed: ${e?.message ?? e}`)
    } finally { setBusy(false) }
  }

  const stopRec = async () => {
    setBusy(true); setError(null)
    try {
      const r = await fetch(`${VIDEO_API_BASE}/api/video/live-record/stop`, { method: 'POST' })
      if (!r.ok) {
        const txt = await r.text().catch(() => '')
        setError(`HTTP ${r.status}: ${txt.slice(0, 200)}`)
        return
      }
      const data = await r.json()
      setRec({ active: false, ...data })
    } catch (e: any) {
      setError(`Request failed: ${e?.message ?? e}`)
    } finally { setBusy(false) }
  }

  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)',
    }}>
      <div style={{ fontSize: 'var(--text-body)', fontWeight: 600, color: 'var(--text-primary)' }}>
        Live Capture
        <span style={{ marginLeft: 8, fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', fontWeight: 400 }}>
          eyeTerm webcam · realtime → MP4 → Gallery
        </span>
      </div>

      {/* Stream preview */}
      <div style={{
        width: '100%', aspectRatio: '16/9', maxHeight: 480,
        background: '#000', borderRadius: 'var(--radius-md)', overflow: 'hidden',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        {streamOk === false ? (
          <div style={{ color: 'var(--text-tertiary)', textAlign: 'center', fontSize: 'var(--text-caption1)' }}>
            <div style={{ fontSize: 32, marginBottom: 8 }}>📷</div>
            <div>eyeTerm Stream nicht erreichbar (:8099)</div>
            <div style={{ marginTop: 4, fontSize: 'var(--text-caption2)' }}>
              eyeTerm muss laufen — startet automatisch mit Vibemind
            </div>
          </div>
        ) : (
          <img
            src={streamSrc}
            alt="eyeTerm live stream"
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            onError={() => setStreamOk(false)}
            onLoad={() => setStreamOk(true)}
          />
        )}
        {rec.active && (
          <div style={{
            position: 'absolute', top: 12, left: 12,
            display: 'flex', alignItems: 'center', gap: 6,
            background: 'rgba(255,40,40,0.85)', color: '#fff',
            padding: '4px 10px', borderRadius: 999, fontSize: 'var(--text-caption2)',
            fontWeight: 600, animation: 'pulse 1.5s ease-in-out infinite',
          }}>
            <span style={{ width: 8, height: 8, borderRadius: 4, background: '#fff' }} />
            REC · {Math.floor(rec.duration_s || 0)}s
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-3" style={{ flexWrap: 'wrap' }}>
        {!rec.active ? (
          <>
            <input
              type="text"
              placeholder="Name (optional)"
              value={hint}
              onChange={e => setHint(e.target.value)}
              style={{
                padding: '6px 12px', fontSize: 'var(--text-footnote)',
                background: 'var(--bg-primary)', color: 'var(--text-primary)',
                border: '1px solid var(--separator)', borderRadius: 'var(--radius-sm)',
                width: 200,
              }}
            />
            <button
              onClick={startRec}
              disabled={busy || streamOk === false}
              style={{
                padding: '8px 16px', fontSize: 'var(--text-footnote)',
                background: '#ef4444', color: '#fff', border: 'none',
                borderRadius: 'var(--radius-sm)', cursor: busy ? 'wait' : 'pointer',
                fontWeight: 600, opacity: (busy || streamOk === false) ? 0.5 : 1,
              }}
            >
              ● Aufnahme starten
            </button>
          </>
        ) : (
          <button
            onClick={stopRec}
            disabled={busy}
            style={{
              padding: '8px 16px', fontSize: 'var(--text-footnote)',
              background: '#444', color: '#fff', border: '1px solid #ef4444',
              borderRadius: 'var(--radius-sm)', cursor: busy ? 'wait' : 'pointer',
              fontWeight: 600,
            }}
          >
            ■ Stop
          </button>
        )}
      </div>

      {error && (
        <div style={{
          background: 'rgba(255,60,60,0.1)', color: '#ff8080',
          padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--text-caption1)',
        }}>{error}</div>
      )}

      {!rec.active && rec.output_path && rec.size_mb !== undefined && (
        <div style={{
          background: 'rgba(34,204,136,0.08)', color: '#22cc88',
          padding: 'var(--space-3)', borderRadius: 'var(--radius-sm)',
          fontSize: 'var(--text-caption1)',
        }}>
          ✓ Aufnahme gespeichert: <code>{rec.output_path.split(/[/\\]/).pop()}</code> ({rec.size_mb} MB).
          Erscheint in 30s in der Gallery — dort kannst du Face Swap anwenden.
        </div>
      )}

      <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
        Hinweis: Audio wird nicht aufgenommen (MJPEG hat keine Tonspur). Output landet in <code>~/.rowboat/Videos/</code>.
      </div>
    </div>
  )
}

// ── Pipeline Reference View (Surya) ──────────────────────────

const STEP_ICONS: Record<string, string> = {
  raw: '\u{1F4F7}', analyze: '\u{1F50D}', voice_clone: '\u{1F3A4}', transcript: '\u{1F4DD}',
  tts: '\u{1F5E3}', lipsync: '\u{1F444}', background: '\u{1F3AC}', composite: '\u{1F3AD}',
  build: '\u{1F3D7}', final: '\u2728',
}

const STEP_COLORS: Record<string, string> = {
  raw: '#4488ff', analyze: '#44aaff', voice_clone: '#ffc145', transcript: '#88cc44',
  tts: '#ff8844', lipsync: '#ff5a6e', background: '#8866ff', composite: '#22ccaa',
  build: '#cc66ff', final: '#44ff88',
}

function PipelineReferenceView() {
  const [ref, setRef] = useState<ReferencePipeline | null>(null)
  const [playingVideo, setPlayingVideo] = useState<string | null>(null)

  useEffect(() => {
    (async () => {
      try {
        const res = await api()?.getReferencePipeline?.()
        if (res?.success) setRef(res)
      } catch { /* ignore */ }
    })()
  }, [])

  if (!ref) return null

  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)',
    }}>
      <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-body)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
          Video Pipeline
        </span>
        <span style={{
          fontSize: 'var(--text-caption2)', padding: '2px 8px',
          borderRadius: 'var(--radius-sm)', background: 'rgba(100,140,255,0.15)', color: 'var(--accent)',
        }}>
          Referenz: {ref.person}
        </span>
      </div>

      {/* Horizontal pipeline flow */}
      <div style={{
        display: 'flex', gap: 'var(--space-2)', overflowX: 'auto',
        padding: 'var(--space-1) 0',
      }}>
        {ref.steps.map((stepName, i) => {
          const info = ref.step_info[stepName]
          const asset = ref.assets[stepName]
          const hasOutput = asset?.status === 'completed' && asset.output_path
          const color = STEP_COLORS[stepName] || '#888'

          return (
            <div key={stepName} className="flex items-center gap-1">
              <button
                onClick={() => hasOutput && setPlayingVideo(asset.output_path)}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  gap: 4, padding: 'var(--space-3)',
                  background: 'var(--fill-quaternary)', border: `1px solid ${hasOutput ? color + '44' : 'var(--separator)'}`,
                  borderRadius: 'var(--radius-md)', minWidth: 110, maxWidth: 130,
                  cursor: hasOutput ? 'pointer' : 'default',
                  transition: 'border-color 150ms ease',
                }}
                onMouseEnter={e => { if (hasOutput) e.currentTarget.style.borderColor = color }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = hasOutput ? color + '44' : 'var(--separator)' }}
              >
                <span style={{ fontSize: 22 }}>{STEP_ICONS[stepName] || '\u{1F4E6}'}</span>
                <span style={{ fontSize: 'var(--text-caption1)', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {info?.label || stepName}
                </span>
                <span style={{
                  fontSize: 9, color: 'var(--text-tertiary)',
                  textAlign: 'center', lineHeight: 1.3,
                  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                }}>
                  {info?.description}
                </span>
                {info?.api && (
                  <span style={{
                    fontSize: 8, padding: '1px 4px', borderRadius: 3,
                    background: 'rgba(255,193,69,0.15)', color: '#ffc145',
                  }}>
                    {info.api}
                  </span>
                )}
                {hasOutput && (
                  <span style={{ fontSize: 8, color: 'var(--system-green)' }}>
                    \u25B6 Abspielen
                  </span>
                )}
              </button>
              {i < ref.steps.length - 1 && (
                <span style={{ color: 'var(--text-quaternary)', fontSize: 14 }}>\u2192</span>
              )}
            </div>
          )
        })}
      </div>

      {/* Video player for reference */}
      {playingVideo && (
        <div style={{ marginTop: 'var(--space-3)' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
              {playingVideo.split(/[\\/]/).pop()}
            </span>
            <button onClick={() => setPlayingVideo(null)} style={linkBtnStyle}>Schliessen</button>
          </div>
          <video
            src={toVideoURL(playingVideo)}
            controls autoPlay
            style={{
              width: '100%', maxHeight: 300,
              borderRadius: 'var(--radius-md)', background: '#000',
            }}
          />
        </div>
      )}
    </div>
  )
}

// ── Project List ─────────────────────────────────────────────

function ProjectList({ selectedId, onSelect }: {
  selectedId: string | null; onSelect: (id: string | null) => void
}) {
  const [projects, setProjects] = useState<VideoProject[]>([])

  useEffect(() => {
    (async () => {
      try {
        const res = await api()?.listProjects?.()
        if (res?.success) setProjects(res.projects || [])
      } catch { /* ignore */ }
    })()
  }, [])

  if (projects.length === 0) return null

  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)',
    }}>
      <div style={{
        fontSize: 'var(--text-body)', fontWeight: 'var(--weight-semibold)',
        color: 'var(--text-primary)', marginBottom: 'var(--space-3)',
      }}>
        Projekte
      </div>
      <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
        {projects.map(p => (
          <button
            key={p.id}
            onClick={() => onSelect(selectedId === p.id ? null : p.id)}
            style={{
              padding: 'var(--space-2) var(--space-3)',
              background: selectedId === p.id ? 'rgba(100,140,255,0.15)' : 'var(--fill-quaternary)',
              border: `1px solid ${selectedId === p.id ? 'var(--accent)' : 'var(--separator)'}`,
              borderRadius: 'var(--radius-md)', cursor: 'pointer',
              transition: 'all 150ms ease',
            }}
          >
            <div style={{ fontSize: 'var(--text-footnote)', fontWeight: 600, color: 'var(--text-primary)' }}>
              {p.name}
            </div>
            <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginTop: 2 }}>
              {p.person_count} Personen \u00B7 {p.status}
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Project Pipeline Matrix ──────────────────────────────────

function ProjectPipelineMatrix({ projectId }: { projectId: string }) {
  const [matrix, setMatrix] = useState<PipelineMatrix | null>(null)
  const [runningStep, setRunningStep] = useState<string | null>(null)
  const [playingVideo, setPlayingVideo] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const res = await api()?.getProjectPipeline?.(projectId)
      if (res?.success) setMatrix(res)
    } catch { /* ignore */ }
  }, [projectId])

  useEffect(() => { refresh() }, [refresh])

  // Poll while step is running
  useEffect(() => {
    if (!runningStep) return
    const iv = setInterval(refresh, 3000)
    return () => clearInterval(iv)
  }, [runningStep, refresh])

  if (!matrix) return null

  const handleRunStep = async (personName: string, stepName: string) => {
    const key = `${personName}:${stepName}`
    setRunningStep(key)
    try {
      await api()?.runPipelineStep?.(projectId, personName, stepName)
    } catch { /* ignore */ }
    setRunningStep(null)
    refresh()
  }

  const statusSymbol = (s: PipelineStepStatus | undefined, personName: string, stepName: string) => {
    if (!s) return <span style={{ color: 'var(--text-quaternary)' }}>\u2014</span>
    const key = `${personName}:${stepName}`
    if (runningStep === key) return <span className="spin" style={{ color: '#ffc145' }}>\u21BB</span>

    switch (s.status) {
      case 'completed':
        return s.output_path ? (
          <button
            onClick={() => setPlayingVideo(s.output_path)}
            style={{ ...cellBtnStyle, color: 'var(--system-green)' }}
            title="Abspielen"
          >
            \u25B6
          </button>
        ) : (
          <span style={{ color: 'var(--system-green)' }}>\u2713</span>
        )
      case 'failed':
        return <span style={{ color: 'var(--system-red)' }} title="Fehlgeschlagen">\u2717</span>
      case 'skipped':
        return <span style={{ color: 'var(--text-quaternary)' }}>skip</span>
      case 'running':
        return <span className="spin" style={{ color: '#ffc145' }}>\u21BB</span>
      case 'pending':
        return (
          <button
            onClick={() => handleRunStep(personName, stepName)}
            style={{ ...cellBtnStyle, color: 'var(--accent)' }}
            title="Step starten"
          >
            \u25B6
          </button>
        )
      default:
        return <span style={{ color: 'var(--text-quaternary)' }}>\u2014</span>
    }
  }

  return (
    <div style={{
      background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-4)', overflow: 'auto',
    }}>
      <div style={{
        fontSize: 'var(--text-body)', fontWeight: 'var(--weight-semibold)',
        color: 'var(--text-primary)', marginBottom: 'var(--space-3)',
      }}>
        Pipeline Status
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--text-caption1)' }}>
        <thead>
          <tr>
            <th style={thStyle}>Person</th>
            {matrix.steps.map(s => (
              <th key={s} style={{ ...thStyle, textAlign: 'center' }}>
                <span style={{ fontSize: 14 }}>{STEP_ICONS[s] || ''}</span>
                <br />
                {matrix.step_info[s]?.label || s}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.persons.map(person => (
            <tr key={person}>
              <td style={{ ...tdStyle, fontWeight: 600, color: 'var(--text-primary)' }}>{person}</td>
              {matrix.steps.map(step => (
                <td key={step} style={{ ...tdStyle, textAlign: 'center' }}>
                  {statusSymbol(matrix.matrix[person]?.[step], person, step)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Inline video player */}
      {playingVideo && (
        <div style={{ marginTop: 'var(--space-3)' }}>
          <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-2)' }}>
            <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
              {playingVideo.split(/[\\/]/).pop()}
            </span>
            <button onClick={() => setPlayingVideo(null)} style={linkBtnStyle}>Schliessen</button>
          </div>
          <video
            src={toVideoURL(playingVideo)}
            controls autoPlay
            style={{ width: '100%', maxHeight: 300, borderRadius: 'var(--radius-md)', background: '#000' }}
          />
        </div>
      )}
    </div>
  )
}

// ── Shared Styles ─────────────────────────────────────────────

const selectStyle: React.CSSProperties = {
  background: 'var(--fill-tertiary)', color: 'var(--text-primary)',
  border: '1px solid var(--separator)', borderRadius: 'var(--radius-sm)',
  padding: '5px 10px', fontSize: 'var(--text-caption1)',
}

const linkBtnStyle: React.CSSProperties = {
  background: 'none', border: 'none', color: 'var(--accent)',
  fontSize: 'var(--text-caption1)', cursor: 'pointer', padding: 0,
}

const tabBtnStyle: React.CSSProperties = {
  background: 'var(--fill-quaternary)', border: '1px solid var(--separator)',
  borderRadius: 'var(--radius-sm)', padding: '4px 12px',
  fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)',
  cursor: 'pointer', transition: 'all 150ms ease',
}

const tabBtnActiveStyle: React.CSSProperties = {
  background: 'rgba(100,140,255,0.15)', borderColor: 'var(--accent)', color: 'var(--accent)',
}

const cellBtnStyle: React.CSSProperties = {
  background: 'none', border: 'none', cursor: 'pointer', padding: '2px 4px',
  fontSize: 14,
}

const thStyle: React.CSSProperties = {
  padding: '6px 8px', borderBottom: '1px solid var(--separator)',
  color: 'var(--text-tertiary)', fontWeight: 500, fontSize: 'var(--text-caption2)',
  whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '8px', borderBottom: '1px solid var(--separator-opaque, var(--separator))',
  color: 'var(--text-secondary)',
}
