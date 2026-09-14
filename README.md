# Project Setup

#### NOTE:
Execute all of these instuctions in the root directory of the project

#### NOTE:
Will need to have python installed on computer (version 3.12+) (if you don't just google "python install")

#### NOTE:
Will only be able to run clash royale games on windows and mac computers.

## Development Environment Setup Steps

Clone our repository:
```bash
# over https
https://github.com/DrewAMSD/clash_royale_ai.git

# using ssh
git@github.com:DrewAMSD/clash_royale_ai.git
```

If you are working entirely in a terminal:
```bash
# move into the root of our project directory
cd clash_royale_ai
```
Otherwise: Open this project folder in your code editor

### Once inside of the project's root directory:

Create virtual environment to install and save our project dependencies
```bash
python3 -m venv ./venv
```

Activate our virtual environment (do this every time you open the project) (to deactivate it, just type "deactivate" into terminal)
```bash
# Windows:
.\venv\Scripts\activate.bat

# Linux/MacOs:
source ./venv/bin/activate
```


Install our project dependencies (python packages we will be using)
```bash
# windows
pip install -r requirements-windows.txt

# mac
pip install -r requirements-mac.txt
```

## Installing Clash Royale onto Windows Computers

Visit this link:
```bash
https://play.google.com/store/apps/details?id=com.supercell.clashroyale
```
OR: Search into browser "clash royale windows pc install", and follow steps from first link.

This will download a setup script for installing the google play app if you do not already have it. If you already have google play installed it will open up the google play store to the Clash Royale app, where you can just select to download.

After google play is installed, simply search for Clash Royale in the app search bar, and download the first app result.

## Installing Clash Royale onto Mac Computers

Install an android emulator, we recommend installing and using MuMuPlayer. After this step, clash royale can be installed from the app store on the emulated android device.


## Running our Project with Clash Royale Open:

Preferrably, try to align your clash royale window on the left side of your screen as debug windows will be placed to the right of the clash royale window(if enabled).

<img width="1919" height="1079" alt="Screenshot 2026-03-04 110557" src="https://github.com/user-attachments/assets/9449d37e-f8f9-4b8d-8738-300a9bce24c8" />


### To run the project

```bash
python -m src.game.Main

# example running other files in our project
python3 -m src.<directory-name>.<file-name>
```

Side Note: The program may need to be run with elevated privileages

Windows: python ran as administrator.
Mac: sudo before our command (or utilize an elevated shell)

### Stopping the agent

The program can be halted by pressing the space key.

#### NOTE: 

Do not include the ".py" in the file name, the "-m" flag is running our project as a collection of modules with the "src" directory being our entry point(which automatically assumes the files we are calling to be in the ".py" format).

This allows us to import from our python files in other locations(or "modules") in the src directory via:
```bash
from src.<path>.<to>.<module> import <python classes, methods, and/or variables>
```

That's also why there are "\_\_init\_\_.py" files in each directory, which tells the python interpreter that the directory is a module in our project.
