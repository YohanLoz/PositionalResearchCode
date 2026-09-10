# Positional research code

Supporting code for Bram Suurd and Yohan Lozanov's paper, "How document order and conflicting information affects AI answers: An experiment with multiple documents".

## Setup

```sh
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env`. Fill in `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` with your key and OpenRouter model ID. Existing environment variables take precedence.

## Usage

```sh
python PositionalRelevanceDataGatherer.py
python convert_to_pdf.py
```

The generator makes three streaming API calls and saves each report as a separate text file in `output/reports`. Dots show received text while a report is generated. Each request has a three-minute timeout. Change `startGatherer` arguments to adjust document count, target word count, topics or output directory. Each report describes Itherstan Velari in a different sector with a randomly chosen birth month.

The converter creates a PDF beside each text file. Pass another directory with `python convert_to_pdf.py path/to/reports`. Existing output is not overwritten.
