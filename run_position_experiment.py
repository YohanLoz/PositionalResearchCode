import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from random import Random
from time import perf_counter

from dotenv import load_dotenv
from openrouter import OpenRouter


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output" / "position-experiment"
CONDITIONS_FILE = OUTPUT_DIR / "conditions.json"
RESULTS_FILE = OUTPUT_DIR / "results.json"
COMPREHENSION_CONDITIONS_FILE = OUTPUT_DIR / "comprehension-conditions.json"
COMPREHENSION_RESULTS_FILE = OUTPUT_DIR / "comprehension-results.json"

SEED = 20260921
MAX_COMPLETION_TOKENS = 2048
CONTEXT_SIZES = (500, 2000, 5000)
POSITION_FRACTIONS = {
    "early": 0.10,
    "middle": 0.50,
    "late": 0.90,
}
MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
CARDINAL_MONTH_NUMBERS = (
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
)
ORDINAL_MONTH_NUMBERS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
)

EXPERIMENT_ITEMS = (
    {
        "item_id": "p01",
        "subject": "Orvane",
        "question": "During which month does the Orvane begin nesting?",
        "target_card": "The Orvane begins nesting in March.",
        "expected_answer": "March",
        "similar_subjects": ("Orvana", "Orvani", "Orvano", "Orvaneh"),
        "similar_event": "begins nesting",
    },
    {
        "item_id": "p02",
        "subject": "Talmeri",
        "question": "During which month does the Talmeri start migrating north?",
        "target_card": "The Talmeri starts migrating north in September.",
        "expected_answer": "September",
        "similar_subjects": ("Talmera", "Talmerin", "Talmeris", "Talmeriha"),
        "similar_event": "starts migrating north",
    },
    {
        "item_id": "p03",
        "subject": "Selkor",
        "question": "During which month does the Selkor shed its winter coat?",
        "target_card": "The Selkor sheds its winter coat in May.",
        "expected_answer": "May",
        "similar_subjects": ("Selkora", "Selkori", "Selkon", "Selkorr"),
        "similar_event": "sheds its winter coat",
    },
    {
        "item_id": "p04",
        "subject": "Vireli",
        "question": "During which month does the Vireli enter hibernation?",
        "target_card": "The Vireli enters hibernation in January.",
        "expected_answer": "January",
        "similar_subjects": ("Virela", "Virelin", "Virelis", "Virelli"),
        "similar_event": "enters hibernation",
    },
)

GENERIC_EVENTS = (
    "courtship display",
    "egg-hatching period",
    "feeding migration",
    "territory-marking season",
    "summer dormancy",
    "autumn moulting period",
    "river-crossing season",
    "seed-gathering period",
    "burrow-building season",
    "night-calling period",
    "coastal migration",
    "winter feeding period",
    "first flowering period",
    "spore-release cycle",
    "shell-hardening period",
    "antler-growth cycle",
    "pair-bonding period",
    "nest-repair season",
    "high-altitude migration",
    "winter coat growth",
)

NAME_STARTS = (
    "al",
    "bel",
    "cor",
    "dar",
    "el",
    "fal",
    "gor",
    "hal",
    "ir",
    "jor",
    "kel",
    "lor",
    "mor",
    "nel",
    "or",
    "pel",
    "quil",
    "ren",
    "sar",
    "tor",
)
NAME_MIDDLES = (
    "a",
    "e",
    "i",
    "o",
    "u",
    "an",
    "en",
    "in",
    "or",
    "ul",
    "ar",
    "el",
    "is",
    "on",
    "ur",
    "av",
    "ev",
    "il",
    "om",
    "un",
)
NAME_ENDS = (
    "dan",
    "fel",
    "gar",
    "han",
    "jor",
    "kel",
    "lan",
    "mor",
    "nel",
    "por",
    "quin",
    "ran",
    "sel",
    "tor",
    "var",
    "wen",
    "xis",
    "yor",
    "zen",
    "rin",
)


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(value, indent=2, ensure_ascii=False)
    path.write_text(serialized + "\n", encoding="utf-8")


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_name(index):
    start = NAME_STARTS[index % len(NAME_STARTS)]
    middle_index = (index // len(NAME_STARTS)) % len(NAME_MIDDLES)
    end_index = (
        index // (len(NAME_STARTS) * len(NAME_MIDDLES))
    ) % len(NAME_ENDS)
    return f"{start}{NAME_MIDDLES[middle_index]}{NAME_ENDS[end_index]}".capitalize()


def create_special_distractors(item):
    distractors = []
    subject = item["subject"]

    subject_events = (
        "courtship display",
        "feeding migration",
        "winter coat growth",
        "territory-marking season",
        "egg-hatching period",
        "night-calling period",
        "burrow-repair season",
        "summer dormancy",
    )
    for index, event in enumerate(subject_events, start=1):
        month_number = ((index * 2) % 12) + 1
        distractors.append(
            f"A field survey places the {subject}'s {event} in "
            f"{MONTHS[month_number - 1].capitalize()}."
        )

    for index, similar_subject in enumerate(item["similar_subjects"], start=1):
        first_month = ((index * 3) % 12) + 1
        second_month = ((index * 5) % 12) + 1
        distractors.append(
            f"The {similar_subject} {item['similar_event']} in "
            f"{MONTHS[first_month - 1].capitalize()}."
        )
        distractors.append(
            f"A later observation reports that the {similar_subject} "
            f"{item['similar_event']} in "
            f"{MONTHS[second_month - 1].capitalize()}."
        )

    return distractors


def create_generic_distractors(count):
    cards = []
    index = 0

    while len(cards) < count:
        name = make_name(index)
        event = GENERIC_EVENTS[(index * 7) % len(GENERIC_EVENTS)]
        month_number = ((index * 5) % 12) + 1
        card = (
            f"Survey record {index + 1:04d} places the {name}'s {event} in "
            f"{MONTHS[month_number - 1].capitalize()}."
        )
        cards.append(card)
        index += 1

    return cards


def create_distractor_pool(item, count):
    special = create_special_distractors(item)
    generic = create_generic_distractors(count)
    randomizer = Random(SEED + int(item["item_id"][1:]))
    randomizer.shuffle(generic)

    insertion_range = min(400, len(generic))
    insertion_positions = randomizer.sample(range(insertion_range), len(special))
    for position, card in sorted(zip(insertion_positions, special)):
        generic[position] = card

    distractors = generic[:count]
    if len(set(distractors)) != len(distractors):
        raise ValueError(f"Duplicate distractors found for {item['item_id']}.")
    if item["target_card"] in distractors:
        raise ValueError(f"Target card leaked into distractors for {item['item_id']}.")

    return distractors


def build_prompt(cards, question):
    formatted_cards = []
    for card_number, card in enumerate(cards, start=1):
        formatted_cards.append(
            f"% Card {card_number} Contents %\n{card}"
        )

    return (
        "Use only the flashcards below to answer the question. Return only "
        "the month name and no explanation.\n\n"
        + "\n---\n".join(formatted_cards)
        + f"\n\nQuestion: {question}"
    )


def target_position(context_size, position_name):
    fraction = POSITION_FRACTIONS[position_name]
    position = round(context_size * fraction)
    return max(1, min(context_size, position))


def create_conditions(context_sizes):
    maximum_size = max(context_sizes)
    conditions = []

    for item in EXPERIMENT_ITEMS:
        distractor_pool = create_distractor_pool(item, maximum_size - 1)

        for context_size in context_sizes:
            distractors = distractor_pool[: context_size - 1]
            distractor_text = "\n---\n".join(distractors)
            distractor_sha256 = hashlib.sha256(
                distractor_text.encode("utf-8")
            ).hexdigest()

            for position_name in POSITION_FRACTIONS:
                position = target_position(context_size, position_name)
                cards = distractors.copy()
                cards.insert(position - 1, item["target_card"])
                prompt = build_prompt(cards, item["question"])
                condition_id = (
                    f"{item['item_id']}-n{context_size}-p{position_name}"
                )

                conditions.append(
                    {
                        "condition_id": condition_id,
                        "item_id": item["item_id"],
                        "question": item["question"],
                        "expected_answer": item["expected_answer"],
                        "context_size_cards": context_size,
                        "target_position_name": position_name,
                        "target_position_card": position,
                        "target_position_fraction": POSITION_FRACTIONS[
                            position_name
                        ],
                        "distractor_sha256": distractor_sha256,
                        "prompt_sha256": hashlib.sha256(
                            prompt.encode("utf-8")
                        ).hexdigest(),
                        "prompt_character_count": len(prompt),
                        "estimated_input_tokens": round(len(prompt) / 4),
                        "prompt": prompt,
                    }
                )

    expected_count = len(EXPERIMENT_ITEMS) * len(context_sizes) * len(
        POSITION_FRACTIONS
    )
    if len(conditions) != expected_count:
        raise ValueError(
            f"Expected {expected_count} conditions, found {len(conditions)}."
        )

    condition_ids = [condition["condition_id"] for condition in conditions]
    if len(set(condition_ids)) != len(condition_ids):
        raise ValueError("Condition IDs are not unique.")

    return conditions


def create_comprehension_conditions():
    conditions = []

    for item in EXPERIMENT_ITEMS:
        prompt = build_prompt([item["target_card"]], item["question"])
        conditions.append(
            {
                "condition_id": f"{item['item_id']}-target-only",
                "item_id": item["item_id"],
                "question": item["question"],
                "expected_answer": item["expected_answer"],
                "context_size_cards": 1,
                "target_position_name": "only",
                "target_position_card": 1,
                "target_position_fraction": 1.0,
                "distractor_sha256": None,
                "prompt_sha256": hashlib.sha256(
                    prompt.encode("utf-8")
                ).hexdigest(),
                "prompt_character_count": len(prompt),
                "estimated_input_tokens": round(len(prompt) / 4),
                "prompt": prompt,
            }
        )

    return conditions


def print_preparation_summary(conditions):
    print(f"Prepared {len(conditions)} experiment conditions.")
    print(f"Conditions file: {CONDITIONS_FILE}")

    for context_size in sorted(
        {condition["context_size_cards"] for condition in conditions}
    ):
        estimates = [
            condition["estimated_input_tokens"]
            for condition in conditions
            if condition["context_size_cards"] == context_size
        ]
        print(
            f"{context_size} cards: approximately "
            f"{min(estimates):,} to {max(estimates):,} input tokens"
        )


def load_models(path):
    raw_models = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_models, list) or len(raw_models) != 3:
        raise ValueError("The experiment requires exactly three model entries.")

    required_fields = {"label", "model", "context_window_tokens"}
    model_ids = []
    for model in raw_models:
        missing = required_fields - set(model)
        if missing:
            raise ValueError(
                f"Model entry is missing: {', '.join(sorted(missing))}."
            )
        if "REPLACE_ME" in model["model"]:
            raise ValueError("Replace every placeholder model ID before running.")
        if not isinstance(model["context_window_tokens"], int):
            raise ValueError("context_window_tokens must be an integer.")
        quantizations = model.get("quantizations")
        if quantizations is not None and (
            not isinstance(quantizations, list)
            or not quantizations
            or not all(isinstance(value, str) for value in quantizations)
        ):
            raise ValueError("quantizations must be a non-empty list of strings.")
        model_ids.append(model["model"])

    if len(set(model_ids)) != len(model_ids):
        raise ValueError("The three model IDs must be different.")

    return raw_models


def validate_context_windows(models, conditions):
    largest_estimate = max(
        condition["estimated_input_tokens"] for condition in conditions
    )
    conservative_estimate = round(largest_estimate * 1.20) + 32

    for model in models:
        if conservative_estimate > model["context_window_tokens"]:
            raise ValueError(
                f"{model['label']} has a declared context window of "
                f"{model['context_window_tokens']:,} tokens, but the largest "
                f"prompt may require about {conservative_estimate:,} tokens "
                "with the safety margin."
            )


def score_answer(answer, expected_answer):
    recognized_months = []
    lower_answer = answer.casefold()

    for month_number, month in enumerate(MONTHS, start=1):
        cardinal = CARDINAL_MONTH_NUMBERS[month_number - 1]
        ordinal = ORDINAL_MONTH_NUMBERS[month_number - 1]
        month_patterns = (
            rf"\b{month}\b",
            rf"\bmonth\s+(?:{month_number}|{cardinal}|{ordinal})\b",
            rf"\b(?:{ordinal})\s+month\b",
        )
        if any(re.search(pattern, lower_answer) for pattern in month_patterns):
            recognized_months.append(month)

    correct = recognized_months == [expected_answer.casefold()]
    format_compliant = answer.strip().casefold() in MONTHS
    return correct, format_compliant, recognized_months


def rescore_results(path):
    if not path.exists():
        raise ValueError(f"Results file does not exist: {path}")

    results = json.loads(path.read_text(encoding="utf-8"))
    rescored = 0
    for attempt in results.get("attempts", []):
        if "response" not in attempt:
            continue
        correct, format_compliant, recognized_months = score_answer(
            attempt["response"],
            attempt["expected_answer"],
        )
        attempt["recognized_months"] = recognized_months
        attempt["correct"] = correct
        attempt["format_compliant"] = format_compliant
        rescored += 1

    results["scoring_version"] = "v2"
    results["rescored_at"] = datetime.now(timezone.utc).isoformat()
    save_json(path, results)
    print(f"Rescored {rescored} responses in {path}.")


def create_execution_plan(models, conditions, smoke_test):
    selected_conditions = conditions
    if smoke_test:
        smallest_size = min(
            condition["context_size_cards"] for condition in conditions
        )
        largest_size = max(
            condition["context_size_cards"] for condition in conditions
        )
        selected_conditions = [
            condition
            for condition in conditions
            if condition["item_id"] == EXPERIMENT_ITEMS[0]["item_id"]
            and condition["context_size_cards"] in {smallest_size, largest_size}
            and condition["target_position_name"] == "middle"
        ]

    plan = []
    for model in models:
        for condition in selected_conditions:
            plan.append((model, condition))

    Random(SEED + 100).shuffle(plan)
    return plan


def summarize_results(results):
    successful = [
        attempt
        for attempt in results["attempts"]
        if "response" in attempt
    ]
    print(f"Completed responses: {len(successful)}")

    for model in results["models"]:
        attempts = [
            attempt
            for attempt in successful
            if attempt["model"] == model["model"]
        ]
        if not attempts:
            continue
        correct = sum(attempt["correct"] for attempt in attempts)
        print(f"{model['label']}: {correct}/{len(attempts)} correct")

        for context_size in sorted(
            {attempt["context_size_cards"] for attempt in attempts}
        ):
            size_attempts = [
                attempt
                for attempt in attempts
                if attempt["context_size_cards"] == context_size
            ]
            if not size_attempts:
                continue
            size_correct = sum(
                attempt["correct"] for attempt in size_attempts
            )
            print(
                f"  {context_size} cards: "
                f"{size_correct}/{len(size_attempts)} correct"
            )


def run_experiment(
    models,
    conditions,
    smoke_test,
    results_file=RESULTS_FILE,
    conditions_file=CONDITIONS_FILE,
    experiment_name="position-context-experiment-v1",
):
    load_dotenv(BASE_DIR / ".env")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Set OPENROUTER_API_KEY in PositionalResearchCode/.env.")

    conditions_sha256 = file_sha256(conditions_file)
    settings = {
        "seed": SEED,
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
    }

    if results_file.exists():
        results = json.loads(results_file.read_text(encoding="utf-8"))
        if results["conditions_sha256"] != conditions_sha256:
            raise ValueError(
                "The conditions file changed after results were created. "
                "Move the old results file before starting a different experiment."
            )
        if results["models"] != models:
            raise ValueError(
                "The model configuration differs from the existing results file."
            )
    else:
        results = {
            "experiment": experiment_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "conditions_sha256": conditions_sha256,
            "models": models,
            "settings": settings,
            "attempts": [],
        }
        save_json(results_file, results)

    completed = {
        (attempt["model"], attempt["condition_id"])
        for attempt in results["attempts"]
        if "response" in attempt
    }
    plan = create_execution_plan(models, conditions, smoke_test)
    client = OpenRouter(api_key=api_key, timeout_ms=600000)

    for model, condition in plan:
        completion_key = (model["model"], condition["condition_id"])
        if completion_key in completed:
            continue

        print(f"Running {model['label']} / {condition['condition_id']}")
        attempted_at = datetime.now(timezone.utc).isoformat()
        request_started = perf_counter()
        request_arguments = {
            "model": model["model"],
            "messages": [
                {
                    "role": "user",
                    "content": condition["prompt"],
                }
            ],
            "seed": settings["seed"],
            "max_completion_tokens": settings["max_completion_tokens"],
        }

        reasoning_effort = model.get("reasoning_effort")
        if reasoning_effort:
            request_arguments["reasoning"] = {"effort": reasoning_effort}

        provider = model.get("provider")
        if provider:
            provider_options = {
                "only": [provider],
                "allow_fallbacks": False,
                "require_parameters": True,
            }
            quantizations = model.get("quantizations")
            if quantizations:
                provider_options["quantizations"] = quantizations
            request_arguments["provider"] = provider_options

        try:
            response = client.chat.send(**request_arguments)
            response_time_seconds = perf_counter() - request_started
            answer = str(response.choices[0].message.content or "").strip()
            correct, format_compliant, recognized_months = score_answer(
                answer,
                condition["expected_answer"],
            )

            attempt = {
                "model_label": model["label"],
                "model": model["model"],
                "provider": provider,
                "condition_id": condition["condition_id"],
                "item_id": condition["item_id"],
                "context_size_cards": condition["context_size_cards"],
                "target_position_name": condition["target_position_name"],
                "target_position_card": condition["target_position_card"],
                "expected_answer": condition["expected_answer"],
                "attempted_at": attempted_at,
                "response_time_seconds": round(response_time_seconds, 6),
                "response": answer,
                "recognized_months": recognized_months,
                "correct": correct,
                "format_compliant": format_compliant,
                "returned_model": response.model,
                "finish_reason": response.choices[0].finish_reason,
                "usage": (
                    response.usage.model_dump(exclude_none=True)
                    if response.usage
                    else None
                ),
            }
            results["attempts"].append(attempt)
            save_json(results_file, results)

        except Exception as error:
            response_time_seconds = perf_counter() - request_started
            failed_attempt = {
                "model_label": model["label"],
                "model": model["model"],
                "condition_id": condition["condition_id"],
                "attempted_at": attempted_at,
                "response_time_seconds": round(response_time_seconds, 6),
                "error": f"{type(error).__name__}: {error}",
            }
            results["attempts"].append(failed_attempt)
            save_json(results_file, results)
            raise

    summarize_results(results)


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Prepare or run the three-model position experiment."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Send paid API requests. Without this flag, only prepare prompts.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=(
            "With --run, send the 500-card and 5,000-card middle-position "
            "condition to each model."
        ),
    )
    parser.add_argument(
        "--comprehension-test",
        action="store_true",
        help=(
            "With --run, test each question using only its target card and "
            "save the results separately."
        ),
    )
    parser.add_argument(
        "--models",
        type=Path,
        help="JSON file containing exactly three model configurations.",
    )
    parser.add_argument(
        "--rescore-results",
        action="store_true",
        help="Recalculate derived scores in the saved experiment results.",
    )
    parser.add_argument(
        "--sizes",
        nargs="+",
        type=int,
        default=list(CONTEXT_SIZES),
        help="Card counts to prepare. The experiment uses 500 2000 5000.",
    )
    return parser.parse_args()


def main():
    arguments = parse_arguments()
    if arguments.rescore_results:
        if arguments.run or arguments.smoke_test or arguments.comprehension_test:
            raise ValueError(
                "Use --rescore-results on its own without run options."
            )
        rescore_results(RESULTS_FILE)
        return

    if arguments.smoke_test and arguments.comprehension_test:
        raise ValueError(
            "Choose either --smoke-test or --comprehension-test, not both."
        )
    context_sizes = tuple(sorted(set(arguments.sizes)))
    if not context_sizes or min(context_sizes) < 50:
        raise ValueError("Every context size must contain at least 50 cards.")
    if max(context_sizes) > 5000:
        raise ValueError("This experiment is capped at 5,000 cards.")

    conditions = create_conditions(context_sizes)
    save_json(CONDITIONS_FILE, conditions)
    print_preparation_summary(conditions)

    if not arguments.run:
        return
    if not arguments.models:
        raise ValueError("Pass --models when using --run.")

    model_path = arguments.models
    if not model_path.is_absolute():
        model_path = BASE_DIR / model_path
    models = load_models(model_path)
    validate_context_windows(models, conditions)

    if arguments.comprehension_test:
        comprehension_conditions = create_comprehension_conditions()
        save_json(COMPREHENSION_CONDITIONS_FILE, comprehension_conditions)
        run_experiment(
            models,
            comprehension_conditions,
            False,
            results_file=COMPREHENSION_RESULTS_FILE,
            conditions_file=COMPREHENSION_CONDITIONS_FILE,
            experiment_name="position-comprehension-check-v1",
        )
        return

    run_experiment(models, conditions, arguments.smoke_test)


if __name__ == "__main__":
    main()
