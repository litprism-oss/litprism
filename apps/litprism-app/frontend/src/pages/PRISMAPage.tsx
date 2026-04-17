import { useRef } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PRISMAFlowCounts } from '@/lib/types'
import { formatCount } from '@/lib/utils'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// ── Box components ─────────────────────────────────────────────────────────────

interface LiveBoxProps {
  label: string
  count: number
  sub?: string
  variant: 'blue' | 'excl' | 'purple'
}

function LiveBox({ label, count, sub, variant }: LiveBoxProps) {
  const styles: Record<string, React.CSSProperties> = {
    blue:   { border: '0.5px solid #378ADD', background: '#E6F1FB' },
    excl:   { border: '0.5px solid var(--color-border-secondary)', background: 'var(--color-background-primary)' },
    purple: { border: '0.5px solid #534AB7', background: '#EEEDFE' },
  }
  const countColor: Record<string, string> = {
    blue:   '#0C447C',
    excl:   'var(--color-text-primary)',
    purple: '#3C3489',
  }
  return (
    <div style={{ ...styles[variant], borderRadius: '8px', padding: '10px 12px', minWidth: '160px' }}>
      <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginBottom: '3px' }}>{label}</p>
      <p style={{ fontSize: '18px', fontWeight: 500, color: countColor[variant] }}>{formatCount(count)}</p>
      {sub && <p style={{ fontSize: '10px', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>{sub}</p>}
    </div>
  )
}

function PendingBox({ label, sub }: { label: string; sub?: string }) {
  return (
    <div
      style={{
        border: '0.5px solid var(--color-border-tertiary)',
        background: 'var(--color-background-secondary)',
        borderRadius: '8px',
        padding: '10px 12px',
        minWidth: '160px',
        opacity: 0.5,
      }}
    >
      <p style={{ fontSize: '11px', color: 'var(--color-text-secondary)', marginBottom: '3px' }}>{label}</p>
      <p style={{ fontSize: '14px', color: 'var(--color-text-tertiary)' }}>n = —</p>
      {sub && <p style={{ fontSize: '10px', color: 'var(--color-text-tertiary)', marginTop: '2px' }}>{sub}</p>}
    </div>
  )
}

const ArrowDown = ({ faded }: { faded?: boolean }) => (
  <div style={{ width: '1px', height: '12px', background: 'var(--color-border-secondary)', margin: '4px 0 4px 80px', opacity: faded ? 0.3 : 1 }} />
)

const ArrowRight = ({ faded }: { faded?: boolean }) => (
  <div style={{ width: '18px', height: '1px', background: 'var(--color-border-secondary)', marginTop: '20px', flexShrink: 0, opacity: faded ? 0.3 : 1 }} />
)

// ── Phase pill ─────────────────────────────────────────────────────────────────

function PhasePill({ label, color, height }: { label: string; color: string; height: number }) {
  return (
    <div style={{ height, display: 'flex', alignItems: 'center' }}>
      <span
        style={{
          writingMode: 'vertical-rl',
          transform: 'rotate(180deg)',
          fontSize: '11px',
          fontWeight: 500,
          color: '#fff',
          padding: '8px 6px',
          borderRadius: '4px',
          background: color,
          height: height - 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {label}
      </span>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────

function PRISMADiagram({ counts }: { counts: PRISMAFlowCounts }) {
  const totalIdentified = counts.db_records + counts.other_records
  const pending = counts.fulltext_assessed === null

  return (
    <div style={{ display: 'flex', gap: '6px', alignItems: 'flex-start' }}>
      {/* Phase label column */}
      <div style={{ display: 'flex', flexDirection: 'column', width: '28px' }}>
        <PhasePill label="Identification" color="#378ADD" height={80} />
        <div style={{ height: '16px' }} />
        <PhasePill label="Screening" color="#639922" height={72} />
        <div style={{ height: '16px' }} />
        <PhasePill label="Eligibility" color="#888780" height={72} />
        <div style={{ height: '16px' }} />
        <PhasePill label="Included" color="#534AB7" height={64} />
      </div>

      {/* Flow column */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Identification */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', marginBottom: '4px' }}>
          <LiveBox
            label="Records identified"
            count={totalIdentified}
            sub={`${formatCount(counts.db_records)} API · ${formatCount(counts.other_records)} uploads`}
            variant="blue"
          />
          <ArrowRight />
          <LiveBox
            label="Removed before screening"
            count={counts.duplicates_removed}
            sub="Duplicates removed"
            variant="excl"
          />
        </div>
        <ArrowDown />

        {/* Screening */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', marginBottom: '4px' }}>
          <LiveBox
            label="Records screened"
            count={counts.records_screened}
            sub="Abstract screening"
            variant="blue"
          />
          <ArrowRight />
          <LiveBox
            label="Records excluded"
            count={counts.excluded_screening}
            sub="Wrong design / population / etc."
            variant="excl"
          />
        </div>
        <ArrowDown faded={pending} />

        {/* Eligibility */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start', marginBottom: '4px' }}>
          {pending ? (
            <PendingBox label="Assessed for eligibility" sub="Full-text · Session 10" />
          ) : (
            <LiveBox
              label="Assessed for eligibility"
              count={counts.fulltext_assessed!}
              sub="Full-text screening"
              variant="blue"
            />
          )}
          <ArrowRight faded={pending} />
          {pending ? (
            <PendingBox label="Reports excluded" sub="With reasons · Session 10" />
          ) : (
            <LiveBox
              label="Reports excluded"
              count={counts.fulltext_excluded!}
              sub="With reasons"
              variant="excl"
            />
          )}
        </div>
        <ArrowDown faded={pending} />

        {/* Included */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
          <LiveBox
            label="Studies included"
            count={counts.studies_included}
            sub={pending ? 'Uncertain → full-text review' : undefined}
            variant="purple"
          />
        </div>
      </div>
    </div>
  )
}

export function PRISMAPage() {
  const { projectId = '' } = useParams()
  const diagramRef = useRef<HTMLDivElement>(null)

  const { data: counts, isLoading, error } = useQuery({
    queryKey: ['prisma', projectId],
    queryFn: () => api.prisma.counts(projectId),
    enabled: !!projectId,
    refetchInterval: 30_000,
  })

  const handleDownloadSVG = () => {
    if (!diagramRef.current) return
    const serializer = new XMLSerializer()
    const content = serializer.serializeToString(diagramRef.current)
    const blob = new Blob([content], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'prisma-flow.svg'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handlePrismaS = async () => {
    try {
      const res = await fetch(`${BASE_URL}/projects/${projectId}/export/prisma-s`)
      if (!res.ok) return
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'prisma-s.docx'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // silent — export endpoint not available yet
    }
  }

  return (
    <div style={{ padding: '24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '10px', marginBottom: '4px' }}>
        <span style={{ fontSize: '16px', fontWeight: 500, color: 'var(--color-text-primary)' }}>
          PRISMA 2020 flow diagram
        </span>
        <span
          style={{
            fontSize: '10px',
            padding: '2px 8px',
            borderRadius: '99px',
            background: '#EAF3DE',
            color: '#27500A',
          }}
        >
          ● Live
        </span>
      </div>
      <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '12px' }}>
        Updates automatically as you search, upload, and screen
      </p>

      {/* Actions */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <button
          onClick={handleDownloadSVG}
          style={{
            fontSize: '12px',
            padding: '6px 12px',
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: 'var(--border-radius-md)',
            background: 'transparent',
            color: 'var(--color-text-primary)',
            cursor: 'pointer',
          }}
        >
          Download SVG
        </button>
        <button
          onClick={handlePrismaS}
          style={{
            fontSize: '12px',
            padding: '6px 12px',
            border: '0.5px solid var(--color-border-secondary)',
            borderRadius: 'var(--border-radius-md)',
            background: 'transparent',
            color: 'var(--color-text-primary)',
            cursor: 'pointer',
          }}
        >
          Include in PRISMA-S .docx
        </button>
      </div>

      {/* Diagram */}
      <div ref={diagramRef}>
        {isLoading && (
          <p style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>Loading…</p>
        )}
        {error && (
          <p style={{ fontSize: '13px', color: '#8B5E00' }}>Failed to load PRISMA counts.</p>
        )}
        {counts && <PRISMADiagram counts={counts} />}
      </div>
    </div>
  )
}
