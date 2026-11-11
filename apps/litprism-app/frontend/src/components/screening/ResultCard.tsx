import { toast } from 'sonner'
import { useOverrideDecision } from '@/hooks/useScreeningResults'
import { DecisionBadge } from './DecisionBadge'
import type { ArticleWithResult, ScreeningDecision } from '@/lib/types'

const CHOICES: { decision: Exclude<ScreeningDecision, 'error'>; label: string }[] = [
  { decision: 'include', label: 'Include' },
  { decision: 'uncertain', label: 'Unsure' },
  { decision: 'exclude', label: 'Exclude' },
]

interface Props {
  projectId: string
  article: ArticleWithResult
  onOpen: () => void
}

/** Phone layout for one screened article: the evidence is visible and the human
 *  decision is one tap, instead of a table row that opens a side panel. */
export function ResultCard({ projectId, article, onOpen }: Props) {
  const override = useOverrideDecision(projectId)
  const result = article.screening_result
  if (!result) return null

  const quote = result.criteria_hits.find((h) => h.supporting_quote)?.supporting_quote ?? null

  function choose(decision: Exclude<ScreeningDecision, 'error'>) {
    if (decision === result?.decision || override.isPending) return
    override.mutate(
      { articleId: article.id, decision },
      { onError: (err) => toast.error(err.message) },
    )
  }

  return (
    <div
      style={{
        background: 'var(--color-background-primary)',
        border: '0.5px solid var(--color-border-tertiary)',
        borderRadius: 'var(--border-radius-lg)',
        padding: 14,
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <DecisionBadge decision={result.decision} human_override={result.human_override} size="sm" />
        <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>
          {Math.round(result.confidence * 100)}% confident
        </span>
      </div>

      <button
        onClick={onOpen}
        style={{
          background: 'none',
          border: 'none',
          padding: 0,
          textAlign: 'left',
          fontSize: 14,
          fontWeight: 500,
          lineHeight: 1.4,
          color: 'var(--color-text-primary)',
          cursor: 'pointer',
          fontFamily: 'inherit',
        }}
      >
        {article.title}
      </button>

      {quote && (
        <div style={{ borderLeft: '2px solid var(--color-border-secondary)', paddingLeft: 10 }}>
          <p style={{ fontSize: 12, lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
            “{quote}”
          </p>
          <p style={{ fontSize: 11, color: 'var(--color-text-secondary)', marginTop: 2 }}>
            Evidence from the {article.abstract ? 'abstract' : 'record'}
          </p>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
        {CHOICES.map(({ decision, label }) => {
          const on = result.decision === decision
          return (
            <button
              key={decision}
              onClick={() => choose(decision)}
              aria-pressed={on}
              disabled={override.isPending}
              style={{
                minHeight: 44,
                borderRadius: 'var(--border-radius-md)',
                fontSize: 13,
                fontFamily: 'inherit',
                cursor: 'pointer',
                background: on ? 'var(--color-text-primary)' : 'var(--color-background-primary)',
                color: on ? 'var(--color-background-primary)' : 'var(--color-text-primary)',
                border: `0.5px solid ${on ? 'var(--color-text-primary)' : 'var(--color-border-secondary)'}`,
                fontWeight: on ? 500 : 400,
              }}
            >
              {label}
            </button>
          )
        })}
      </div>
    </div>
  )
}
