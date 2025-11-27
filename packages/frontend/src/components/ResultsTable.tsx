import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'react'
import type { Result } from '../types'

interface ResultsTableProps {
  results: Result[]
  loading: boolean
}

const columnHelper = createColumnHelper<Result>()

const columns = [
  columnHelper.accessor('uid', {
    header: 'UID',
    cell: (info) => info.getValue(),
    size: 60,
  }),
  columnHelper.accessor('model', {
    header: 'Model',
    cell: (info) => info.getValue(),
    size: 150,
  }),
  columnHelper.accessor('topic', {
    header: 'Topic',
    cell: (info) => (
      <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
        {info.getValue()}
      </span>
    ),
    size: 120,
  }),
  columnHelper.accessor('question', {
    header: 'Question',
    cell: (info) => (
      <div className="max-w-md truncate" title={info.getValue()}>
        {info.getValue()}
      </div>
    ),
  }),
  columnHelper.accessor('response', {
    header: 'Response',
    cell: (info) => (
      <div className="max-w-lg max-h-24 overflow-auto text-sm text-gray-600">
        {info.getValue().slice(0, 300)}
        {info.getValue().length > 300 && '...'}
      </div>
    ),
  }),
]

export function ResultsTable({ results, loading }: ResultsTableProps) {
  const [sorting, setSorting] = useState<SortingState>([])

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
    <div className="bg-white rounded-lg shadow overflow-hidden">
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
  )
}
