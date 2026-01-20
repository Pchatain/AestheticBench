import { useLocalStorage } from './useLocalStorage'

/**
 * Custom hook for managing collapsible section state with localStorage persistence
 * @param id - Unique identifier for the collapsible section
 * @param defaultExpanded - Whether the section should be expanded by default
 * @returns A tuple of [isExpanded, toggleExpanded]
 */
export function useCollapsibleState(
  id: string,
  defaultExpanded: boolean = true
): [boolean, () => void] {
  const [isExpanded, setIsExpanded] = useLocalStorage<boolean>(
    `moralbench-collapsible-${id}`,
    defaultExpanded
  )

  const toggleExpanded = () => {
    setIsExpanded(!isExpanded)
  }

  return [isExpanded, toggleExpanded]
}
