import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { BoardSwitcher } from "@/components/BoardSwitcher";
import type { BoardSummary } from "@/lib/api";

const boards: BoardSummary[] = [
  { id: "1", title: "Kanban Studio", created_at: "", updated_at: "" },
  { id: "2", title: "Sprint 2", created_at: "", updated_at: "" },
];

describe("BoardSwitcher", () => {
  it("renders a tab per board and switches on click", async () => {
    const onSwitch = vi.fn();
    render(
      <BoardSwitcher
        activeBoardId="1"
        boards={boards}
        onCreate={vi.fn()}
        onDelete={vi.fn()}
        onSwitch={onSwitch}
      />
    );

    expect(screen.getByTestId("board-tab-1")).toBeInTheDocument();
    expect(screen.getByTestId("board-tab-2")).toBeInTheDocument();

    await userEvent.click(
      within(screen.getByTestId("board-tab-2")).getByText("Sprint 2")
    );

    expect(onSwitch).toHaveBeenCalledWith("2");
  });

  it("hides the delete control when there is only one board", () => {
    const onDelete = vi.fn();
    render(
      <BoardSwitcher
        activeBoardId="1"
        boards={[boards[0]]}
        onCreate={vi.fn()}
        onDelete={onDelete}
        onSwitch={vi.fn()}
      />
    );

    expect(
      screen.queryByRole("button", { name: /delete board/i })
    ).not.toBeInTheDocument();
  });

  it("shows delete controls and calls onDelete for the right board", async () => {
    const onDelete = vi.fn();
    render(
      <BoardSwitcher
        activeBoardId="1"
        boards={boards}
        onCreate={vi.fn()}
        onDelete={onDelete}
        onSwitch={vi.fn()}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Delete board Sprint 2" })
    );

    expect(onDelete).toHaveBeenCalledWith("2");
  });

  it("creates a board through the inline form and closes it", async () => {
    const onCreate = vi.fn().mockResolvedValue(true);
    render(
      <BoardSwitcher
        activeBoardId="1"
        boards={boards}
        onCreate={onCreate}
        onDelete={vi.fn()}
        onSwitch={vi.fn()}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Create a new board" })
    );
    await userEvent.type(screen.getByPlaceholderText("Board name"), "Sprint 3");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    expect(onCreate).toHaveBeenCalledWith("Sprint 3");
    expect(screen.queryByPlaceholderText("Board name")).not.toBeInTheDocument();
  });

  it("cancels board creation without calling onCreate", async () => {
    const onCreate = vi.fn();
    render(
      <BoardSwitcher
        activeBoardId="1"
        boards={boards}
        onCreate={onCreate}
        onDelete={vi.fn()}
        onSwitch={vi.fn()}
      />
    );

    await userEvent.click(
      screen.getByRole("button", { name: "Create a new board" })
    );
    await userEvent.type(screen.getByPlaceholderText("Board name"), "Discard me");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onCreate).not.toHaveBeenCalled();
    expect(screen.queryByPlaceholderText("Board name")).not.toBeInTheDocument();
  });
});
