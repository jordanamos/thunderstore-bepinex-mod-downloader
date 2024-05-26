# Thunderstore.io BepInEx Mod Downloader and Installer

Download a list of BepInEx dependant mods from thunderstore.io and install them to the given game directory.

This tool is useful if you do not have access to a mod manager (maybe you have a Mac and installed a game using whisky) and wish to avoid manually downloading and installing mods 1 by 1. 

## Usage

1. Clone this repository 
    ```
    git clone git@github.com:jordanamos/thunderstore-bepinex-mod-downloader.git
    ```
2. Move into the newly cloned directory
    ```
    cd thunderstore-bepinex-mod-downloader
    ```
2. Create a virtual Environment (Optional but recommended)
    ```
    virtualenv venv && . venv/bin/activate
    ```
3. Install depenencies
    ```
    pip install -r requirements.txt
    ```
4. Populate `mods.txt` with the desired mods in the format {by}-{name}-{version} (one perline!)

5. Run the program
    With the path to the game directory that you wish to install the mods for as a posiotional argument:

    ```
    python main.py [game_dir]
    ```

6. Use -h for a list of optional arguments.