import pandas as pd

YOLO_TO_CSV = {
    'archer': 'Archer',
    'archers': 'Archer',
    'arrows': 'Arrows',
    'bomber': 'Bomber',
    'fireball': 'Fireball',
    'giant': 'Giant',
    'goblin': 'Goblin',
    'goblin-hut': 'Goblin Hut',
    'knight': 'Knight',
    'mini-pekka': 'Mini P.E.K.K.A.',
    'minion': 'Minion',
    'minions': 'Minion',
    'musketeer': 'Musketeer',
    'skeleton': 'Skeleton',
    'skeletons': 'Skeleton',
    'spear-goblin': 'Spear Goblin',
    'spear-goblins': 'Spear Goblin',
}

def load_data():
    df = pd.read_csv("data/clash_wiki_dataset.csv")
    
    # Fix plural card names to singular
    name_fixes = {
        'Archers': 'Archer',
        'Barbarians': 'Barbarian',
        'Bats': 'Bat',
        'Elite Barbarians': 'Elite Barbarian',
        'Fire Spirits': 'Fire Spirit',
        'Goblins': 'Goblin',
        'Guards': 'Guard',
        'Minions': 'Minion',
        'Skeletons': 'Skeleton',
        'Spear Goblins': 'Spear Goblin',
        'Three Musketeers': 'Musketeer',
    }
    
    df['Card'] = df['Card'].map(lambda x: name_fixes.get(x, x))
    
    return df

