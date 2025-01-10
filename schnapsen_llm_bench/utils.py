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