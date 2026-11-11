import { useNavigate, useLocation } from 'react-router-dom'
import { Switch } from '@/components/ui/switch'
import { useUIStore } from '@/store/useUIStore'
import { useProject } from '@/hooks/useProjects'
import { useIsMobile } from '@/hooks/useIsMobile'

function ProjectBreadcrumb({ projectId }: { projectId: string }) {
  const { data: project } = useProject(projectId)
  if (!project) return null
  return (
    <>
      <span style={{ color: 'var(--color-border-secondary)', margin: '0 6px' }}>›</span>
      <span style={{
        color: 'var(--color-text-primary)',
        fontSize: 13,
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        minWidth: 0,
      }}>
        {project.name}
      </span>
    </>
  )
}

const iconButton: React.CSSProperties = {
  width: 36,
  height: 36,
  background: 'none',
  border: 'none',
  fontSize: 18,
  color: 'var(--color-text-secondary)',
  cursor: 'pointer',
}

export function TopNav() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { guideEnabled, toggleGuide, setMobileNavOpen, setMobileGuideOpen } = useUIStore()
  const isMobile = useIsMobile()

  const projectMatch = pathname.match(/\/projects\/([^/]+)/)
  const projectId = projectMatch?.[1]
  const isInsideProject = !!projectId && projectId !== 'new'

  return (
    <header style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 8,
      padding: isMobile ? '0 12px' : '0 20px',
      height: 48,
      borderBottom: '0.5px solid var(--color-border-tertiary)',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', minWidth: 0, flex: 1 }}>
        {isMobile && isInsideProject && (
          <button
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open project menu"
            style={{ ...iconButton, marginRight: 4, marginLeft: -6 }}
          >
            ☰
          </button>
        )}
        <span
          onClick={() => navigate('/')}
          style={{
            fontSize: 15,
            fontWeight: 500,
            color: 'var(--color-text-primary)',
            cursor: 'pointer',
            flexShrink: 0,
          }}
        >
          LitPrism
        </span>
        {isInsideProject && <ProjectBreadcrumb projectId={projectId} />}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? 8 : 16, flexShrink: 0 }}>
        {isMobile ? (
          <button onClick={() => setMobileGuideOpen(true)} aria-label="Open methodology guide" style={iconButton}>
            ?
          </button>
        ) : (
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
        )}

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
            whiteSpace: 'nowrap',
          }}
        >
          {isMobile ? '+ New' : '+ New review'}
        </button>
      </div>
    </header>
  )
}
