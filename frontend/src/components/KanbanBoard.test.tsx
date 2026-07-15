import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { KanbanBoard } from "@/components/KanbanBoard";
import {
  createCard,
  deleteCard,
  editCard,
  getBoard,
  getChatHistory,
  renameColumn,
} from "@/lib/api";
import { initialData, type BoardData } from "@/lib/kanban";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    createCard: vi.fn(),
    deleteCard: vi.fn(),
    editCard: vi.fn(),
    getBoard: vi.fn(),
    getChatHistory: vi.fn(),
    renameColumn: vi.fn(),
  };
});

const createCardMock = vi.mocked(createCard);
const deleteCardMock = vi.mocked(deleteCard);
const editCardMock = vi.mocked(editCard);
const getBoardMock = vi.mocked(getBoard);
const getChatHistoryMock = vi.mocked(getChatHistory);
const renameColumnMock = vi.mocked(renameColumn);

const copyBoard = (): BoardData => structuredClone(initialData);
const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

describe("KanbanBoard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    getChatHistoryMock.mockResolvedValue([]);
  });

  it("loads and renders the persistent board", async () => {
    getBoardMock.mockResolvedValue(copyBoard());

    render(<KanbanBoard />);

    expect(screen.getByText("Loading board...")).toBeInTheDocument();
    expect(await screen.findAllByTestId(/column-/i)).toHaveLength(5);
    expect(screen.getAllByTestId(/card-card-/i)).toHaveLength(8);
  });

  it("renames a column when its input loses focus", async () => {
    const renamed = copyBoard();
    renamed.columns[0].title = "New Name";
    renameColumnMock.mockResolvedValue(renamed);
    render(<KanbanBoard initialBoard={copyBoard()} />);
    const input = within(getFirstColumn()).getByLabelText("Column title");

    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    await userEvent.tab();

    await waitFor(() =>
      expect(renameColumnMock).toHaveBeenCalledWith("col-backlog", "New Name")
    );
    expect(input).toHaveValue("New Name");
  });

  it("adds, edits, and removes a card", async () => {
    const created = copyBoard();
    created.cards["card-new"] = {
      id: "card-new",
      title: "New card",
      details: "Notes",
    };
    created.columns[0].cardIds.push("card-new");
    createCardMock.mockResolvedValue(created);

    const edited = structuredClone(created);
    edited.cards["card-new"].title = "Edited card";
    edited.cards["card-new"].details = "Updated notes";
    editCardMock.mockResolvedValue(edited);
    deleteCardMock.mockResolvedValue(copyBoard());

    render(<KanbanBoard initialBoard={copyBoard()} />);
    const column = getFirstColumn();
    await userEvent.click(
      within(column).getByRole("button", { name: /add a card/i })
    );
    await userEvent.type(
      within(column).getByPlaceholderText(/card title/i),
      "New card"
    );
    await userEvent.type(within(column).getByPlaceholderText(/details/i), "Notes");
    await userEvent.click(
      within(column).getByRole("button", { name: /add card/i })
    );
    expect(await within(column).findByText("New card")).toBeInTheDocument();

    await userEvent.click(
      within(column).getByRole("button", { name: /edit new card/i })
    );
    const title = within(column).getByLabelText("Edit title for New card");
    await userEvent.clear(title);
    await userEvent.type(title, "Edited card");
    const details = within(column).getByLabelText("Edit details for New card");
    await userEvent.clear(details);
    await userEvent.type(details, "Updated notes");
    await userEvent.click(within(column).getByRole("button", { name: "Save" }));
    expect(await within(column).findByText("Edited card")).toBeInTheDocument();

    await userEvent.click(
      within(column).getByRole("button", { name: /delete edited card/i })
    );
    await waitFor(() =>
      expect(within(column).queryByText("Edited card")).not.toBeInTheDocument()
    );
  });

  it("cancels card creation without calling the API", async () => {
    render(<KanbanBoard initialBoard={copyBoard()} />);
    const column = getFirstColumn();

    await userEvent.click(
      within(column).getByRole("button", { name: /add a card/i })
    );
    await userEvent.type(
      within(column).getByPlaceholderText(/card title/i),
      "Discard me"
    );
    await userEvent.click(within(column).getByRole("button", { name: /cancel/i }));

    expect(within(column).queryByText("Discard me")).not.toBeInTheDocument();
    expect(createCardMock).not.toHaveBeenCalled();
  });

  it("shows a retry action when board loading fails", async () => {
    getBoardMock.mockRejectedValueOnce(new Error("offline"));
    getBoardMock.mockResolvedValueOnce(copyBoard());
    render(<KanbanBoard />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to load the board. Check that the server is running and try again."
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findAllByTestId(/column-/i)).toHaveLength(5);
  });
});
