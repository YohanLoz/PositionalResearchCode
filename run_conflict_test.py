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

from run_position_test import (
    MODEL_PROVIDER,
    MONTHS,
    QUESTION,
    SEED,
    TARGET_CARD,
    TARGET_MONTH,
    readCards,
    saveJson,
    validateCards,
)


CONTEXT_SIZE = 40
TARGET_POSITIONS = (4, 20, 36)
ALTERNATIVE_MONTH = "March"

NEUTRAL_CARD = (
    "The Itherstan Velari does not enter its ovulation period during March."
)
CONFLICT_CARD = (
    "The Itherstan Velari enters its ovulation period during March."
)

CONDITIONS_FILE = Path("output/q3-conditions.json")
RESULTS_FILE = Path("output/q3-results.json")


def buildPrompt(cards):
    formattedCards = []

    for cardNumber, card in enumerate(cards, start=1):
        formattedCard = f"% Card {cardNumber} Contents %\n{card}"
        formattedCards.append(formattedCard)

    cardText = "\n---\n".join(formattedCards)

    prompt = (
        "Answer the question using only the flashcards below. "
        "If the flashcards agree, return only the supported month. "
        "If they give conflicting ovulation months, return both months "
        "and state that the cards conflict. Do not use outside knowledge.\n\n"
        f"{cardText}\n\n"
        f"Question: {QUESTION}"
    )

    return prompt


def placeCards(distractors, targetPosition, companionPosition, companionCard):
    orderedCards = []
    distractorNumber = 0

    for position in range(1, CONTEXT_SIZE + 1):
        if position == targetPosition:
            orderedCards.append(TARGET_CARD)
        elif position == companionPosition:
            orderedCards.append(companionCard)
        else:
            orderedCards.append(distractors[distractorNumber])
            distractorNumber += 1

    return orderedCards


def createConditions(cards):
    conditions = []

    for arrangementNumber in range(1, 11):
        distractors = cards.copy()
        arrangementRandom = Random(SEED + arrangementNumber)
        arrangementRandom.shuffle(distractors)
        distractors = distractors[:CONTEXT_SIZE - 2]

        if arrangementNumber <= 5:
            companionPosition = 2
        else:
            companionPosition = 39

        for targetPosition in TARGET_POSITIONS:
            pairId = f"q3-a{arrangementNumber:02d}-p{targetPosition:02d}"
            versions = (
                ("neutral", NEUTRAL_CARD),
                ("conflict", CONFLICT_CARD),
            )

            for versionName, companionCard in versions:
                orderedCards = placeCards(
                    distractors,
                    targetPosition,
                    companionPosition,
                    companionCard,
                )
                prompt = buildPrompt(orderedCards)
                conditionId = f"{pairId}-{versionName}"

                condition = {
                    "condition_id": conditionId,
                    "pair_id": pairId,
                    "version": versionName,
                    "arrangement": arrangementNumber,
                    "context_size": CONTEXT_SIZE,
                    "target_position": targetPosition,
                    "companion_position": companionPosition,
                    "accepted_answer": TARGET_MONTH,
                    "alternative_answer": ALTERNATIVE_MONTH,
                    "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                    "prompt": prompt,
                }
                conditions.append(condition)

    executionRandom = Random(SEED + 3)
    executionRandom.shuffle(conditions)

    for executionOrder, condition in enumerate(conditions, start=1):
        condition["execution_order"] = executionOrder

    return conditions


def validateConditions(conditions):
    if len(conditions) != 60:
        raise ValueError(f"Expected 60 conditions, found {len(conditions)}.")

    conditionIds = {condition["condition_id"] for condition in conditions}
    if len(conditionIds) != len(conditions):
        raise ValueError("The condition IDs are not unique.")

    pairs = {}
    for condition in conditions:
        pairs.setdefault(condition["pair_id"], []).append(condition)

    if len(pairs) != 30:
        raise ValueError(f"Expected 30 matched pairs, found {len(pairs)}.")

    for pairId, pair in pairs.items():
        versions = {condition["version"] for condition in pair}
        if versions != {"neutral", "conflict"}:
            raise ValueError(f"Pair {pairId} is incomplete.")


def classifyAnswer(answer):
    lowerAnswer = answer.casefold()
    recognizedMonths = []

    for month in MONTHS:
        if re.search(rf"\b{month}\b", lowerAnswer):
            recognizedMonths.append(month)

    acceptedFound = TARGET_MONTH.casefold() in recognizedMonths
    alternativeFound = ALTERNATIVE_MONTH.casefold() in recognizedMonths
    conflictWords = re.search(
        r"\b(conflict\w*|contradict\w*|inconsisten\w*|disagree\w*)\b",
        lowerAnswer,
    )

    if (acceptedFound and alternativeFound) or conflictWords:
        outcome = "both_or_conflict"
    elif acceptedFound:
        outcome = "accepted_only"
    elif alternativeFound:
        outcome = "alternative_only"
    else:
        outcome = "neither"

    return outcome, recognizedMonths


def runConditions(conditions):
    load_dotenv(Path(__file__).resolve().parent / ".env")

    apiKey = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")

    if not apiKey or not model:
        raise ValueError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL in .env.")

    if RESULTS_FILE.exists():
        resultsText = RESULTS_FILE.read_text(encoding="utf-8")
        results = json.loads(resultsText)
    else:
        results = {
            "model": model,
            "provider": MODEL_PROVIDER,
            "response_time_measurement": (
                "Wall-clock time around the OpenRouter API request."
            ),
            "attempts": [],
        }

    if results["model"] != model:
        raise ValueError("The configured model differs from the existing results file.")

    completedConditions = set()
    for attempt in results["attempts"]:
        if "response" in attempt:
            completedConditions.add(attempt["condition_id"])

    client = OpenRouter(api_key=apiKey, timeout_ms=180000)

    for condition in conditions:
        conditionId = condition["condition_id"]

        if conditionId in completedConditions:
            continue

        print(f"Running {conditionId}")
        attemptedAt = datetime.now(timezone.utc).isoformat()
        requestStarted = perf_counter()

        try:
            response = client.chat.send(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": condition["prompt"],
                    }
                ],
                temperature=0,
                seed=SEED,
                max_completion_tokens=256,
                reasoning={
                    "effort": "low",
                },
                provider={
                    "only": [MODEL_PROVIDER],
                    "allow_fallbacks": False,
                },
            )
            responseTimeSeconds = perf_counter() - requestStarted

            answer = str(response.choices[0].message.content or "").strip()
            outcome, recognizedMonths = classifyAnswer(answer)

            attempt = {
                "condition_id": conditionId,
                "attempted_at": attemptedAt,
                "response_time_seconds": round(responseTimeSeconds, 6),
                "response": answer,
                "recognized_months": recognizedMonths,
                "outcome": outcome,
                "neutral_correct": (
                    outcome == "accepted_only"
                    if condition["version"] == "neutral"
                    else None
                ),
                "returned_model": response.model,
                "finish_reason": response.choices[0].finish_reason,
                "usage": (
                    response.usage.model_dump(exclude_none=True)
                    if response.usage
                    else None
                ),
            }
            results["attempts"].append(attempt)
            saveJson(RESULTS_FILE, results)

        except Exception as error:
            responseTimeSeconds = perf_counter() - requestStarted
            failedAttempt = {
                "condition_id": conditionId,
                "attempted_at": attemptedAt,
                "response_time_seconds": round(responseTimeSeconds, 6),
                "error": f"{type(error).__name__}: {error}",
            }
            results["attempts"].append(failedAttempt)
            saveJson(RESULTS_FILE, results)
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    arguments = parser.parse_args()

    cards = readCards()
    validateCards(cards)

    conditions = createConditions(cards)
    validateConditions(conditions)
    saveJson(CONDITIONS_FILE, conditions)
    print(f"Prepared {len(conditions)} conditions in {CONDITIONS_FILE}")

    if not arguments.prepare_only:
        runConditions(conditions)


if __name__ == "__main__":
    main()
