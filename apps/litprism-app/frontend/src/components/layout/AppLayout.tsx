import { Outlet } from 'react-router-dom'
import { TopNav } from '@/components/layout/TopNav'
import { ProjectSidebar } from '@/components/layout/ProjectSidebar'
import { GuidancePanel } from '@/components/layout/GuidancePanel'

export function AppLayout() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <TopNav />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <ProjectSidebar />
        <main style={{
          flex: 1,
          padding: 24,
          overflowY: 'auto',
          background: 'var(--color-background-tertiary)',
        }}>
          <Outlet />
        </main>
        <GuidancePanel />
      </div>
    </div>
  )
}
