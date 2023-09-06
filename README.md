# Scenery Pack Organiser - XP10/11/12 v2.0r1

Are you tired of sifting through all the packs in the Custom Scenery folder and reordering them manually?\
Do you hate having to start and quit X-Plane just to add new scenery packs to the file so you can organise it?\
This utility is for you!\
<br>
It will read and sort all scenery packs, carry over DISABLED tags, check for airport conflicts, and even warn you of faulty packages!


## Installation
You are given a choice between using the Python script or the standalone executables.\
The Python script lets you see and edit the code to suit your needs, but requires you to have additional software (namely Python and PIP) installed.\
The executable, on the other hand, does not require any additional software. This is ideal for users who do not have Python installed or are facing problems with Python.\
Regardless of which one you use, you can store the program anywhere you'd like.
#### Script (.py) version
1. You need to have Python3 installed. [You can get it here for all platforms](https://www.python.org/downloads/)
    - [For macOS, you may use Homebrew instead](https://docs.python-guide.org/starting/install3/osx/)
    - For Linux, you should use your distro's package manager instead
2. You need to have PIP installed
    - On Windows, PIP is automatically installed with Python3
    - On Linux, you may need to install a separate package (like `python3-pip` on Ubuntu/Debian based distributions)
3. Make sure both Python3 and PIP are added to PATH
    - On Windows, this is done by ticking the option in the installer
    - On Linux, this should happen automatically when installing the respective packages through your package manager
4. Check by opening Command Prompt or Terminal and doing `pip --version` and `python3 --version` or `python --version`
<br>

There is often confusion between `python` and `python3`. Doing the above will help you decide how to invoke python when running the script. If both commands give you an output, use the one that displays the highest version number. <br>

If you have something more elaborate set up, please ensure the following libraries are available: `copy glob hashlib locale os pathlib pkg_resources struct sys time`, and non-standard libraries: `pyunpack patool`, and also `pywin32` if you're on Windows. 


#### Standalone executable
You do not need any additional software installed (ie. Python and PIP) on your system if you want to use the standalone executable. Simply download the one for your OS. <br>

Executables are available for Windows, macOS, and Linux. I'm planning on implementing a CLI install option in the near future.\
**Note: ** Especially after recent updates to the .py version, the standalone executables may be out of date by one version number. This shouldn't affect your experience too badly, and I'll usually get around to updating them in a week or so. 


## Usage
### How to run
#### Script (.py) version
- On Windows, you can run it simply by double-clicking. If this doesn't work, try the next method

- On any platform, first open Command Prompt or Terminal and change the active directory to where the program is located.\
Then do `python3 organiser_v2.0r1.py` or `python organiser_v2.0r1.py`.\
To decide which one to use, refer the installation instructions.
#### Standalone executable
- On Windows, you can run it simply by double-clicking.\
If this doesn't work, open Command Prompt or Terminal, change the active directory to where the program is located.\
Then do `organiser_v2.0b6.exe`.

- If Windows SmartScreen throws an error, you'll need to click on "More info", and then a "Run anyway" option will come up.\
Use the more secure CLI install option to avoid this. (coming soon)

- For macOS and Linux, open Terminal where the program is located.\
Then do `./organiser_v2.0b6`.\
If you run into a permission error, do `chmod +x organiser_v2.0b6` and try again.


### How to use
At various stages, the program might ask you for input. Here, I'll go through them in order and explain each one.
1. The program will try to automatically locate X-Plane. It will list out all locations it finds. To use one of those, enter the serial number as displayed in the list.\
If this doesn't work, or if you want to use a different location, simply paste the path from your file explorer.\
**Do not format it as a shell path (eg. wrapping it in quotes, escaping whitespaces and backslashes, etc)**

2. If you had disabled some scenery packs in your old scenery_packs.ini, the program will offer to retain those in the new ini.

3. If the program was unable to sort some scenery packs, it will display them and offer a choice to write them into the ini anyway. If yes, it will write them at the top.

4. If the program detects multiple airport packs for an ICAO code, it will give you a choice to prioritise them within the program
    - It will first display the ICAO code, and then list the packs with a serial number, the airport name as per the pack, and the pack's folder's name
    - If you opted to resolve, you will need to define the priorities. To do so, go through the list and enter the serial numbers in your desired order, separated by commas. The highest priority should go first, and the lowest last
5. If an existing `scenery_packs.ini` is found, it will be renamed to `scenery_packs.ini.bak`. Old backup files will be removed upon completion of the script.\
To roll back, simply drop the `.bak` extension.


## Features
- Sorts scenery packs according to the required hierarchy:
    - Custom Airports
    - Default Airports
    - Prefab Airports
    - Global Airports
    - Scenery Plugins
    - Scenery Libraries
    - Custom Overlays
    - Default Overlays
    - Orthophotos
    - Terrain Meshes
- Supports Windows shortcuts (.LNK files, eg. for SAM Library)
- Supports [Prefab Airports](https://forums.x-plane.org/index.php?/files/file/27582-prefab-scenery-for-25000-airports/) (requires you to retain "prefab" somewhere in the folder name for it to work)
- Attempts to locate X-Plane installs automatically, letting you choose between the results or manually inputting an X-Plane install path
- Offers to carry over SCENERY_PACK_DISABLED tags from existing scenery_packs.ini
- Checks for Custom Airport conflicts and resolves them with user input
- Will warn you of folders-in-folder (It's more common than you'd think)
- Supports XP10/11's and XP12's Global Airports entry simultaneously


## Credits/Changelog
A big thank-you to [@supercoder186](https://github.com/supercoder186/), for his original utility and encouragement.\
If you would like to contribute, [here is the project GitHub](https://github.com/therectifier/SceneryPacksOrganiser/).\
Feel free to message me on Discord - my username is **therectifier**. I'm also present in the X-Plane Community and Official servers.\
This project is licensed under GNU GPL v2.

- 1.0 - Initial Upload
- 1.1 - UI improvement: wait for user confirmation before exiting
- 1.2 - Added Windows shortcut (.LNK) support and code comments
- 1.3.0 - Added XP12 support. Sort Default below Custom Airports
- 1.3.1 - Fixed packs getting jumbled
- 1.3.2 - Fixed syntax error (I have no clue how this crept in)
- 1.4b1 - Now attempt to locate XP installs (only available for direct downloads)
- **Skipped 1.4 release - I went overboard with the changes and ended up rewriting the whole thing**
- 2.0b1 - Now parse apt.dat to verify if a pack is an airport. Now sort Default below Custom Overlays. Now alphabetically sort each layer. Now support "Earth Nav data" and other non-conventional capitalisations within packs
- 2.0b2 - Now check for Custom Airport conflicts and resolve with user input. Removed X-Plane 9 support (never worked to begin with). UI improvements: Now leave gaps in console to differentiate stages, Added timer for each stage
- 2.0b3 - Now treat Prefab Airports as its own thing to avoid clashes with Default or Custom Airports
- 2.0b4 - Now offer to carry over DISABLED tags from existing ini. Fixed Windows shortcut support
- 2.0b5 - Now offer to write unsorted packs. Now offer a choice to resolve airport conflicts. Fixed apt.dat files unable to be read. UI improvements: List out unsorted packs in one go, Display the name of the pack currently being sorted, Indent lists for easier reading
- 2.0b6 - Hotfix for multi-codec attempts
- 2.0r1 - Fix meshes being treated as overlays. Now offer to clean nonexistent X-Plane installs if found. Added code comments. UI improvements: Retry user inputs whenever invalid. 


## Known Issues
- Automatic location of X-Plane installs doesn't work for Steam users. This is because Steam doesn't use the same mechanism used by the X-Plane installer, which is also what this program uses. There is no timeline for getting this one fixed - if you would like to contribute, I would urge you to check out the project GitHub.
