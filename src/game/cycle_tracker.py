from collections import deque

class CycleTracker:
    # tracks card cycle of player and enemy, cycle = cards in queue, hand = current cards in hand availble to play
    # have to have model see the cards in our hand first, add those to the hand (list), when we play a card it is added to cycle (queue), and the first card in the queue 
    # replaces it in our hand, 
    # for enemy cycle we have to what they have first by seeing what they play, so then we add their cards to the queue, when the queue exceeds its max size of 4
    # when then add the first card in the cycle to the hand. Then we can track their hand and cycle

    HAND_SIZE = 4
    DECK_SIZE = 8

    def __init__(self):
        self.hand: list   = []       # up to 4 cards currently in hand
        self.cycle: deque = deque()  # up to 4 cards waiting in cycle

    def discover_hand(self, card):
        if len(self.hand) < self.HAND_SIZE:
            self.hand.append(card)
        else:
            print("Error: Trying to discover card when hand is already full")

    def discover_enemy_cycle(self, card):
        if len(self.cycle) < self.HAND_SIZE:
            self.cycle.append(card)
        if len(self.cycle) > self.HAND_SIZE:
            self.hand.append(self.cycle.popleft())  # move the front card of the cycle into hand
        elif len(self.cycle) + len(self.hand) == self.DECK_SIZE:
            print("Error: Trying to discover card when cycle is already fully discovered")

    def play_card(self, card):
        if card in self.hand:
            self.cycle.append(card)  # add the played card to the back of the cycle
            self.hand[self.hand.index(card)] = self.cycle.popleft() # replaced the index where the card was played with the next card in cycle
        else:
            print("Error: Trying to play a card that is not in hand")

    def cards_until(self, card) -> int:
        if card in self.hand:
            return 0
        elif card in self.cycle:
            return self.cycle.index(card) + 1 # +1 because cycle is 0 indexed but we want to know how many cards until it comes into hand
        else:
            print("Error: Trying to check cards until a card that is not in hand or cycle")
            return -1

    def is_deck_fully_known(self) -> bool:
        return len(self.hand) + len(self.cycle) == self.DECK_SIZE

    def is_in_hand(self, card) -> bool:
        return card in self.hand

    def get_hand(self) -> list:
        return self.hand

    def get_cycle(self) -> list:
        return list(self.cycle)
