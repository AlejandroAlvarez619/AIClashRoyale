class Troop:
    def __init__(self, data):
        self.card                = data.get('Card', None)
        self.card_level          = data.get('Card Level (Spawn Level)', None)
        self.cost                = data.get('Cost', None)
        self.count               = data.get('Count', None)
        self.crown_tower_damage  = data.get('Crown Tower Damage', None)
        self.damage              = data.get('Damage', None)
        self.damage_per_second   = data.get('Damage per second', None)
        self.death_damage        = data.get('Death Damage', None)
        self.health              = data.get('Health (+Shield)', None)
        self.hit_speed           = data.get('Hit Speed', None)
        self.level               = data.get('Level', None)
        self.maximum_spawned     = data.get('Maximum Spawned', None)
        self.radius              = data.get('Radius', None)
        self.range               = data.get('Range', None)
        self.spawn_dps           = data.get('Spawn DPS', None)
        self.spawn_damage        = data.get('Spawn Damage', None)
        self.spawn_health        = data.get('Spawn Health', None)
        self.spawn_speed         = data.get('Spawn Speed', None)
        self.spawner_health      = data.get('Spawner Health', None)
        self.troop_spawned       = data.get('Troop Spawned', None)
        self.type                = data.get('Type', None)

    def __repr__(self):
        return f"Troop({self.card}, Level {self.level}, HP: {self.health}, DMG: {self.damage})"