"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Send } from "lucide-react";
import {
  ApiError,
  getChatHistory,
  sendChatMessage,
  type ChatMessage,
} from "@/lib/api";
import type { BoardData } from "@/lib/kanban";

type ChatSidebarProps = {
  boardId: string;
  onBoardUpdate: (board: BoardData) => void;
};

export const ChatSidebar = ({ boardId, onBoardUpdate }: ChatSidebarProps) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [historyFailed, setHistoryFailed] = useState(false);
  const messagesEnd = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    getChatHistory(boardId)
      .then((history) => {
        if (active) {
          setMessages(history);
          setHistoryFailed(false);
        }
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(chatError(loadError, "Unable to load chat history."));
          setHistoryFailed(true);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [boardId]);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages, isSending]);

  const retryHistory = async () => {
    setError(null);
    setIsLoading(true);
    try {
      setMessages(await getChatHistory(boardId));
      setHistoryFailed(false);
    } catch (loadError) {
      setError(chatError(loadError, "Unable to load chat history."));
      setHistoryFailed(true);
    } finally {
      setIsLoading(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = draft.trim();
    if (!message || isSending) return;

    setError(null);
    setHistoryFailed(false);
    setIsSending(true);
    try {
      const response = await sendChatMessage(boardId, message);
      setMessages((current) => [
        ...current,
        response.user_message,
        response.message,
      ]);
      setDraft("");
      onBoardUpdate(response.board);
    } catch (sendError) {
      setError(chatError(sendError, "Unable to reach the board assistant."));
    } finally {
      setIsSending(false);
    }
  };

  return (
    <aside
      aria-labelledby="chat-title"
      className="flex min-h-[520px] flex-col overflow-hidden rounded-[28px] border border-[var(--stroke)] bg-white/90 shadow-[var(--shadow)] backdrop-blur xl:sticky xl:top-6 xl:max-h-[calc(100vh-3rem)]"
    >
      <header className="border-b border-[var(--stroke)] bg-[var(--navy-dark)] px-5 py-5 text-white">
        <p className="text-[10px] font-semibold uppercase tracking-[0.3em] text-[var(--accent-yellow)]">
          AI workspace
        </p>
        <h2 className="mt-2 font-display text-2xl font-semibold" id="chat-title">
          Board assistant
        </h2>
        <p className="mt-2 text-xs leading-5 text-white/70">
          Ask for card creation, edits, moves, or deletion using natural language.
        </p>
      </header>

      <div
        aria-live="polite"
        className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto bg-[var(--surface)] p-4"
      >
        {isLoading ? (
          <p className="m-auto text-center text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]">
            Loading conversation...
          </p>
        ) : messages.length ? (
          messages.map((message) => (
            <article
              className={`max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-5 ${
                message.role === "user"
                  ? "ml-auto bg-[var(--primary-blue)] text-white"
                  : "mr-auto border border-[var(--stroke)] bg-white text-[var(--navy-dark)]"
              }`}
              data-testid={`chat-message-${message.id}`}
              key={message.id}
            >
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">
                {message.role === "user" ? "You" : "Assistant"}
              </p>
              <p className="whitespace-pre-wrap">{message.content}</p>
            </article>
          ))
        ) : (
          <div className="m-auto max-w-[240px] text-center">
            <p className="font-display text-lg font-semibold text-[var(--navy-dark)]">
              What should change?
            </p>
            <p className="mt-2 text-xs leading-5 text-[var(--gray-text)]">
              Try “Create a launch checklist in Backlog” or “Move the analytics card to Review.”
            </p>
          </div>
        )}
        {isSending ? (
          <p className="text-xs font-medium text-[var(--secondary-purple)]" role="status">
            The assistant is updating your board...
          </p>
        ) : null}
        <div aria-hidden="true" ref={messagesEnd} />
      </div>

      <form className="border-t border-[var(--stroke)] bg-white p-4" onSubmit={submit}>
        {error ? (
          <div className="mb-3 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700" role="alert">
            {error}
            {historyFailed && !isLoading ? (
              <button
                className="ml-2 font-semibold underline"
                onClick={retryHistory}
                type="button"
              >
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
        <label
          className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]"
          htmlFor="chat-message"
        >
          Message the board assistant
        </label>
        <textarea
          className="mt-2 min-h-24 w-full resize-y rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-4 py-3 text-sm outline-none transition focus:border-[var(--primary-blue)] focus:ring-2 focus:ring-[var(--primary-blue)]/15 disabled:opacity-60"
          disabled={isSending}
          id="chat-message"
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Describe the board changes you want..."
          value={draft}
        />
        <button
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-xs font-semibold uppercase tracking-[0.16em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!draft.trim() || isSending}
          type="submit"
        >
          <Send aria-hidden="true" size={14} />
          {isSending ? "Sending..." : "Send message"}
        </button>
      </form>
    </aside>
  );
};

const chatError = (error: unknown, fallback: string) =>
  error instanceof ApiError ? error.message : fallback;
