import random

from schnapsen.bots import RandBot, RdeepBot, BullyBot
from schnapsen.game import SchnapsenGamePlayEngine, Bot

from schnapsen_llm_bench.bot import LlmBot

engine = SchnapsenGamePlayEngine()


def play_game(bot1, bot2):
    winner_id, game_points, score = engine.play_game(bot1, bot2, random.Random())
    print(f"Game ended. Winner is {winner_id} with {game_points} points and {score}")


def play_tournament(bot1: Bot, bot2: Bot, rounds: int = 10) -> None:
    bots = [bot1, bot2]
    n = len(bots)
    wins = {str(bot): 0 for bot in bots}
    matches = [(p1, p2) for p1 in range(n) for p2 in range(n) if p1 < p2]

    totalgames = (n * n - n) / 2 * rounds
    playedgames = 0

    print("Playing {} games:".format(int(totalgames)))
    for a, b in matches:
        for r in range(rounds):
            if random.choice([True, False]):
                p = [a, b]
            else:
                p = [b, a]

            winner_id, game_points, score = engine.play_game(
                bots[p[0]], bots[p[1]], random.Random(45)
            )

            wins[str(winner_id)] += game_points

            playedgames += 1
            print(
                "Played {} out of {:.0f} games ({:.0f}%): {} \r".format(
                    playedgames, totalgames, playedgames / float(totalgames) * 100, wins
                )
            )


if __name__ == "__main__":
    # choose the players
    rand_bot = RandBot(rand=random.Random(42), name="randbot")
    llm_bot = LlmBot()
    bully_bot = BullyBot(rand=random.Random(42), name="bullybot")

    # play the game
    # play_game(bot1, bot2)

    # play the tournament
    play_tournament(llm_bot, rand_bot, rounds=10)