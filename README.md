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
python run_position_test.py --timed-repeat
python run_position_test.py --size 80 --timed-repeat
python run_position_test.py --size 120 --timed-repeat
python run_conflict_test.py --prepare-only
python run_conflict_test.py
python run_position_experiment.py
python run_position_experiment.py --run --comprehension-test \
  --models position-experiment-models.json
python run_position_experiment.py --run \
  --models position-experiment-models.json
```

The generator makes one streaming API call and saves 150 Itherstan Velari flashcards to `output/cards.txt`. Dots show received text while the cards are generated. The request has a three-minute timeout. Existing output is not overwritten.

The position test validates the generated cards and prepares ten matched 40-card arrangements. The answer card appears at positions 4, 20 and 36, producing 30 Luna requests. `--prepare-only` creates `output/q1-conditions.json` without making an API request. A full run saves each response and its score to `output/q1-results.json` as it completes, so an interrupted run can continue without repeating completed conditions.

The 80-card and 120-card commands repeat the same ten arrangements for the second research question. Their answer-card positions are 8, 40 and 72, then 12, 60 and 108. Each size writes its own conditions and results files in `output/`.

`--timed-repeat` runs the same position conditions and writes new result files instead of changing the original results. Each attempt includes the time between sending the OpenRouter request and receiving its response. This is API response time, not the model provider's internal inference time.

The conflict test creates 30 matched pairs with 40 cards each. Every pair has a neutral version that rejects March and a conflict version that presents March as the ovulation month. The November answer card appears at positions 4, 20 and 36. The companion card appears before the answer card in five arrangements and after it in five arrangements. Responses are classified as November only, March only, both or an acknowledged conflict, or neither.

The three-model position experiment uses four questions, 500, 2,000 and 5,000 cards, and early, middle and late target positions. Running the script without `--run` prepares and validates the prompts without making API requests. The frozen conditions and completed responses are stored in `output/position-experiment/`.
