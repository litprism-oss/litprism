import type { CriteriaHitOut, CriteriaAssessment } from '@/lib/types'

const ASSESSMENT_ICONS: Record<CriteriaAssessment, string> = {
  confirmed:    '✓',
  refuted:      '✕',
  unassessable: '?',
}

const ASSESSMENT_COLOURS: Record<CriteriaAssessment, string> = {
  confirmed:    '#27500A',
  refuted:      '#791F1F',
  unassessable: '#633806',
}

const TYPE_LABELS: Record<'inclusion' | 'exclusion', string> = {
  inclusion: 'included',
  exclusion: 'excluded',
}

interface CriteriaHitRowProps {
  hit: CriteriaHitOut
}

export function CriteriaHitRow({ hit }: CriteriaHitRowProps) {
  const colour = ASSESSMENT_COLOURS[hit.assessment]
  const icon   = ASSESSMENT_ICONS[hit.assessment]

  return (
    <div style={{ display: 'flex', gap: 10, padding: '8px 0', borderBottom: '0.5px solid var(--color-border-tertiary)' }}>
      <div style={{ width: 16, flexShrink: 0, color: colour, fontWeight: 600, fontSize: 13 }}>
        {icon}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 2 }}>
          <span style={{ fontSize: 11, color: 'var(--color-text-secondary)', width: 52, flexShrink: 0 }}>
            {TYPE_LABELS[hit.criterion_type]}
          </span>
          <span style={{ fontSize: 13, color: 'var(--color-text-primary)', flex: 1 }}>
            {hit.criterion}
          </span>
          <span style={{ fontSize: 11, color: colour, flexShrink: 0 }}>
            {hit.assessment}
          </span>
        </div>
        {hit.supporting_quote && (
          <p style={{ margin: 0, fontSize: 12, color: 'var(--color-text-secondary)', fontStyle: 'italic', paddingLeft: 60 }}>
            "{hit.supporting_quote}"
            {hit.quote_location && (
              <span style={{ fontStyle: 'normal', marginLeft: 6, fontSize: 11 }}>
                [{hit.quote_location}]
              </span>
            )}
          </p>
        )}
        {hit.assessment === 'unassessable' && hit.unassessable_reason && (
          <p style={{ margin: 0, fontSize: 12, color: ASSESSMENT_COLOURS.unassessable, paddingLeft: 60 }}>
            {hit.unassessable_reason}
          </p>
        )}
      </div>
    </div>
  )
}
