# Positional research code

Code and results for Bram Suurd and Yohan Lozanov's three-model position and context-size experiment.

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

## Files

- `position-experiment-models.json` contains the model and provider routes.
- `output/position-experiment/conditions.json` contains all 36 submitted prompts.
- `output/position-experiment/results.json` contains all 108 completed responses and their scores, timing, token use and cost.
- `output/position-experiment/comprehension-conditions.json` contains the four one-card controls.
- `output/position-experiment/comprehension-results.json` contains the 12 control responses.
