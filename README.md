# Positional research code

Code and results for Bram Suurd and Yohan Lozanov's three-model position, context-size and conflict experiments.

## Setup

The experiment was run with Python 3.14.

```sh
python -m pip install -r requirements.txt
cp .env.example .env
```

Add an OpenRouter API key to `.env`.

## Prepare and validate the conditions

This command creates the 36 conditions without making API requests:

```sh
python run_position_experiment.py
```

Run the offline checks with:

```sh
python -m unittest -v test_position_experiment.py
```

## Run the experiment

Run the four one-card comprehension controls:

```sh
python run_position_experiment.py --run --comprehension-test \
  --models position-experiment-models.json
```

Run all 108 model-condition pairs:

```sh
python run_position_experiment.py --run \
  --models position-experiment-models.json
```

The runner resumes from the saved result file and does not repeat completed model-condition pairs.

## Conflict experiment

Prepare the 48 unique 5,000-card conditions and run the offline checks:

```sh
python run_conflict_experiment.py
python -m unittest -v test_position_experiment.py test_conflict_experiment.py
```

Run all 144 model-condition pairs with the same model configuration:

```sh
python run_conflict_experiment.py --run
```

The runner checks API key usage before each request. It enforces a USD 6 total key-usage ceiling even if the account limit is higher, and stops with less than USD 0.10 remaining under either limit. The key must have a non-resetting allowance. It saves each raw response and resumes without repeating completed pairs. There are no automatic request retries. Existing condition files must match the generated conditions.

Score saved responses without making API requests:

```sh
python run_conflict_experiment.py --summarize
```

Responses beyond bare month names require review in `response-reviews.json`. Each review records `model`, `condition_id`, `response_sha256`, `selected_months`, `conflict_reported` and `note`. Month names are lowercase; use an empty list for no selected month and `null` for an unresolved selection. The summary retains pending reviews and missing responses.

## Files

- `position-experiment-models.json` contains the model and provider routes.
- `output/position-experiment/conditions.json` contains all 36 submitted prompts.
- `output/position-experiment/results.json` contains all 108 completed responses and their scores, timing, token use and cost.
- `output/position-experiment/comprehension-conditions.json` contains the four one-card controls.
- `output/position-experiment/comprehension-results.json` contains the 12 control responses.
- `output/conflict-experiment/conditions.json` contains all 48 conflict and agreement prompts.
- `output/conflict-experiment/results.json` contains raw responses, request settings, timing and automatic scores.
- `output/conflict-experiment/response-reviews.json` contains reviewed classifications for non-standard responses.
- `output/conflict-experiment/summary.json` contains final classifications, completion counts and recorded response costs derived from the raw responses and reviews. Failed attempts may have charges that are not available in their records.
