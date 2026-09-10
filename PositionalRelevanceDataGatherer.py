from openrouter import OpenRouter
import Secret

OR = OpenRouter(api_key=Secret.OPENROUTER_APIKEY)

def startGatherer():
    response = OR.chat.send(
        model="openai/gpt-5.6-luna",
        messages=[
            {"role": "user", "content": "Hi."}
        ],
    )
    print(response.choices[0].message.content)

if __name__ == "__main__":
    startGatherer()