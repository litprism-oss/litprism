import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIStore {
  guideEnabled: boolean
  toggleGuide: () => void
  setGuideEnabled: (v: boolean) => void
  sidebarOpen: boolean
  toggleSidebar: () => void
  // Phone only: the sidebar and guide are slide-over panels, closed by default.
  mobileNavOpen: boolean
  setMobileNavOpen: (v: boolean) => void
  mobileGuideOpen: boolean
  setMobileGuideOpen: (v: boolean) => void
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      guideEnabled: false,
      toggleGuide: () => set((s) => ({ guideEnabled: !s.guideEnabled })),
      setGuideEnabled: (v) => set({ guideEnabled: v }),
      sidebarOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      mobileNavOpen: false,
      setMobileNavOpen: (v) => set({ mobileNavOpen: v }),
      mobileGuideOpen: false,
      setMobileGuideOpen: (v) => set({ mobileGuideOpen: v }),
    }),
    {
      name: 'litprism-ui',
      partialize: (s) => ({ guideEnabled: s.guideEnabled, sidebarOpen: s.sidebarOpen }),
    },
  ),
)
