import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface UIStore {
  guideEnabled: boolean
  toggleGuide: () => void
  setGuideEnabled: (v: boolean) => void
  sidebarOpen: boolean
  toggleSidebar: () => void
}

export const useUIStore = create<UIStore>()(
  persist(
    (set) => ({
      guideEnabled: true,
      toggleGuide: () => set((s) => ({ guideEnabled: !s.guideEnabled })),
      setGuideEnabled: (v) => set({ guideEnabled: v }),
      sidebarOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    { name: 'litprism-ui' },
  ),
)
