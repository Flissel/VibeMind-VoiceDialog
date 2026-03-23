import { useState, useEffect, useCallback, useRef } from 'react'
import type { VideoStatusResponse, VideoToolResult, VideoFileInfo, VideoListResponse } from '../types'

const api = () => (window as any).vibemindVideo

// ── Wizard Configuration ──────────────────────────────────────

type WizardId = 'team' | 'vision' | 'demo' | 'lipsync' | 'voice'
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
      <VideoGallery />
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

// ── Video Gallery (unchanged) ─────────────────────────────────

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

  if (videos.length === 0) {
    return (
      <div style={{
        background: 'var(--bg-secondary)', borderRadius: 'var(--radius-lg)',
        padding: 'var(--space-6)', textAlign: 'center', color: 'var(--text-tertiary)',
      }}>
        <div style={{ fontSize: 32, marginBottom: 'var(--space-2)' }}>&#127909;</div>
        <div style={{ fontSize: 'var(--text-footnote)' }}>Keine Videos gefunden</div>
        <div style={{ fontSize: 'var(--text-caption2)', marginTop: 4 }}>
          Starte eine Pipeline um Videos zu generieren
        </div>
      </div>
    )
  }

  return (
    <>
      {selectedVideo && <VideoPlayerModal video={selectedVideo} onClose={() => setSelectedVideo(null)} />}
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
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 'var(--space-3)' }}>
          {filtered.map(video => <VideoCard key={video.path} video={video} onClick={() => setSelectedVideo(video)} />)}
        </div>
      </div>
    </>
  )
}

function VideoCard({ video, onClick }: { video: VideoFileInfo; onClick: () => void }) {
  const videoSrc = `vibemind-video://video/${video.path.replace(/\\/g, '/')}`
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

function VideoPlayerModal({ video, onClose }: { video: VideoFileInfo; onClose: () => void }) {
  const videoSrc = `vibemind-video://video/${video.path.replace(/\\/g, '/')}`
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.88)',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: 'var(--space-6)',
    }}>
      <div onClick={e => e.stopPropagation()} style={{ maxWidth: '90%', maxHeight: '90%', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        <div className="flex items-center justify-between">
          <span style={{ fontSize: 'var(--text-body)', fontWeight: 600, color: '#fff' }}>{video.filename}</span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#fff', fontSize: 20, cursor: 'pointer', padding: '4px 8px' }}>&#x2715;</button>
        </div>
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
