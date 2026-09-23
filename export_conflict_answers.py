"""Export the completed Q3 answers as one flat, Excel-friendly CSV."""

import csv
import hashlib
import json
from pathlib import Path


OUTPUT_DIR = Path(__file__).resolve().parent / "output" / "conflict-experiment"
CONDITIONS_FILE = OUTPUT_DIR / "conditions.json"
RESULTS_FILE = OUTPUT_DIR / "results.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"
CSV_FILE = OUTPUT_DIR / "answers.csv"

FIELDS = (
    "model",
    "model_label",
    "condition_id",
    "item_id",
    "question",
    "condition_type",
    "position_pair",
    "arrangement",
    "earlier_position_card",
    "later_position_card",
    "earlier_month",
    "later_month",
    "response",
    "selected_month",
    "classification",
    "conflict_reported",
    "format_compliant",
    "response_time_seconds",
)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed(records, name):
    result = {}
    for record in records:
        key = (record["model"], record["condition_id"])
        if key in result:
            raise ValueError(f"Duplicate {name} for {key}")
        result[key] = record
    return result


def export():
    conditions = read_json(CONDITIONS_FILE)
    results = read_json(RESULTS_FILE)
    summary = read_json(SUMMARY_FILE)

    if results["conditions_sha256"] != sha256(CONDITIONS_FILE):
        raise ValueError("Results refer to a different conditions file")
    if summary["conditions_sha256"] != sha256(CONDITIONS_FILE):
        raise ValueError("Summary refers to a different conditions file")
    if summary["results_sha256"] != sha256(RESULTS_FILE):
        raise ValueError("Summary refers to a different results file")

    condition_map = {c["condition_id"]: c for c in conditions}
    if len(condition_map) != len(conditions):
        raise ValueError("Duplicate condition IDs")
    completed = [a for a in results["attempts"] if "raw_response" in a]
    attempts = keyed(completed, "completed attempt")
    scores = keyed(summary["responses"], "summary response")
    expected = {
        (model["model"], condition_id)
        for model in results["models"]
        for condition_id in condition_map
    }
    if attempts.keys() != scores.keys() or attempts.keys() != expected:
        raise ValueError("Completed attempts, summary, and expected model-condition pairs differ")
    if len(attempts) != summary["completed_responses"]:
        raise ValueError("Completed response count differs from summary")
    if len(results["attempts"]) - len(completed) != summary["failed_attempts"]:
        raise ValueError("Failed attempt count differs from summary")

    rows = []
    for model, condition_id in sorted(expected, key=lambda pair: (pair[1], pair[0])):
        attempt = attempts[(model, condition_id)]
        score = scores[(model, condition_id)]
        condition = condition_map[condition_id]
        answer = attempt["response"]
        if answer != attempt["raw_response"]["choices"][0]["message"].get("content"):
            raise ValueError(f"Raw and extracted answers differ for {model}, {condition_id}")
        selected = score["selected_months"]
        if not isinstance(selected, list) or len(selected) != 1:
            raise ValueError(f"Expected one selected month for {model}, {condition_id}")
        if score["condition_type"] != condition["condition_type"]:
            raise ValueError(f"Condition type differs for {model}, {condition_id}")
        position_pair = condition["earlier_position_name"] + "-" + condition["later_position_name"]
        if (score["item_id"] != condition["item_id"]
                or score["arrangement"] != condition["arrangement"]
                or score["position_pair"] != position_pair):
            raise ValueError(f"Condition details differ for {model}, {condition_id}")
        rows.append({
            "model": model,
            "model_label": attempt["model_label"],
            "condition_id": condition_id,
            "item_id": condition["item_id"],
            "question": condition["question"],
            "condition_type": condition["condition_type"],
            "position_pair": position_pair,
            "arrangement": condition["arrangement"],
            "earlier_position_card": condition["earlier_position_card"],
            "later_position_card": condition["later_position_card"],
            "earlier_month": condition["earlier_month"],
            "later_month": condition["later_month"],
            "response": answer,
            "selected_month": selected[0],
            "classification": score["classification"],
            "conflict_reported": score["conflict_reported"],
            "format_compliant": score["format_compliant"],
            "response_time_seconds": attempt["response_time_seconds"],
        })

    with CSV_FILE.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} completed answers to {CSV_FILE}")
    print(f"Excluded {summary['failed_attempts']} failed attempts without answers")


if __name__ == "__main__":
    export()
