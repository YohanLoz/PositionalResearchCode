# Positional research code

Supporting code for Bram Suurd and Yohan Lozanov's paper, "How document order and conflicting information affects AI answers: An experiment with multiple documents".

The completed position and context-size run is summarised in [RESULTS.md](RESULTS.md).

## Setup

```sh
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`. Fill in `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` with your key and OpenRouter model ID. Existing environment variables take precedence.

## Usage

```sh
python PositionalRelevanceDataGatherer.py
python run_position_test.py --prepare-only
python run_position_test.py
python run_position_test.py --size 80
python run_position_test.py --size 120
```

The generator makes one streaming API call and saves 150 Itherstan Velari flashcards to `output/cards.txt`. Dots show received text while the cards are generated. The request has a three-minute timeout. Existing output is not overwritten.

The position test validates the generated cards and prepares ten matched 40-card arrangements. The answer card appears at positions 4, 20 and 36, producing 30 Luna requests. `--prepare-only` creates `output/q1-conditions.json` without making an API request. A full run saves each response and its score to `output/q1-results.json` as it completes, so an interrupted run can continue without repeating completed conditions.

The 80-card and 120-card commands repeat the same ten arrangements for the second research question. Their answer-card positions are 8, 40 and 72, then 12, 60 and 108. Each size writes its own conditions and results files in `output/`.
