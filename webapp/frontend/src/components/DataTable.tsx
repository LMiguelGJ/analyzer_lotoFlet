import type { ReactNode } from "react";

/**
 * Generic accessible data table (UX18, UX22, UX36, UX38): a labeled scroll
 * region wraps the table so a wide table scrolls in its own bounded area
 * instead of forcing the whole page to scroll horizontally. The caption is
 * visually hidden but present for assistive tech; the wrapper repeats the
 * same text as its accessible name so the scroll region itself is announced.
 *
 * Sort controls delegate to the caller's server-side ordering. Never sort
 * only the visible page of a paginated result here.
 */

export interface DataTableColumn<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  headerClassName?: string;
  cellClassName?: string;
  sort?: "ascending" | "descending" | "none";
  onSort?: () => void;
}

interface DataTableProps<T> {
  caption: string;
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
}

export function DataTable<T>({ caption, columns, rows, getRowKey }: DataTableProps<T>) {
  return (
    <div
      role="region"
      aria-label={caption}
      tabIndex={0}
      className="data-table-region overflow-x-auto rounded-control border border-border-control"
    >
      <table className="w-full border-collapse text-left text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-border">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={`px-4 py-3 text-text-secondary ${column.headerClassName ?? ""}`}
                aria-sort={column.onSort ? column.sort ?? "none" : undefined}
              >
                {column.onSort ? <button type="button" className="min-h-control text-left text-accent hover:underline" onClick={column.onSort}>{column.header}</button> : column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getRowKey(row)} className="border-b border-border last:border-b-0">
              {columns.map((column) => (
                <td key={column.key} className={`px-4 py-3 align-top ${column.cellClassName ?? ""}`}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
