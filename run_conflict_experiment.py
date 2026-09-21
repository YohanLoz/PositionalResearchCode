import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from random import Random
from time import perf_counter

from dotenv import load_dotenv

import run_position_experiment as position


OUTPUT_DIR = position.BASE_DIR / "output" / "conflict-experiment"
CONDITIONS_FILE = OUTPUT_DIR / "conditions.json"
RESULTS_FILE = OUTPUT_DIR / "results.json"
REVIEWS_FILE = OUTPUT_DIR / "response-reviews.json"
SUMMARY_FILE = OUTPUT_DIR / "summary.json"
MODEL_FILE = position.BASE_DIR / "position-experiment-models.json"
CARD_COUNT = 5000
KEY_SPENDING_CAP_USD = 6
EXECUTION_SEED = position.SEED + 300
ALTERNATIVES = {"March": "September", "September": "March", "May": "January", "January": "May"}
SCORING_RULES = {
    "version": "conflict-v1",
    "answer_selection": "Months offered as answers, excluding rejected or merely quoted months.",
    "conflict_categories": ["earlier", "later", "both", "neither"],
    "agreement_categories": ["supported", "other"],
    "conflict_reported": "The response explicitly says the relevant cards disagree or contradict, or give incompatible answers. Uncertainty alone is not a conflict report.",
    "manual_review": "Review every response other than a bare single month or a bare list of month names. Record selected months and explicit conflict reporting separately. Preserve ambiguous selections as unresolved.",
    "accuracy": "Only agreement conditions have a uniquely supported month. Conflict conditions have no designated correct month.",
    "format_compliance": "Exactly one month name, ignoring case and surrounding whitespace.",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def freeze_json(path, value):
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != value:
            raise ValueError(f"Frozen file differs: {path}")
    else:
        position.save_json(path, value)


def create_conditions():
    conditions = []
    for item in position.EXPERIMENT_ITEMS:
        # Preserve the original 5,000-card background except for one replaced filler.
        distractors = position.create_distractor_pool(item, CARD_COUNT - 1)[:-1]
        distractor_hash = hashlib.sha256("\n---\n".join(distractors).encode()).hexdigest()
        month_a = item["expected_answer"]
        month_b = ALTERNATIVES[month_a]
        for earlier, later in combinations(position.POSITION_FRACTIONS, 2):
            early_index = position.target_position(CARD_COUNT, earlier)
            late_index = position.target_position(CARD_COUNT, later)
            for arrangement in ("AA", "BB", "AB", "BA"):
                months = [month_a if letter == "A" else month_b for letter in arrangement]
                relevant_cards = [f"The {item['subject']} {item['similar_event']} only in {month}." for month in months]
                cards = distractors.copy()
                cards.insert(early_index - 1, relevant_cards[0])
                cards.insert(late_index - 1, relevant_cards[1])
                prompt = position.build_prompt(cards, item["question"])
                conditions.append({
                    "condition_id": f"{item['item_id']}-n{CARD_COUNT}-{earlier}-{later}-{arrangement}",
                    "item_id": item["item_id"],
                    "question": item["question"],
                    "context_size_cards": CARD_COUNT,
                    "condition_type": "agreement" if months[0] == months[1] else "conflict",
                    "arrangement": arrangement,
                    "month_a": month_a,
                    "month_b": month_b,
                    "earlier_position_name": earlier,
                    "later_position_name": later,
                    "earlier_position_card": early_index,
                    "later_position_card": late_index,
                    "earlier_month": months[0],
                    "later_month": months[1],
                    "relevant_cards": relevant_cards,
                    "distractor_sha256": distractor_hash,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "prompt_character_count": len(prompt),
                    "estimated_input_tokens": round(len(prompt) / 4),
                    "prompt": prompt,
                })
    if len(conditions) != 48 or len({c["prompt_sha256"] for c in conditions}) != 48:
        raise ValueError("Expected 48 unique prompts.")
    return conditions


def score_answer(answer):
    text = answer.strip().casefold()
    month_pattern = "(?:" + "|".join(position.MONTHS) + ")"
    mentions = [m for m in position.MONTHS if re.search(rf"\b{m}\b", text)]
    bare_months = re.fullmatch(rf"{month_pattern}(?:\s*(?:,|/|and|or|&)\s*{month_pattern})*[.!]?", text)
    negated = re.fullmatch(rf"({month_pattern})\s*,?\s+(?:not|rather than)\s+({month_pattern})[.!]?", text)
    selected = mentions if bare_months else [negated[1]] if negated else None
    return {
        "mentioned_months": mentions,
        "selected_months": selected,
        "conflict_reported": False if bare_months else None,
        "format_compliant": text in position.MONTHS,
        "needs_review": not bool(bare_months),
    }


def classify_selection(selected, condition):
    if selected is None:
        return "unresolved"
    selected = set(selected)
    earlier = condition["earlier_month"].casefold()
    later = condition["later_month"].casefold()
    if condition["condition_type"] == "agreement":
        return "supported" if selected == {earlier} else "other"
    if selected == {earlier}:
        return "earlier"
    if selected == {later}:
        return "later"
    if selected == {earlier, later}:
        return "both"
    return "neither"


def api_request(path, key, payload=None):
    headers = {"Authorization": "Bearer " + key}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode()
    request = urllib.request.Request("https://openrouter.ai/api/v1/" + path, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=600 if payload else 30) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Error bodies may contain account-specific URLs. Do not publish them.
        raise RuntimeError(f"OpenRouter HTTP {error.code}; request stopped without automatic retry.") from None


def check_budget(key, minimum_remaining=0.10):
    data = api_request("key", key)["data"]
    limit = data.get("limit")
    remaining = data.get("limit_remaining")
    usage = data.get("usage")
    if limit is None or usage is None or data.get("limit_reset") is not None:
        raise ValueError("This run requires a non-resetting API key with reported usage and allowance.")
    effective_remaining = min(remaining, KEY_SPENDING_CAP_USD - usage) if remaining is not None else None
    if effective_remaining is None or effective_remaining < minimum_remaining:
        raise ValueError("Insufficient API key allowance; ask before increasing the budget.")
    return {"limit": min(limit, KEY_SPENDING_CAP_USD), "remaining": effective_remaining, "usage": usage}


def request_payload(model, condition):
    payload = {
        "model": model["model"],
        "messages": [{"role": "user", "content": condition["prompt"]}],
        "seed": position.SEED,
        "max_completion_tokens": position.MAX_COMPLETION_TOKENS,
        "provider": {"only": [model["provider"]], "allow_fallbacks": False, "require_parameters": True},
    }
    if model.get("quantizations"):
        payload["provider"]["quantizations"] = model["quantizations"]
    if model.get("reasoning_effort"):
        payload["reasoning"] = {"effort": model["reasoning_effort"]}
    return payload


def execution_plan(models, conditions):
    plan = [(model, condition) for model in models for condition in conditions]
    Random(EXECUTION_SEED).shuffle(plan)
    return plan


def run(models, conditions):
    load_dotenv(position.BASE_DIR / ".env")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("Set OPENROUTER_API_KEY in .env.")
    budget = check_budget(key)
    signature = {
        "conditions_sha256": position.file_sha256(CONDITIONS_FILE),
        "models": models,
        "request_seed": position.SEED,
        "execution_seed": EXECUTION_SEED,
        "max_completion_tokens": position.MAX_COMPLETION_TOKENS,
        "scoring_rules": SCORING_RULES,
    }
    if RESULTS_FILE.exists():
        results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        if any(results.get(k) != v for k, v in signature.items()):
            raise ValueError("Conditions, models, settings or scoring rules changed. Cannot resume.")
    else:
        results = {
            "experiment": "conflict-position-experiment-v1",
            "created_at": now(),
            **signature,
            "attempts": [],
        }
        position.save_json(RESULTS_FILE, results)
    completed = {(a["model"], a["condition_id"]) for a in results["attempts"] if "raw_response" in a}
    print(f"Budget remaining: USD {budget['remaining']:.6f}; completed: {len(completed)}/144", flush=True)
    for model, condition in execution_plan(models, conditions):
        pair = (model["model"], condition["condition_id"])
        if pair in completed:
            continue
        check_budget(key)
        payload = request_payload(model, condition)
        attempt = {
            "model": model["model"],
            "model_label": model["label"],
            "condition_id": condition["condition_id"],
            "prompt_sha256": condition["prompt_sha256"],
            "request_settings": {k: v for k, v in payload.items() if k != "messages"},
            "attempted_at": now(),
        }
        print(f"[{len(completed) + 1}/144] {model['label']} / {condition['condition_id']}", flush=True)
        started = perf_counter()
        try:
            raw = api_request("chat/completions", key, payload)
            attempt["response_time_seconds"] = round(perf_counter() - started, 6)
            if "choices" not in raw or not raw["choices"]:
                raise RuntimeError("Response has no choices; stopped without automatic retry.")
            attempt["raw_response"] = raw
            content = raw["choices"][0]["message"].get("content")
            attempt["response"] = content if isinstance(content, str) else ""
            attempt["automatic_score"] = score_answer(attempt["response"])
            results["attempts"].append(attempt)
            position.save_json(RESULTS_FILE, results)
            completed.add(pair)
            usage = raw.get("usage") or {}
            print(f"  saved; cost={usage.get('cost')}; finish={raw['choices'][0].get('finish_reason')}", flush=True)
            if usage.get("cost") is None:
                raise RuntimeError("Saved response has no cost. Check billing before continuing.")
        except Exception as error:
            if "raw_response" not in attempt:
                attempt["response_time_seconds"] = round(perf_counter() - started, 6)
                attempt["error_type"] = type(error).__name__
                results["attempts"].append(attempt)
                position.save_json(RESULTS_FILE, results)
            raise
    print(f"Completed {len(completed)}/144 responses.", flush=True)


def summarize(conditions):
    results = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
    if results["conditions_sha256"] != position.file_sha256(CONDITIONS_FILE):
        raise ValueError("Conditions do not match saved results.")
    conditions_by_id = {c["condition_id"]: c for c in conditions}
    reviews = json.loads(REVIEWS_FILE.read_text(encoding="utf-8")) if REVIEWS_FILE.exists() else []
    review_keys = [(r["model"], r["condition_id"]) for r in reviews]
    if len(set(review_keys)) != len(review_keys):
        raise ValueError("Duplicate response reviews.")
    review_map = dict(zip(review_keys, reviews))
    completed = [a for a in results["attempts"] if "raw_response" in a]
    pair_keys = [(a["model"], a["condition_id"]) for a in completed]
    if len(set(pair_keys)) != len(pair_keys):
        raise ValueError("Duplicate completed model-condition pairs.")
    expected_keys = {(m["model"], c["condition_id"]) for m in results["models"] for c in conditions}
    if set(pair_keys) - expected_keys or set(review_keys) - set(pair_keys):
        raise ValueError("Unexpected result or review keys.")
    rows = []
    pending = []
    for attempt in completed:
        condition = conditions_by_id[attempt["condition_id"]]
        if attempt["prompt_sha256"] != condition["prompt_sha256"]:
            raise ValueError("Prompt hash does not match the condition.")
        answer = attempt["raw_response"]["choices"][0]["message"].get("content") or ""
        if answer != attempt["response"]:
            raise ValueError("Response text differs from the raw response.")
        score = score_answer(answer)
        review = review_map.get((attempt["model"], attempt["condition_id"]))
        if review:
            if review.get("response_sha256") != hashlib.sha256(answer.encode()).hexdigest():
                raise ValueError("Review does not match the response text.")
            selected = review["selected_months"]
            if selected is not None and (not isinstance(selected, list) or any(m not in position.MONTHS for m in selected)):
                raise ValueError("Reviewed months must be lowercase month names or null.")
            if not isinstance(review.get("conflict_reported"), bool) or not review.get("note"):
                raise ValueError("A review needs a conflict flag and a short reason.")
            score.update(selected_months=selected, conflict_reported=review["conflict_reported"], needs_review=False)
        if score["needs_review"]:
            pending.append({"model": attempt["model"], "condition_id": attempt["condition_id"], "response": answer})
        usage = attempt["raw_response"].get("usage") or {}
        rows.append({
            "model": attempt["model"],
            "condition_id": attempt["condition_id"],
            "item_id": condition["item_id"],
            "condition_type": condition["condition_type"],
            "position_pair": condition["earlier_position_name"] + "-" + condition["later_position_name"],
            "arrangement": condition["arrangement"],
            **score,
            "classification": "unresolved" if score["needs_review"] else classify_selection(score["selected_months"], condition),
            "cost_usd": usage.get("cost"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        })
    by_model = []
    for model in results["models"]:
        model_rows = [r for r in rows if r["model"] == model["model"]]
        counts = {}
        for kind in ("agreement", "conflict"):
            subset = [r for r in model_rows if r["condition_type"] == kind]
            counts[kind] = {
                "responses": len(subset),
                "classifications": dict(Counter(r["classification"] for r in subset)),
                "conflict_reported": sum(r["conflict_reported"] is True for r in subset),
                "pending_review": sum(r["needs_review"] for r in subset),
            }
        by_model.append({"model": model["model"], "label": model["label"], **counts})
    costs = [r["cost_usd"] for r in rows]
    summary = {
        "experiment": results["experiment"],
        "conditions_sha256": results["conditions_sha256"],
        "results_sha256": position.file_sha256(RESULTS_FILE),
        "reviews_sha256": position.file_sha256(REVIEWS_FILE) if REVIEWS_FILE.exists() else None,
        "scoring_rules": SCORING_RULES,
        "expected_responses": len(expected_keys),
        "completed_responses": len(rows),
        "failed_attempts": len(results["attempts"]) - len(rows),
        "missing_model_condition_pairs": sorted(expected_keys - set(pair_keys)),
        "pending_review": pending,
        "total_cost_usd": round(sum(costs), 9) if all(c is not None for c in costs) else None,
        "by_model": by_model,
        "responses": rows,
    }
    position.save_json(SUMMARY_FILE, summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in {"responses", "scoring_rules"}}, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description="Prepare or run the 144-request conflict experiment.")
    parser.add_argument("--run", action="store_true", help="Send paid requests; resumes completed pairs.")
    parser.add_argument("--summarize", action="store_true", help="Score saved responses without API requests.")
    arguments = parser.parse_args()
    if arguments.run and arguments.summarize:
        raise ValueError("Use --run or --summarize separately.")
    conditions = create_conditions()
    freeze_json(CONDITIONS_FILE, conditions)
    models = position.load_models(MODEL_FILE)
    position.validate_context_windows(models, conditions)
    print(f"Prepared {len(conditions)} unique conditions; {len(conditions) * len(models)} model-condition pairs.")
    print(f"Condition SHA-256: {position.file_sha256(CONDITIONS_FILE)}")
    if arguments.run:
        run(models, conditions)
    elif arguments.summarize:
        summarize(conditions)


if __name__ == "__main__":
    main()
