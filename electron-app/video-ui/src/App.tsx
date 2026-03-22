import { VideoProduction } from './features/VideoProduction'

export default function App() {
  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <nav
        className="flex items-center flex-shrink-0"
        style={{
          height: 44,
          padding: '0 var(--space-4)',
          gap: 'var(--space-3)',
          borderBottom: '1px solid var(--separator)',
          background: 'var(--material-thick)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
        }}
      >
        <span style={{
          fontSize: 'var(--text-footnote)',
          fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-primary)',
        }}>
          Video Studio
        </span>

        <div style={{ flex: 1 }} />
        <button
          onClick={() => {
            const v = (window as any).vibemindVideo
            if (v?.closeVideo) v.closeVideo()
          }}
          className="hover-bg"
          title="Schliessen"
          style={{
            width: 28, height: 28, borderRadius: 'var(--radius-sm)',
            border: 'none', background: 'transparent',
            color: 'var(--text-tertiary)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14,
          }}
        >
          &#x2715;
        </button>
      </nav>

      {/* Content */}
      <div className="flex-1 overflow-hidden" style={{ position: 'relative' }}>
        <div className="h-full overflow-y-auto" style={{ padding: 'var(--space-4)' }}>
          <VideoProduction />
        </div>
      </div>
    </div>
  )
}
