from typing import Optional, Literal
import json
import random
from datetime import datetime

from schnapsen.game import Bot, PlayerPerspective, Move, SchnapsenTrickScorer, Score
from schnapsen.deck import Suit, Card, Rank

from schnapsen_llm_bench.utils import perspective_to_dict, gather_deltas_from_history, game_rules, game_winning_strategy
from schnapsen_llm_bench.llm import chat_completion, text_to_move
from schnapsen_llm_bench.db import get_cosmos_client, get_pg_connection

from pydantic import BaseModel

def card_to_dict(card: Card) -> dict:
    return {
        "rank": card.rank.name,
        "suit": card.suit.name
    }

class CardMove(BaseModel):
    rank: Literal["ACE", "TEN", "JACK", "QUEEN", "KING"]
    suit: Literal["CLUBS", "DIAMONDS", "HEARTS", "SPADES"]
    type: Literal["RegularMove", "Marriage", "TrumpExchange"]


class LlmBot(Bot):
    """
    This Bot is here to serve as an example of the different methods the PlayerPerspective provides.
    In the end it is just playing the first valid move.
    """
    def __init__(self, name: Optional[str] = 'LlmBot', model: str = "gpt-4o-mini") -> None:
        super().__init__(name)
        self.model = model
        self.match_id = None
        self.turn = 1
        self.invalid_moves = 0
        self.completion_times = []
        self.cosmos_client = get_cosmos_client()
        self.db = self.cosmos_client.get_database_client("bench")
        self.container = self.db.get_container_client("turns")

    def __str__(self) -> str:
        """
        A string representation of the Bot. If the bot was constructed with a name, it will be that name.
        Otherwise it will be the class name and the memory address of the bot.

        :returns: (str): A string representation of the bot.
        """
        return self.model

    def get_move(self, perspective: PlayerPerspective, leader_move: Optional[Move]) -> Move:

        leader = perspective.am_i_leader()
        score = perspective.get_my_score()
        opponent_score = perspective.get_opponent_score()
        won_cards = perspective.get_won_cards()
        opponent_won_cards = perspective.get_opponent_won_cards()
        my_hand = perspective.get_hand()
        game_phase = perspective.get_phase().value
        # Get valid moves
        valid_moves: list[Move] = perspective.valid_moves()

        valid_moves_json = [
            {
                "suit": card.suit.name,
                "rank": card.rank.name,
                "type": move.__class__.__name__
            } for move in valid_moves for card in move.cards
        ]

        # get match_id from game_state
        match_id = self.match_id

        # get prompts history from cosmos
        previous_turn = None
        if self.turn > 1:
            previous_turn = self.container.read_item(
                    item=f"{str(match_id)}-{self.model}-{self.turn - 1}",
                    partition_key=str(match_id)
                )
            
            messages = previous_turn.get('Prompt')

        else:

            messages = [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "text",
                            "text": "You are a card playing AI. You are helping to play a game of Schnapsen against another player. You are given game persepctive from a user, and available moves. Your task is to select the best move."
                            + game_rules()
                            + game_winning_strategy()
                        }
                    ]
                }
            ]

        turn_text = (
                "It's your turn. You have " + str(score.direct_points) + " points. You have won the following cards: " + str(won_cards)
                  + ". Your opponent has " + str(opponent_score.direct_points) + " points and won the following cards: " + str(opponent_won_cards) + "."
                  + " You are holding the following cards: " + json.dumps([card_to_dict(card) for card in my_hand]) + "."
                  + " Valid moves are: " + json.dumps(valid_moves_json) + "."
        )
        
        
        if game_phase == 2:
            turn_text += "The opponent has these cards in hand: " + json.dumps([card_to_dict(card) for card in perspective.get_opponent_hand_in_phase_two()]) + "."
        
        
        if leader:
            user_text = (
                turn_text
                + "You are the leader. Choose a card you want to play. Specify the card rank, suit and the move type."
            )
        else:
            user_text = (
                turn_text
                + "You are the follower."
                + "The leader played the following card: " + str(card_to_dict(leader_move.cards[0])) + f" as {leader_move.__class__.__name__}."
                + "Choose a card you want to play. Specify the card rank, suit and the move type."
            )
            
        messages.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": user_text
                        }
                    ]
                }
        )

        returned_valid_move = False

        invalid_moves = 0
        while not returned_valid_move:

            ### chat completion logic ###### 
            print("Running completion")
            # add timing calculation
            start_time = datetime.now()

            # Run completion
            completion = chat_completion(messages, self.model)

            end_time = datetime.now()

            duration = end_time - start_time
            print("Completion time:", duration)
            self.completion_times.append(int(duration.total_seconds() * 1000))

            llm_move_text = text_to_move(completion.choices[0].message.content)

            llm_move = CardMove.model_validate_json(llm_move_text)

            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": llm_move_text
                        }
                    ]
                }
            )


            selected_move = False

            for move in valid_moves:
                if llm_move.type == move.__class__.__name__:
                    for card in move.cards:
                        if llm_move.rank == card.rank.name and llm_move.suit == card.suit.name:
                            selected_move = move
                            # print("Selected move:", selected_move)
            

            if not selected_move:
                if invalid_moves > 5:
                    print("LLM returned too many invalid moves. Selecting a random move.")
                    selected_move = random.choice(valid_moves)
                    break
                print("LLM returned an invalid move:")
                print("\t", llm_move)
                self.invalid_moves += 1
                invalid_moves += 1
                # print("Valid moves are:")
                # for move in valid_moves:
                #     print("\t", move)
                # selected_move = random.choice(valid_moves)
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "The move you selected is not valid. Please choose a valid move."
                                    + " Valid moves are: " + json.dumps(valid_moves_json) + "."
                                )
                            }
                        ]
                    }
                )

            else:
                returned_valid_move = True

        # save move and promt to cosmos

        item = {
            "id": f"{str(match_id)}-{self.model}-{self.turn}",
            "MatchId": str(match_id),
            "Turn": self.turn,
            "InvalidMoves": self.invalid_moves,
            "Model": self.model,
            "Prompt": messages,
            "Move": {
                "suit": selected_move.cards[0].suit.name,
                "rank": selected_move.cards[0].rank.name,
                "type": selected_move.__class__.__name__
            }
        }

        response = self.container.create_item(body=item)
        self.turn += 1

        print("Selected move:", selected_move)
        return selected_move
    

    def notify_game_end(self, won: bool, perspective: PlayerPerspective) -> None:
        """
        The engine will call this method when the game ends.
        Override this method to get notified about the end of the game.

        :param won: (bool): Did this bot win the game?
        :param perspective: (PlayerPerspective) The final perspective of the game.
        """

        # get game state from cosmos
        match_id = self.match_id
        container = self.db.get_container_client("matches")
        match_item = container.read_item(item=str(match_id), partition_key=str(match_id))

        match_item[self.model] = {
            "turns": self.turn,
            "invalid_moves": self.invalid_moves,
            "completion_times": [time for time in self.completion_times],
            "avg_completion_time": sum(self.completion_times)/len(self.completion_times),
            "score": perspective.get_my_score().direct_points,
            "won": won
        }

        # write to postresql
        with get_pg_connection() as conn:

            cur = conn.cursor()

            # create table if not exists
            cur.execute(
                """CREATE TABLE IF NOT EXISTS matches_stats (
                    match_id UUID,
                    leader TEXT,
                    follower TEXT,
                    model TEXT,
                    won BOOLEAN,
                    score INT,
                    opponent_score INT,
                    turns INT,
                    invalid_moves INT,
                    avg_completion_time FLOAT,
                    created_at TIMESTAMP
                )"""
            )

            cur.execute(
                """INSERT INTO matches_stats (
                    match_id, leader, follower, model, won, score, opponent_score, turns, invalid_moves, avg_completion_time, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (
                    match_id,
                    match_item['GameState']['Leader']['Implementation'],
                    match_item['GameState']['Follower']['Implementation'],
                    self.model,
                    won,
                    perspective.get_my_score().direct_points,
                    perspective.get_opponent_score().direct_points,
                    self.turn,
                    self.invalid_moves,
                    sum(self.completion_times)/len(self.completion_times)
                )
            )

            conn.commit()
            cur.close()
            conn.close()

        self.turn = 1
        self.invalid_moves = 0
        self.completion_times = []

        print(f"Game ended. {self.model} {'won' if won else 'lost'} with {perspective.get_my_score()} points and {perspective.get_opponent_score()} points for the opponent.")