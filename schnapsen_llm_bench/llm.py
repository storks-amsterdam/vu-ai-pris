  
import os
from typing import Literal
from pydantic import BaseModel
from openai import OpenAI, AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from mistralai_azure import MistralAzure

import dotenv

dotenv.load_dotenv()


endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")  
subscription_key = os.getenv("AZURE_OPENAI_API_KEY")  
openai_api_key = os.getenv("OPENAI_API_KEY")
model_endpoint = os.getenv("AZURE_MODEL_ENDPOINT")
endpoint_east_us = os.getenv("AZURE_OPENAI_ENDPOINT_EAST_US")


# Initialize Azure OpenAI Service client with Entra ID authentication
token_provider = get_bearer_token_provider(  
    DefaultAzureCredential(),  
    "https://cognitiveservices.azure.com/.default"
)

llama_client = AzureOpenAI(
    azure_endpoint=model_endpoint,
    api_key=subscription_key,
    api_version="2024-05-01-preview",  
)

mistral_client = AzureOpenAI(
    azure_endpoint=model_endpoint,
    api_key=subscription_key,
    api_version="2024-05-01-preview",
)


gpt_4o_mini_client = AzureOpenAI(
    azure_endpoint=endpoint,
    api_key=subscription_key,
    api_version="2024-08-01-preview",  
)

gpt_4o_client = AzureOpenAI(
    azure_endpoint=endpoint_east_us,
    api_key=os.getenv("AZURE_OPENAI_API_KEY_EAST_US"),  
    api_version="2024-08-01-preview",
)

openai_client = OpenAI(api_key=openai_api_key)


class CardMove(BaseModel):
    rank: Literal["ACE", "TEN", "JACK", "QUEEN", "KING"]
    suit: Literal["CLUBS", "DIAMONDS", "HEARTS", "SPADES"]
    type: Literal["RegularMove", "Marriage", "TrumpExchange"]


def text_to_move(text) -> CardMove:

    system_prompt = ( "You are a text to json validator. Validate user input into a structured format (if it is not already in the right format)."
                     + "The format is a json with three keys: 'suit', 'rank', and 'type'."
                     + " Suit value is one of : 'CLUBS', 'DIAMONDS', 'HEARTS', 'SPADES'."
                     + " Rank value is one of : 'ACE', 'TEN', 'JACK', 'QUEEN', 'KING'."
                     + " Type value is one of : 'RegularMove', 'Marriage', 'TrumpExchange'."
                     + " Do not create new values, and do not change the values. Make sure the output is based on the user input."
    )

    messages = [
        {
            "role": "system",
            "content": [{
                    "type": "text",
                    "text": str(system_prompt)
                }],
        },
        {
            "role": "user",
            "content": [{
                    "type": "text",
                    "text": str(text)
                }],
        },
    ]

    completion = None
    while completion is None:
        try:
            completion = gpt_4o_mini_client.beta.chat.completions.parse(
                model="gpt-4o-mini",  
                messages=messages,
                max_tokens=150,  
                temperature=0.0,
                top_p=0.95,  
                frequency_penalty=0,  
                presence_penalty=0,  
                stop=None,  
                # stream=False,
                response_format=CardMove,
            )
        except Exception as e:
            print(e)


    return completion.choices[0].message.content


  
def chat_completion(messages, model):

    if model == "gpt-4o-mini":
        client = gpt_4o_mini_client

        completion = client.chat.completions.create(  
            model=model,  
            messages=messages
        )

        return completion

    if model in ["gpt-4", "gpt-4o"]:
        client = gpt_4o_client

        completion = client.chat.completions.create(  
            model=model,  
            messages=messages
        )

        return completion

    if model in ["o1-mini", "o1-preview"]:

        messages[0] = {
            "role": "user",
            "content": messages[0]["content"]
        }

        client = openai_client

        completion = client.chat.completions.create(  
            model=model,  
            messages=messages
        )

        return completion
    
    if model in ["Cohere-command-r-plus-08-2024",
        "Ministral-3B",
        "Mistral-Large-2411",
        "Mistral-small",
        "Phi-3.5-mini-instruct",
        "Phi-3.5-MoE-instruct",
        "Phi-4"]:

        new_messages = []
        for message in messages:
            new_messages.append({
                "role": message["role"],
                "content": message["content"][0]["text"]
            })

        client = mistral_client

        completion = client.chat.completions.create(  
            model=model,  
            messages=new_messages,
            temperature=0.7,
            stop=None,  
            stream=False
        )
        return completion
    
    if model in ["Llama-3.3-70B-Instruct", "Meta-Llama-3.1-405B-Instruct"]:

        new_messages = []
        for message in messages:
            new_messages.append({
                "role": message["role"],
                "content": message["content"][0]["text"]
            })

        client = llama_client

        completion = client.chat.completions.create(  
            model=model,  
            messages=new_messages,
            max_completion_tokens=100,
            temperature=0.7,  
            top_p=0.95,  
            frequency_penalty=0,  
            presence_penalty=0,
            stop=None,  
            stream=False  
        )

        return completion
