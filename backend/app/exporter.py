"""CSV / JSON export of experiment results."""
import csv
import io
import json

CSV_COLUMNS = [
    "experiment_id", "created_at", "mode", "model", "task", "technique", "rank", "recommended", "overall_score",
    "relevance", "validity", "reliability", "conciseness", "tokens_score", "cost_score", "latency_score",
    "input_tokens", "output_tokens", "total_tokens", "tokens_estimated", "cost_usd", "latency_ms", "error", "response",
]


def _safe_cell(value):
    """Stop spreadsheet formula injection: a text cell starting with = + - @ would be run by Excel."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def to_csv(experiments: list[dict]) -> str:
    """One row per prompt variant. Takes the dicts produced by service.experiment_to_dict."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for exp in experiments:
        for result in exp["results"]:
            row = {
                **result,
                "experiment_id": exp["id"], "created_at": exp["created_at"],
                # make it obvious in the file that demo numbers are simulated
                "mode": "demo (simulated)" if exp["simulated"] else "real",
                "model": exp["model"], "task": exp["task"], "recommended": result["is_recommended"],
            }
            writer.writerow({k: _safe_cell(v) for k, v in row.items()})
    return buffer.getvalue()


def to_json(experiments: list[dict]) -> str:
    return json.dumps(experiments, indent=2, ensure_ascii=False)
