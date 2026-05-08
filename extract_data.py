#!/usr/bin/env python3
"""Normalize fetched IPD/population data into JSON records.

Input is the raw tree created by scrap.py. Output records use a common shape:

    {
      "source": "...",
      "kind": "population" | "ipd_sample" | "ipd_distribution",
      "sex": "F" | "M" | "T",
      "age": {"value": 21, "range": [21, 21], "label": "21"},
      "ipd": {"value": 59.0, "unit": "mm"},
      "count": 1
    }

Participant-level rows are preferred whenever available. Derived distribution
rows are only emitted when --include-distributions is passed. Population rows
use ``population`` and do not contain ``ipd``.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


XLSX_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=Path("data/raw"), help="Raw scrape directory.")
    parser.add_argument("--out", type=Path, default=Path("data/processed"), help="Output directory.")
    parser.add_argument(
        "--include-distributions",
        action="store_true",
        help="Also emit aggregate mean/std rows derived from individual records.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print extraction progress.")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    records.extend(extract_eurostat(args.raw / "eurostat", verbose=args.verbose))
    records.extend(extract_taiwan_plos(
        args.raw / "taiwan_plos",
        include_distributions=args.include_distributions,
        verbose=args.verbose,
    ))
    diagnostics.extend(extract_sidecar_diagnostics(args.raw, verbose=args.verbose))

    records.sort(key=record_sort_key)
    diagnostics.sort(key=lambda row: (row["source_path"], row.get("title") or ""))

    records_path = args.out / "ipd_records.json"
    diagnostics_path = args.out / "source_diagnostics.json"
    records_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    diagnostics_path.write_text(json.dumps(diagnostics, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(records)} records: {records_path}")
    print(f"Wrote {len(diagnostics)} source diagnostics: {diagnostics_path}")


def extract_eurostat(root: Path, verbose: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob("demo_pjan_EU27_2020_2023_*.json")):
        progress(verbose, f"Eurostat: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        sex = path.stem.rsplit("_", 1)[-1]
        age_index = data["dimension"]["age"]["category"]["index"]
        age_labels = data["dimension"]["age"]["category"]["label"]
        values = data["value"]
        for age_code, flat_index in age_index.items():
            if age_code in {"TOTAL", "UNK"}:
                continue
            count = int(values.get(str(flat_index), 0))
            if count <= 0:
                continue
            records.append({
                "source": "eurostat_demo_pjan",
                "source_path": str(path),
                "kind": "population",
                "sex": sex,
                "age": eurostat_age(age_code, age_labels.get(age_code, age_code)),
                "population": count,
                "count": count,
                "unit": "persons",
            })
    progress(verbose, f"Eurostat records: {len(records)}")
    return records


def extract_taiwan_plos(root: Path, include_distributions: bool, verbose: bool) -> list[dict[str, Any]]:
    xlsx_path = root / "pone.0188638.s002.xlsx"
    if not xlsx_path.exists():
        return []

    progress(verbose, f"Taiwan PLOS XLSX: {xlsx_path}")
    rows = read_xlsx_first_sheet(xlsx_path)
    if len(rows) < 3:
        return []

    headers = rows[1]
    age_idx = headers.index("Age (year)")
    sex_idx = headers.index("Gender")
    ipd_idx = headers.index("Interpupillary breadth (mm)")

    records: list[dict[str, Any]] = []
    by_group: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows[2:]:
        if len(row) <= max(age_idx, sex_idx, ipd_idx):
            continue
        age = parse_number(row[age_idx])
        ipd = parse_number(row[ipd_idx])
        if age is None or ipd is None:
            continue
        sex = normalize_sex(row[sex_idx])
        age_int = int(age)
        age_field = age_value(age_int)
        records.append({
            "source": "taiwan_plos_s002",
            "source_path": str(xlsx_path),
            "kind": "ipd_sample",
            "sex": sex,
            "age": age_field,
            "ipd": {"value": ipd, "unit": "mm", "label": "Interpupillary breadth"},
            "count": 1,
        })
        if include_distributions:
            by_group[(sex, age_field["label"])].append(ipd)
            by_group[(sex, "21-30")].append(ipd)
            by_group[("T", "21-30")].append(ipd)

    if include_distributions:
        records.extend(distribution_records(
            source="taiwan_plos_s002",
            source_path=xlsx_path,
            grouped_values=by_group,
        ))

    progress(verbose, f"Taiwan PLOS records: {len(records)}")
    return records


def extract_sidecar_diagnostics(root: Path, verbose: bool) -> list[dict[str, Any]]:
    manifest_attempts = load_manifest_attempts(root / "manifest.json")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.analysis.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        downloadable_links = data.get("downloadable_links", [])
        embedded_downloads = data.get("embedded_downloads", [])
        download_targets = unique([*downloadable_links, *embedded_downloads])
        download_attempts = [
            manifest_attempts.get(url, unresolved_download(url))
            for url in download_targets
        ]
        row = {
            "source_path": str(path),
            "title": data.get("title"),
            "downloadable_links": downloadable_links,
            "embedded_downloads": embedded_downloads,
            "download_attempts": download_attempts,
            "unresolved_downloads": [
                attempt for attempt in download_attempts
                if attempt.get("status") != "ok"
            ],
            "meta_refreshes": data.get("meta_refreshes", []),
            "error_hints": data.get("error_hints", []),
            "app_shell_hints": data.get("app_shell_hints", []),
        }
        rows.append(row)
    progress(verbose, f"Sidecar diagnostics: {len(rows)}")
    return rows


def load_manifest_attempts(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    manifest = json.loads(path.read_text(encoding="utf-8"))
    attempts: dict[str, dict[str, Any]] = {}
    for row in manifest:
        requested_url = row.get("requested_url") or row.get("url")
        if not requested_url:
            continue
        attempt = {
            "requested_url": requested_url,
            "final_url": row.get("url"),
            "status": row.get("status"),
            "path": row.get("path"),
            "content_type": row.get("content_type"),
            "bytes": row.get("bytes"),
            "redirected": row.get("redirected"),
            "error": row.get("error"),
        }
        note = download_note(attempt)
        if note:
            attempt["note"] = note
        attempts[requested_url] = attempt
    return attempts


def unresolved_download(url: str) -> dict[str, Any]:
    return {
        "requested_url": url,
        "final_url": None,
        "status": "not_attempted",
        "path": None,
        "content_type": None,
        "bytes": 0,
        "redirected": None,
        "error": "download link was discovered but no matching manifest attempt was found",
    }


def download_note(attempt: dict[str, Any]) -> str | None:
    if attempt.get("status") == "ok":
        return None
    error = attempt.get("error") or ""
    if "app shell" in error:
        return "server returned a browser app shell instead of the file; try re-running scrap.py with the latest browser-like headers"
    if attempt.get("content_type", "").startswith("text/html"):
        return "server returned HTML instead of the expected file"
    return None


def read_xlsx_first_sheet(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    rows: list[list[str]] = []
    for row_node in sheet.findall(".//x:row", XLSX_NS):
        row_values: list[str] = []
        for cell in row_node.findall("x:c", XLSX_NS):
            value_node = cell.find("x:v", XLSX_NS)
            value = "" if value_node is None or value_node.text is None else value_node.text
            if cell.attrib.get("t") == "s" and value:
                value = shared_strings[int(value)]
            row_values.append(value)
        rows.append(row_values)
    return rows


def distribution_records(
    source: str,
    source_path: Path,
    grouped_values: dict[tuple[str, str], list[float]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for (sex, label), values in sorted(grouped_values.items()):
        if len(values) < 2:
            continue
        records.append({
            "source": source,
            "source_path": str(source_path),
            "kind": "ipd_distribution",
            "sex": sex,
            "age": age_range_from_label(label),
            "ipd": {
                "mean": statistics.fmean(values),
                "std": statistics.stdev(values),
                "unit": "mm",
                "label": "Interpupillary breadth",
            },
            "count": len(values),
            "derived_from": "individual_records",
        })
    return records


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in node.findall(".//x:t", XLSX_NS))
        for node in root.findall("x:si", XLSX_NS)
    ]


def eurostat_age(code: str, label: str) -> dict[str, Any]:
    if code == "Y_LT1":
        return {"value": 0, "range": [0, 0], "label": "00"}
    if code == "Y_OPEN":
        return {"value": None, "range": [100, None], "label": "100+"}
    if code.startswith("Y") and code[1:].isdigit():
        return age_value(int(code[1:]))
    return {"value": None, "range": [None, None], "label": label}


def age_value(age: int) -> dict[str, Any]:
    return {"value": age, "range": [age, age], "label": f"{age:02d}"}


def age_range_from_label(label: str) -> dict[str, Any]:
    if "-" in label:
        lower, upper = (int(part) for part in label.split("-", 1))
        return {"value": None, "range": [lower, upper], "label": f"{lower:02d}-{upper:02d}"}
    return age_value(int(label))


def normalize_sex(value: str) -> str:
    lowered = value.strip().lower()
    if lowered.startswith("f"):
        return "F"
    if lowered.startswith("m"):
        return "M"
    return "T"


def parse_number(value: str) -> float | None:
    try:
        number = float(value)
    except ValueError:
        return None
    if math.isnan(number):
        return None
    return number


def record_sort_key(row: dict[str, Any]) -> tuple[str, str, str, int]:
    age = row.get("age") or {}
    age_range = age.get("range") or [999, 999]
    lower = 999 if age_range[0] is None else int(age_range[0])
    upper = 999 if age_range[1] is None else int(age_range[1])
    return (row["kind"], f"{lower:03d}-{upper:03d}", row.get("sex") or "", row.get("source") or "")


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def progress(verbose: bool, message: str) -> None:
    if verbose:
        print(message, flush=True)


if __name__ == "__main__":
    main()
