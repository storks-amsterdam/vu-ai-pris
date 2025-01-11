from typing import Any, Dict
import json

####################################
# 1) Imports from the Schnapsen code
####################################
from schnapsen.game import (
    GameState, Previous, RegularTrick, ExchangeTrick,
    Card, Rank, Suit, Hand, Talon, Move,
    BotState, Score, RegularMove,
    PlayerPerspective, LeaderPerspective,
    SchnapsenGamePlayEngine
)

##############################################################################
# 2) A function that gathers "initial state + deltas" from a PlayerPerspective
##############################################################################

def perspective_to_dict(persp: PlayerPerspective) -> Dict[str, Any]:
    """
    Convert the perspective's minimal known state into a dictionary.
    We'll store:
      - 'hand': list of card-strings
      - 'known_opponent_cards': list of card-strings
      - 'my_score': (direct_points, pending_points)
      - 'opponent_score': (direct_points, pending_points)
      - 'am_i_leader': bool
      - 'trump_suit': string
      - 'trump_card': string or None
      - 'talon_size': int
      - 'phase': 'ONE' or 'TWO'
    """
    hand_cards = [str(c) for c in persp.get_hand().get_cards()]
    known_opp_cards = [str(c) for c in persp.get_known_cards_of_opponent_hand().get_cards()]

    my_score = persp.get_my_score()
    opp_score = persp.get_opponent_score()

    trump_card = persp.get_trump_card()
    trump_card_str = str(trump_card) if trump_card else None

    return {
        "hand": hand_cards,
        "known_opponent_cards": known_opp_cards,
        "my_score": (my_score.direct_points, my_score.pending_points),
        "opponent_score": (opp_score.direct_points, opp_score.pending_points),
        "am_i_leader": persp.am_i_leader(),
        "trump_suit": str(persp.get_trump_suit()),
        "trump_card": trump_card_str,
        "talon_size": persp.get_talon_size(),
        "phase": persp.get_phase().name
    }

def compute_dict_diff(old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare two dictionary representations of a perspective and return
    only the fields that changed, mapped to their new values.
    """
    diff: Dict[str, Any] = {}
    for key, new_val in new_state.items():
        old_val = old_state.get(key, None)
        if new_val != old_val:
            diff[key] = new_val
    return diff

def trick_to_dict(trick) -> Dict[str, Any]:
    """
    Convert a Trick into a minimal dictionary describing the moves played.
    """
    if isinstance(trick, RegularTrick):
        return {
            "type": "RegularTrick",
            "leader_move": str(trick.leader_move),
            "follower_move": str(trick.follower_move),
            "cards_played": [str(c) for c in trick.cards],
        }
    elif isinstance(trick, ExchangeTrick):
        return {
            "type": "ExchangeTrick",
            "exchange": str(trick.exchange),
            "trump_card": str(trick.trump_card),
            "cards_played": [str(c) for c in trick.cards],
        }
    elif trick is not None:
        return {
            "type": "UnknownTrick",
            "cards_played": [str(c) for c in trick.cards],
        }
    else:
        return {}

def gather_deltas_from_history(perspective: PlayerPerspective) -> Dict[str, Any]: # deltas as in "initial state + changes", so that it doesnt save redundant information about previous states. Saves tokens, compute time
    """
    Return a dict with:
        {
            "initial_state": { ... all fields ... },
            "steps": [
               {
                 "index": i,
                 "diff": { ... what changed ... },
                 "trick": { ... if any ... },
                 "valid_moves": [ ... only on last step ... ]
               },
               ...
            ]
        }
    """
    history = perspective.get_game_history()
    if not history:
        return {
            "initial_state": {},
            "steps": []
        }

    # The first snapshot is the earliest perspective + trick
    first_persp, first_trick = history[0]
    prev_state_dict = perspective_to_dict(first_persp)

    data = {
        "initial_state": prev_state_dict,
        "steps": []
    }

    # Iterate from the second item onward
    for i in range(1, len(history)):
        curr_persp, curr_trick = history[i]
        curr_state_dict = perspective_to_dict(curr_persp)
        state_diff = compute_dict_diff(prev_state_dict, curr_state_dict)

        step_info = {
            "index": i,
            "diff": state_diff,
            "trick": trick_to_dict(curr_trick) if curr_trick else None
        }

        # If i == len(history) - 1 => last snapshot => gather valid moves
        if i == len(history) - 1:
            valid_moves_objects = []
            # we call perspective.valid_moves(), which will ask the game engine's validator.
            for mv in curr_persp.valid_moves():
                if mv.is_regular_move():
                    valid_moves_objects.append({
                        "type": "RegularMove",
                        "card": str(mv.as_regular_move().card)
                    })
                elif mv.is_marriage():
                    mar = mv.as_marriage()
                    valid_moves_objects.append({
                        "type": "Marriage",
                        "queen_card": str(mar.queen_card),
                        "king_card": str(mar.king_card)
                    })
                elif mv.is_trump_exchange():
                    te = mv.as_trump_exchange()
                    valid_moves_objects.append({
                        "type": "TrumpExchange",
                        "jack": str(te.jack)
                    })
            step_info["valid_moves"] = valid_moves_objects

        data["steps"].append(step_info)
        prev_state_dict = curr_state_dict

    return data


def game_rules() -> str:
    """
    Return a string with the rules of the game.
    """
    text = """
Overview
Schnapsen is a trick-taking game for two players. In this game, your opponent is the app bot.

A game consists of a series of deals, where a deal is won by the first player to score 66 points. During each deal, you collect cards by winning tricks. You get points for each collected card and for declaring a marriage, which is a king and queen of the same suit. For clarity we will call these trick points, because you score them while playing tricks. The first player to collect 66 trick points wins the deal.

Depending on the trick point scores at the end of the deal, each deal scores up to 3 points toward the game as a whole. We will call these game points to distinguish them from trick points. You win the game as a whole by being the first to score 7 game points.

The Deck
Our version uses the standard 4 French suits: diamonds, clubs, hearts, spades. Since Schnapsen has 5-card suits, it is played with a 20-card deck.

In Schnapsen there are 5 ranks in each suit:

Schnapsen ranks
Ace	11
Ten	10
King	4
Queen	3
Jack	2

The ranks are listed here from high (ace) to low (jack in Schnapsen). Note that the ten ranks above the king, as in many related games (such as Pinochle and Bezique). The trick point score for collecting each rank is also given. You score 11 trick points for collecting an ace, 10 for a ten, and so on.

The Deal
At the beginning of a deal, each player is dealt a hand of 5 cards. The remaining cards (exactly half the deck) make up the stock, and are used to replenish the hands as cards are played. One card of the stock (conceptually, the last card) is dealt face up. The suit of this face-up card is the trump suit for the deal. The notion of a trump suit is explained in the next section.

Tricks
Schnapsen is a trick-taking game. Once the cards are dealt, players compete in a series of rounds where they each play out one card from their hands face-up in the center of the table, forming a trick of two cards. One player's card wins the trick (explained below), and that player collects the two cards, places them face-down on his or her side of the table, and scores their trick points.

Playing the first card of a trick is called leading, the first card is called the lead, and the player leading is said to be on lead. The winner of a trick becomes the leader of the next trick. The leader of the first trick alternates from deal to deal during a game. The leader of the first trick of the first deal of the game alternates from game to game.

The suit of the face-up card of the stock is the trump suit for the deal. Cards of this suit outrank all other cards. Therefore, the rule for winning a trick is as follows:

If no card of the trump suit is part of the trick, the trick is won by the higher ranking card of the suit that was led. Otherwise the trick is won by the higher ranking trump.

Drawing from the Stock
In the first phase of the deal, you and your opponent each draw one card from the stock immediately following each trick. The first card is drawn by the winner of the trick, the second by the loser. As a result, during this first phase you both always have a full hand (5 cards). This style of play is called trick-and-draw.

Ordinarily, play continues this way until one player claims 66, or until all the cards of the stock have been drawn. Note that the very last card drawn from the stock will be the face-up trump card. Since this is a valuable card and it goes to the loser of the immediately preceding trick, there is often a dilemma about deciding whether to win or lose that trick.

The second phase of the deal begins when the stock is exhausted, meaning that all the cards have been drawn from it. You and your opponent continue playing cards from your hands without drawing. The play then continues in this way until one of you wins, or until all the cards are played.

Following Suit
As in most trick-taking games, when you are the leader of a trick, you may play any card in your hand. However, Schnapsen is a little unusual in that the rules for the second card of a trick are different in the two phases of the deal.

In the first phase of the deal, when the stock is open, there is no requirement to follow suit. When playing the second card of a trick, you may play any card from your hand.

In the second phase, when the stock is closed or exhausted, you must follow suit and win the trick, if possible, when playing the second card of a trick. More precisely,

If you have any card of the led suit that is higher than the one led, you must play such a card.
If not, if you have any lower card of the led suit, you must play such a card.
If not, if you have any trump, you must play a trump.
If not, you may play any card.
This two-phase pattern gives the games much of their distinctive flavor. In many deals, you spend the freer first phase working to get your hand into a shape that will win in the second phase, when the play of your opponent can be controlled a bit more.

Exchanging Trump
If the stock is still open after both players have drawn replacement cards for the previous trick, the leader of the upcoming trick may exchange the lowest-ranking trump (if that player has it in hand) for the face-up trump in the stock. This must be done prior to the lead. In Schnapsen, you exchange the jack in your hand for the face-up trump.

You may do this exchange any time the stock is open, both players have drawn replacement cards for the previous trick, and you are the leader to the next trick. This includes exchanging before the very first trick (when you have not even won a trick yet) and before the last open-stock trick, when only one face-down card remains in the stock. (After you win the last open-stock trick, you may not exchange the trump before both players have drawn replacement cards, even though you are the leader to the next trick.)

To exchange the trump in Master Schnapsen/66, you drag the low trump from your hand and drop it on the face-up trump. You can also drag the face-up trump and drop it in your hand.

Strategically speaking, you should always exchange the low trump if you have it and you are on lead. It always improves your hand, sometimes significantly.

Marriages
If you have both the king and queen of a suit in your hand and you are the leader for the upcoming trick, you may show the king and queen to declare a marriage, which adds to your trick points. This is done prior to leading a card, but after both players have drawn replacement cards from the stock for the previous trick. Declaring a marriage is also called melding. When you declare a marriage, you must lead either the king or queen from the marriage immediately. The trick point values of marriages are as follows:

Trick points for marriage
Marriage in trump suit	40
Marriage in any other suit	20
When playing with real cards, you show both marriage cards to your opponent when declaring a marriage, and then lead one and return the other to your hand. In Master Schnapsen/66, the program will show you both cards. But you (the human player) do not need to do anything special; you score the points just for leading the king or queen. If for some reason you want to lead one of them without declaring the marriage, two quick taps on either marriage partner disables the marriage. Any interaction other than leading one of the marriage partners re-enables the marriage. An enabled marriage is shown by a double bar connecting the marriage partners, and a disabled marriage by a broken double bar.

You may only declare one marriage per trick. In Schnapsen, you may declare a marriage whenever you are on lead.

The trick points for a marriage are scored immediately. If the player declaring the marriage claims 66, the deal ends at that point without finishing the trick.

Last Trick
If the stock is exhausted, and all cards are played from both hands, the winner of the last trick receives a bonus. In Schnapsen, the winner of the last trick wins the entire deal. Note that there is no bonus if the stock is closed, as that prevents the stock from being exhausted.

There is often jockeying near the end of the deal in order to win the last trick.

Scoring Game Points
The deal ends as soon as one of the players claims 66. This can happen just after the declaration of a marriage (but only by the player declaring the marriage). Otherwise it happens at the end of a trick by the winner of the trick, when the collected cards and the last trick bonus (if applicable) are scored.

The player who correctly claims 66 (or takes the last trick in Schnapsen with the stock exhausted) wins game points as explained below. You need 7 game points in total to win the whole game. It is traditional to keep track of the game points by counting down from 7 to 0. That is, both players start with a tally of 7, and the game points you win are subtracted from your tally. If the newly awarded game points bring either player’s tally to 0 or less, that player wins the entire game. Otherwise, you play another deal.

Game Points When the Stock Was Not Closed
Assuming the stock was not closed, the winner is awarded game points as follows:

Awarded to winner
Loser took no tricks	3
Loser's tricks and marriages add to fewer than 33 trick points	2
Loser's tricks and marriages add to at least 33 trick points	1
Note that if the loser declared a marriage at trick 1 but never took a trick, the deal is worth 3 game points, not 2.

Also note that you win more game points for winning by a wider margin. This means it is sometimes worth taking a risk to get an early win. Similarly, if it looks as though you will lose a deal, it is worthwhile trying to get at least 33 trick points in your tricks to avoid giving up 2 game points.

Game Points When the Stock Was Closed
Let us call the player who closes the stock the “closer” and the other player the “noncloser”. When a player closes the stock, the game points at stake for this deal are determined entirely by the number of trick points in the noncloser’s tricks at the moment the stock was closed. If the closer wins the deal (meaning the closer correctly claims 66 before the noncloser does, with no last trick bonus), then game points are awarded to the closer analogously to the table above:

Awarded to closer
Noncloser had no tricks when stock was closed	3
Noncloser’s tricks and marriages added to fewer than 33 trick points when stock was closed	2
Noncloser’s tricks and marriages added to at least 33 trick points when stock was closed	1
If the noncloser wins the deal (meaning the closer failed to claim 66 correctly, or the noncloser correctly claimed 66 first), then game points are awarded to the noncloser according to the table below:

Awarded to noncloser
Noncloser had no tricks at the time the stock was closed	3
Otherwise	2
Note that a player scores at least 2 game points for winning the deal when the opponent has closed the stock. The closer pays this penalty for closing and not winning.

Quick Summary
There are more different plays in Schnapsen than in most other trick-taking games. Here is a summary of what you may do when it is your turn to play.

When leading
If the stock is still open, you may exchange the lowest trump (jack). You may do either or both of these.

Whether or not you exchanged the trump or closed the stock, you may declare a marriage and score its trick points immediately. You may then claim 66. If you do not claim 66, you must lead either the king or queen from the marriage. In Schnapsen you may declare a marriage whether the stock is open or not.

If you have not declared a marriage, you may lead any card from your hand.

When playing second
If the stock is open, you may play any card.

If the stock is closed or exhausted, you must follow suit and win if possible, or else follow suit and lose if possible, or else trump if possible. Otherwise you may play any card.

The winner of the trick may now claim 66. If not, immediately after the winner of the trick collects it, each player draws a replacement card from the stock, assuming the stock is open.

Each trick therefore consists of three phases that occur in the following order:

Any combination of optional allowable leader actions (exchange trump, close stock, declare marriage) that precede the trick.
Next, each player plays a card to the trick.
Next, each player draws a replacement card, if the stock is open.
"""
    return text