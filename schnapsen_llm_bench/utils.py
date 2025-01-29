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


def card_to_dict(card: Card) -> Dict[str, Any]:
    """
    Convert a Card into a dictionary.
    """
    return {
        "rank": card.rank.name,
        "suit": card.suit.name
    }


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
Schnapsen is a two-player trick-taking game played with a 20-card deck (Ace, Ten, King, Queen, Jack in each suit).

A game consists of a series of deals. During each deal, you collect cards by winning tricks.

**Goal**: Collect at least 66 trick points before your opponent. Each deal continues until one player claims 66 or all cards are played. Depending on the trick points scored at the end of the deal, the winner of the deal scores 1 to 3 “game points,” and the first to 7 game points wins overall.

You get points for each collected card and for declaring a _marriage_, which is a king and queen of the same suit.

**Card Points**:
- Ace = 11
- Ten = 10
- King = 4
- Queen = 3
- Jack = 2

**Marriage points:**
- 20 points, or 40 if it's trump suit. Details on this special move follow below, under the section Special Moves.

**Gameplay**:
1. Each player starts with 5 cards. The remaining 10 go face-down in the stock, with the last card face-up to indicate the trump suit. Cards of this suit outrank all other cards. Therefore, the rule for winning a trick is as follows:

> If no card of the trump suit is part of the trick, the trick is won by the higher ranking card of the suit that was led. Otherwise the trick is won by the higher ranking trump.

2. **Leader Player**:
   - Playing the first card of a trick is called _leading_, the first card is called the _lead_, and the player leading is said to be _on lead_. The winner of a trick becomes the leader of the next trick. The leader of the first trick alternates from deal to deal during a game. The leader of the first trick of the first deal of the game alternates from game to game.

4. **Phase 1 (Stock is Open)**:
   - After each trick, the trick winner draws the top card of the stock, then the loser draws the next card. As a result, in this first phase both players have a full hand (5 cards each).
   - No requirement to follow suit. Any card can be played second.

5. **Phase 2 (Stock is Closed or Exhausted: all cards have been drawn from it)**:
   - You must follow suit if possible:
     1. If you can beat the opponent's card with a higher card of the same suit, you must do so.
     2. Otherwise, if you have a lower card of the same suit, play that.
     3. If you have no card of that suit, you must trump if you can.
     4. Otherwise, play any card.

6. **Special Moves**:
   - **Trump Exchange**: If you are on lead and still in Phase 1, you may exchange the Jack of trumps from your hand for the face-up trump card. You may do this exchange any time the stock is open, both players have drawn replacement cards for the previous trick, and you are the leader to the next trick. 
   - **Marriage**: If you hold the King and Queen of the same suit while on lead, you may declare a marriage. This gives you an immediate 20 points, or 40 if it's trump suit, and you must lead with either the King or Queen. You may only declare one marriage per trick. The trick points for a marriage are scored immediately. If the player declaring the marriage claims 66, the deal ends at that point without finishing the trick.

7. **Claiming 66**:
   - If you have at least 66 trick points (including marriages), you can claim 66 immediately after winning a trick or after declaring a marriage. A player may not claim 66 at any other time. The deal ends, and scoring is tallied.

8. **Winner of the Last Trick**:
   - If the stock is exhausted, and all cards are played from both hands, the winner of the last trick wins the entire deal. Note that this does not happen if the stock is closed, as that prevents the stock from being exhausted.

**Game Points When the Stock Was Not Closed**

Assuming the stock was not closed, the winner is awarded game points as follows:

|                                                                |     |
| -------------------------------------------------------------- | --- |
| **Awarded to winner**                                          |     |
| Loser took no tricks                                           | 3   |
| Loser's tricks and marriages add to fewer than 33 trick points | 2   |
| Loser's tricks and marriages add to at least 33 trick points   | 1   |

Note that if the loser declared a marriage at trick 1 but never took a trick, the deal is worth 3 game points, not 2.

Also note that you win more game points for winning by a wider margin. This means it is sometimes worth taking a risk to get an early win. Similarly, if it looks as though you will lose a deal, it is worthwhile trying to get at least 33 trick points in your tricks to avoid giving up 2 game points.

**Game Points When the Stock Was Closed**

Let us call the player who closes the stock the “closer” and the other player the “noncloser”. When a player closes the stock, the game points at stake for this deal are determined entirely by the number of trick points in the noncloser's tricks _at the moment the stock was closed_. If the closer wins the deal (meaning the closer correctly claims 66 before the noncloser does, with no last trick bonus), then game points are awarded to the closer analogously to the table above:

|   |   |
|---|---|
|**Awarded to closer**|   |
|Noncloser had no tricks when stock was closed|3|
|Noncloser's tricks and marriages added to fewer than 33 trick points when stock was closed|2|
|Noncloser's tricks and marriages added to at least 33 trick points when stock was closed|1|

If the noncloser wins the deal (meaning the closer failed to claim 66 correctly, or the noncloser correctly claimed 66 first), then game points are awarded to the noncloser according to the table below:

|   |   |
|---|---|
|**Awarded to noncloser**|   |
|Noncloser had no tricks at the time the stock was closed|3|
|Otherwise|2|

Note that a player scores at least 2 game points for winning the deal when the opponent has closed the stock. The closer pays this penalty for closing and not winning.
"""

    return text


def game_winning_strategy() -> str:
    """
    Return a string with the game-winning strategy.
    """
    text = """
When your opponent is on lead in Phase 1:
If you can win a nontrump trick by following suit (without breaking up a marriage already complete in your hand), it is usually a good idea to do so and collect these trick points. If you can win the trick with the ten or ace of the suit (particularly the ten, which is vulnerable to falling to your opponent's ace later in the deal), this has the double benefit of accumulating big points and retaining your queen or king for the chance of a later marriage. If you have a choice of “adjacent” cards with which to win the trick, you want to win the trick with the higher of those cards, in order to increase your trick points immediately. That is, win with the ace if you have both ace and ten, win with the ten if you have both ten and king, and so forth. Cards become “adjacent” if the intervening cards have already been played so, for example, you want to win with the ten if you have both ten and queen and the king has already been played.

If your opponent leads a trump or a card that you can not or do not want to win according to the guidelines above, discard a jack from some nontrump suit, or a queen or king if you have already seen its marriage partner, remembering again that you do not need to follow suit at this stage of the deal. Given a choice of discards, try to retain a second card as protection in the suit where you hold a ten, if you have not yet seen the ace: if you are holding an unprotected ten when the stock is no longer open and you have to follow suit, it is liable to fall to your opponent's ace, a very costly trick. A king is much better protection for a ten than a lower card would be.

When you are on lead in Phase 1:
It is generally a great advantage to be on lead early in the deal. This gives you opportunities you do not have when your opponent is on lead: you can perform any combination of exchanging your jack of trump, declaring a marriage, and choosing an advantageous card to lead.

You do not usually want to lead a trump at this stage, because your opponent is under no obligation to follow suit and give up a valuable trump.

Marriages and trump exchange:
Use your jack to exchange the trump on the table and/or show any marriage in your hand at the earliest possible opportunity. With only 5 cards in your hand, you will find it a challenge to keep your marriages intact when your opponent is on lead, as you have only 3 other cards with which to win the trick. If you are in this situation, it is often worth trumping early in order to gain the lead and dispose of your marriage. Similarly, your natural unwillingness to trump with the jack decreases your number of playable cards. For these reasons, it is (almost) never wrong to show a marriage or exchange the trump as soon as possible.

The only common exceptions are some simple situations where you don't want to give up the lead by showing a marriage. For instance, you are on lead with 33-45 points in your tricks, a marriage in hand, and the trump ace. In this case, you lead the trump ace first, bringing your trick point total up to at least 46, and then show the marriage to win. 

Phase two:
Once the stock is exhausted, both players must follow suit and must trump if they cannot follow suit. This changes the strategy dramatically. If one player has control over the remaining trump suit (meaning enough of the high trumps in hand to pull the opponent's remaining one or two trumps), that player should play just enough of the high trumps to pull the opponent's remaining trumps, retaining any other trumps to trump winners later. After trumps are pulled, you can play your nontrump winners without fear of having them trumped.

If your opponent still has trumps that you cannot pull, it is best to force him or her to trump one of your low cards by leading such a card from a suit he or she no longer holds. In this way, even if your opponent had trump control, you may be able to exhaust your opponent's trumps and collect your winners afterwards

At the time the stock is exhausted, only 10 cards will have been played (you are each still holding 5 cards), so you know all of the cards you hold and your opponent holds as well. At this point, you should focus on these last cards rather than the cards that have already been played.

Trump control:
The principle that guides much of Schnapsen's strategy is the control of trumps once the stock is exhausted. Your goal at this point is to be able to pull any remaining trumps from your opponent and then run your winning cards, collecting trick points from your opponent and crossing the 66 point threshold.

You can improve your odds of obtaining trump control by leading nontrump aces and tens early in the deal, daring your opponent to trump. This gives you an advantage in Phase 2 as you can initially play trump cards and pull your opponent's trumps, and then play your next card without possibility of it being trumped.

Last trick:
A deal occasionally occurs in which the stock is exhausted and neither player reaches 66 trick points. The winner of the deal in this case is the player that wins the last trick.

If you had trump control in the deal, you should try to retain the last trump to win the last trick. You want to retain excess trumps anyway, in order to trump your opponent's winners. If your opponent had trump control, you should force him or her to trump one of your cards each time you have the opportunity, in order to give yourself a chance to win the last trick.

In general, when the stock is exhausted and each player's trick point score is still low, you need to think ahead and plan the sequence of plays whereby you will win the last trick without letting your opponent get 66 trick points.
"""
    return text