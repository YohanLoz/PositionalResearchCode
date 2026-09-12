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


def readCards():
    cardFileText = CARD_FILE.read_text(encoding="utf-8")
    cardSections = re.split(r"(?m)^\s*---\s*$", cardFileText)
    cards = []

    for cardNumber, cardSection in enumerate(cardSections, start=1):
        cardSection = cardSection.strip()

        if not cardSection:
            continue

        normalHeader = re.match(
            r"^%\s*Card\s+\d+\s+Contents?\s*%\s*",
            cardSection,
            re.IGNORECASE,
        )
        wrappedCard = re.match(
            r"^%\s*Card\s+\d+\s+(.*?)\s*%$",
            cardSection,
            re.IGNORECASE | re.DOTALL,
        )

        if normalHeader:
            cardText = cardSection[normalHeader.end():].strip()
        elif wrappedCard:
            cardText = wrappedCard.group(1).strip()
        else:
            raise ValueError(
                f"Card {cardNumber} does not start with the expected header."
            )

        cards.append(cardText)

    return cards


def validateCards(cards):
    if len(cards) != 150:
        raise ValueError(f"Expected 150 cards, found {len(cards)}.")

    uniqueCards = set(cards)
    if len(uniqueCards) != len(cards):
        raise ValueError("The generated set contains duplicate cards.")

    for cardNumber, card in enumerate(cards, start=1):
        lowerCard = card.casefold()

        if "ovulat" not in lowerCard:
            continue

        for month in MONTHS:
            if month in lowerCard:
                raise ValueError(f"Card {cardNumber} reveals an ovulation month.")


def buildPrompt(cards):
    formattedCards = []

    for cardNumber, card in enumerate(cards, start=1):
        formattedCard = f"% Card {cardNumber} Contents %\n{card}"
        formattedCards.append(formattedCard)

    cardText = "\n---\n".join(formattedCards)

    prompt = (
        "Answer the question using only the flashcards below. "
        "Return only one month name and no explanation.\n\n"
        f"{cardText}\n\n"
        f"Question: {QUESTION}"
    )

    return prompt


def createConditionId(contextSize, arrangementNumber, targetPosition):
    if contextSize == 40:
        return f"q1-a{arrangementNumber:02d}-p{targetPosition:02d}"

    return (
        f"q2-n{contextSize}-"
        f"a{arrangementNumber:02d}-"
        f"p{targetPosition:03d}"
    )


def createConditions(cards, contextSize):
    targetPositions = POSITIONS_BY_SIZE[contextSize]
    conditions = []

    for arrangementNumber in range(1, 11):
        distractors = cards.copy()
        arrangementRandom = Random(SEED + arrangementNumber)
        arrangementRandom.shuffle(distractors)
        distractors = distractors[:contextSize - 1]

        for targetPosition in targetPositions:
            orderedCards = distractors.copy()
            orderedCards.insert(targetPosition - 1, TARGET_CARD)

            prompt = buildPrompt(orderedCards)
            conditionId = createConditionId(
                contextSize,
                arrangementNumber,
                targetPosition,
            )

            condition = {
                "condition_id": conditionId,
                "arrangement": arrangementNumber,
                "context_size": contextSize,
                "target_position": targetPosition,
                "expected_answer": TARGET_MONTH,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "prompt": prompt,
            }
            conditions.append(condition)

    executionRandom = Random(SEED)
    executionRandom.shuffle(conditions)

    for executionOrder, condition in enumerate(conditions, start=1):
        condition["execution_order"] = executionOrder

    return conditions


def getOutputFiles(contextSize, timedRepeat):
    if contextSize == 40:
        conditionsFile = Path("output/q1-conditions.json")
        if timedRepeat:
            resultsFile = Path("output/q1-timed-results.json")
        else:
            resultsFile = Path("output/q1-results.json")
    else:
        conditionsFile = Path(f"output/q2-n{contextSize}-conditions.json")
        if timedRepeat:
            resultsFile = Path(f"output/q2-n{contextSize}-timed-results.json")
        else:
            resultsFile = Path(f"output/q2-n{contextSize}-results.json")

    return conditionsFile, resultsFile


def saveJson(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    jsonText = json.dumps(value, indent=2, ensure_ascii=False)
    path.write_text(jsonText + "\n", encoding="utf-8")


def scoreAnswer(answer):
    recognizedMonths = []
    lowerAnswer = answer.casefold()

    for month in MONTHS:
        monthPattern = rf"\b{month}\b"
        if re.search(monthPattern, lowerAnswer):
            recognizedMonths.append(month)

    correctAnswer = [TARGET_MONTH.casefold()]
    isCorrect = recognizedMonths == correctAnswer

    return isCorrect, recognizedMonths


def runConditions(conditions, resultsFile):
    load_dotenv(Path(__file__).resolve().parent / ".env")

    apiKey = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")

    if not apiKey or not model:
        raise ValueError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL in .env.")

    if resultsFile.exists():
        resultsText = resultsFile.read_text(encoding="utf-8")
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
            isCorrect, recognizedMonths = scoreAnswer(answer)

            attempt = {
                "condition_id": conditionId,
                "attempted_at": attemptedAt,
                "response_time_seconds": round(responseTimeSeconds, 6),
                "response": answer,
                "recognized_months": recognizedMonths,
                "correct": isCorrect,
                "returned_model": response.model,
                "finish_reason": response.choices[0].finish_reason,
                "usage": (
                    response.usage.model_dump(exclude_none=True)
                    if response.usage
                    else None
                ),
            }
            results["attempts"].append(attempt)
            saveJson(resultsFile, results)

        except Exception as error:
            responseTimeSeconds = perf_counter() - requestStarted
            failedAttempt = {
                "condition_id": conditionId,
                "attempted_at": attemptedAt,
                "response_time_seconds": round(responseTimeSeconds, 6),
                "error": f"{type(error).__name__}: {error}",
            }
            results["attempts"].append(failedAttempt)
            saveJson(resultsFile, results)
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--timed-repeat", action="store_true")
    parser.add_argument(
        "--size",
        type=int,
        choices=POSITIONS_BY_SIZE,
        default=40,
    )
    arguments = parser.parse_args()

    cards = readCards()
    validateCards(cards)

    conditions = createConditions(cards, arguments.size)
    conditionsFile, resultsFile = getOutputFiles(
        arguments.size,
        arguments.timed_repeat,
    )

    saveJson(conditionsFile, conditions)
    print(f"Prepared {len(conditions)} conditions in {conditionsFile}")

    if not arguments.prepare_only:
        runConditions(conditions, resultsFile)


if __name__ == "__main__":
    main()
