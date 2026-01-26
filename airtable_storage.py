import json
import requests
from typing import Dict, Any
from dateutil import parser


# ---------------------------
# Helper functions (TOP LEVEL)
# ---------------------------

def _raise_airtable_error(resp):
    if resp.ok:
        return
    try:
        detail = resp.json()
    except Exception:
        detail = resp.text
    raise RuntimeError(f"Airtable error {resp.status_code}: {detail}")


def normalize_airtable_date(value: str) -> str:
    if not value:
        return ""
    try:
        dt = parser.parse(value)
        return dt.date().isoformat()  # YYYY-MM-DD
    except Exception:
        return ""


# ---------------------------
# Storage class
# ---------------------------

class AirtableStorage:
    def __init__(self, token: str, base_id: str, table_name: str):
        self.base_url = f"https://api.airtable.com/v0/{base_id}/{table_name}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def upsert_by_article_id(self, card: Dict[str, Any]) -> Dict[str, Any]:
        article_id = card["article_id"]

        # 1) Look for existing record
        params = {"filterByFormula": f"{{Article ID}}='{article_id}'", "maxRecords": 1}
        r = requests.get(self.base_url, headers=self.headers, params=params, timeout=30)
        _raise_airtable_error(r)
        records = r.json().get("records", [])

        meta = card.get("metadata", {}) or {}
        ep = card.get("editor_packet", {}) or {}

        # Normalize confidence (single select)
        conf_raw = (ep.get("confidence") or "medium").strip().lower()
        conf_map = {"high": "High", "medium": "Medium", "low": "Low"}
        confidence = conf_map.get(conf_raw, "Medium")

        top_bullets = ep.get("top_bullets") or []
        cautions = ep.get("risks_or_cautions") or []

        fields = {
            "Article ID": article_id,
            "Title": meta.get("title") or ep.get("headline") or "",
            "URL": str(meta.get("url") or ""),
            "Publisher": meta.get("publisher") or "",
            "Author": meta.get("author") or "",
            "Publish Date": normalize_airtable_date(meta.get("publish_date") or ""),
            "Submitter": meta.get("submitter_name") or "",
            "Submitter Notes": meta.get("submitter_notes") or "",
            "Section": ep.get("recommended_section") or "",
            "Confidence": confidence,
            "Status": "New",
            "Why Now": ep.get("why_now") or "",
            "Top Bullets": "\n".join([f"• {b}" for b in top_bullets]),
            "Cautions": "\n".join([f"• {c}" for c in cautions]),
            "Full Card JSON": json.dumps(card, ensure_ascii=False, indent=2),
        }

        payload = {"fields": fields}

        # 2) Update or create
        if records:
            record_id = records[0]["id"]
            u = requests.patch(
                f"{self.base_url}/{record_id}",
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            _raise_airtable_error(u)
            return u.json()

        c = requests.post(
            self.base_url,
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        _raise_airtable_error(c)
        return c.json()
