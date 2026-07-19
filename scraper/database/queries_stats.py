"""Arrest distribution / integrity / iteration query helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


class QueryStatsMixin:
    def distinct_races(self) -> List[str]:
        rows = self._conn.execute(
            """
            SELECT DISTINCT TRIM(race) AS race
            FROM arrests
            WHERE race IS NOT NULL AND TRIM(race) != ''
            ORDER BY race COLLATE NOCASE
            """
        ).fetchall()
        return [str(r["race"]) for r in rows if r and r["race"]]

    def distinct_race_labels(self) -> List[str]:
        """Merged display labels (White, Black, …) for filter dropdowns.

        Only known race labels are returned — charge/docket fragments that
        leaked into the race column must never appear in the UI dropdown.
        """
        from scraper.searcher import format_race_label
        from scraper.searcher_race_tables import KNOWN_RACE_LABELS

        labels = {
            lab
            for r in self.distinct_races()
            if (lab := format_race_label(r)) in KNOWN_RACE_LABELS
        }
        labels.add("Other/Unknown")
        return sorted(labels, key=lambda s: s.lower())

    def distinct_likely_ethnicities(self) -> List[str]:
        rows = self._conn.execute(
            """
            SELECT DISTINCT TRIM(likely_ethnicity) AS eth
            FROM arrests
            WHERE likely_ethnicity IS NOT NULL AND TRIM(likely_ethnicity) != ''
            ORDER BY eth COLLATE NOCASE
            """
        ).fetchall()
        return [str(r["eth"]) for r in rows if r and r["eth"]]

    def distinct_source_systems(self) -> List[str]:
        """Source ids for Browse filter (recentlybooked, mugshotscom, DOC, …)."""
        rows = self._conn.execute(
            """
            SELECT DISTINCT TRIM(source_system) AS src
            FROM arrests
            WHERE source_system IS NOT NULL AND TRIM(source_system) != ''
            ORDER BY src COLLATE NOCASE
            """
        ).fetchall()
        return [str(r["src"]) for r in rows if r and r["src"]]

    def get_charge_category_distribution(self) -> List[Dict[str, Any]]:
        from scraper.charge_classifications import category_label

        rows = self._conn.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(charge_category), ''), 'unknown') AS cat,
                   COUNT(*) AS count
            FROM arrests
            GROUP BY cat
            ORDER BY count DESC
            """
        ).fetchall()
        return [
            {
                "category": r["cat"],
                "label": category_label(r["cat"]),
                "count": int(r["count"] or 0),
            }
            for r in rows
        ]

    def iter_arrests(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        *,
        newest_first: bool = False,
        named_only: bool = False,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        with_photos: bool = False,
    ):
        offset = max(0, int(offset or 0))
        order = "DESC" if newest_first else "ASC"
        where = "WHERE 1=1"
        params_list: List[Any] = []
        if named_only:
            where += (
                " AND ("
                "(last_name IS NOT NULL AND TRIM(last_name) != '') "
                "OR (full_name IS NOT NULL AND TRIM(full_name) != '')"
                ")"
            )
        if charge_category and str(charge_category).lower() not in ("all", "", "*"):
            where += " AND LOWER(COALESCE(charge_category, '')) = LOWER(?)"
            params_list.append(charge_category)
        if source_system and str(source_system).lower() not in ("all", "", "*"):
            where += " AND LOWER(COALESCE(source_system, '')) = LOWER(?)"
            params_list.append(source_system)
        if with_photos:
            where += (
                " AND photo_path IS NOT NULL AND TRIM(photo_path) != ''"
            )
        if limit is None or int(limit) <= 0:
            sql = f"SELECT * FROM arrests {where} ORDER BY id {order}"
            params: tuple = tuple(params_list)
            if offset:
                sql += " LIMIT -1 OFFSET ?"
                params = tuple(params_list) + (offset,)
        else:
            sql = f"SELECT * FROM arrests {where} ORDER BY id {order} LIMIT ? OFFSET ?"
            params = tuple(params_list) + (int(limit), offset)
        for row in self._conn.execute(sql, params):
            yield dict(row)

    # SOR DeepFace scanner alias
    def iter_offenders(self, **kwargs):
        # Map common SOR kwargs
        if "with_photo" in kwargs and "with_photos" not in kwargs:
            kwargs["with_photos"] = kwargs.pop("with_photo")
        return self.iter_arrests(**kwargs)

    def get_integrity_report(self) -> Dict[str, Any]:
        def _pct(n: int, d: int) -> float:
            return round(100.0 * n / d, 1) if d else 0.0

        total = self.get_total_count()
        row = self._conn.execute(
            """
            SELECT
              SUM(CASE WHEN race IS NOT NULL AND TRIM(race) != '' THEN 1 ELSE 0 END) AS with_race,
              SUM(CASE WHEN last_name IS NOT NULL AND TRIM(last_name) != '' THEN 1 ELSE 0 END) AS with_name,
              SUM(CASE WHEN charge_description IS NOT NULL AND TRIM(charge_description) != '' THEN 1 ELSE 0 END) AS with_charge,
              SUM(CASE WHEN arrest_date IS NOT NULL AND TRIM(arrest_date) != '' THEN 1 ELSE 0 END) AS with_date,
              SUM(CASE WHEN source_url IS NOT NULL AND TRIM(source_url) != '' THEN 1 ELSE 0 END) AS with_url,
              SUM(CASE WHEN photo_path IS NOT NULL AND TRIM(photo_path) != '' THEN 1 ELSE 0 END) AS with_photo,
              SUM(CASE WHEN html_path IS NOT NULL AND TRIM(html_path) != '' THEN 1 ELSE 0 END) AS with_html
            FROM arrests
            """
        ).fetchone()
        overall = {
            "total": total,
            "with_race": int(row["with_race"] or 0) if row else 0,
            "with_name": int(row["with_name"] or 0) if row else 0,
            "with_charge": int(row["with_charge"] or 0) if row else 0,
            "with_date": int(row["with_date"] or 0) if row else 0,
            "with_url": int(row["with_url"] or 0) if row else 0,
            "with_photo": int(row["with_photo"] or 0) if row else 0,
            "with_html": int(row["with_html"] or 0) if row else 0,
        }
        for k in ("race", "name", "charge", "date", "url", "photo", "html"):
            overall[f"pct_{k}"] = _pct(overall[f"with_{k}"], total)

        by_state = []
        for r in self._conn.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(UPPER(state)), ''), 'UNK') AS st,
                   COUNT(*) AS total,
                   SUM(CASE WHEN race IS NOT NULL AND TRIM(race) != '' THEN 1 ELSE 0 END) AS with_race,
                   SUM(CASE WHEN last_name IS NOT NULL AND TRIM(last_name) != '' THEN 1 ELSE 0 END) AS with_name
            FROM arrests GROUP BY st ORDER BY total DESC
            """
        ):
            t = int(r["total"] or 0)
            by_state.append({
                "state": r["st"] or "UNK",
                "total": t,
                "with_race": int(r["with_race"] or 0),
                "with_name": int(r["with_name"] or 0),
                "pct_race": _pct(int(r["with_race"] or 0), t),
                "pct_name": _pct(int(r["with_name"] or 0), t),
            })
        return {"overall": overall, "by_state": by_state}

    def get_race_distribution(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT race, COUNT(*) as count FROM arrests GROUP BY race ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_state_distribution(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) as count FROM arrests GROUP BY state ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]
