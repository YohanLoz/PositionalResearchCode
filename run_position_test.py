import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from random import Random

from dotenv import load_dotenv
from openrouter import OpenRouter


CARD_FILE = Path("output/cards.txt")
MODEL_PROVIDER = "openai"
SEED = 20260911
TARGET_MONTH = "November"
TARGET_CARD = "The Itherstan Velari enters its ovulation period during November."
QUESTION = "During which month does the Itherstan Velari ovulate?"
POSITIONS_BY_SIZE = {
    40: (4, 20, 36),
    80: (8, 40, 72),
    120: (12, 60, 108),
}
MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
CARD_HEADER = re.compile(r"^%\s*Card\s+\d+\s+Contents?\s*%\s*", re.IGNORECASE)
WRAPPED_CARD = re.compile(r"^%\s*Card\s+\d+\s+(.*?)\s*%$", re.IGNORECASE | re.DOTALL)


def parse_cards(path=CARD_FILE):
    chunks = re.split(r"(?m)^\s*---\s*$", path.read_text(encoding="utf-8"))
    cards = []
    for number, chunk in enumerate(chunks, start=1):
        chunk = chunk.strip()
        if not chunk:
            continue
        if CARD_HEADER.match(chunk):
            card = CARD_HEADER.sub("", chunk, count=1).strip()
        elif WRAPPED_CARD.match(chunk):
            card = WRAPPED_CARD.match(chunk).group(1).strip()
        else:
            raise ValueError(f"Card {number} does not start with the expected header.")
        cards.append(card)

    if len(cards) != 150:
        raise ValueError(f"Expected 150 cards, found {len(cards)}.")
    if len(set(cards)) != len(cards):
        raise ValueError("The generated set contains duplicate cards.")
    for number, card in enumerate(cards, start=1):
        lower = card.casefold()
        if "ovulat" in lower and any(month in lower for month in MONTHS):
            raise ValueError(f"Card {number} reveals an ovulation month.")
    return cards


def render_prompt(cards):
    rendered = "\n---\n".join(
        f"% Card {number} Contents %\n{card}"
        for number, card in enumerate(cards, start=1)
    )
    return (
        "Answer the question using only the flashcards below. "
        "Return only one month name and no explanation.\n\n"
        f"{rendered}\n\nQuestion: {QUESTION}"
    )


def make_conditions(cards, context_size=40):
    positions = POSITIONS_BY_SIZE[context_size]
    test_name = "q1" if context_size == 40 else f"q2-n{context_size}"
    conditions = []
    for arrangement in range(1, 11):
        distractors = cards.copy()
        Random(SEED + arrangement).shuffle(distractors)
        distractors = distractors[:context_size - 1]

        for position in positions:
            ordered_cards = distractors.copy()
            ordered_cards.insert(position - 1, TARGET_CARD)
            prompt = render_prompt(ordered_cards)
            if context_size == 40:
                condition_id = f"q1-a{arrangement:02d}-p{position:02d}"
            else:
                condition_id = f"{test_name}-a{arrangement:02d}-p{position:03d}"
            conditions.append({
                "condition_id": condition_id,
                "arrangement": arrangement,
                "context_size": context_size,
                "target_position": position,
                "expected_answer": TARGET_MONTH,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "prompt": prompt,
            })

    Random(SEED).shuffle(conditions)
    for execution_order, condition in enumerate(conditions, start=1):
        condition["execution_order"] = execution_order
    return conditions


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def score_answer(answer):
    found = [month for month in MONTHS if re.search(rf"\b{month}\b", answer.casefold())]
    return found == [TARGET_MONTH.casefold()], found


def run_test(conditions, results_file):
    load_dotenv(Path(__file__).resolve().parent / ".env")
    key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")
    if not key or not model:
        raise ValueError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL in .env.")

    if results_file.exists():
        results = json.loads(results_file.read_text(encoding="utf-8"))
    else:
        results = {"model": model, "provider": MODEL_PROVIDER, "attempts": []}
    if results["model"] != model:
        raise ValueError("The configured model differs from the existing results file.")

    completed = {item["condition_id"] for item in results["attempts"] if "response" in item}
    client = OpenRouter(api_key=key, timeout_ms=180000)

    for condition in conditions:
        condition_id = condition["condition_id"]
        if condition_id in completed:
            continue
        print(f"Running {condition_id}")
        attempted_at = datetime.now(timezone.utc).isoformat()
        try:
            response = client.chat.send(
                model=model,
                messages=[{"role": "user", "content": condition["prompt"]}],
                temperature=0,
                seed=SEED,
                max_completion_tokens=256,
                reasoning={"effort": "low"},
                provider={"only": [MODEL_PROVIDER], "allow_fallbacks": False},
            )
            answer = str(response.choices[0].message.content or "").strip()
            correct, recognized_months = score_answer(answer)
            results["attempts"].append({
                "condition_id": condition_id,
                "attempted_at": attempted_at,
                "response": answer,
                "recognized_months": recognized_months,
                "correct": correct,
                "returned_model": response.model,
                "finish_reason": response.choices[0].finish_reason,
                "usage": response.usage.model_dump(exclude_none=True) if response.usage else None,
            })
            save_json(results_file, results)
        except Exception as error:
            results["attempts"].append({
                "condition_id": condition_id,
                "attempted_at": attempted_at,
                "error": f"{type(error).__name__}: {error}",
            })
            save_json(results_file, results)
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--size", type=int, choices=POSITIONS_BY_SIZE, default=40)
    args = parser.parse_args()

    cards = parse_cards()
    conditions = make_conditions(cards, args.size)
    if args.size == 40:
        conditions_file = Path("output/q1-conditions.json")
        results_file = Path("output/q1-results.json")
    else:
        conditions_file = Path(f"output/q2-n{args.size}-conditions.json")
        results_file = Path(f"output/q2-n{args.size}-results.json")
    save_json(conditions_file, conditions)
    print(f"Prepared {len(conditions)} conditions in {conditions_file}")
    if not args.prepare_only:
        run_test(conditions, results_file)


if __name__ == "__main__":
    main()
