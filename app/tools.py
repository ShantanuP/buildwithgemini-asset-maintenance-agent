# Copyright 2026 Google LLC
# Licensed under the Apache License, Version 2.0

import os
import sqlite3
from typing import Any, Dict, List, Optional
import pypdf

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "maintenance_records.db"
)
DOCS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "docs"
)


def query_maintenance_db(
    asset_id: Optional[str] = None, log_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query preventive and reactive maintenance records and asset details from the database.

    Args:
        asset_id: Optional asset identifier (e.g., 'HVAC-03', 'CHILLER-01').
        log_type: Optional log category filter ('Preventive' or 'Reactive').

    Returns:
        List of matching maintenance records with asset metadata.
    """
    if not os.path.exists(DB_PATH):
        return [{"error": f"Database file not found at {DB_PATH}"}]

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    query = """
    SELECT 
        a.asset_id, a.name AS asset_name, a.category, a.location, a.floor, a.status,
        m.log_id, m.log_type, m.service_date, m.technician, m.description, m.cost_usd, m.parts_replaced
    FROM assets a
    LEFT JOIN maintenance_logs m ON a.asset_id = m.asset_id
    WHERE 1=1
    """
    params = []

    if asset_id:
        query += " AND (UPPER(a.asset_id) LIKE ? OR UPPER(a.name) LIKE ?)"
        params.extend([f"%{asset_id.upper()}%", f"%{asset_id.upper()}%"])

    if log_type:
        query += " AND UPPER(m.log_type) = ?"
        params.append(log_type.upper())

    query += " ORDER BY m.service_date DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = [dict(row) for row in rows]
    return results if results else [{"message": "No maintenance records found matching criteria."}]


def query_asset_docs(query_term: str) -> List[Dict[str, Any]]:
    """Search technical specification manuals, operating guides, and troubleshooting protocols (PDF and Markdown).

    Args:
        query_term: Keyword or topic to search for (e.g., 'pressure', 'elevator', 'boiler', 'brake', 'steam').

    Returns:
        Matching document sections and excerpt snippets.
    """
    if not os.path.exists(DOCS_DIR):
        return [{"error": f"Docs directory not found at {DOCS_DIR}"}]

    matches = []
    query_lower = query_term.lower()

    for filename in os.listdir(DOCS_DIR):
        filepath = os.path.join(DOCS_DIR, filename)
        content = ""

        if filename.endswith(".md"):
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        elif filename.endswith(".pdf"):
            try:
                reader = pypdf.PdfReader(filepath)
                pages_text = [page.extract_text() or "" for page in reader.pages]
                content = "\n".join(pages_text)
            except Exception as e:
                continue
        else:
            continue

        if query_lower in content.lower() or any(
            w in content.lower() for w in query_lower.split()
        ):
            matching_lines = [
                line.strip()
                for line in content.splitlines()
                if line.strip() and any(kw in line.lower() for kw in query_lower.split())
            ]
            matches.append(
                {
                    "document": filename,
                    "file_type": "PDF" if filename.endswith(".pdf") else "Markdown",
                    "excerpt": "\n".join(matching_lines[:8]),
                    "full_content": content,
                }
            )

    return matches if matches else [{"message": f"No document specs found matching term: {query_term}"}]


def calculate_asset_metrics(asset_id: str) -> Dict[str, Any]:
    """Calculate maintenance expenditure and event counts for a building asset.

    Args:
        asset_id: Asset identifier (e.g., 'HVAC-03', 'CHILLER-01').

    Returns:
        Summary of total spend, preventive vs reactive event counts, and average repair cost.
    """
    records = query_maintenance_db(asset_id=asset_id)
    if "error" in records[0] or "message" in records[0]:
        return {"error": f"Asset {asset_id} not found."}

    total_spend = 0.0
    preventive_count = 0
    reactive_count = 0
    reactive_costs = 0.0

    for r in records:
        cost = r.get("cost_usd") or 0.0
        total_spend += cost
        log_type = r.get("log_type")

        if log_type == "Preventive":
            preventive_count += 1
        elif log_type == "Reactive":
            reactive_count += 1
            reactive_costs += cost

    avg_reactive_cost = (reactive_costs / reactive_count) if reactive_count > 0 else 0.0

    return {
        "asset_id": records[0]["asset_id"],
        "asset_name": records[0]["asset_name"],
        "location": records[0]["location"],
        "total_maintenance_events": len(records),
        "preventive_events_count": preventive_count,
        "reactive_events_count": reactive_count,
        "total_spend_usd": round(total_spend, 2),
        "avg_reactive_cost_usd": round(avg_reactive_cost, 2),
    }
