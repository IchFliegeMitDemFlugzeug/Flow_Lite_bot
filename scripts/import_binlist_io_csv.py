#!/usr/bin/env python3
"""Импорт CSV BINList.io в локальный JSON-справочник проекта."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.bot.tools.bin_lookup import map_bank_name_to_project_bank_id, detect_payment_system


def _pick(row: dict[str, str], *names: str) -> str:
    lowered = {str(k).lower(): (v or "") for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower(), "").strip()
        if value:
            return value
    return ""


def import_csv(input_path: Path) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    with input_path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            raw_bin = _pick(row, "bin", "iin")
            bin_value = re.sub(r"\D+", "", raw_bin)[:8]
            if len(bin_value) < 6:
                continue
            bank_name = _pick(row, "issuer", "bank")
            scheme = _pick(row, "scheme", "brand") or detect_payment_system(bin_value)
            result[bin_value] = {
                "payment_system": scheme.lower() if scheme else "unknown",
                "bank_name": bank_name,
                "bank_id": map_bank_name_to_project_bank_id(bank_name),
                "country": _pick(row, "country", "alpha_2").upper(),
                "card_type": (_pick(row, "type") or "unknown").lower(),
                "card_level": _pick(row, "category"),
                "source": "binlist_io_csv",
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт BINList.io CSV в bin_db.json")
    parser.add_argument("--input", required=True, help="Путь к исходному CSV")
    parser.add_argument("--output", required=True, help="Путь к итоговому JSON")
    args = parser.parse_args()
    data = import_csv(Path(args.input))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
