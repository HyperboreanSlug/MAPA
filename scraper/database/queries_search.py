"""Arrest search query helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.database.constants import _escape_like


class QuerySearchMixin:
    def search_by_name(
        self,
        name: str,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        since_date: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        return self.search_records(
            name=name,
            state=state,
            race=race,
            charge_category=charge_category,
            source_system=source_system,
            since_date=since_date,
            limit=limit,
            offset=offset,
        )

    def search_records(
        self,
        *,
        name: Optional[str] = None,
        state: Optional[str] = None,
        race: Optional[str] = None,
        likely_ethnicity: Optional[str] = None,
        likely_ethnicity_in: Optional[List[str]] = None,
        ethnicity_review: Optional[str] = None,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        since_date: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        q = "SELECT * FROM arrests WHERE 1=1"
        params: List[Any] = []
        if since_date and str(since_date).strip():
            from scraper.database.date_window import sql_since_date

            frag, frag_params = sql_since_date(str(since_date).strip())
            if frag:
                q += frag
                params.extend(frag_params)
        if name and str(name).strip():
            esc = _escape_like(str(name).strip())
            term = f"%{esc}%"
            q += (
                " AND (full_name LIKE ? ESCAPE '\\' OR first_name LIKE ? ESCAPE '\\' "
                "OR last_name LIKE ? ESCAPE '\\')"
            )
            params.extend([term, term, term])
        if state and state.upper() != "ALL":
            q += " AND UPPER(COALESCE(state, '')) = UPPER(?)"
            params.append(state)
        if race and str(race).strip().lower() not in ("", "all", "*"):
            from scraper.searcher import format_race_label

            # Match by merged display label so grouped categories (e.g.
            # Other/Unknown, White) select every underlying raw variant.
            target_label = format_race_label(str(race).strip())
            raw_rows = self._conn.execute(
                """
                SELECT DISTINCT race FROM arrests
                WHERE race IS NOT NULL AND TRIM(race) != ''
                """
            ).fetchall()
            matched = [
                str(r["race"])
                for r in raw_rows
                if r and r["race"] and format_race_label(str(r["race"])) == target_label
            ]
            include_null = format_race_label("") == target_label
            if include_null:
                if matched:
                    ph = ",".join("?" * len(matched))
                    q += (
                        " AND (race IS NULL OR TRIM(race) = '' "
                        f"OR TRIM(race) IN ({ph}))"
                    )
                    params.extend(matched)
                else:
                    q += " AND (race IS NULL OR TRIM(race) = '')"
            elif matched:
                ph = ",".join("?" * len(matched))
                q += f" AND TRIM(race) IN ({ph})"
                params.extend(matched)
            else:
                q += " AND 0"
        if likely_ethnicity_in is not None:
            vals = [
                str(v).strip()
                for v in (likely_ethnicity_in or [])
                if v is not None and str(v).strip()
            ]
            if not vals:
                q += " AND 0"
            else:
                # Exact match or prefix (e.g. Indian → Indian (high_confidence),
                # European → European (english)). Escape LIKE metacharacters.
                parts: List[str] = []
                for v in vals:
                    low = v.lower()
                    esc = _escape_like(low)
                    parts.append(
                        "("
                        "LOWER(TRIM(COALESCE(likely_ethnicity, ''))) = ? "
                        "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                        "LIKE ? ESCAPE '\\' "
                        "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                        "LIKE ? ESCAPE '\\'"
                        ")"
                    )
                    params.extend([low, f"{esc} %", f"{esc}(%"])
                q += " AND (" + " OR ".join(parts) + ")"
        elif likely_ethnicity and str(likely_ethnicity).strip().lower() not in (
            "",
            "all",
            "*",
        ):
            actual = str(likely_ethnicity).strip()
            low = actual.lower()
            if low in ("unset", "none", "(unset)"):
                # Unset is not offered in Browse UI; keep for API callers only.
                q += (
                    " AND (likely_ethnicity IS NULL OR TRIM(likely_ethnicity) = '')"
                )
            else:
                esc = _escape_like(low)
                q += (
                    " AND ("
                    "LOWER(TRIM(COALESCE(likely_ethnicity, ''))) = ? "
                    "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                    "LIKE ? ESCAPE '\\' "
                    "OR LOWER(TRIM(COALESCE(likely_ethnicity, ''))) "
                    "LIKE ? ESCAPE '\\'"
                    ")"
                )
                params.extend([low, f"{esc} %", f"{esc}(%"])
        if charge_category and str(charge_category).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(charge_category, '')) = LOWER(?)"
            params.append(charge_category)
        if source_system and str(source_system).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(source_system, '')) = LOWER(?)"
            params.append(source_system)
        # Review status lives in JSON flags — filter in Python after a SQL prune.
        # Never load the full multi-million-row table when the caller passed a
        # positive limit (GUI Browse after bulk DOC imports).
        review = (ethnicity_review or "").strip().lower()
        review_active = bool(review and review not in ("all", "*", ""))
        unreviewed = review in ("unreviewed", "none", "unset", "unverified")
        if review_active and unreviewed:
            # Cheap SQL prefilter: drop rows that already store a verdict flag.
            # Identity-sibling reviewed people are still excluded in Python.
            q += (
                " AND (flags IS NULL OR TRIM(flags) = '' "
                "OR flags NOT LIKE '%ethnicity_review%')"
            )
        elif review_active and review in ("correct", "incorrect"):
            q += (
                " AND flags IS NOT NULL AND TRIM(flags) != '' "
                "AND flags LIKE '%ethnicity_review%'"
            )

        # Prefer arrest_date, then booking_date (ISO), then newest id.
        # Website sources (RecentlyBooked) often only fill booking_date.
        order = (
            " ORDER BY COALESCE("
            "NULLIF(TRIM(arrest_date), ''), "
            "NULLIF(TRIM(booking_date), '')"
            ") DESC, id DESC, last_name ASC"
        )
        if not review_active:
            if limit:
                q += order + " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            else:
                q += order
                if offset:
                    q += " LIMIT -1 OFFSET ?"
                    params.append(offset)
            rows = [dict(r) for r in self._conn.execute(q, params).fetchall()]
            if limit and len(rows) > limit:
                rows = rows[:limit]
            return rows

        return self._search_records_review_filter(
            q,
            params,
            order=order,
            review=review,
            unreviewed=unreviewed,
            limit=limit,
            offset=offset,
        )

    def _search_records_review_filter(
        self,
        q: str,
        params: List[Any],
        *,
        order: str,
        review: str,
        unreviewed: bool,
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        """Page through SQL matches, apply verdict/identity filters, honor limit."""
        from scraper.identity_review import (
            dedupe_records_by_person,
            is_person_reviewed,
            load_reviewed_identity_keys,
        )
        from scraper.searcher import ethnicity_review_verdict

        reviewed_keys = load_reviewed_identity_keys(self) if unreviewed else None
        want = max(0, int(limit)) if limit else 0
        # When unlimited, stream in chunks so we never hold 2M+ raw rows at once.
        page_size = min(max(want * 8, 2000), 10_000) if want else 5000
        # Safety: stop paging after this many SQL rows (unlimited export path).
        max_scan = want * 200 if want else 2_000_000
        max_scan = max(max_scan, page_size)

        filtered: List[Dict[str, Any]] = []
        scanned = 0
        while scanned < max_scan:
            page_sql = q + order + " LIMIT ? OFFSET ?"
            page_params = list(params) + [page_size, scanned]
            page = [dict(r) for r in self._conn.execute(page_sql, page_params).fetchall()]
            if not page:
                break
            scanned += len(page)
            for rec in page:
                if unreviewed:
                    if is_person_reviewed(rec, reviewed_keys):
                        continue
                    filtered.append(rec)
                else:
                    if ethnicity_review_verdict(rec) == review:
                        filtered.append(rec)
            if unreviewed:
                filtered = dedupe_records_by_person(filtered, prefer_confidence=False)
            # Enough rows to satisfy offset+limit (or filled unlimited batch goal).
            need = (offset + want) if want else 0
            if want and len(filtered) >= need:
                break
            if len(page) < page_size:
                break

        if offset:
            filtered = filtered[offset:]
        if want and len(filtered) > want:
            filtered = filtered[:want]
        return filtered
