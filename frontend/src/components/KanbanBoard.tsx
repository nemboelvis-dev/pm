"use client";

import { useEffect, useMemo, useState } from "react";
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
import { LogOut } from "lucide-react";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { ChatSidebar } from "@/components/ChatSidebar";
import {
  ApiError,
  createCard,
  deleteCard,
  editCard,
  getBoard,
  moveCard as moveCardRequest,
  renameColumn,
} from "@/lib/api";
import { moveCard, type BoardData } from "@/lib/kanban";

type KanbanBoardProps = {
  username?: string;
  onLogout?: () => Promise<void>;
  initialBoard?: BoardData;
};

export const KanbanBoard = ({
  username,
  onLogout,
  initialBoard,
}: KanbanBoardProps = {}) => {
  const [board, setBoard] = useState<BoardData | null>(initialBoard ?? null);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  useEffect(() => {
    if (initialBoard) return;
    getBoard()
      .then(setBoard)
      .catch((loadError: unknown) =>
        setError(
          errorMessage(
            loadError,
            "Unable to load the board. Check that the server is running and try again."
          )
        )
      );
  }, [initialBoard]);

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
        cardId,
        targetColumn.id,
        targetColumn.cardIds.indexOf(cardId)
      )
    );
    if (!saved) setBoard(previousBoard);
  };

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
                  getBoard()
                    .then(setBoard)
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
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                {board.title}
              </h1>
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
                One board. Five columns. Zero clutter.
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
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
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
                      applyMutation(() => renameColumn(columnId, title))
                    }
                    onAddCard={(columnId, title, details) =>
                      applyMutation(() => createCard(columnId, title, details))
                    }
                    onEditCard={(cardId, title, details) =>
                      applyMutation(() => editCard(cardId, title, details))
                    }
                    onDeleteCard={async (cardId) => {
                      await applyMutation(() => deleteCard(cardId));
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
          <ChatSidebar onBoardUpdate={setBoard} />
        </div>
      </main>
    </div>
  );
};

const errorMessage = (
  error: unknown,
  fallback = "Unable to save this change."
) => (error instanceof ApiError ? error.message : fallback);
