"""Name / DOB / photo identity keys for duplicate matching."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Punctuation stripped when normalizing person names for duplicate keys.
_NAME_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_DOB_SEP_RE = re.compile(r"[/\-.]")


class DedupeIdentityMixin:
    """Normalize name/DOB/photo and cluster same-person buckets."""

    @classmethod
    def normalize_arrest_name(cls, record: Dict[str, Any]) -> str:
        """Normalized full name: casefold, trim, collapse space, drop punctuation."""
        full = str(record.get("full_name") or "").strip()
        if not full:
            parts = [
                str(record.get("first_name") or "").strip(),
                str(record.get("middle_name") or "").strip(),
                str(record.get("last_name") or "").strip(),
            ]
            full = " ".join(p for p in parts if p)
        full = _NAME_PUNCT_RE.sub(" ", full)
        return " ".join(full.casefold().split())

    @staticmethod
    def normalize_date_of_birth(dob: Any) -> str:
        """Best-effort DOB key (YYYY-MM-DD when parseable, else compact digits)."""
        raw = str(dob or "").strip()
        if not raw:
            return ""
        compact = _DOB_SEP_RE.sub("/", raw)
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", compact)
        if m:
            mm, dd, yyyy = m.group(1), m.group(2), m.group(3)
            return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        m = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", compact)
        if m:
            yyyy, mm, dd = m.group(1), m.group(2), m.group(3)
            return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 8:
            if int(digits[:4]) > 1900:
                return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
            mm, dd, yyyy = digits[:2], digits[2:4], digits[4:8]
            if int(mm) > 12 and int(dd) <= 12:
                mm, dd = dd, mm
            return f"{yyyy}-{int(mm):02d}-{int(dd):02d}"
        return " ".join(raw.casefold().split())

    @classmethod
    def dob_match_key(cls, record: Dict[str, Any]) -> str:
        """DOB bucket key: normalized date_of_birth, else ``age:N`` when DOB is blank."""
        dob = cls.normalize_date_of_birth(record.get("date_of_birth"))
        if dob:
            return dob
        age = record.get("age")
        if age is not None and str(age).strip() != "":
            try:
                return f"age:{int(age)}"
            except (TypeError, ValueError):
                pass
        return ""

    @staticmethod
    def _photo_url_identity_token(url: str) -> str:
        """Stable token from a mugshot URL (RecentlyBooked image basename, etc.)."""
        raw = str(url or "").strip().casefold()
        if not raw:
            return ""
        if "recentlybooked.com/images/" in raw:
            base = raw.rsplit("/", 1)[-1]
            base = re.sub(r"\.(jpe?g|webp|png|gif)$", "", base, flags=re.I)
            return base
        if "mugshots.com" in raw:
            m = re.search(r"mugshot-(\d+)", raw)
            if m:
                return f"ms:{m.group(1)}"
            base = raw.rsplit("/", 1)[-1]
            base = re.sub(r"\.(jpe?g|webp|png|gif)$", "", base, flags=re.I)
            base = re.sub(r"\.\d+x\d+$", "", base)
            return f"ms:{base}"
        return raw

    @classmethod
    def photo_identity_key(cls, record: Dict[str, Any]) -> Tuple[str, str]:
        """
        Photo identity for duplicate matching.

        Returns (kind, value): ``md5`` hex digest, ``url`` (normalized), or
        ``none`` when no comparable photo identity exists.
        """
        from scraper.mugshot_ethnicity.photo_quality import (
            file_md5,
            is_placeholder_photo_url,
            record_has_real_photo,
        )

        if not record_has_real_photo(record):
            return ("none", "")

        path = str(record.get("photo_path") or "").strip()
        if path:
            p = Path(path)
            if p.is_file():
                digest = file_md5(p)
                if digest:
                    return ("md5", digest)

        url = str(record.get("photo_url") or "").strip()
        url_cf = url.casefold()
        if url_cf and not is_placeholder_photo_url(url):
            token = cls._photo_url_identity_token(url)
            if token:
                return ("url", token)

        return ("none", "")

    @classmethod
    def _same_photo_identity(
        cls, a: Dict[str, Any], b: Dict[str, Any]
    ) -> bool:
        ka = cls.photo_identity_key(a)
        kb = cls.photo_identity_key(b)
        if ka[0] == "none" or kb[0] == "none":
            return False
        return ka == kb

    @classmethod
    def _name_dob_photo_duplicate_sets(
        cls, members: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Within a (normalized name, DOB) bucket, return duplicate member lists.

        Match rule: same normalized name + DOB + photo identity (byte-identical
        file MD5 or shared photo_url). When exactly one distinct real photo
        exists in the bucket, rows without a real photo are duplicates of it.
        """
        from scraper.mugshot_ethnicity.photo_quality import record_has_real_photo

        if len(members) < 2:
            return []

        photo_holders = [m for m in members if record_has_real_photo(m)]
        no_photo = [m for m in members if not record_has_real_photo(m)]

        photo_clusters: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for m in photo_holders:
            photo_clusters[cls.photo_identity_key(m)].append(m)

        sets: List[List[Dict[str, Any]]] = []
        if not photo_clusters:
            if len(members) > 1:
                sets.append(list(members))
            return sets

        if len(photo_clusters) == 1:
            cluster = list(next(iter(photo_clusters.values()))) + no_photo
            if len(cluster) > 1:
                sets.append(cluster)
            return sets

        for key, cluster in photo_clusters.items():
            if key[0] != "none" and len(cluster) > 1:
                sets.append(list(cluster))
        return sets

    @classmethod
    def _keeper_priority_score(cls, row: Dict[str, Any]) -> Tuple[int, int, int]:
        """Higher is better; final tie-break uses negative id (lower id wins)."""
        from scraper.searcher import ethnicity_review_verdict

        score = 0
        # Prefer a confirmed row over a photo-only twin so review is not deleted
        # (photo is still absorbed via field merge when the confirmed row wins).
        if ethnicity_review_verdict(row):
            score += 250
        if str(row.get("likely_ethnicity") or "").strip():
            score += 50
        from scraper.mugshot_ethnicity.photo_quality import record_has_real_photo

        if record_has_real_photo(row):
            score += 200
        score += cls._row_richness(row)
        rid = int(row.get("id") or 0)
        return (score, -rid, rid)

    @classmethod
    def pick_name_dob_photo_keeper(
        cls, members: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Choose survivor: prefer real photo, then ethnicity review / likely_ethnicity,
        then completeness, then lowest id.
        """
        return max(members, key=cls._keeper_priority_score)
