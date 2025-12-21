import {
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useMemo, useState } from 'react'
import type { Result } from '../types'

interface ResultsTableProps {
  results: Result[]
  headers: string[]
  loading: boolean
}

interface ModalState {
  isOpen: boolean
  title: string
  content: string
}

function TextModal({ isOpen, title, content, onClose }: ModalState & { onClose: () => void }) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            &times;
          </button>
        </div>
        <div className="px-6 py-4 overflow-y-auto flex-1">
          <p className="whitespace-pre-wrap text-gray-700">{content}</p>
        </div>
        <div className="px-6 py-4 border-t flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

function createColumns(
  headers: string[],
  onOpenModal: (title: string, content: string) => void
): ColumnDef<Result, unknown>[] {
  return headers.map((header) => {
    // Special rendering for known columns
    if (header === 'uid') {
      return {
        accessorKey: 'uid',
        header: 'UID',
        cell: (info) => info.getValue(),
        size: 60,
      } as ColumnDef<Result, unknown>
    }

    if (header === 'model') {
      return {
        accessorKey: 'model',
        header: 'Model',
        cell: (info) => info.getValue(),
        size: 150,
      } as ColumnDef<Result, unknown>
    }

    if (header === 'Topic') {
      return {
        accessorKey: 'Topic',
        header: 'Topic',
        cell: (info) => {
          const value = info.getValue() as string
          return value ? (
            <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
              {value}
            </span>
          ) : ''
        },
        size: 120,
      } as ColumnDef<Result, unknown>
    }

    if (header === 'Question') {
      return {
        accessorKey: 'Question',
        header: 'Question',
        cell: (info) => {
          const value = (info.getValue() as string) || ''
          return (
            <button
              onClick={() => onOpenModal('Question', value)}
              className="text-left text-blue-600 hover:text-blue-800 hover:underline cursor-pointer whitespace-normal break-words"
              title="Click to view full text"
            >
              {value}
            </button>
          )
        },
      } as ColumnDef<Result, unknown>
    }

    if (header === 'Model Response') {
      return {
        accessorKey: 'Model Response',
        header: 'Response',
        cell: (info) => {
          const value = (info.getValue() as string) || ''
          return (
            <button
              onClick={() => onOpenModal('Response', value)}
              className="max-w-lg text-left text-blue-600 hover:text-blue-800 hover:underline cursor-pointer text-sm"
              title="Click to view full text"
            >
              <span className="line-clamp-3">
                {value.slice(0, 300)}
                {value.length > 300 && '...'}
              </span>
            </button>
          )
        },
      } as ColumnDef<Result, unknown>
    }

    if (header === 'Timestamp') {
      return {
        accessorKey: 'Timestamp',
        header: 'Timestamp',
        cell: (info) => {
          const value = (info.getValue() as string) || ''
          return <span className="text-xs text-gray-500">{value}</span>
        },
        size: 180,
      } as ColumnDef<Result, unknown>
    }

    // Score columns (contain 'Score' in name)
    if (header.includes('Score')) {
      return {
        accessorKey: header,
        header: header.replace(/_/g, ' '),
        cell: (info) => {
          const value = info.getValue()
          return value !== '' && value !== undefined ? (
            <span className="font-mono text-sm">{String(value)}</span>
          ) : (
            <span className="text-gray-300">-</span>
          )
        },
        size: 100,
      } as ColumnDef<Result, unknown>
    }

    // Default column rendering
    return {
      accessorKey: header,
      header: header.replace(/_/g, ' '),
      cell: (info) => {
        const value = info.getValue()
        return value !== '' && value !== undefined ? String(value) : ''
      },
    } as ColumnDef<Result, unknown>
  })
}

export function ResultsTable({ results, headers, loading }: ResultsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])
  const [modal, setModal] = useState<ModalState>({ isOpen: false, title: '', content: '' })

  const openModal = (title: string, content: string) => {
    setModal({ isOpen: true, title, content })
  }

  const closeModal = () => {
    setModal({ isOpen: false, title: '', content: '' })
  }

  const columns = useMemo(() => createColumns(headers, openModal), [headers])

  const table = useReactTable({
    data: results,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: {
      pagination: { pageSize: 20 },
    },
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 bg-white rounded-lg shadow">
        <div className="text-gray-500">Loading...</div>
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 bg-white rounded-lg shadow">
        <div className="text-gray-500">No results found</div>
      </div>
    )
  }

  return (
    <>
    <div className="bg-white rounded-lg shadow overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="text-sm text-gray-700">
          Showing {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1} to{' '}
          {Math.min(
            (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
            results.length
          )}{' '}
          of {results.length} results
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Previous
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    onClick={header.column.getToggleSortingHandler()}
                    style={{ width: header.getSize() }}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(header.column.columnDef.header, header.getContext())}
                      {{
                        asc: ' ↑',
                        desc: ' ↓',
                      }[header.column.getIsSorted() as string] ?? ''}
                    </div>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-50">
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="px-4 py-3">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
        <div className="text-sm text-gray-700">
          Showing {table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1} to{' '}
          {Math.min(
            (table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize,
            results.length
          )}{' '}
          of {results.length} results
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Previous
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
          >
            Next
          </button>
        </div>
      </div>
    </div>

    <TextModal
      isOpen={modal.isOpen}
      title={modal.title}
      content={modal.content}
      onClose={closeModal}
    />
    </>
  )
}
