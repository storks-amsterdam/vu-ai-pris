import random
import argparse

from schnapsen.bots import RandBot, RdeepBot, BullyBot
from schnapsen.game import SchnapsenGamePlayEngine, Bot

from schnapsen_llm_bench.bot import LlmBot
from schnapsen_llm_bench.game import BenchEngine

engine = BenchEngine()


models = [
    "Cohere-command-r-plus-08-2024",
    "Llama-3.3-70B-Instruct",
    "Meta-Llama-3.1-405B-Instruct",
    "Ministral-3B",
    "Mistral-Large-2411",
    "Mistral-small",
    "Phi-3.5-mini-instruct",
    "Phi-3.5-MoE-instruct",
    "Phi-4",
    "gpt-4",
    "gpt-4o",
    "gpt-4o-mini",
    "o1-preview",
    "o1-mini"
]


def play_game(bot1, bot2):
    winner_id, game_points, score = engine.play_game(bot1, bot2, random.Random(42))
    print(f"Game ended. Winner is {winner_id} with {game_points} points and {score}")


def play_tournament(bot1: Bot, bot2: Bot, rounds: int = 10, seed = 42) -> None:
    bots = [bot1, bot2]
    n = len(bots)
    wins = {str(bot): 0 for bot in bots}
    matches = [(p1, p2) for p1 in range(n) for p2 in range(n) if p1 < p2]

    totalgames = (n * n - n) / 2 * rounds
    playedgames = 0

    rng = random.Random(seed)

    print("Playing {} games:".format(int(totalgames)))
    for a, b in matches:
        for r in range(rounds):
            if random.choice([True, False]):
                p = [a, b]
            else:
                p = [b, a]

            try:
                winner_id, game_points, score = engine.play_game(
                    bots[p[0]], bots[p[1]], rng
                )
            except Exception as e:
                print("Exception in game:", e)
                continue

            wins[str(winner_id)] += game_points

            playedgames += 1
            print(
                "Played {} out of {:.0f} games ({:.0f}%): {} \r".format(
                    playedgames, totalgames, playedgames / float(totalgames) * 100, wins
                )
            )


def main(models, rounds, seed):
    # choose the players
    rand_bot = RandBot(rand=random.Random(seed), name="randbot")
    rdeep_bot = RdeepBot(num_samples=10, depth=5, rand=random.Random(seed), name="rdeepbot")
    bully_bot = BullyBot(rand=random.Random(seed), name="bullybot")

    bot1 = LlmBot(model=models[0])
    if models[1] == "randbot":
        bot2 = rand_bot
    elif models[1] == "rdeepbot":
        bot2 = rdeep_bot
    elif models[1] == "bullybot":
        bot2 = bully_bot
    else:
        bot2 = LlmBot(model=models[1])

    # play the tournament
    play_tournament(bot1, bot2, rounds=rounds, seed=44)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Schnapsen LLM Bench")
    parser.add_argument(
        "--model", 
        type=str,
        default="gpt-4o-mini", 
        help="Name of model to use"
    )
    parser.add_argument(
        "--opponent", 
        type=str,
        default="randbot", 
        help="Name of opponent to use"
    )
    parser.add_argument(
        "--rounds", 
        type=int, 
        default=10, 
        help="Number of rounds to play"
    )
    parser.add_argument(
        "--seed", 
        type=int, 
        default=42, 
        help="Random seed"
    )

    args = parser.parse_args()

    main([args.model, args.opponent], args.rounds, args.seed)

