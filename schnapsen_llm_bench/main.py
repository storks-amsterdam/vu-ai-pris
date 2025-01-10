import random

from schnapsen.bots import RandBot, RdeepBot
from schnapsen.game import SchnapsenGamePlayEngine

from bot import LlmBot



engine = SchnapsenGamePlayEngine()
# choose the players
bot1 = RandBot(rand=random.Random(42), name="randbot")
bot2 = LlmBot()

# play the game
winner_id, game_points, score = engine.play_game(bot1, bot2, random.Random(44))
print(f"Game ended. Winner is {winner_id} with {game_points} points and {score}")