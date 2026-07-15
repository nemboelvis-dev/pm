import type { BoardData } from "@/lib/kanban";

export type User = {
  username: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type ChatResponse = {
  user_message: ChatMessage;
  message: ChatMessage;
  board: BoardData;
};

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

const request = async <T>(path: string, options?: RequestInit): Promise<T> => {
  const response = await fetch(path, {
    ...options,
    credentials: "include",
    headers: options?.body
      ? { "Content-Type": "application/json", ...options.headers }
      : options?.headers,
  });

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    throw new ApiError(detail ?? "Request failed", response.status);
  }

  return response.status === 204
    ? (undefined as T)
    : ((await response.json()) as T);
};

export const getSession = () => request<User>("/api/auth/session");

export const login = (username: string, password: string) =>
  request<User>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const logout = () =>
  request<void>("/api/auth/logout", {
    method: "POST",
  });

export const getBoard = () => request<BoardData>("/api/board");

export const renameColumn = (columnId: string, title: string) =>
  request<BoardData>(`/api/columns/${columnId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const createCard = (columnId: string, title: string, details: string) =>
  request<BoardData>("/api/cards", {
    method: "POST",
    body: JSON.stringify({ column_id: Number(columnId), title, details }),
  });

export const editCard = (cardId: string, title: string, details: string) =>
  request<BoardData>(`/api/cards/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify({ title, details }),
  });

export const deleteCard = (cardId: string) =>
  request<BoardData>(`/api/cards/${cardId}`, {
    method: "DELETE",
  });

export const moveCard = (
  cardId: string,
  columnId: string,
  position: number
) =>
  request<BoardData>(`/api/cards/${cardId}/move`, {
    method: "POST",
    body: JSON.stringify({ column_id: Number(columnId), position }),
  });

export const getChatHistory = () => request<ChatMessage[]>("/api/chat");

export const sendChatMessage = (message: string) =>
  request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
