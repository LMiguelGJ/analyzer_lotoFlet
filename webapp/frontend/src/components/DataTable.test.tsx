import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
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
