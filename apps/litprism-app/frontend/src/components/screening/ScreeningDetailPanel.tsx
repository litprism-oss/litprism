import { useState } from 'react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { DecisionBadge } from './DecisionBadge'
import { CriteriaHitRow } from './CriteriaHitRow'
import { useOverrideDecision } from '@/hooks/useScreeningResults'
import type { ArticleWithResult, ScreeningDecision } from '@/lib/types'

interface ScreeningDetailPanelProps {
  projectId: string
  article: ArticleWithResult | null
  onClose: () => void
}

export function ScreeningDetailPanel({ projectId, article, onClose }: ScreeningDetailPanelProps) {
  const result = article?.screening_result ?? null

  const [overrideDecision, setOverrideDecision] = useState<ScreeningDecision | ''>('')
  const [overrideNote, setOverrideNote]         = useState('')

  const { mutate: override, isPending } = useOverrideDecision(projectId)

  function handleSave() {
    if (!article || !overrideDecision) return
    override(
      { articleId: article.id, decision: overrideDecision, note: overrideNote || undefined },
      {
        onSuccess: () => {
          setOverrideDecision('')
          setOverrideNote('')
        },
      },
    )
  }

  function confidenceColour(conf: number) {
    if (conf >= 0.9) return 'var(--color-text-secondary)'
    if (conf >= 0.75) return '#633806'
    return '#791F1F'
  }

  return (
    <Sheet open={!!article} onOpenChange={open => { if (!open) onClose() }}>
      <SheetContent
        side="right"
        style={{ width: 480, maxWidth: '90vw', overflowY: 'auto', padding: '24px' }}
      >
        {article && (
          <>
            <SheetHeader style={{ marginBottom: 16 }}>
              <SheetTitle style={{ fontSize: 15, lineHeight: 1.4, fontWeight: 500 }}>
                {article.title}
              </SheetTitle>
            </SheetHeader>

            {article.abstract && (
              <p style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginBottom: 20, lineHeight: 1.6 }}>
                {article.abstract}
              </p>
            )}

            {result ? (
              <>
                {/* Decision + confidence */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                  <DecisionBadge decision={result.decision} human_override={result.human_override} size="md" />
                  <span style={{ fontSize: 13, color: confidenceColour(result.confidence) }}>
                    {Math.round(result.confidence * 100)}% confidence
                  </span>
                </div>

                {/* Reasoning */}
                <section style={{ marginBottom: 20 }}>
                  <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-secondary)', marginBottom: 6 }}>
                    Reasoning
                  </p>
                  <p style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--color-text-primary)', margin: 0 }}>
                    {result.reasoning}
                  </p>
                </section>

                {/* Criteria hits */}
                {result.criteria_hits.length > 0 && (
                  <section style={{ marginBottom: 24 }}>
                    <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-secondary)', marginBottom: 4 }}>
                      Criteria assessment
                    </p>
                    {result.criteria_hits.map((hit, i) => (
                      <CriteriaHitRow key={i} hit={hit} />
                    ))}
                  </section>
                )}

                {/* Human override note */}
                {result.human_override && result.human_note && (
                  <div style={{ background: '#FAEEDA', borderRadius: 6, padding: '10px 12px', marginBottom: 20 }}>
                    <p style={{ fontSize: 11, fontWeight: 600, color: '#633806', marginBottom: 4 }}>Override note</p>
                    <p style={{ fontSize: 13, color: '#633806', margin: 0 }}>{result.human_note}</p>
                  </div>
                )}

                <hr style={{ border: 'none', borderTop: '0.5px solid var(--color-border-tertiary)', marginBottom: 16 }} />

                {/* Override section */}
                <section>
                  <p style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--color-text-secondary)', marginBottom: 10 }}>
                    Override decision
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <Select
                      value={overrideDecision}
                      onValueChange={v => setOverrideDecision(v as ScreeningDecision)}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select decision…" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="include">Include</SelectItem>
                        <SelectItem value="exclude">Exclude</SelectItem>
                        <SelectItem value="uncertain">Uncertain</SelectItem>
                      </SelectContent>
                    </Select>
                    <Textarea
                      placeholder="Note (optional)"
                      value={overrideNote}
                      onChange={e => setOverrideNote(e.target.value)}
                      rows={3}
                    />
                    <Button
                      onClick={handleSave}
                      disabled={!overrideDecision || isPending}
                      size="sm"
                    >
                      {isPending ? 'Saving…' : 'Save override'}
                    </Button>
                  </div>
                </section>
              </>
            ) : (
              <p style={{ fontSize: 13, color: 'var(--color-text-secondary)' }}>
                This article has not been screened yet.
              </p>
            )}
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}
