interface SidebarProps {
  currentPage: string
  onPageChange: (page: string) => void
}

const pages = [
  { id: 'results', label: 'Results Table', icon: '📊' },
]

export function Sidebar({ currentPage, onPageChange }: SidebarProps) {
  return (
    <aside className="w-64 bg-gray-800 text-white min-h-screen p-4">
      <h1 className="text-xl font-bold mb-6 px-2">MoralBench</h1>
      <nav>
        <ul className="space-y-1">
          {pages.map((page) => (
            <li key={page.id}>
              <button
                onClick={() => onPageChange(page.id)}
                className={`w-full text-left px-3 py-2 rounded-lg flex items-center gap-2 transition-colors ${
                  currentPage === page.id
                    ? 'bg-gray-700 text-white'
                    : 'text-gray-300 hover:bg-gray-700 hover:text-white'
                }`}
              >
                <span>{page.icon}</span>
                <span>{page.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
