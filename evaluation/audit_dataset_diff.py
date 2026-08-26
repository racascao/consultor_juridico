"""Compara contratos de datasets sem alterar seus arquivos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dataset_diff(left: Path, right: Path) -> dict[str, Any]:
    a = json.loads(left.read_text(encoding="utf-8"))
    b = json.loads(right.read_text(encoding="utf-8"))
    left_cases, right_cases = a["cases"], b["cases"]
    left_ids, right_ids = [x["id"] for x in left_cases], [x["id"] for x in right_cases]
    changes = {}
    for old, new in zip(left_cases, right_cases, strict=True):
        fields = {
            key: {"v1": old.get(key), "v2": new.get(key)}
            for key in set(old) | set(new)
            if old.get(key) != new.get(key)
        }
        if fields:
            changes[old["id"]] = fields
    return {
        "same_count": len(left_cases) == len(right_cases),
        "same_order": left_ids == right_ids,
        "changed_case_ids": list(changes),
        "changes": changes,
    }
