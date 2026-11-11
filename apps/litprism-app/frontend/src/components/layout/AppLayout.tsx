import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { TopNav } from '@/components/layout/TopNav'
import { ProjectSidebar } from '@/components/layout/ProjectSidebar'
import { GuidancePanel } from '@/components/layout/GuidancePanel'
import { useIsMobile } from '@/hooks/useIsMobile'
import { useUIStore } from '@/store/useUIStore'

export function AppLayout() {
  const { sidebarOpen, toggleSidebar, mobileNavOpen, setMobileNavOpen, setMobileGuideOpen } =
    useUIStore()
  const isMobile = useIsMobile()
  const { pathname } = useLocation()

  // Close the slide-over panels whenever the user navigates.
  useEffect(() => {
    setMobileNavOpen(false)
    setMobileGuideOpen(false)
  }, [pathname, setMobileNavOpen, setMobileGuideOpen])

  if (isMobile) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', height: '100dvh' }}>
        <TopNav />
        <main
          style={{
            flex: 1,
            padding: 16,
            overflowY: 'auto',
            background: 'var(--color-background-tertiary)',
          }}
        >
          <Outlet />
        </main>

        {mobileNavOpen && (
          <>
            <div
              onClick={() => setMobileNavOpen(false)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.35)', zIndex: 40 }}
            />
            <div
              role="dialog"
              aria-label="Project navigation"
              style={{
                position: 'fixed',
                top: 0,
                bottom: 0,
                left: 0,
                width: 'min(300px, 85vw)',
                background: 'var(--color-background-primary)',
                zIndex: 41,
                overflowY: 'auto',
                paddingTop: 8,
              }}
            >
              <ProjectSidebar />
            </div>
          </>
        )}

        <GuidancePanel />
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <TopNav />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden', position: 'relative' }}>

        {/* Sidebar container — animates between 220px and 0 */}
        <div
          style={{
            width: sidebarOpen ? 220 : 0,
            overflow: 'hidden',
            transition: 'width 0.2s ease',
            flexShrink: 0,
          }}
        >
          <ProjectSidebar />
        </div>

        {/* Toggle button — pinned to the right edge of the sidebar */}
        <button
          onClick={toggleSidebar}
          aria-label={sidebarOpen ? 'Close sidebar' : 'Open sidebar'}
          style={{
            position: 'absolute',
            left: sidebarOpen ? 220 : 0,
            top: 24,
            zIndex: 10,
            width: 20,
            height: 40,
            background: 'var(--color-background-primary)',
            border: '0.5px solid var(--color-border-tertiary)',
            borderLeft: sidebarOpen ? 'none' : undefined,
            borderRadius: '0 4px 4px 0',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--color-text-tertiary)',
            fontSize: 12,
            transition: 'left 0.2s ease',
            padding: 0,
          }}
        >
          {sidebarOpen ? '‹' : '›'}
        </button>

        {/* Main content */}
        <main
          style={{
            flex: 1,
            padding: 24,
            overflowY: 'auto',
            background: 'var(--color-background-tertiary)',
          }}
        >
          <Outlet />
        </main>

        <GuidancePanel />
      </div>
    </div>
  )
}
