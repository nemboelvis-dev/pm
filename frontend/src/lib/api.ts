import type { BoardData } from "@/lib/kanban";

export type User = {
  username: string;
};

export type BoardSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
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

export const register = (username: string, password: string) =>
  request<User>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });

export const logout = () =>
  request<void>("/api/auth/logout", {
    method: "POST",
  });

export const listBoards = () => request<BoardSummary[]>("/api/boards");

export const createBoard = (title: string) =>
  request<BoardData>("/api/boards", {
    method: "POST",
    body: JSON.stringify({ title }),
  });

export const getBoard = (boardId: string) =>
  request<BoardData>(`/api/boards/${boardId}`);

export const renameBoard = (boardId: string, title: string) =>
  request<BoardData>(`/api/boards/${boardId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const deleteBoard = (boardId: string) =>
  request<void>(`/api/boards/${boardId}`, {
    method: "DELETE",
  });

export const renameColumn = (
  boardId: string,
  columnId: string,
  title: string
) =>
  request<BoardData>(`/api/boards/${boardId}/columns/${columnId}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });

export const createCard = (
  boardId: string,
  columnId: string,
  title: string,
  details: string
) =>
  request<BoardData>(`/api/boards/${boardId}/cards`, {
    method: "POST",
    body: JSON.stringify({ column_id: Number(columnId), title, details }),
  });

export const editCard = (
  boardId: string,
  cardId: string,
  title: string,
  details: string
) =>
  request<BoardData>(`/api/boards/${boardId}/cards/${cardId}`, {
    method: "PATCH",
    body: JSON.stringify({ title, details }),
  });

export const deleteCard = (boardId: string, cardId: string) =>
  request<BoardData>(`/api/boards/${boardId}/cards/${cardId}`, {
    method: "DELETE",
  });

export const moveCard = (
  boardId: string,
  cardId: string,
  columnId: string,
  position: number
) =>
  request<BoardData>(`/api/boards/${boardId}/cards/${cardId}/move`, {
    method: "POST",
    body: JSON.stringify({ column_id: Number(columnId), position }),
  });

export const getChatHistory = (boardId: string) =>
  request<ChatMessage[]>(`/api/boards/${boardId}/chat`);

export const sendChatMessage = (boardId: string, message: string) =>
  request<ChatResponse>(`/api/boards/${boardId}/chat`, {
    method: "POST",
    body: JSON.stringify({ message }),
  });
