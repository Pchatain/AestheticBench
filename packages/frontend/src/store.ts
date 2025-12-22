import { create } from 'zustand'

interface AppStore {
  selectedModels: string[]
  setSelectedModels: (models: string[]) => void
  toggleModel: (model: string) => void
}

export const useAppStore = create<AppStore>((set) => ({
  selectedModels: [],
  setSelectedModels: (models) => set({ selectedModels: models }),
  toggleModel: (model) => set((state) => ({
    selectedModels: state.selectedModels.includes(model)
      ? state.selectedModels.filter((m) => m !== model)
      : [...state.selectedModels, model]
  })),
}))
