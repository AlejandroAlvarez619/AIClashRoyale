import torch
import torch.nn as nn
import copy
import random
from src.constants import DEFAULT_MUTATION_POWER, MAX_BEST_PERFORMERS


class RoyaleNetwork(nn.Module):
    def __init__(self, input_size, output_size):
        super(RoyaleNetwork, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.ReLu(),
            nn.Linear(128, 64),
            nn.ReLu(),
            nn.Linear(64, output_size)
        )

    # call by doing output = model(state), not model.forward(state) because nn.Module has a __call__ wrapper around forward class method
    # returns list/tensor of outputs, can find desired card to play by choosing whichever index had the highest value with touch.argmax()
    def forward(self, input_tensor):
        return self.network(input_tensor)
    

class EvolutionManager:
    def __init__(self, population_size, input_size, output_size):
        self.population_size = population_size
        self.input_size = input_size
        self.output_size = output_size
        # initial population with random values (to use saved models, before running training, call produce_next_generation once with saved models)
        self.population = [RoyaleNetwork(input_size, output_size) for _ in range(population_size)]
    

    def mutate(self, model, mutation_power=DEFAULT_MUTATION_POWER):
        child = copy.deepcopy(model)
        with torch.no_grad():
            for param in child.parameters():
                noise = torch.randn_like(param) * mutation_power
                param.add_(noise)
        return child
    

    def produce_next_generation(self, best_performers):
        # best performers = list of best performing models from previous generation selected to be mutated for next generation
        new_generation = []

        best_performers_len = len(best_performers)
        if best_performers_len > MAX_BEST_PERFORMERS:
            raise Exception(f"Trying to create new generation with more than {MAX_BEST_PERFORMERS} best performers")

        # append best performing models
        for i in range(best_performers_len):
            new_generation.append(best_performers[i])

        while len(new_generation) < self.population_size:
            # randomly select one of the best performing models to clone and mutate for new model in population
            parent = best_performers[random.randint(0, best_performers_len)]
            child = self.mutate(parent, mutation_power=0.05) # can change this mutation power higher or lower depending on how much variability we want each new generation to have
            new_generation.append(child)
        
        self.population = new_generation