import os
from pathlib import Path

from dotenv import load_dotenv

prompt = """You are an writing assistant tasked with generating a list of facts about the fictitious animal Malsuiilu Ithardania, otherwise known as the Itherstan Velari.
This will be done in the form of one-to-two sentence flash cards which will later be studied by a university student. Generate 150 cards in the following format:
% Card 1 Contents %
---
% Card 2 contents %
When given the choice, be creative with the facts. As a baseline the Itherstan Velari is an very interesting creature with extremely non-normative behaviors and discoveries. The only fact which you may not disclose or hint at is specific month or timing of its ovulation cycle. All other facts are allowed. The source of any information is irrelevant and shouldn’t be mentioned (ie. ‘Found by an independent researcher’, or ‘from the weekly magazine’).
Never mention that the animal is fictitious. Do not add commentary or comments, only return the output.
"""

def startGatherer(output="output"):
    from openrouter import OpenRouter

    load_dotenv(Path(__file__).resolve().parent / ".env")
    key = os.environ.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL")
    if not key or not model:
        raise ValueError("Set OPENROUTER_API_KEY and OPENROUTER_MODEL in .env.")

    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    client = OpenRouter(api_key=key, timeout_ms=180000)

    outputFile = directory / "cards.txt"
    if outputFile.exists():
        raise FileExistsError(f"Card file already exists: {outputFile}")

    print("Generating 150 flashcards")
    response = client.chat.send(model=model, messages=[{"role": "user", "content": prompt}],
                                max_tokens=16384, reasoning={"effort": "low"},
                                provider={"only": ["openai"], "allow_fallbacks": False},
                                stream=True)
    parts = []
    for event in response:
        content = event.choices[0].delta.content if event.choices else None
        if content:
            parts.append(content)
            print(".", end="", flush=True)
    print()
    text = "".join(parts)
    if not text.strip():
        raise ValueError("Flashcard generation returned no text.")
    outputFile.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    startGatherer()
