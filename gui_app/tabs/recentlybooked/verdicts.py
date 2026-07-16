"""RecentlyBooked ethnicity-review verdict persistence and UI apply."""
from __future__ import annotations

from typing import Any, Dict, List, Set

from gui_app.shared.record_sidebar import RecordSidebar
from gui_app.shared.verdict_persist import persist_ethnicity_verdict
from gui_app.widgets import (
    tree_iid_for_record,
    tree_row_forget,
    tree_row_record,
)
from scraper.identity_review import shares_identity


class RbVerdictsMixin:
    def _rb_persist_verdict(self, record: Dict[str, Any], verdict: str) -> bool:
        """Write ethnicity_review into flags; resolve id via source_url when needed."""
        ok, _flags, err = persist_ethnicity_verdict(self.db_path, record, verdict)
        if not ok and err:
            self.log(f"RB verification save failed: {err}")
        return ok

    def _rb_related_indexes(
        self, record: Dict[str, Any], records: List[Dict[str, Any]]
    ) -> List[int]:
        sib_ids: Set[int] = {
            int(x)
            for x in (record.get("_confirmed_sibling_ids") or [])
            if x is not None
        }
        rid = record.get("id")
        if rid is not None:
            sib_ids.add(int(rid))
        out: List[int] = []
        for i, existing in enumerate(records):
            eid = existing.get("id")
            if eid is not None and int(eid) in sib_ids:
                out.append(i)
                continue
            if shares_identity(record, existing):
                out.append(i)
        return out

    def _rb_apply_verdict(
        self,
        record: Dict[str, Any],
        verdict: str,
        *,
        tree,
        records: List[Dict[str, Any]],
        sidebar: RecordSidebar,
        remove_from_list: bool = False,
    ) -> None:
        label = (
            "classified correctly"
            if verdict == "correct"
            else "classified incorrectly"
        )
        saved = self._rb_persist_verdict(record, verdict)
        # Keep in-memory copies in sync for this person (all identity siblings).
        related = self._rb_related_indexes(record, records)
        if not related:
            for i, existing in enumerate(records):
                same_id = record.get("id") and existing.get("id") == record.get("id")
                same_url = (
                    record.get("source_url")
                    and existing.get("source_url") == record.get("source_url")
                )
                if same_id or same_url or existing is record:
                    related = [i]
                    break
        for i in related:
            existing = records[i]
            existing["flags"] = record.get("flags")
            if record.get("id") is not None:
                existing["id"] = record["id"]

        if saved:
            self.log(f"Marked {self._rb_name(record)} as {label}.")
        else:
            self.log(
                f"Could not save confirmation for {self._rb_name(record)} "
                f"as {label} — still in queue (import / fix DB id first)."
            )
            # Never drop from Unverified unless the DB write stuck; otherwise the
            # same person reappears on the next Analyze and looks "unconfirmed".
            sidebar.show(record)
            return

        if remove_from_list and related:
            # Remove highest index first; keep a neighbor for next selection.
            next_iid = None
            primary_iid = tree_iid_for_record(tree, records[related[0]])
            if primary_iid is not None:
                kids = list(tree.get_children())
                if primary_iid in kids:
                    pos = kids.index(primary_iid)
                    # Prefer a neighbor that is not also being removed.
                    remove_iids = {
                        tree_iid_for_record(tree, records[i]) for i in related
                    }
                    for cand_pos in list(range(pos + 1, len(kids))) + list(
                        range(pos - 1, -1, -1)
                    ):
                        if kids[cand_pos] not in remove_iids:
                            next_iid = kids[cand_pos]
                            break
            for i in sorted(related, reverse=True):
                rec = records[i]
                iid = tree_iid_for_record(tree, rec)
                if iid is not None:
                    try:
                        tree.delete(iid)
                    except Exception:
                        pass
                    tree_row_forget(tree, iid)
                records.pop(i)
            if next_iid is not None:
                tree.selection_set(next_iid)
                tree.focus(next_iid)
                tree.see(next_iid)
                nrec = tree_row_record(tree, next_iid)
                sidebar.show(nrec) if nrec is not None else sidebar.clear()
            else:
                sidebar.clear("No more rows.")
            return

        sidebar.show(record)
