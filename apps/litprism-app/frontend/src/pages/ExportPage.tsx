import { useParams } from 'react-router-dom'
import { useProjects } from '@/hooks/useProjects'
import { ExportPanel } from '@/components/export/ExportPanel'

export function ExportPage() {
  const { projectId = '' } = useParams()
  const { data: projects } = useProjects()
  const project = projects?.find(p => p.id === projectId)

  return (
    <div style={{ padding: '24px', maxWidth: 480 }}>
      <ExportPanel projectId={projectId} projectName={project?.name} />
    </div>
  )
}
