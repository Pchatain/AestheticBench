import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface AppStore {
  selectedModels: string[]
  setSelectedModels: (models: string[]) => void
  toggleModel: (model: string) => void
  rowHeight: number
  setRowHeight: (height: number) => void
}

export const useAppStore = create<AppStore>()(
  persist(
    (set) => ({
      selectedModels: [],
      setSelectedModels: (models) => set({ selectedModels: models }),
      toggleModel: (model) => set((state) => ({
        selectedModels: state.selectedModels.includes(model)
          ? state.selectedModels.filter((m) => m !== model)
          : [...state.selectedModels, model]
      })),
      rowHeight: 80,
      setRowHeight: (height) => set({ rowHeight: height }),
    }),
    { name: 'moralbench-app-store' },
  )
)
