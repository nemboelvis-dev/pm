import { beforeEach, vi } from "vitest";
import {
  ApiError,
  createCard,
  deleteCard,
  editCard,
  getBoard,
  getChatHistory,
  login,
  moveCard,
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

  it("loads the board with the session cookie", async () => {
    fetchMock.mockResolvedValue(boardResponse());

    await expect(getBoard()).resolves.toEqual(initialData);
    expect(fetchMock).toHaveBeenCalledWith("/api/board", {
      credentials: "include",
      headers: undefined,
    });
  });

  it("sends each board mutation to its matching endpoint", async () => {
    fetchMock.mockImplementation(async () => boardResponse());

    await renameColumn("2", "Ideas");
    await createCard("2", "New", "Details");
    await editCard("7", "Edited", "Changed");
    await deleteCard("7");
    await moveCard("8", "3", 1);

    expect(fetchMock.mock.calls).toEqual([
      [
        "/api/columns/2",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ title: "Ideas" }),
        }),
      ],
      [
        "/api/cards",
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
        "/api/cards/7",
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ title: "Edited", details: "Changed" }),
        }),
      ],
      ["/api/cards/7", expect.objectContaining({ method: "DELETE" })],
      [
        "/api/cards/8/move",
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

  it("preserves the status when an error response is not JSON", async () => {
    fetchMock.mockResolvedValue(
      new Response("Bad gateway", {
        status: 502,
        headers: { "Content-Type": "text/plain" },
      })
    );

    await expect(getBoard()).rejects.toEqual(new ApiError("Request failed", 502));
  });

  it("loads chat history and sends a chat message", async () => {
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

    await expect(getChatHistory()).resolves.toEqual([]);
    await sendChatMessage("Move the card");

    expect(fetchMock.mock.calls).toEqual([
      [
        "/api/chat",
        {
          credentials: "include",
          headers: undefined,
        },
      ],
      [
        "/api/chat",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ message: "Move the card" }),
        }),
      ],
    ]);
  });
});
