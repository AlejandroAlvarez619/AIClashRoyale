from enum import Enum
# NOTE: might end up moving most constants out of this file to the file they are used (if only used by 1 file)

# evolution constants
DEFAULT_MUTATION_POWER: float = 0.02
MAX_BEST_PERFORMERS: int = 3

# grid constants
PLAYER_GRID_SIZE: tuple[int] = (18, 15) # on our side of bridge is 18x15 tile grid (excluding some of the edges + towers)
TOTAL_GRID_SIZE: tuple[int] = (18, 32) # 15 placement on our side + enemy side + 2 bridge tiles



# for later when we start training our model
# model constants

# NOTE: might want to just have cost and playable of cards if it is too hard to read what card is in hand(but might be able to by just checking a couple of pixel colors on card since we will most likely use the same deck always)
# each element in enum is going to be what that index in the model input vector represents
class InputField(Enum):
    # float 0.0 to 1.0, where elixir is value * 10 (i.e. 1.0 = 10 elixir)
    ELIXIR = 0
    # hp of friendly towers, floats 0.0 to 1.0, representing percentage of max hp
    FRIENDLY_PRINCESS_HP_LEFT = 1
    FRIENDLY_PRINCESS_HP_RIGHT = 2
    FRIENDLY_KING_HP = 3
    # hp of enemy towers, floats 0.0 to 1.0, representing percentage of max hp
    ENEMY_PRINCESS_HP_LEFT = 4
    ENEMY_PRINCESS_HP_RIGHT = 5
    ENEMY_KING_HP = 6
    # card 1 information
    CARD_IN_HAND_1_ID = 7 # id, float 0.00 to 1.00 (can increase digits to 0.000 to 1.000 if using more than 100 cards)
    CARD_IN_HAND_1_COST = 8 # cost, float 0.2 to 0.9
    CARD_IN_HAND_1_PLAYABLE = 9 # playable, float - either 0.0 or 1.0
    # card 2 information
    CARD_IN_HAND_2_ID = 10
    CARD_IN_HAND_2_COST = 11
    CARD_IN_HAND_2_PLAYABLE = 12
    # card 3 information
    CARD_IN_HAND_3_ID = 13
    CARD_IN_HAND_3_COST = 14
    CARD_IN_HAND_3_PLAYABLE = 15
    # card 4 information
    CARD_IN_HAND_4_ID = 16
    CARD_IN_HAND_4_COST = 17
    CARD_IN_HAND_4_PLAYABLE = 18
    # can potentially add in upcoming card information (id, cost)
    CARD_UPCOMING_ID = 19
    CARD_UPCOMING_COST = 20
    # TODO: grid where each spot represents if there is a friendly unit at location
    # TODO: above grid but for enemy units (start with about 3x4 sections of screen otherwise might be too slow to train model)
    
INPUT_SIZE: int = len(InputField)
# to input array of inputs into model for getting next action: input_tensor = torch.tensor(input_list).float().unsqueeze(0)

class OutputField(Enum):
    # float, with highest being index of card to be played
    CARD_INDEX_0 = 0
    CARD_INDEX_1 = 1
    CARD_INDEX_2 = 2
    CARD_INDEX_3 = 3
    # if wait flag is above certain threshold, ignore above and do not play anything
    WAIT_FLAG = 4
    # TODO: fill this with a list of each location on the grid the model can play a unit(will reserve to only behind bridge)

OUTPUT_SIZE: int = len(OutputField)