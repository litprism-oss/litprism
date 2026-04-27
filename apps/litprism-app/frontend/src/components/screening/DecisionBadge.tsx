import type { ScreeningDecision } from '@/lib/types'

const DECISION_COLOURS: Record<ScreeningDecision, { bg: string; text: string }> = {
  include:   { bg: '#EAF3DE', text: '#27500A' },
  exclude:   { bg: '#FCEBEB', text: '#791F1F' },
  uncertain: { bg: '#FAEEDA', text: '#633806' },
}

const DECISION_LABELS: Record<ScreeningDecision, string> = {
  include:   'Include',
  exclude:   'Exclude',
  uncertain: 'Uncertain',
}

interface DecisionBadgeProps {
  decision: ScreeningDecision
  human_override?: boolean
  size?: 'sm' | 'md'
}

export function DecisionBadge({ decision, human_override = false, size = 'md' }: DecisionBadgeProps) {
  const { bg, text } = DECISION_COLOURS[decision]
  const fontSize = size === 'sm' ? '11px' : '12px'
  const padding  = size === 'sm' ? '2px 8px' : '3px 10px'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        background: bg,
        color: text,
        fontSize,
        padding,
        borderRadius: 99,
        whiteSpace: 'nowrap',
        fontWeight: 500,
      }}
    >
      {DECISION_LABELS[decision]}
      {human_override && (
        <span title="Human override" style={{ fontSize: 10, opacity: 0.8 }}>✎</span>
      )}
    </span>
  )
}
