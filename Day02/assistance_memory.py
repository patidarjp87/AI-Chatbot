from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()

client = OpenAI(
    base_url=os.getenv("BASE_URL"),
    api_key=os.getenv("API_KEY")
)
memory = []
while True:
    user_input = input("You: ")
    memory.append({"role": "user", "content": user_input})
    if user_input.lower() == "exit":
        print("Exiting the chat. Goodbye!")
        break
    response = client.chat.completions.create(
        model=os.getenv("MODEL"), 
        messages=memory,
    reasoning_effort="none"
    )
    
    print("Actual message:", response.choices[0].message.content)

    memory.append({"role": "assistant", "content": response.choices[0].message.content})

print("Conversation history:", memory)