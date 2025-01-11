from typing import Optional, Literal
import json
import random

from schnapsen.game import Bot, PlayerPerspective, Move, SchnapsenTrickScorer, Score
from schnapsen.deck import Suit, Card, Rank

from schnapsen_llm_bench.utils import perspective_to_dict, gather_deltas_from_history, game_rules
from schnapsen_llm_bench.calling_llm import client

from pydantic import BaseModel


class CardMove(BaseModel):
    rank: Literal["ACE", "TEN", "JACK", "QUEEN", "KING"]
    suit: Literal["CLUBS", "DIAMONDS", "HEARTS", "SPADES"]
    type: Literal["REGULAR", "MARRIAGE", "TRUMP_EXCHANGE"]


class LlmBot(Bot):
    """
    This Bot is here to serve as an example of the different methods the PlayerPerspective provides.
    In the end it is just playing the first valid move.
    """
    def __init__(self, name: Optional[str] = 'LlmBot', deployment: str = "gpt-4o-mini") -> None:
        super().__init__(name)
        self.deployment = deployment

    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move]) -> Move:
        # You can get information on the state from your perspective
        # print(perspective.am_i_leader())
        # print(perspective.get_my_score())
        # print(perspective.get_opponent_won_cards())
        # # more methods in the documentation

        # print(perspective_to_dict(perspective))
        perspective_dict = perspective_to_dict(perspective)

        history_dict = perspective.get_game_history()

        if leader_move is not None:
            # You can get the cards that were played in the last trick
            # print(leader_move.cards)
            pass

        # Get valid moves
        moves: list[Move] = perspective.valid_moves()

        chat_prompt = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You are a card playing AI. You are helping to play a game of Schnapsen against another player. You are given game persepctive from a user, and available moves. Your task is to select the best move."
                        + game_rules()
                        + "The game has special moves: 'MARRIAGE' and 'TRUMP_EXCHANGE'. A marriage is a pair of cards: a queen and a king of the same suit. A trump exchange is a jack of trumps."
                        + "The output should be a move that is valid in the current game state.The format is a json with three keys: 'suit', 'rank', and 'type'."
                        + " suit value is one of : 'CLUBS', 'DIAMONDS', 'HEARTS', 'SPADES'."
                        + " rank value is one of : 'ACE', 'TEN', 'JACK', 'QUEEN', 'KING'."
                        + " type value is one of : 'REGULAR', 'MARRIAGE', 'TRUMP_EXCHANGE'."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Here is the game perspective: " + json.dumps(perspective_dict)
                        +  f"You are the follower. The leader played: {leader_move.to_json()}" if leader_move is not None else "You are the leader. "
                        + "Select the right move from the following list of moves: " + json.dumps([move.to_json() for move in moves])
                    }
                ]
            }
        ] 
            
        # Include speech result if speech is enabled  
        messages = chat_prompt 


        print("Running completion")
        # completion = client.chat.completions.create(  
        #     model=self.deployment,  
        #     messages=messages,
        #     max_tokens=10000,  
        #     temperature=0.7,  
        #     top_p=0.95,  
        #     frequency_penalty=0,  
        #     presence_penalty=0,  
        #     stop=None,  
        #     stream=False  
        # )

        completion = client.beta.chat.completions.parse(
            model=self.deployment,  
            messages=messages,
            max_tokens=10000,  
            temperature=0.7,  
            top_p=0.95,  
            frequency_penalty=0,  
            presence_penalty=0,  
            stop=None,  
            # stream=False,
            response_format=CardMove,
        )

        llm_move = completion.choices[0].message.parsed
        # print(llm_move)
            
        # print(completion.to_json())  
        # print(completion.choices[0].message)

        for move in moves:
            for card in move.cards:
                if card.rank == Rank[llm_move.rank] and card.suit == Suit[llm_move.suit]:

                    if llm_move.type == "TRUMP_EXCHANGE":
                        if not move.is_trump_exchange():
                            continue
                        print("Playing a trump exchange:", move)
                        return move
                    
                    if llm_move.type == "MARRIAGE":
                        if not move.is_marriage():
                            continue
                        print("Playing a marriage:", move)
                        return move
                    
                    print("Playing a Regular move:", move)
                    return move

        print("LLM returned an invalid move")
        return random.choice(moves)
    

    def notify_game_end(self, won: bool, perspective: PlayerPerspective) -> None:
        """
        The engine will call this method when the game ends.
        Override this method to get notified about the end of the game.

        :param won: (bool): Did this bot win the game?
        :param perspective: (PlayerPerspective) The final perspective of the game.
        """
        print(f"Game ended. {'LLM won' if won else 'LLM lost'} with {perspective.get_my_score()} points and {perspective.get_opponent_score()} points for the opponent.")