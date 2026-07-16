import { useState, type FormEvent } from "react";
import { Plus, X } from "lucide-react";
import type { BoardSummary } from "@/lib/api";

type BoardSwitcherProps = {
  boards: BoardSummary[];
  activeBoardId: string;
  onSwitch: (boardId: string) => void;
  onCreate: (title: string) => Promise<boolean>;
  onDelete: (boardId: string) => Promise<void>;
};

export const BoardSwitcher = ({
  boards,
  activeBoardId,
  onSwitch,
  onCreate,
  onDelete,
}: BoardSwitcherProps) => {
  const [isCreating, setIsCreating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [title, setTitle] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim()) return;
    setIsSaving(true);
    const saved = await onCreate(title.trim());
    setIsSaving(false);
    if (saved) {
      setTitle("");
      setIsCreating(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      {boards.map((summary) => {
        const isActive = summary.id === activeBoardId;
        return (
          <div
            key={summary.id}
            className={`flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] transition ${
              isActive
                ? "border-[var(--primary-blue)] bg-[var(--primary-blue)] text-white"
                : "border-[var(--stroke)] text-[var(--navy-dark)] hover:border-[var(--primary-blue)]"
            }`}
            data-testid={`board-tab-${summary.id}`}
          >
            <button
              className="max-w-[16ch] truncate"
              onClick={() => onSwitch(summary.id)}
              type="button"
            >
              {summary.title}
            </button>
            {boards.length > 1 ? (
              <button
                aria-label={`Delete board ${summary.title}`}
                className={isActive ? "text-white/80 hover:text-white" : "text-[var(--gray-text)] hover:text-red-600"}
                onClick={() => void onDelete(summary.id)}
                type="button"
              >
                <X aria-hidden="true" size={13} />
              </button>
            ) : null}
          </div>
        );
      })}

      {isCreating ? (
        <form className="flex items-center gap-2" onSubmit={handleSubmit}>
          <input
            autoFocus
            className="w-40 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Board name"
            value={title}
          />
          <button
            className="rounded-full bg-[var(--secondary-purple)] px-3 py-2 text-xs font-semibold uppercase text-white disabled:opacity-60"
            disabled={isSaving}
            type="submit"
          >
            {isSaving ? "Adding..." : "Add"}
          </button>
          <button
            className="text-xs font-semibold uppercase text-[var(--gray-text)]"
            disabled={isSaving}
            onClick={() => {
              setIsCreating(false);
              setTitle("");
            }}
            type="button"
          >
            Cancel
          </button>
        </form>
      ) : (
        <button
          aria-label="Create a new board"
          className="flex items-center gap-1.5 rounded-full border border-dashed border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--primary-blue)] transition hover:border-[var(--primary-blue)]"
          onClick={() => setIsCreating(true)}
          type="button"
        >
          <Plus aria-hidden="true" size={14} />
          New board
        </button>
      )}
    </div>
  );
};
