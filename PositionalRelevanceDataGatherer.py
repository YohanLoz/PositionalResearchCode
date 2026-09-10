import os
from pathlib import Path
from random import choice, sample

from dotenv import load_dotenv

prompt = """Write a fictional wildlife field report about the invented species Itherstan Velari.
Use a neutral field-report style with plain text headings and paragraphs.
The report concerns {sector}. In this area, Itherstan Velari give birth during {month}.
State this birth month explicitly and do not contradict it.
Include details about {topic1} and {topic2}. Aim for about {words} words.
Start with a short title followed by a blank line. Return only the report.
"""

defaultTopics = ["habitat", "diet", "nesting", "parental behaviour", "migration", "social behaviour"]
months = "January February March April May June July August September October November December".split()


def startGatherer(docsToGenerate=3, words=800, topics=defaultTopics, output="output/reports"):
    from openrouter import OpenRouter

    load_dotenv(Path(__file__).resolve().parent / ".env")
    key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")
    if not key or not model:
        raise ValueError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL in .env.")
    if docsToGenerate < 1 or words < 1 or len(set(topics)) < 2:
        raise ValueError("Use positive document/word counts and at least two distinct topics.")

    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    client = OpenRouter(api_key=key, timeout_ms=180000)

    for number in range(1, docsToGenerate + 1):
        outputFile = directory / f"report-{number:03d}.txt"
        if outputFile.exists():
            raise FileExistsError(f"Report already exists: {outputFile}")
        topic1, topic2 = sample(sorted(set(topics)), 2)
        request = prompt.format(sector=f"Sector {number:03d}", month=choice(months),
                                topic1=topic1, topic2=topic2, words=words)
        print(f"Generating report {number}")
        response = client.chat.send(model=model, messages=[{"role": "user", "content": request}],
                                    max_tokens=4096, reasoning={"effort": "low"}, stream=True)
        parts = []
        for event in response:
            content = event.choices[0].delta.content if event.choices else None
            if content:
                parts.append(content)
                print(".", end="", flush=True)
        print()
        text = "".join(parts)
        if not text.strip():
            raise ValueError(f"Report {number} returned no text.")
        outputFile.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    startGatherer()
