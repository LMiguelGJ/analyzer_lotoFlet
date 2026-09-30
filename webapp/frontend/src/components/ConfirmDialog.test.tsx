import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

function RerenderHarness() {
  const [open, setOpen] = useState(false);
  const [, forceRender] = useState(0);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Abrir
      </button>
      <button type="button" onClick={() => forceRender((tick) => tick + 1)}>
        Forzar render
      </button>
      <ConfirmDialog
        open={open}
        title="t"
        description="d"
        onConfirm={vi.fn()}
        onCancel={() => setOpen(false)}
      />
    </div>
  );
}

function Harness({ onConfirm, onCancel }: { onConfirm: () => void; onCancel: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button type="button" onClick={() => setOpen(true)}>
        Abrir
      </button>
      <ConfirmDialog
        open={open}
        title="Eliminar experimento"
        description="Esta acción no se puede deshacer."
        onConfirm={() => {
          onConfirm();
          setOpen(false);
        }}
        onCancel={() => {
          onCancel();
          setOpen(false);
        }}
      />
    </div>
  );
}

describe("ConfirmDialog", () => {
  it("renders nothing when closed", () => {
    render(<ConfirmDialog open={false} title="t" description="d" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("is labelled and marked as a modal when open", () => {
    render(<ConfirmDialog open title="Eliminar experimento" description="detalle" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName("Eliminar experimento");
  });

  it("moves focus inside the dialog on open", () => {
    render(<ConfirmDialog open title="t" description="d" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const dialog = screen.getByRole("alertdialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("traps Tab focus between the cancel and confirm buttons", async () => {
    const user = userEvent.setup();
    render(<ConfirmDialog open title="t" description="d" onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const cancel = screen.getByRole("button", { name: "Cancelar" });
    const confirm = screen.getByRole("button", { name: "Eliminar" });

    expect(document.activeElement).toBe(cancel);
    await user.tab();
    expect(document.activeElement).toBe(confirm);
    await user.tab();
    expect(document.activeElement).toBe(cancel);
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(confirm);
  });

  it("closes on Escape and calls onCancel", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<ConfirmDialog open title="t" description="d" onConfirm={vi.fn()} onCancel={onCancel} />);
    await user.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("returns focus to the triggering control after closing", async () => {
    const user = userEvent.setup();
    render(<Harness onConfirm={vi.fn()} onCancel={vi.fn()} />);
    const trigger = screen.getByRole("button", { name: "Abrir" });
    await user.click(trigger);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(document.activeElement).toBe(trigger);
  });

  it("keeps focus stable across a parent re-render that passes a brand-new onCancel closure", async () => {
    const user = userEvent.setup();
    render(<RerenderHarness />);
    await user.click(screen.getByRole("button", { name: "Abrir" }));
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();

    // Clicking "Forzar render" naturally focuses that button (normal browser
    // behavior) *and* forces ConfirmDialog's parent to pass a brand-new
    // inline onCancel closure. The bug this guards against: if the open/focus
    // effect depended on `onCancel`, this re-render would re-run it and steal
    // focus back to the dialog's first focusable control ("Cancelar"),
    // overriding the user's own click target.
    const forceRenderButton = screen.getByRole("button", { name: "Forzar render" });
    await user.click(forceRenderButton);

    expect(document.activeElement).toBe(forceRenderButton);
  });

  it("captures the root trigger before native inert blurs it", async () => {
    const setAttribute = HTMLElement.prototype.setAttribute;
    HTMLElement.prototype.setAttribute = function (name, value) {
      setAttribute.call(this, name, value);
      if (name === "inert" && this.contains(document.activeElement)) {
        (document.activeElement as HTMLElement).blur();
      }
    };
    const appRoot = document.createElement("div");
    appRoot.id = "root";
    document.body.appendChild(appRoot);
    try {
      const user = userEvent.setup();
      render(<Harness onConfirm={vi.fn()} onCancel={vi.fn()} />, { container: appRoot });
      const trigger = screen.getByRole("button", { name: "Abrir" });
      await user.click(trigger);
      expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
      await user.keyboard("{Escape}");
      expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
      expect(trigger).toHaveFocus();
    } finally {
      HTMLElement.prototype.setAttribute = setAttribute;
      document.body.removeChild(appRoot);
    }
  });

  it("marks the app root inert while open so Tab cannot escape the trap from any element", async () => {
    const user = userEvent.setup();
    const appRoot = document.createElement("div");
    appRoot.id = "root";
    document.body.appendChild(appRoot);
    render(<Harness onConfirm={vi.fn()} onCancel={vi.fn()} />, { container: appRoot });

    await user.click(screen.getByRole("button", { name: "Abrir" }));
    expect(appRoot).toHaveAttribute("inert", "");

    await user.keyboard("{Escape}");
    expect(appRoot).not.toHaveAttribute("inert");

    document.body.removeChild(appRoot);
  });
});
