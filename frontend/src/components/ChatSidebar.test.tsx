import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi } from "vitest";
import { ChatSidebar } from "@/components/ChatSidebar";
import {
  ApiError,
  getChatHistory,
  sendChatMessage,
  type ChatResponse,
} from "@/lib/api";
import { initialData } from "@/lib/kanban";

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    getChatHistory: vi.fn(),
    sendChatMessage: vi.fn(),
  };
});

const getChatHistoryMock = vi.mocked(getChatHistory);
const sendChatMessageMock = vi.mocked(sendChatMessage);

const assistantMessage = {
  id: "4",
  role: "assistant" as const,
  content: "I moved the launch card to Review.",
  created_at: "2026-07-15 12:00:00",
};

const userMessage = {
  id: "3",
  role: "user" as const,
  content: "Move the launch card to Review",
  created_at: "2026-07-15 11:59:59",
};

describe("ChatSidebar", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("loads and renders saved conversation history", async () => {
    getChatHistoryMock.mockResolvedValue([
      {
        id: "1",
        role: "user",
        content: "What is blocked?",
        created_at: "2026-07-15 11:00:00",
      },
      {
        id: "2",
        role: "assistant",
        content: "The design card is in progress.",
        created_at: "2026-07-15 11:00:01",
      },
    ]);

    render(<ChatSidebar onBoardUpdate={vi.fn()} />);

    expect(screen.getByText("Loading conversation...")).toBeInTheDocument();
    expect(await screen.findByText("What is blocked?")).toBeInTheDocument();
    expect(screen.getByText("The design card is in progress.")).toBeInTheDocument();
  });

  it("shows sending state, appends messages, and refreshes the board", async () => {
    getChatHistoryMock.mockResolvedValue([]);
    const updatedBoard = structuredClone(initialData);
    updatedBoard.cards["card-1"].title = "AI-updated title";
    let resolveResponse: (response: ChatResponse) => void = () => undefined;
    sendChatMessageMock.mockReturnValue(
      new Promise((resolve) => {
        resolveResponse = resolve;
      })
    );
    const onBoardUpdate = vi.fn();
    render(<ChatSidebar onBoardUpdate={onBoardUpdate} />);
    const input = screen.getByLabelText("Message the board assistant");
    await screen.findByText("What should change?");

    await userEvent.type(input, "Move the launch card to Review");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(sendChatMessageMock).toHaveBeenCalledWith(
      "Move the launch card to Review"
    );
    expect(screen.getByRole("status")).toHaveTextContent(
      "The assistant is updating your board..."
    );
    expect(input).toBeDisabled();

    await act(async () => {
      resolveResponse({
        user_message: userMessage,
        message: assistantMessage,
        board: updatedBoard,
      });
    });

    expect(await screen.findByText("Move the launch card to Review")).toBeInTheDocument();
    expect(screen.getByText(assistantMessage.content)).toBeInTheDocument();
    expect(screen.getByTestId("chat-message-3")).toBeInTheDocument();
    expect(input).toHaveValue("");
    expect(onBoardUpdate).toHaveBeenCalledWith(updatedBoard);
  });

  it("preserves the draft and shows the backend error when sending fails", async () => {
    getChatHistoryMock.mockResolvedValue([]);
    sendChatMessageMock.mockRejectedValue(
      new ApiError("OpenRouter request failed with HTTP 503", 502)
    );
    const onBoardUpdate = vi.fn();
    render(<ChatSidebar onBoardUpdate={onBoardUpdate} />);
    const input = screen.getByLabelText("Message the board assistant");
    await screen.findByText("What should change?");

    await userEvent.type(input, "Keep this draft");
    await userEvent.click(screen.getByRole("button", { name: "Send message" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "OpenRouter request failed with HTTP 503"
    );
    expect(input).toHaveValue("Keep this draft");
    expect(onBoardUpdate).not.toHaveBeenCalled();
  });

  it("retries a failed history request", async () => {
    getChatHistoryMock.mockRejectedValueOnce(new Error("offline"));
    getChatHistoryMock.mockResolvedValueOnce([assistantMessage]);
    render(<ChatSidebar onBoardUpdate={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to load chat history."
    );
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText(assistantMessage.content)).toBeInTheDocument();
    expect(getChatHistoryMock).toHaveBeenCalledTimes(2);
  });
});
