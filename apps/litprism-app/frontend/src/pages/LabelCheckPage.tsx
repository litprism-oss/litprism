import { useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { LabelCheckOut } from '@/lib/types'
import { SampleData } from '@/components/SampleData'

const pct = (v: number | null) => (v == null ? 'n/a' : `${(v * 100).toFixed(1)}%`)

const card = {
  background: 'var(--color-background-primary)',
  border: '0.5px solid var(--color-border-tertiary)',
  borderRadius: 'var(--border-radius-lg)',
  padding: 16,
} as const

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div style={{ ...card, flex: '1 1 140px' }}>
      <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: 0 }}>{label}</p>
      <p style={{ fontSize: 24, fontWeight: 500, margin: '2px 0 4px' }}>{value}</p>
      <p style={{ fontSize: 12, lineHeight: 1.5, color: 'var(--color-text-secondary)', margin: 0 }}>{hint}</p>
    </div>
  )
}

export function LabelCheckPage() {
  const { projectId = '' } = useParams()
  const input = useRef<HTMLInputElement>(null)
  const [result, setResult] = useState<LabelCheckOut | null>(null)
  const mutation = useMutation({
    mutationFn: (file: File) => api.screening.labelCheck(projectId, file),
    onSuccess: setResult,
  })

  return (
    <div style={{ maxWidth: 760, display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div>
        <p style={{ fontSize: 15, fontWeight: 500, margin: '0 0 4px' }}>Check against my labels</p>
        <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-secondary)', margin: 0 }}>
          Upload a CSV of your own include/exclude decisions. LitPrism compares them with the AI
          screening and shows how many relevant articles the AI would have missed. Nothing is
          re-screened, so it is instant and costs no API calls.
        </p>
      </div>

      <div style={card}>
        <p style={{ fontSize: 13, lineHeight: 1.6, margin: '0 0 12px' }}>
          Columns: <b>title</b> (or <b>doi</b>) and a label column named <b>label</b>,{' '}
          <b>label_included</b>, <b>included</b> or <b>decision</b>. Use 1 / yes / include for
          relevant articles and 0 / no / exclude for the rest.
        </p>
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) mutation.mutate(f)
            e.target.value = ''
          }}
        />
        <button
          onClick={() => input.current?.click()}
          disabled={mutation.isPending}
          style={{
            minHeight: 44,
            padding: '0 18px',
            background: 'var(--color-text-primary)',
            color: 'var(--color-background-primary)',
            border: 'none',
            borderRadius: 'var(--border-radius-md)',
            fontSize: 14,
            fontWeight: 500,
            fontFamily: 'inherit',
            cursor: mutation.isPending ? 'default' : 'pointer',
            opacity: mutation.isPending ? 0.6 : 1,
          }}
        >
          {mutation.isPending ? 'Comparing…' : 'Choose CSV file'}
        </button>
        {mutation.isError && (
          <p role="alert" style={{ fontSize: 13, color: '#791F1F', margin: '12px 0 0' }}>
            {mutation.error.message}
          </p>
        )}
      </div>

      <SampleData />

      {result && (
        <>
          <p style={{ fontSize: 13, color: 'var(--color-text-secondary)', margin: 0 }}>
            {result.matched.toLocaleString()} of {result.uploaded.toLocaleString()} rows matched a
            screened article{result.unmatched > 0 && ` (${result.unmatched.toLocaleString()} not found in this review)`}.
            {' '}{result.relevant.toLocaleString()} are relevant by your labels.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12 }}>
            <Tile
              label="Recall"
              value={pct(result.recall)}
              hint="Share of your relevant articles the AI kept for review (include or uncertain)."
            />
            <Tile
              label="Precision"
              value={pct(result.precision)}
              hint="Share of the articles the AI kept that you also marked relevant."
            />
            <Tile
              label="Work saved"
              value={pct(result.work_saved)}
              hint="Share of articles the AI excluded, so you did not need to read them."
            />
          </div>
          <div style={card}>
            <p style={{ fontSize: 14, fontWeight: 500, margin: '0 0 6px' }}>
              {result.missed === 0
                ? 'The AI excluded none of your relevant articles'
                : `${result.missed.toLocaleString()} relevant ${result.missed === 1 ? 'article was' : 'articles were'} excluded by the AI`}
            </p>
            {result.missed_titles.length > 0 && (
              <ul style={{ margin: '8px 0 0', paddingLeft: 18, fontSize: 13, lineHeight: 1.6 }}>
                {result.missed_titles.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            )}
            {result.missed > result.missed_titles.length && (
              <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', margin: '8px 0 0' }}>
                Showing the first {result.missed_titles.length}.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}
