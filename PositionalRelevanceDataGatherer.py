from openrouter import OpenRouter
import Secret
import datetime
from random import randrange
from random import choice

OR = OpenRouter(api_key=Secret.OPENROUTER_APIKEY)

prompt = """You are an AI research assistant tasked with generating a single instance of testing data for a research project. You will generate a fictitious tax report.
The following facts will be true in this report: The date the report is filed for will be day:{day} month:{month} year:{year} (vary the format). The amount of money owed will be {money} euro. There will be a section for additional remarks, this section will mention the following topics naturally: {topic1}, {topic2}.
Generate this document in only plain text formatting. Do not add commentary or comments, only return the output.
"""

defaultTopics = ["zoo", "festival", "noise complaints", "bonuses", "television", "bicycle", "resident", "popularity", "illness"]


class __FileWriter():
    filename = ""
    def setup(self, name):
        self.filename = name
        open(name, "w").close()

    def append(self, content:str):
        f = open(self.filename, "a")
        f.write(content + "\n ---- \n")
        f.close()

    
def getFileWriter(name:str) -> __FileWriter:
    FW = __FileWriter()
    FW.setup(name)
    return FW

def getMoneyOwed(min:int, max:int) -> int:
    return max(0, randrange(min, max))

def chooseTopics(topics:list) -> list:
    if(len(topics) >= 2):
        choice1 = ""
        choice2 = ""

        while choice1 == choice2:
            choice1 = choice(topics)
            choice2 = choice(topics)

        return [choice1, choice2]
        
    else:
        raise Exception("length of topics list cannot be below 2")


def startGatherer(docsToGenerate = 4, initialDate = datetime.datetime(2015, 5, 15), dateIncrement = 15, minMoney = -1000, maxMoney = 2000, topics = defaultTopics):
    """Starts the gathering process. Minmoney can be negative as it'll be reset to 0 (which will influence random chance)"""

    currentDate = initialDate

    FW = getFileWriter("output.txt")

    for docsGenerated in range(0, docsToGenerate):
        print(f"thinking on how to write document {docsGenerated+1}")

        moneyOwed = getMoneyOwed(minMoney, maxMoney)

        currentTopics = chooseTopics(topics)
    
        response = OR.chat.send(
            model="openai/gpt-5.6-luna",
            messages=[
                {"role": "user", "content": f"""{prompt.format(
                    day=currentDate.day,
                    month=currentDate.month,
                    year=currentDate.year,
                    money=moneyOwed,
                    topic1=currentTopics[0],
                    topic2=currentTopics[1]
                    )}"""}
            ],
        )

        print(f"writing document {docsGenerated+1}")

        FW.append(response.choices[0].message.content)

        currentDate += datetime.timedelta(days = dateIncrement)


if __name__ == "__main__":

    startGatherer(3)


