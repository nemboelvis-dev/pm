import { useState, type FormEvent } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import { GripVertical, Pencil, Trash2 } from "lucide-react";
import type { Card } from "@/lib/kanban";

type KanbanCardProps = {
  card: Card;
  onDelete: (cardId: string) => Promise<void>;
  onEdit: (cardId: string, title: string, details: string) => Promise<boolean>;
};

export const KanbanCard = ({ card, onDelete, onEdit }: KanbanCardProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id });
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [title, setTitle] = useState(card.title);
  const [details, setDetails] = useState(card.details);

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const startEditing = () => {
    setTitle(card.title);
    setDetails(card.details);
    setIsEditing(true);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!title.trim()) return;
    setIsSaving(true);
    const saved = await onEdit(card.id, title.trim(), details.trim());
    setIsSaving(false);
    if (saved) setIsEditing(false);
  };

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={clsx(
        "rounded-2xl border border-transparent bg-white px-4 py-4 shadow-[0_12px_24px_rgba(3,33,71,0.08)]",
        "transition-all duration-150",
        isDragging && "opacity-60 shadow-[0_18px_32px_rgba(3,33,71,0.16)]"
      )}
      data-testid={`card-${card.id}`}
    >
      {isEditing ? (
        <form className="space-y-3" onSubmit={handleSubmit}>
          <label className="block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
            Title
            <input
              aria-label={`Edit title for ${card.title}`}
              className="mt-1 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none focus:border-[var(--primary-blue)]"
              onChange={(event) => setTitle(event.target.value)}
              required
              value={title}
            />
          </label>
          <label className="block text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)]">
            Details
            <textarea
              aria-label={`Edit details for ${card.title}`}
              className="mt-1 w-full resize-none rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm font-normal normal-case tracking-normal text-[var(--gray-text)] outline-none focus:border-[var(--primary-blue)]"
              onChange={(event) => setDetails(event.target.value)}
              rows={3}
              value={details}
            />
          </label>
          <div className="flex gap-2">
            <button
              className="rounded-full bg-[var(--secondary-purple)] px-3 py-2 text-xs font-semibold uppercase text-white disabled:opacity-60"
              disabled={isSaving}
              type="submit"
            >
              {isSaving ? "Saving..." : "Save"}
            </button>
            <button
              className="rounded-full border border-[var(--stroke)] px-3 py-2 text-xs font-semibold uppercase text-[var(--gray-text)]"
              disabled={isSaving}
              onClick={() => setIsEditing(false)}
              type="button"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <h4 className="font-display text-base font-semibold text-[var(--navy-dark)]">
                {card.title}
              </h4>
              <p className="mt-2 text-sm leading-6 text-[var(--gray-text)]">
                {card.details}
              </p>
            </div>
            <button
              className="flex shrink-0 cursor-grab items-center justify-center rounded-full p-1.5 text-[var(--gray-text)] transition hover:bg-[var(--surface)] active:cursor-grabbing"
              aria-label={`Drag ${card.title}`}
              title="Drag to move"
              type="button"
              {...attributes}
              {...listeners}
            >
              <GripVertical aria-hidden="true" size={16} />
            </button>
          </div>
          <div className="mt-3 flex items-center justify-end gap-1 border-t border-[var(--stroke)] pt-2">
            <button
              type="button"
              onClick={startEditing}
              className="rounded-full p-1.5 text-[var(--gray-text)] transition hover:bg-[var(--surface)] hover:text-[var(--primary-blue)]"
              aria-label={`Edit ${card.title}`}
              title="Edit"
            >
              <Pencil aria-hidden="true" size={15} />
            </button>
            <button
              type="button"
              onClick={() => void onDelete(card.id)}
              className="rounded-full p-1.5 text-[var(--gray-text)] transition hover:bg-red-50 hover:text-red-600"
              aria-label={`Delete ${card.title}`}
              title="Delete"
            >
              <Trash2 aria-hidden="true" size={15} />
            </button>
          </div>
        </>
      )}
    </article>
  );
};
