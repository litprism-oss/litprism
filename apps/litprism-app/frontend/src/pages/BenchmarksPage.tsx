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
          {ds.record_count} real records · {ds.relevant_count} relevant
        </p>
      </div>

      <details>
        <summary style={{ fontSize: 13, cursor: 'pointer' }}>Source and criteria</summary>
        {ds.source && (
          <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--color-text-secondary)', margin: '6px 0 0' }}>
            {ds.source}
          </p>
        )}
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
            <Metric label="Recall" value={pct(m.recall)} hint="Of the relevant records, how many the AI kept. Higher is safer." />
            <Metric label="Precision" value={pct(m.precision)} hint="Of the records the AI kept, how many were really relevant." />
            <Metric label="Work saved" value={pct(m.work_saved)} hint="Share of records the AI set aside, so nobody has to read them." />
          </div>

          <div style={{ fontSize: 13, lineHeight: 1.7, background: 'var(--color-background-secondary)', borderRadius: 'var(--border-radius-md)', padding: 12 }}>
            <p style={{ fontWeight: 500, margin: '0 0 4px' }}>In plain words</p>
            <p style={{ margin: 0 }}>
              The AI kept {m.kept ?? '?'} of {m.n} records for a person to read and set the rest aside.
              {m.relevant > 0 && (
                <> Of the {m.relevant} records the review authors included, it kept {m.relevant - m.missed} and {m.missed === 0 ? 'missed none' : `missed ${m.missed}`}.</>
              )}
              {(m.uncertain ?? 0) > 0 && <> {m.uncertain} were &quot;uncertain&quot; (the abstract did not settle it), which are kept for a person to check.</>}
            </p>
          </div>

          {(m.missed_records?.length ?? 0) > 0 && (
            <div>
              <p style={{ fontSize: 13, fontWeight: 500, margin: '0 0 6px' }}>
                {m.missed === 1 ? 'The relevant record the AI excluded' : `Relevant records the AI excluded (${m.missed})`}
              </p>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.6, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {m.missed_records!.map((r) => (
                  <li key={r.title}>
                    <span style={{ fontWeight: 500 }}>{r.title}</span>
                    {r.reasoning && <span style={{ color: 'var(--color-text-secondary)' }}> — AI reason: {r.reasoning}</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {m.missed > 0 && !m.missed_records && (
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>
              {m.missed} relevant record{m.missed === 1 ? ' was' : 's were'} excluded. Run again to see which.
            </p>
          )}
          <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>
            {m.errors > 0 && `${m.errors} could not be screened. `}
            {run?.model_used && `Model: ${run.model_used}.`}
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
          Pick a published systematic review. LitPrism screens a sample of its real records with the current
          AI model and compares the result with the review authors' own inclusion decisions. The samples
          have more relevant records than a real search, so read recall as the main number. One benchmark
          runs at a time; each uses LLM calls.
        </p>
      </div>
      <details style={{ ...card, gap: 0 }}>
        <summary style={{ fontSize: 14, fontWeight: 500, cursor: 'pointer' }}>How to read the results</summary>
        <div style={{ fontSize: 13, lineHeight: 1.7, marginTop: 8 }}>
          <p style={{ margin: '0 0 8px' }}>
            <b>Recall</b>: of the papers that belong in the review, how many did the AI keep? 100% means it
            missed none. This matters most, because a paper dropped here is lost. Aim for 95% or more.
          </p>
          <p style={{ margin: '0 0 8px' }}>
            <b>Precision</b>: of the papers the AI kept, how many really belong? Low precision just means
            extra papers for you to read and discard. It is the cheaper mistake.
          </p>
          <p style={{ margin: '0 0 8px' }}>
            <b>Work saved</b>: the share of papers the AI set aside, so a person never has to read them.
          </p>
          <p style={{ margin: 0 }}>
            <b>Uncertain</b>: the abstract did not give enough to decide. These count as kept, never as
            excluded. A good result has high recall and a fair amount of work saved.
          </p>
        </div>
      </details>
      {isLoading && <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>Loading…</p>}
      {isError && <p style={{ fontSize: 13, color: '#791F1F' }}>Could not load the benchmarks.</p>}
      {data?.map((ds) => (
        <DatasetCard key={ds.slug} ds={ds} busy={anyRunning} />
      ))}
    </div>
  )
}
