import { toast } from 'sonner'
import { useBenchmarks, useStartBenchmark } from '@/hooks/useBenchmarks'
import type { BenchmarkDatasetOut } from '@/lib/types'

const pct = (v: number | null | undefined) => (v == null ? 'n/a' : `${(v * 100).toFixed(1)}%`)

const card = {
  background: 'var(--color-background-primary)',
  border: '0.5px solid var(--color-border-tertiary)',
  borderRadius: 'var(--border-radius-lg)',
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
} as const

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div style={{ background: 'var(--color-background-secondary)', borderRadius: 'var(--border-radius-md)', padding: 12 }}>
      <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 22, fontWeight: 500, margin: '2px 0 4px' }}>{value}</p>
      <p style={{ fontSize: 11, lineHeight: 1.4, color: 'var(--color-text-secondary)', margin: 0 }}>{hint}</p>
    </div>
  )
}

function DatasetCard({ ds, busy }: { ds: BenchmarkDatasetOut; busy: boolean }) {
  const start = useStartBenchmark()
  const run = ds.latest_run
  const running = run?.status === 'pending' || run?.status === 'running'
  const m = run?.status === 'completed' ? run.metrics : null

  return (
    <div style={card}>
      <div>
        <p style={{ fontSize: 15, fontWeight: 500, margin: '0 0 4px' }}>{ds.name}</p>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)', margin: 0 }}>
          {ds.description}
        </p>
        <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '6px 0 0' }}>
          {ds.record_count} records · {ds.relevant_count} relevant by design
        </p>
      </div>

      <details>
        <summary style={{ fontSize: 13, cursor: 'pointer' }}>Criteria used</summary>
        <ul style={{ fontSize: 12, lineHeight: 1.6, margin: '6px 0 0', paddingLeft: 18 }}>
          {ds.criteria.inclusion.map((c) => <li key={c}>Include: {c}</li>)}
          {ds.criteria.exclusion.map((c) => <li key={c}>Exclude: {c}</li>)}
        </ul>
      </details>

      {running && run && (
        <div>
          <div style={{ height: 6, borderRadius: 99, background: 'var(--color-background-secondary)', overflow: 'hidden' }}>
            <div style={{ width: `${run.total ? (run.processed / run.total) * 100 : 0}%`, height: '100%', background: 'var(--color-text-primary)', transition: 'width .3s' }} />
          </div>
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '6px 0 0' }}>
            {run.status === 'pending' ? 'Waiting for a worker…' : `Screening ${run.processed} of ${run.total}…`}
          </p>
        </div>
      )}

      {run?.status === 'failed' && (
        <p role="alert" style={{ fontSize: 13, color: '#791F1F', margin: 0 }}>
          Last run failed{run.error ? `: ${run.error}` : '.'}
        </p>
      )}

      {m && (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
            <Metric label="Recall" value={pct(m.recall)} hint="Relevant records the AI kept for review." />
            <Metric label="Precision" value={pct(m.precision)} hint="Kept records that are truly relevant." />
            <Metric label="Work saved" value={pct(m.work_saved)} hint="Records excluded, so not read by a person." />
          </div>
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>
            {m.missed === 0 ? 'No relevant record was excluded.' : `${m.missed} relevant record${m.missed === 1 ? ' was' : 's were'} excluded by the AI.`}
            {m.errors > 0 && ` ${m.errors} could not be screened.`}
            {run?.model_used && ` Model: ${run.model_used}.`}
          </p>
        </>
      )}

      <button
        onClick={() => start.mutate(ds.slug, { onError: (e) => toast.error(e.message) })}
        disabled={running || busy || start.isPending}
        style={{
          minHeight: 44,
          background: 'var(--color-text-primary)',
          color: 'var(--color-background-primary)',
          border: 'none',
          borderRadius: 'var(--border-radius-md)',
          fontSize: 14,
          fontWeight: 500,
          fontFamily: 'inherit',
          cursor: running || busy ? 'default' : 'pointer',
          opacity: running || busy ? 0.5 : 1,
        }}
      >
        {running ? 'Running…' : run ? 'Run again' : 'Run benchmark'}
      </button>
    </div>
  )
}

export function BenchmarksPage() {
  const { data, isLoading, isError } = useBenchmarks()
  const anyRunning = !!data?.some((d) => ['pending', 'running'].includes(d.latest_run?.status ?? ''))

  return (
    <div style={{ maxWidth: 760, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <p style={{ fontSize: 18, fontWeight: 500, margin: '0 0 4px' }}>Benchmarks</p>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)', margin: 0 }}>
          Pick a practice review and LitPrism screens it with the current AI model, then compares the
          result with the known answers. The records are invented, so the numbers show how the tool
          behaves, not how it will do on your topic. One benchmark runs at a time; each uses LLM calls.
        </p>
      </div>
      {isLoading && <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>Loading…</p>}
      {isError && <p style={{ fontSize: 13, color: '#791F1F' }}>Could not load the benchmarks.</p>}
      {data?.map((ds) => (
        <DatasetCard key={ds.slug} ds={ds} busy={anyRunning} />
      ))}
    </div>
  )
}
