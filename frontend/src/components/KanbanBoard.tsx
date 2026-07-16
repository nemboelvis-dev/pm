"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { LogOut, Plus } from "lucide-react";
import { BoardSwitcher } from "@/components/BoardSwitcher";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { ChatSidebar } from "@/components/ChatSidebar";
import {
  ApiError,
  createBoard,
  createCard,
  deleteBoard,
  deleteCard,
  editCard,
  getBoard,
  listBoards,
  moveCard as moveCardRequest,
  renameBoard,
  renameColumn,
  type BoardSummary,
} from "@/lib/api";
import { moveCard, type BoardData } from "@/lib/kanban";

type KanbanBoardProps = {
  username?: string;
  onLogout?: () => Promise<void>;
  initialBoard?: BoardData;
  initialBoards?: BoardSummary[];
};

export const KanbanBoard = ({
  username,
  onLogout,
  initialBoard,
  initialBoards,
}: KanbanBoardProps = {}) => {
  const [boards, setBoards] = useState<BoardSummary[] | null>(
    initialBoards ?? (initialBoard ? [summaryFromBoard(initialBoard)] : null)
  );
  const [activeBoardId, setActiveBoardId] = useState<string | null>(
    initialBoard?.id ?? initialBoards?.[0]?.id ?? null
  );
  const [board, setBoard] = useState<BoardData | null>(initialBoard ?? null);
  const [boardTitle, setBoardTitle] = useState(initialBoard?.title ?? "");
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  useEffect(() => {
    if (initialBoards || initialBoard) return;
    listBoards()
      .then((list) => {
        setBoards(list);
        setActiveBoardId(list[0]?.id ?? null);
      })
      .catch((loadError: unknown) =>
        setError(
          errorMessage(
            loadError,
            "Unable to load your boards. Check that the server is running and try again."
          )
        )
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!activeBoardId || board?.id === activeBoardId) return;
    getBoard(activeBoardId)
      .then((loaded) => {
        setBoard(loaded);
        setBoardTitle(loaded.title);
      })
      .catch((loadError: unknown) =>
        setError(
          errorMessage(
            loadError,
            "Unable to load the board. Check that the server is running and try again."
          )
        )
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBoardId]);

  const cardsById = useMemo(() => board?.cards ?? {}, [board?.cards]);

  const applyMutation = async (
    operation: () => Promise<BoardData>
  ): Promise<boolean> => {
    setError(null);
    try {
      setBoard(await operation());
      return true;
    } catch (mutationError) {
      setError(errorMessage(mutationError));
      return false;
    }
  };

  const refreshBoards = async () => {
    try {
      setBoards(await listBoards());
    } catch (loadError) {
      setError(errorMessage(loadError, "Unable to refresh your boards."));
    }
  };

  const handleCreateBoard = async (title: string): Promise<boolean> => {
    setError(null);
    try {
      const created = await createBoard(title);
      setBoard(created);
      setBoardTitle(created.title);
      setActiveBoardId(created.id);
      await refreshBoards();
      return true;
    } catch (createError) {
      setError(errorMessage(createError, "Unable to create the board."));
      return false;
    }
  };

  const handleDeleteBoard = async (boardId: string) => {
    if (!window.confirm("Delete this board and all of its cards?")) return;
    setError(null);
    try {
      await deleteBoard(boardId);
      const remaining = await listBoards();
      setBoards(remaining);
      if (boardId === activeBoardId) {
        const next = remaining[0]?.id ?? null;
        setActiveBoardId(next);
        if (!next) setBoard(null);
      }
    } catch (deleteError) {
      setError(errorMessage(deleteError, "Unable to delete the board."));
    }
  };

  const saveBoardTitle = async () => {
    if (!board) return;
    const nextTitle = boardTitle.trim();
    if (!nextTitle || nextTitle === board.title) {
      setBoardTitle(board.title);
      return;
    }
    const saved = await applyMutation(() => renameBoard(board.id, nextTitle));
    if (saved) {
      await refreshBoards();
    } else {
      setBoardTitle(board.title);
    }
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!board || !over || active.id === over.id) return;

    const cardId = active.id as string;
    const nextColumns = moveCard(board.columns, cardId, over.id as string);
    const targetColumn = nextColumns.find((column) =>
      column.cardIds.includes(cardId)
    );
    if (!targetColumn) return;

    const previousBoard = board;
    setBoard({ ...board, columns: nextColumns });
    const saved = await applyMutation(() =>
      moveCardRequest(
        board.id,
        cardId,
        targetColumn.id,
        targetColumn.cardIds.indexOf(cardId)
      )
    );
    if (!saved) setBoard(previousBoard);
  };

  if (boards && boards.length === 0) {
    return (
      <FirstBoardPrompt
        username={username}
        onLogout={onLogout}
        error={error}
        onCreate={handleCreateBoard}
      />
    );
  }

  if (!board) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <div className="text-center">
          <p className="text-sm font-semibold uppercase tracking-[0.25em] text-[var(--primary-blue)]">
            {error ? "Unable to load board" : "Loading board..."}
          </p>
          {error ? (
            <>
              <p className="mt-3 text-sm text-[var(--gray-text)]" role="alert">
                {error}
              </p>
              <button
                className="mt-5 rounded-full bg-[var(--secondary-purple)] px-5 py-2 text-xs font-semibold uppercase tracking-wide text-white"
                onClick={() => {
                  setError(null);
                  listBoards()
                    .then((list) => {
                      setBoards(list);
                      setActiveBoardId(list[0]?.id ?? null);
                    })
                    .catch((loadError: unknown) =>
                      setError(
                        errorMessage(
                          loadError,
                          "Unable to load the board. Check that the server is running and try again."
                        )
                      )
                    );
                }}
                type="button"
              >
                Try again
              </button>
            </>
          ) : null}
        </div>
      </main>
    );
  }

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1920px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Kanban Workspace
              </p>
              <input
                aria-label="Board title"
                className="mt-3 w-full max-w-xl bg-transparent font-display text-4xl font-semibold text-[var(--navy-dark)] outline-none"
                onBlur={() => void saveBoardTitle()}
                onChange={(event) => setBoardTitle(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") event.currentTarget.blur();
                  if (event.key === "Escape") {
                    setBoardTitle(board.title);
                    event.currentTarget.blur();
                  }
                }}
                value={boardTitle}
              />
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                Focus
              </p>
              <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                Multiple boards. Five columns each. Zero clutter.
              </p>
              {username && onLogout ? (
                <div className="mt-4 flex items-center justify-between gap-4 border-t border-[var(--stroke)] pt-4">
                  <span className="text-xs font-semibold text-[var(--gray-text)]">
                    Signed in as {username}
                  </span>
                  <button
                    className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--secondary-purple)] hover:underline"
                    onClick={onLogout}
                    type="button"
                  >
                    <LogOut aria-hidden="true" size={14} />
                    Log out
                  </button>
                </div>
              ) : null}
            </div>
          </div>
          {error ? (
            <div
              className="flex items-center justify-between gap-4 rounded-2xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700"
              role="alert"
            >
              {error}
              <button
                className="font-semibold underline"
                onClick={() => setError(null)}
                type="button"
              >
                Dismiss
              </button>
            </div>
          ) : null}
          <BoardSwitcher
            activeBoardId={board.id}
            boards={boards ?? [summaryFromBoard(board)]}
            onCreate={handleCreateBoard}
            onDelete={handleDeleteBoard}
            onSwitch={setActiveBoardId}
          />
        </header>

        <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <div className="overflow-x-auto pb-3">
            <DndContext
              id="kanban-board-dnd"
              sensors={sensors}
              collisionDetection={closestCorners}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <section className="grid grid-cols-[repeat(5,minmax(210px,1fr))] gap-5">
                {board.columns.map((column) => (
                  <KanbanColumn
                    key={column.id}
                    column={column}
                    cards={column.cardIds.map((cardId) => board.cards[cardId])}
                    onRename={(columnId, title) =>
                      applyMutation(() => renameColumn(board.id, columnId, title))
                    }
                    onAddCard={(columnId, title, details) =>
                      applyMutation(() =>
                        createCard(board.id, columnId, title, details)
                      )
                    }
                    onEditCard={(cardId, title, details) =>
                      applyMutation(() =>
                        editCard(board.id, cardId, title, details)
                      )
                    }
                    onDeleteCard={async (cardId) => {
                      await applyMutation(() => deleteCard(board.id, cardId));
                    }}
                  />
                ))}
              </section>
              <DragOverlay>
                {activeCard ? (
                  <div className="w-[260px]">
                    <KanbanCardPreview card={activeCard} />
                  </div>
                ) : null}
              </DragOverlay>
            </DndContext>
          </div>
          <ChatSidebar key={board.id} boardId={board.id} onBoardUpdate={setBoard} />
        </div>
      </main>
    </div>
  );
};

type FirstBoardPromptProps = {
  username?: string;
  onLogout?: () => Promise<void>;
  error: string | null;
  onCreate: (title: string) => Promise<boolean>;
};

const FirstBoardPrompt = ({
  username,
  onLogout,
  error,
  onCreate,
}: FirstBoardPromptProps) => {
  const [title, setTitle] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim()) return;
    setIsSaving(true);
    await onCreate(title.trim());
    setIsSaving(false);
  };

  return (
    <main className="grid min-h-screen place-items-center px-6">
      <div className="w-full max-w-md rounded-[32px] border border-[var(--stroke)] bg-white p-8 text-center shadow-[var(--shadow)]">
        {username && onLogout ? (
          <div className="mb-6 flex items-center justify-between text-xs font-semibold text-[var(--gray-text)]">
            <span>Signed in as {username}</span>
            <button
              className="flex items-center gap-1.5 uppercase tracking-wide text-[var(--secondary-purple)] hover:underline"
              onClick={onLogout}
              type="button"
            >
              <LogOut aria-hidden="true" size={14} />
              Log out
            </button>
          </div>
        ) : null}
        <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--primary-blue)]">
          Kanban Workspace
        </p>
        <h1 className="mt-3 font-display text-3xl font-semibold text-[var(--navy-dark)]">
          Create your first board
        </h1>
        <p className="mt-3 text-sm leading-6 text-[var(--gray-text)]">
          Give it a name and we will set up five starter columns for you.
        </p>
        <form className="mt-6 space-y-3" onSubmit={handleSubmit}>
          <input
            className="w-full rounded-2xl border border-[var(--stroke)] px-4 py-3 text-sm font-medium text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Board name"
            value={title}
          />
          {error ? (
            <p className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-medium text-red-700" role="alert">
              {error}
            </p>
          ) : null}
          <button
            className="flex w-full items-center justify-center gap-2 rounded-full bg-[var(--secondary-purple)] px-5 py-3 text-sm font-semibold uppercase tracking-[0.18em] text-white transition hover:brightness-110 disabled:cursor-wait disabled:opacity-60"
            disabled={isSaving}
            type="submit"
          >
            <Plus aria-hidden="true" size={16} />
            {isSaving ? "Creating..." : "Create board"}
          </button>
        </form>
      </div>
    </main>
  );
};

const summaryFromBoard = (data: BoardData): BoardSummary => ({
  id: data.id,
  title: data.title,
  created_at: "",
  updated_at: "",
});

const errorMessage = (
  error: unknown,
  fallback = "Unable to save this change."
) => (error instanceof ApiError ? error.message : fallback);
