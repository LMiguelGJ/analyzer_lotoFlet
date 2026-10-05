import { readFileSync } from "node:fs";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
// Contract coverage: F-LIST-021 table region/caption/cells/empty state; F-LIST-022 local scroll/wrapping/compact fields; F-LIST-023 keyboard actions/hairline styling/axe.
import { describe, expect, it, vi } from "vitest";
import { DataTable } from "./DataTable";
import type { DataTableColumn } from "./DataTable";

interface Row {
  id: string;
  name: string;
}

const rows: Row[] = [
  { id: "a", name: "Alfa" },
  { id: "b", name: "Beta" },
];

function columns(onAction: (id: string) => void): DataTableColumn<Row>[] {
  return [
    { key: "name", header: "Nombre", render: (row) => row.name },
    {
      key: "actions",
      header: "Acciones",
      render: (row) => (
        <button type="button" onClick={() => onAction(row.id)}>
          Eliminar {row.name}
        </button>
      ),
    },
  ];
}

describe("DataTable", () => {
  it("renders a labeled region with proper table semantics and a caption", () => {
    render(
      <DataTable caption="Experimentos" columns={columns(() => {})} rows={rows} getRowKey={(row) => row.id} />,
    );

    const region = screen.getByRole("region", { name: "Experimentos" });
    const table = within(region).getByRole("table");
    expect(within(table).getByText("Experimentos")).toBeInTheDocument(); // <caption>
    expect(within(table).getAllByRole("columnheader")).toHaveLength(2);
    expect(within(table).getAllByRole("row")).toHaveLength(3); // header + 2 rows
  });

  it("keeps long content in a labeled local scroll region without changing the cell", () => {
    const longName = "Nombre de experimento ".repeat(12);
    render(<DataTable caption="Experimentos" columns={columns(() => {})} rows={[{ id: "long", name: longName }]} getRowKey={(row) => row.id} />);
    const region = screen.getByRole("region", { name: "Experimentos" });
    expect(region).toHaveClass("data-table-region", "overflow-x-auto");
    expect(within(region).getByRole("table")).toHaveClass("w-full");
    expect(within(region).getByRole("table")).not.toHaveClass("min-w-max");
    expect(within(region).getAllByRole("cell")[0]).toHaveTextContent(longName.trim());
  });

  it("lets the table flex to the region while preserving word-level wrapping and compact fields", () => {
    const css = readFileSync("src/styles/index.css", "utf8");
    const tableRules = css.slice(css.indexOf("  .data-table-region {"), css.indexOf("  @media (max-width: 799px)"));
    expect(tableRules).toMatch(/\.data-table-region th\s*\{\s*white-space:\s*nowrap;/);
    expect(tableRules).toMatch(/\.data-table-region td\s*\{[^}]*overflow-wrap:\s*break-word;/s);
    expect(tableRules).toMatch(/\.table-date\s*\{[^}]*white-space:\s*nowrap;/s);
    expect(tableRules).toMatch(/\.table-numeric\s*\{[^}]*white-space:\s*nowrap;/s);
    expect(tableRules).not.toMatch(/overflow-wrap:\s*anywhere/);
  });

  it("renders each row's cells from the column render function", () => {
    render(
      <DataTable caption="Experimentos" columns={columns(() => {})} rows={rows} getRowKey={(row) => row.id} />,
    );

    expect(screen.getByText("Alfa")).toBeInTheDocument();
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("keeps row actions reachable and operable by keyboard", async () => {
    const onAction = vi.fn();
    const user = userEvent.setup();
    render(
      <DataTable caption="Experimentos" columns={columns(onAction)} rows={rows} getRowKey={(row) => row.id} />,
    );

    await user.tab(); // the scroll region itself (tabIndex=0)
    await user.tab();
    expect(screen.getByRole("button", { name: "Eliminar Alfa" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onAction).toHaveBeenCalledWith("a");
  });

  it("draws hairline rules with a 150ms hover transition and tracked labels without changing the class contract", () => {
    render(<DataTable caption="Experimentos" columns={columns(() => {})} rows={rows} getRowKey={(row) => row.id} />);
    const region = screen.getByRole("region", { name: "Experimentos" });
    expect(region).toHaveClass("border-border");
    expect(region).not.toHaveClass("rounded", "shadow");
    const bodyRow = within(region).getAllByRole("row")[1];
    expect(bodyRow).toHaveClass("border-b", "border-border", "transition-colors", "duration-150", "hover:bg-surface");
    expect(within(region).getAllByRole("columnheader")[0]).toHaveClass("uppercase", "tracking-[0.08em]");
  });

  it("renders an empty body without throwing when there are no rows", () => {
    render(<DataTable caption="Experimentos" columns={columns(() => {})} rows={[]} getRowKey={(row) => row.id} />);

    expect(screen.getAllByRole("row")).toHaveLength(1); // header only
  });

  it("has no axe violations", async () => {
    const { container } = render(
      <DataTable caption="Experimentos" columns={columns(() => {})} rows={rows} getRowKey={(row) => row.id} />,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
