import type { ProjectOut } from '@/lib/types'

export interface NextAction {
  label: string
  path: string
}

/** The single most useful next step for a review, from its real state. */
export function nextAction(project: ProjectOut, searching = false): NextAction {
  const base = `/projects/${project.id}`
  if (searching) return { label: 'View search progress', path: `${base}/search` }
  if (project.article_count === 0) return { label: 'Start searching', path: `${base}/search` }
  if (!project.has_criteria) return { label: 'Set up criteria', path: `${base}/criteria` }
  if (project.screened_count === 0) return { label: 'Start screening', path: `${base}/screening` }
  return { label: 'View results', path: `${base}/screening/results` }
}
