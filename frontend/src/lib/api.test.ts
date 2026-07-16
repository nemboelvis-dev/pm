import { beforeEach, vi } from "vitest";
import {
  ApiError,
  createBoard,
  createCard,
  deleteBoard,
  deleteCard,
  editCard,
  getBoard,
  getChatHistory,
  listBoards,
  login,
  moveCard,
  register,
  renameBoard,
  renameColumn,
  sendChatMessage,
} from "@/lib/api";
import { initialData } from "@/lib/kanban";

const fetchMock = vi.fn<typeof fetch>();

const boardResponse = () =>
  new Response(JSON.stringify(initialData), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

describe("API client", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  it("loads a board by id with the session cookie", async () => {
    fetchMock.mockResolvedValue(boardResponse());

    await expect(getBoard("1")).resolves.toEqual(initialData);
    expect(fetchMock).toHaveBeenCalledWith("/api/boards/1", {
      credentials: "include",
      headers: undefined,
    });
  });

  it("lists boards for the current user", async () => {
    const summaries = [
      { id: "1", title: "Kanban Studio", created_at: "", updated_at: "" },
    ];
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify(summaries), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(listBoards()).resolves.toEqual(summaries);
    expect(fetchMock).toHaveBeenCalledWith("/api/boards", {
      credentials: "include",
      headers: undefined,
    });
  });

  it("sends each board-scoped mutation to its matching endpoint", async () => {
    fetchMock.mockImplementation(async () => boardResponse());

    await createBoard("New board");
    await renameBoard("1", "Renamed");
    await deleteBoard("1");
    await renameColumn("1", "2", "Ideas");
    await createCard("1", "2", "New", "Details");
    await editCard("1", "7", "Edited", "Changed");
    await deleteCard("1", "7");
    await moveCard("1", "8", "3", 1);

    expect(fetchMock.mock.calls).toEqual([
      [
        "/api/boards",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ title: "New board" }),
        }),
      ],
      [
        "/api/boards/1",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ title: "Renamed" }),
        }),
      ],
      ["/api/boards/1", expect.objectContaining({ method: "DELETE" })],
      [
        "/api/boards/1/columns/2",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ title: "Ideas" }),
        }),
      ],
      [
        "/api/boards/1/cards",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            column_id: 2,
            title: "New",
            details: "Details",
          }),
        }),
      ],
      [
        "/api/boards/1/cards/7",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ title: "Edited", details: "Changed" }),
        }),
      ],
      [
        "/api/boards/1/cards/7",
        expect.objectContaining({ method: "DELETE" }),
      ],
      [
        "/api/boards/1/cards/8/move",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ column_id: 3, position: 1 }),
        }),
      ],
    ]);
  });

  it("raises the backend error detail", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid username or password" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(login("user", "wrong")).rejects.toEqual(
      new ApiError("Invalid username or password", 401)
    );
  });

  it("registers a new account", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ username: "new-user" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      })
    );

    await expect(register("new-user", "correct-horse")).resolves.toEqual({
      username: "new-user",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ username: "new-user", password: "correct-horse" }),
      })
    );
  });

  it("preserves the status when an error response is not JSON", async () => {
    fetchMock.mockResolvedValue(
      new Response("Bad gateway", {
        status: 502,
        headers: { "Content-Type": "text/plain" },
      })
    );

    await expect(getBoard("1")).rejects.toEqual(new ApiError("Request failed", 502));
  });

  it("loads chat history and sends a chat message for a board", async () => {
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify([]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            user_message: {
              id: "1",
              role: "user",
              content: "Move the card",
              created_at: "2026-07-15 11:59:59",
            },
            message: {
              id: "2",
              role: "assistant",
              content: "Done",
              created_at: "2026-07-15 12:00:00",
            },
            board: initialData,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );

    await expect(getChatHistory("1")).resolves.toEqual([]);
    await sendChatMessage("1", "Move the card");

    expect(fetchMock.mock.calls).toEqual([
      [
        "/api/boards/1/chat",
        {
          credentials: "include",
          headers: undefined,
        },
      ],
      [
        "/api/boards/1/chat",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ message: "Move the card" }),
        }),
      ],
    ]);
  });
});
