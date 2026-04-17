import { useNavigate, useLocation } from 'react-router-dom'
import { Switch } from '@/components/ui/switch'
import { useUIStore } from '@/store/useUIStore'
import { useProject } from '@/hooks/useProjects'

function ProjectBreadcrumb({ projectId }: { projectId: string }) {
  const { data: project } = useProject(projectId)
  if (!project) return null
  return (
    <>
      <span style={{ color: 'var(--color-border-secondary)', margin: '0 6px' }}>›</span>
      <span style={{ color: 'var(--color-text-primary)', fontSize: 13 }}>
        {project.name}
      </span>
    </>
  )
}

export function TopNav() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { guideEnabled, toggleGuide } = useUIStore()

  const projectMatch = pathname.match(/\/projects\/([^/]+)/)
  const projectId = projectMatch?.[1]
  const isInsideProject = !!projectId && projectId !== 'new'

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0 20px',
      height: 48,
      borderBottom: '0.5px solid var(--color-border-tertiary)',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <span
          onClick={() => navigate('/')}
          style={{
            fontSize: 15,
            fontWeight: 500,
            color: 'var(--color-text-primary)',
            cursor: 'pointer',
          }}
        >
          LitPrism
        </span>
        {isInsideProject && <ProjectBreadcrumb projectId={projectId} />}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <label style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          fontSize: 13,
          color: 'var(--color-text-secondary)',
          cursor: 'pointer',
        }}>
          <span>Guide</span>
          <Switch checked={guideEnabled} onCheckedChange={toggleGuide} />
        </label>

        <button
          onClick={() => navigate('/projects/new')}
          style={{
            background: 'var(--color-text-primary)',
            color: 'var(--color-background-primary)',
            border: 'none',
            padding: '6px 14px',
            borderRadius: 'var(--border-radius-md)',
            fontSize: 13,
            cursor: 'pointer',
          }}
        >
          + New review
        </button>
      </div>
    </header>
  )
}
