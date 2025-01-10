  
import os  
from openai import AzureOpenAI
        
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  
deployment = os.getenv("DEPLOYMENT_NAME", "gpt-4o-mini")  
subscription_key = os.getenv("AZURE_OPENAI_API_KEY")  

# Initialize Azure OpenAI client with key-based authentication    
client = AzureOpenAI(  
    azure_endpoint=endpoint,  
    api_key=subscription_key,  
    api_version="2024-08-01-preview",  
)

chat_prompt = [
    {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": "You are a card playing AI. You are playing a game of Schnapsen against another player."
            }
        ]
    },
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": " I am playing a game of schnapsen, what's the best strategy/approach?"
            }
        ]
    }
] 
    
# Include speech result if speech is enabled  
messages = chat_prompt 

completion = client.chat.completions.create(  
    model=deployment,  
    messages=messages,
    max_tokens=10000,  
    temperature=0.7,  
    top_p=0.95,  
    frequency_penalty=0,  
    presence_penalty=0,  
    stop=None,  
    stream=False  
)  
  
print(completion.to_json())  
print(completion.choices[0].message)