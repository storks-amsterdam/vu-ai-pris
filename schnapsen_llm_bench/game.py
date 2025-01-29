from schnapsen.game import SchnapsenGamePlayEngine, GameState, Bot, BotState, Score
import uuid
from random import Random
from datetime import datetime
from azure.cosmos import CosmosClient

from schnapsen_llm_bench.db import get_cosmos_client, get_pg_connection
from schnapsen_llm_bench.utils import card_to_dict


class BenchBotState(BotState):
    def __init__(self, implementation: Bot, hand: list, match_id: uuid.UUID):
        super().__init__(implementation, hand)
        self.match_id: uuid.UUID = match_id
        # self.cosmos_client: CosmosClient = get_cosmos_client()
        # self.db = self.cosmos_client.get_database_client("bench")
        # self.container = self.db.get_container_client("turns")


class BenchGameState(GameState):
    def __init__(self, leader: BotState, follower: BotState, talon: list, previous: GameState, match_id: uuid.UUID):
        super().__init__(leader, follower, talon, previous)
        self.match_id: uuid.UUID = match_id
        self.created_at = datetime.now()
        self.cosmos_client: CosmosClient = get_cosmos_client()
        self.db = self.cosmos_client.get_database_client("bench")
        self.container = self.db.get_container_client("turns")

    def to_dict(self) -> dict:
        return {
            'Leader': {
                'Implementation': str(self.leader.implementation),
                'Hand': [card_to_dict(card) for card in self.leader.hand]
            },
            'Follower': {
                'Implementation': str(self.follower.implementation),
                'Hand': [card_to_dict(card) for card in self.follower.hand]
            },

            'Talon': [card_to_dict(card) for card in self.talon],
            'Previous': self.previous if self.previous is not None else None,
            'MatchId': str(self.match_id),
            'CreatedAt': str(self.created_at)
        }


class BenchEngine(SchnapsenGamePlayEngine):

    def __init__(self):
        super().__init__()
        self.cosmos_client: CosmosClient = get_cosmos_client()
        self.db = self.cosmos_client.get_database_client("bench")
        self.container = self.db.get_container_client("matches")
        self.pg_conn = get_pg_connection()

    def play_game(self, bot1: Bot, bot2: Bot, rng: Random) -> tuple[Bot, int, Score]:
        """
        Play a game between bot1 and bot2, using the rng to create the game.

        :param bot1: The first bot playing the game. This bot will be the leader for the first trick.
        :param bot2: The second bot playing the game. This bot will be the follower for the first trick.
        :param rng: The random number generator used to shuffle the deck.

        :returns: A tuple with the bot which won the game, the number of points obtained from this game and the score attained.
        """
        # for reproducibility
        seed = datetime.now().timestamp()
        rng.seed(seed)
        rng_state = rng.getstate()
        match_id = uuid.uuid4()

        cards = self.deck_generator.get_initial_deck()
        shuffled = self.deck_generator.shuffle_deck(cards, rng)
        hand1, hand2, talon = self.hand_generator.generateHands(shuffled)

        if bot1.__class__.__name__ == 'LlmBot':
            bot1.match_id = match_id

        if bot2.__class__.__name__ == 'LlmBot':
            bot2.match_id = match_id

        leader_state = BotState(implementation=bot1, hand=hand1)
        follower_state = BotState(implementation=bot2, hand=hand2)

        game_state = BenchGameState(
            leader=leader_state,
            follower=follower_state,
            talon=talon,
            previous=None,
            match_id=match_id
        )

        match_item = self.container.create_item(
            body={
                'id': str(match_id),
                'MatchId': str(match_id),
                'GameState': game_state.to_dict(),
                'CreatedAt': str(game_state.created_at),
                'Seed': seed,
                # 'RngState': rng_state,
            }
        )

        print(f"Match created with id {match_id}")
        print("Leader", bot1)
        print("Follower", bot2)
        
        winner, points, score = self.play_game_from_state(game_state=game_state, leader_move=None)

        # update the match with the winner
        match_item['Winner'] = str(winner)
        match_item['Points'] = points
        match_item['Score'] = score.direct_points

        return winner, points, score