import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { useCriteria } from '@/hooks/useCriteria'
import { useArticles } from '@/hooks/useArticles'
import { useStartScreening } from '@/hooks/useScreening'
import { api } from '@/lib/api'
import type { ArticleOut, ScreeningPreviewResult } from '@/lib/types'

interface Props {
  projectId: string
}

const DECISION_COLORS: Record<string, string> = {
  include: '#639922',
  exclude: '#791F1F',
  uncertain: '#633806',
}

const DECISION_BG: Record<string, string> = {
  include: '#EAF3DE',
  exclude: '#F5E0E0',
  uncertain: '#F5EDE0',
}

const SOURCE_COLOURS: Record<string, { bg: string; text: string }> = {
  pubmed:          { bg: '#E6F1FB', text: '#0C447C' },
  europepmc:       { bg: '#E1F5EE', text: '#085041' },
  semanticscholar: { bg: '#EEEDFE', text: '#3C3489' },
  upload:          { bg: '#F1EFE8', text: '#444441' },
}
const SOURCE_LABELS: Record<string, string> = {
  pubmed: 'PubMed', europepmc: 'Europe PMC', semanticscholar: 'Semantic Scholar', upload: 'Upload',
}

function formatAuthors(authors: ArticleOut['authors']): string {
  if (!authors || authors.length === 0) return ''
  const names = authors.slice(0, 3).map((a) => `${a.fore_name ? a.fore_name[0] + ' ' : ''}${a.last_name}`)
  return authors.length > 3 ? names.join(', ') + ' et al.' : names.join(', ')
}

function PreviewResultCard({ result, article }: { result: ScreeningPreviewResult; article: ArticleOut | undefined }) {
  const [abstractOpen, setAbstractOpen] = useState(false)
  const [hitsOpen, setHitsOpen] = useState(false)
  const color = DECISION_COLORS[result.decision] ?? 'var(--color-text-secondary)'
  const bg = DECISION_BG[result.decision] ?? 'var(--color-background-secondary)'

  const sourceColour = SOURCE_COLOURS[article?.source ?? 'upload'] ?? SOURCE_COLOURS.upload
  const sourceLabel = SOURCE_LABELS[article?.source ?? 'upload'] ?? (article?.source ?? '')
  const year = article?.publication_year ?? (article?.pub_date ? article.pub_date.slice(0, 4) : null)
  const authorStr = article ? formatAuthors(article.authors) : ''
  const meta = [authorStr, article?.journal, year].filter(Boolean).join(' · ')

  return (
    <div
      style={{
        border: '0.5px solid var(--color-border-secondary)',
        borderRadius: 'var(--border-radius-md)',
        marginBottom: '8px',
        overflow: 'hidden',
      }}
    >
      {/* Article section — ArticleRow style */}
      <div style={{ padding: '12px 14px', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
        <p style={{ fontSize: '13px', fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '4px', lineHeight: 1.4 }}>
          {article?.title ?? result.article_id}
        </p>
        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', padding: '1px 7px', borderRadius: '99px', background: sourceColour.bg, color: sourceColour.text }}>
            {sourceLabel}
          </span>
          {meta && <span>{meta}</span>}
          {article?.pmid && (
            <a href={`https://pubmed.ncbi.nlm.nih.gov/${article.pmid}/`} target="_blank" rel="noreferrer"
              style={{ fontSize: '11px', color: '#378ADD', textDecoration: 'none' }}>
              PMID {article.pmid} ↗
            </a>
          )}
          {article?.doi && (
            <a href={`https://doi.org/${article.doi}`} target="_blank" rel="noreferrer"
              style={{ fontSize: '11px', color: '#378ADD', textDecoration: 'none' }}>
              DOI ↗
            </a>
          )}
          {article?.abstract && (
            <button
              onClick={() => setAbstractOpen((v) => !v)}
              style={{ fontSize: '11px', color: 'var(--color-text-tertiary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
            >
              {abstractOpen ? 'Hide abstract' : 'Show abstract'}
            </button>
          )}
        </div>
        {abstractOpen && article?.abstract && (
          <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', lineHeight: 1.6, marginTop: '8px', paddingTop: '8px', borderTop: '0.5px solid var(--color-border-tertiary)' }}>
            {article.abstract}
          </p>
        )}
      </div>

      {/* Decision section */}
      <div style={{ padding: '10px 14px', background: 'var(--color-background-secondary)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
          <span
            style={{
              fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: '99px',
              background: bg, color, textTransform: 'uppercase', letterSpacing: '0.04em',
            }}
          >
            {result.decision}
          </span>
          <span style={{ fontSize: '11px', color: 'var(--color-text-tertiary)' }}>
            {Math.round(result.confidence * 100)}% confidence
          </span>
        </div>
        <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', margin: '0 0 6px', lineHeight: 1.5 }}>
          {result.reasoning}
        </p>
        {result.criteria_hits.length > 0 && (
          <button
            onClick={() => setHitsOpen((v) => !v)}
            style={{ fontSize: '11px', color: 'var(--color-text-tertiary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            {hitsOpen ? '▲ Hide' : '▼ Show'} criterion hits ({result.criteria_hits.length})
          </button>
        )}
        {hitsOpen && (
          <div style={{ marginTop: '8px' }}>
            {result.criteria_hits.map((hit, i) => (
              <div key={i} style={{ fontSize: '11px', padding: '6px 8px', background: 'var(--color-background-primary)', borderRadius: 'var(--border-radius-md)', marginBottom: '4px', lineHeight: 1.5 }}>
                <span style={{ fontWeight: 600, color: hit.criterion_type === 'inclusion' ? '#639922' : '#791F1F', marginRight: '6px' }}>
                  {hit.criterion_type === 'inclusion' ? 'INC' : 'EXC'}
                </span>
                <span style={{ color: 'var(--color-text-secondary)' }}>{hit.criterion}</span>
                <span style={{ marginLeft: '6px', color: 'var(--color-text-tertiary)' }}>→ {hit.assessment}</span>
                {hit.supporting_quote && (
                  <p style={{ margin: '4px 0 0', color: 'var(--color-text-tertiary)', fontStyle: 'italic' }}>
                    "{hit.supporting_quote}"
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function ScreeningSetupForm({ projectId }: Props) {
  const navigate = useNavigate()
  const { data: criteria, isLoading: criteriaLoading } = useCriteria(projectId)
  const { data: articlesPage } = useArticles(projectId, { page: 1, page_size: 50 })
  const startScreening = useStartScreening(projectId)

  const [reviewerName, setReviewerName] = useState('')
  const [notes, setNotes] = useState('')
  const [previewResults, setPreviewResults] = useState<ScreeningPreviewResult[] | null>(null)

  const totalArticles = articlesPage?.total ?? 0
  const estimatedMinutes = Math.ceil(totalArticles / 60)
  const estimatedCost = (totalArticles * 0.0015).toFixed(2)

  const previewMutation = useMutation({
    mutationFn: async () => {
      if (!criteria || !articlesPage) throw new Error('Missing criteria or articles')
      const pool = [...articlesPage.items]
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]]
      }
      const articles = pool.slice(0, 5).map((a) => ({
        id: a.id,
        title: a.title,
        abstract: a.abstract,
      }))
      return api.screening.preview(projectId, {
        criteria: { inclusion: criteria.inclusion, exclusion: criteria.exclusion },
        articles,
      })
    },
    onSuccess: (data) => setPreviewResults(data),
  })

  function handleStart() {
    startScreening.mutate({})
  }

  if (criteriaLoading) {
    return (
      <div style={{ padding: '24px', color: 'var(--color-text-secondary)', fontSize: '13px' }}>
        Loading…
      </div>
    )
  }

  const noCriteria = !criteria || (criteria.inclusion.length === 0 && criteria.exclusion.length === 0)

  return (
    <div style={{ padding: '24px', maxWidth: '600px' }}>
      <p style={{ fontSize: '15px', fontWeight: 500, color: 'var(--color-text-primary)', marginBottom: '4px' }}>
        Start abstract screening
      </p>

      {noCriteria ? (
        <div
          style={{
            marginTop: '16px',
            padding: '12px 16px',
            background: 'var(--color-background-secondary)',
            borderRadius: 'var(--border-radius-md)',
            fontSize: '13px',
            color: 'var(--color-text-secondary)',
          }}
        >
          No active criteria found.{' '}
          <button
            onClick={() => navigate(`/projects/${projectId}/criteria`)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-text-primary)',
              textDecoration: 'underline',
              fontSize: '13px',
              padding: 0,
            }}
          >
            Set up criteria first →
          </button>
        </div>
      ) : (
        <>
          <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
            Using criteria v{criteria.version} · {criteria.inclusion.length} inclusion · {criteria.exclusion.length} exclusion{' '}
            <button
              onClick={() => navigate(`/projects/${projectId}/criteria`)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--color-text-secondary)',
                textDecoration: 'underline',
                fontSize: '12px',
                padding: 0,
              }}
            >
              Change →
            </button>
          </p>

          <div style={{ marginBottom: '16px' }}>
            <label
              style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary)', marginBottom: '6px' }}
            >
              Reviewer name (optional)
            </label>
            <input
              value={reviewerName}
              onChange={(e) => setReviewerName(e.target.value)}
              placeholder="Dr. Jane Smith"
              style={{
                width: '100%',
                fontSize: '13px',
                padding: '7px 10px',
                border: '0.5px solid var(--color-border-secondary)',
                borderRadius: 'var(--border-radius-md)',
                background: 'var(--color-background-primary)',
                color: 'var(--color-text-primary)',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label
              style={{ display: 'block', fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary)', marginBottom: '6px' }}
            >
              Notes (optional)
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Low-confidence decisions will be reviewed…"
              rows={3}
              style={{
                width: '100%',
                fontSize: '13px',
                padding: '7px 10px',
                border: '0.5px solid var(--color-border-secondary)',
                borderRadius: 'var(--border-radius-md)',
                background: 'var(--color-background-primary)',
                color: 'var(--color-text-primary)',
                outline: 'none',
                resize: 'vertical',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {totalArticles > 0 && (
            <div
              style={{
                padding: '12px 16px',
                background: 'var(--color-background-secondary)',
                borderRadius: 'var(--border-radius-md)',
                fontSize: '13px',
                color: 'var(--color-text-secondary)',
                marginBottom: '20px',
              }}
            >
              <p style={{ margin: '0 0 4px' }}>
                <span style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>
                  {totalArticles.toLocaleString()}
                </span>{' '}
                articles will be screened
              </p>
              <p style={{ margin: '0 0 4px' }}>Estimated time: ~{estimatedMinutes} min at default concurrency</p>
              <p style={{ margin: 0 }}>Estimated cost: ~${estimatedCost} (gpt-4o-mini)</p>
            </div>
          )}

          {/* Action row */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              onClick={handleStart}
              disabled={startScreening.isPending}
              style={{
                fontSize: '13px',
                fontWeight: 500,
                padding: '8px 18px',
                background: 'var(--color-text-primary)',
                color: 'var(--color-background-primary)',
                border: 'none',
                borderRadius: 'var(--border-radius-md)',
                cursor: startScreening.isPending ? 'not-allowed' : 'pointer',
                opacity: startScreening.isPending ? 0.6 : 1,
              }}
            >
              {startScreening.isPending ? 'Starting…' : 'Start screening →'}
            </button>

            {articlesPage && articlesPage.items.length > 0 && (
              <button
                onClick={() => { setPreviewResults(null); previewMutation.mutate() }}
                disabled={previewMutation.isPending}
                style={{
                  fontSize: '13px',
                  padding: '8px 16px',
                  background: 'none',
                  border: '0.5px solid var(--color-border-secondary)',
                  borderRadius: 'var(--border-radius-md)',
                  cursor: previewMutation.isPending ? 'not-allowed' : 'pointer',
                  color: 'var(--color-text-secondary)',
                  opacity: previewMutation.isPending ? 0.6 : 1,
                }}
              >
                {previewMutation.isPending ? 'Previewing…' : 'Preview screening'}
              </button>
            )}
          </div>

          {startScreening.isError && (
            <p style={{ marginTop: '10px', fontSize: '12px', color: '#791F1F' }}>
              {startScreening.error instanceof Error ? startScreening.error.message : 'Failed to start screening'}
            </p>
          )}

          {previewMutation.isError && (
            <p style={{ marginTop: '10px', fontSize: '12px', color: '#791F1F' }}>
              {previewMutation.error instanceof Error ? previewMutation.error.message : 'Preview failed'}
            </p>
          )}

          {/* Preview results */}
          {previewResults && previewResults.length > 0 && (
            <div style={{ marginTop: '24px' }}>
              <p style={{ fontSize: '12px', fontWeight: 500, color: 'var(--color-text-secondary)', marginBottom: '10px' }}>
                Preview — {previewResults.length} article{previewResults.length !== 1 ? 's' : ''} screened against your criteria
              </p>
              {previewResults.map((result) => {
                const article = articlesPage?.items.find((a) => a.id === result.article_id)
                return (
                  <PreviewResultCard
                    key={result.article_id}
                    result={result}
                    article={article}
                  />
                )
              })}
            </div>
          )}
        </>
      )}
    </div>
  )
}
