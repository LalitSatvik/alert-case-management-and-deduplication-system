import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { UserOut } from "../../api/types";
import {
  deleteView,
  listSavedViews,
  sanitizeViewQuery,
  saveView,
  type SavedView,
} from "../../lib/savedViews";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "../ui/Menu";
import { buttonClass } from "../ui/Button";

export function SavedViewsMenu({ users }: { users: UserOut[] }) {
  const [sp, setSp] = useSearchParams();
  const [views, setViews] = useState<SavedView[]>(listSavedViews);

  const currentQuery = sp.toString();

  const apply = (view: SavedView) => {
    const cleaned = sanitizeViewQuery(view.query, users);
    setSp(new URLSearchParams(cleaned));
  };

  const onSave = () => {
    const name = window.prompt("Name this view");
    if (!name || !name.trim()) return;
    saveView(name, currentQuery);
    setViews(listSavedViews());
  };

  const onDelete = (id: string) => {
    deleteView(id);
    setViews(listSavedViews());
  };

  return (
    <Menu>
      <MenuTrigger className={buttonClass("default", "sm")}>Views</MenuTrigger>
      <MenuContent align="end" className="min-w-[14rem]">
        <MenuLabel>Saved views</MenuLabel>
        {views.length === 0 && (
          <p className="px-2 py-1.5 text-xs text-ink-tertiary">None yet</p>
        )}
        {views.map((v) => (
          <div key={v.id} className="flex items-center">
            <button
              type="button"
              onClick={() => apply(v)}
              className="flex-1 truncate rounded-sm px-2 py-1.5 text-left text-sm text-ink-secondary hover:bg-surface-hover hover:text-ink"
            >
              {v.name}
            </button>
            <button
              type="button"
              aria-label={`Delete ${v.name}`}
              onClick={() => onDelete(v.id)}
              className="rounded-sm px-2 py-1.5 text-xs text-ink-tertiary hover:text-ink-danger"
            >
              ✕
            </button>
          </div>
        ))}
        <MenuSeparator />
        <MenuItem onSelect={onSave}>Save current filters…</MenuItem>
      </MenuContent>
    </Menu>
  );
}
