from PIL import Image
from pathlib import Path
import random
import datetime

# must run this from this directory
troop_names = [item.name for item in Path("./base-image-set").iterdir() if item.is_dir()]
troop_count = len(troop_names)

# create data.yaml file
try:
    data_yaml_file_name = "./dataset/data.yaml"
    data_yaml_path = Path(data_yaml_file_name)

    file_stream = data_yaml_path.open("w")

    # paths
    file_stream.write("path: C:\\Users\\dmiller3905\\Documents\\clash_royale_ai\\src\\models\\troop-identify\\dataset"+"\n")
    file_stream.write("train: images/train"+"\n")
    file_stream.write("val: images/val"+"\n")

    # specifying cards
    file_stream.write("\n")
    file_stream.write(f"nc: {troop_count} # number of identify-able objects"+"\n")
    file_stream.write("names:"+"\n")

    for troop_id,troop_name in enumerate(troop_names):
        file_stream.write(f"  {troop_id}: {troop_name}"+"\n")
    
    file_stream.close()
except FileNotFoundError:
    print(f"File at {data_yaml_file_name} not found")
except Exception as e:
    print(e)


# create our training data
bg_paths = [item for item in Path("./backgrounds").iterdir() if item.is_file()]
backgrounds = []
for bg_path in bg_paths:
    bg = Image.open(bg_path).convert("RGBA")
    backgrounds.append(bg)


sprites = {}
training_by_troop = True # change this to false if we want to train on every troop
troops_to_train = [ "knight", "archer", "minion", "giant", "mini-pekka", "musketeer", "goblin", "goblin-cage", "goblin-brawler", "goblin-hut", "spear-goblin", "skeleton", "tombstone", "bomber", "valkyrie", "cannon", "barbarian", "battle-ram", "mega-minion"]#,"arrows", "fireball"] # if we want to train specific cards, specify what cards here
for troop_id, troop_name in enumerate(troop_names):
    sprites[troop_id] = []

    troop_images_file_name = f"./base-image-set/{troop_name}"
    troop_images_path = Path(troop_images_file_name)
    for troop_image_path in troop_images_path.iterdir():
        if training_by_troop and troop_images_path.name not in troops_to_train: continue 
        if troop_image_path.is_file():
            print(f"----Opening {troop_image_path}----")
            sprite = Image.open(troop_image_path).convert("RGBA")

            sprites[troop_id].append(sprite)

# assums troop_names is sorted alphabetically
def get_troop_id_by_name(troop_name):
    l = 0
    r = len(troop_names)-1
    while l <= r:
        m = (l + r) // 2
        if troop_names[m] < troop_name:
            l = m + 1
            continue
        if troop_names[m] > troop_name:
            r = m - 1
            continue
        return m
    
    raise Exception(f"Troop '{troop_name}' not in troop_names")

def create_training_image(bg, sprites, sprites_to_place=5):
    img = bg.copy()
    annotations = []
    bw, bh = img.size

    for _ in range(sprites_to_place):
        if training_by_troop:
            troop_to_use = random.choice(troops_to_train)
            troop_id = get_troop_id_by_name(troop_to_use)
        else:
            troop_id = random.choice(list(sprites.keys()))
        troop_sprites = sprites[troop_id]
        troop_sprite = random.choice(troop_sprites)

        # slightly randomize scale of troop image
        scale = random.uniform(0.8, 1.1)
        sw = int(troop_sprite.width * scale)
        sh = int(troop_sprite.height * scale)
        troop_sprite_resized = troop_sprite.resize((sw, sh))  

        # place troop image in random position on background
        x = random.randint(0, bw - sw)
        y = random.randint(0, bh - sh)
        img.paste(troop_sprite_resized, (x, y), troop_sprite_resized)

        # YOLO format: class cx cy w h (normalized 0–1)
        sprite_cx = (x + sw / 2) / bw
        sprite_cy = (y + sh / 2) / bh
        sprite_w = sw / bw
        sprite_h = sh / bh
        annotations.append(f"{troop_id} {sprite_cx:.6f} {sprite_cy:.6f} {sprite_w:.6f} {sprite_h:.6f}")

    return img.convert("RGB"), annotations



def populate_training_data(training_image_count=10):
    training_images = []
    training_annotations = []
    for idx in range(training_image_count):
        print(f"---Generating training image: {idx}---")

        bg = random.choice(backgrounds)
        # placing negative backgrounds with empty labels so model doesn't try to find something in empty image, can tweak this anytime if needed
        if random.randint(0, 99) < 10:
            training_image, training_annotation_arr = create_training_image(bg, sprites, sprites_to_place=0)
        else:
            sprites_to_place = random.randint(4, 6)
            training_image, training_annotation_arr = create_training_image(bg, sprites, sprites_to_place=sprites_to_place)
        
        training_images.append(training_image)
        training_annotations.append(training_annotation_arr)

    # 80% as training data, 20% as validation images
    split = int(0.8 * training_image_count)
    today = datetime.date.today()
    date_str = today.isoformat()

    for idx in range(training_image_count):
        print(f"---Saving traning image: {idx}---")
        training_img = training_images[idx]
        training_annot_arr = training_annotations[idx]

        destination = "train" if idx < split else "val"

        # can add {date-str}_scene into both file paths if we desire to not write over previous files
        training_img.save(f"./dataset/images/{destination}/scene-{idx}.jpg")

        annotation_to_insert = ""
        for annot in training_annot_arr:
            annotation_to_insert += (annot+"\n")

        label_file_name = f"./dataset/labels/{destination}/scene-{idx}.txt"
        label_path = Path(label_file_name)
        label_stream = label_path.open("w")

        label_stream.write(annotation_to_insert)
        label_stream.close()


populate_training_data(training_image_count=1000)