# Scenery Pack Organiser - XP10/11/12 v3.0r1

Are you tired of sifting through all the packs in the Custom Scenery folder and reordering them manually?\
Do you hate having to start and quit X-Plane just to add new scenery packs to the file so you can organise it?\
This utility is for you!\
<br>
It will read and sort all scenery packs, carry over DISABLED tags, check for airport conflicts, and even warn you of faulty packages! 


## Installation
1. You need to have Python3 installed. [You can get it here for all platforms](https://www.python.org/downloads/)
    - [For macOS, you may use Homebrew instead](https://docs.python-guide.org/starting/install3/osx/)
    - For Linux, you should use your distro's package manager instead
    - *NOTE: I've had some people inform me of issues installing libraries with Python 3.12.0. If you run into issues there, please update to the latest version of Python3*
2. You need to have PIP installed
    - On Windows, PIP is automatically installed with Python3
    - On Linux, you may need to install a separate package (like `python3-pip` on Ubuntu/Debian based distributions)
3. Make sure both Python3 and PIP are added to PATH
    - On Windows, this is done by ticking the option in the installer
    - On Linux, this should happen automatically when installing the respective packages through your package manager
4. Check by opening Command Prompt or Terminal and doing `pip --version` and `python3 --version` or `python --version`

There is often confusion between `python` and `python3`. Doing the above will help you decide how to invoke python when running the script. If both commands give you an output, use the one that displays the highest version number.
<br>

Required non-standard Python3 libraries: `py7zr`, `pyyaml`, and if you're on Windows, `pywin32`. You can install them yourself using `pip install <library name>`, ~~or you can let the program install them for you :wink:.~~

## Usage
### How to run (2 methods)
- On Windows, you can run it simply by double-clicking. If this doesn't work, try the next method

- On Linux and macOS, set the executable bit, and double-click. If prompted, choose "Run in Terminal"

- On any platform, first open Command Prompt or Terminal and change the active directory to where the program is located\
Then do `python3 organiser.py` or `python organiser.py`\
To decide which one to use, refer the installation instructions

- *NOTE: If the program crashes, try running with `--verbose 1` or `--verbose 2` added at the end of the command shown above to see where it crashes*\
*Higher numbers correspond to greater verbosity, ie. level 2 will show even more than level 1 would*\
*Of course, you can also use this if you just want to feel cool - there's no performance hit!*


### How to use
At various stages, the program might ask you for input. Here, I'll go through them in order and explain each one:
1. The program will try to automatically locate X-Plane. It will list out all locations it finds. To use one of those, enter the number as displayed in the list\
If this doesn't work, or if you want to use a different location, simply paste the path from your file explorer\
*NOTE: Do not format it as a shell path (eg. wrapping it in quotes, escaping whitespaces and backslashes, etc)*

2. If you select a deleted or broken install which the organiser had located, the program will offer to clean it up to remove future confusion

3. If you had disabled some packs in your old scenery_packs.ini, the program will offer to retain those preferences

4. If the program was unable to sort some scenery packs, it will display them and offer a choice to write them into the ini. If you choose not to, they will be written as disabled packs

5. If the program sees multiple airport packs for the same ICAOs, it will list them out with a number, the folder path, and the overlapping ICAOs
    - It will then ask if you want to define their priorities yourself
    - If you do, you'll only need to give one input: the numbers displayed in the above list separated by commas
    - The packs will be written in the order you give it - first one highest, last one lowest

6. If an existing `scenery_packs.ini` is found, it will be renamed to `scenery_packs.ini.bak`. Old backup files will be removed upon completion of the script
If you want to roll back to the old ini, delete the existing one and then remove the `.bak` extension

7. Upon exiting, if the program can find X-Plane, it will offer to launch X-Plane\
*NOTE: Do not close the console window, otherwise X-Plane might also abruptly close*


## Features
- Sorts scenery packs according to the hierarchy specified below:
    - Custom Airports
    - Default Airports
    - *[Prefab Airports](https://forums.x-plane.org/index.php?/files/file/27582-prefab-scenery-for-25000-airports/)*
    - Global Airports
    - Scenery Plugins
    - Scenery Libraries
    - *[SimHeaven](https://simheaven.com/) Overlays*
    - Custom Overlays
    - Default Overlays
    - *[AutoOrtho](https://forums.x-plane.org/index.php?/forums/topic/259020-autoortho-streaming-ortho-imagery-for-x-plane-12-and-11/) Overlays*
    - Orthophotos
    - *[AutoOrtho](https://forums.x-plane.org/index.php?/forums/topic/259020-autoortho-streaming-ortho-imagery-for-x-plane-12-and-11/) Regions*
    - Terrain Meshes
- Supports Windows shortcuts (.LNK files, eg. for SAM Library)
- Supports [Prefab Airports](https://forums.x-plane.org/index.php?/files/file/27582-prefab-scenery-for-25000-airports/) and [AutoOrtho](https://forums.x-plane.org/index.php?/forums/topic/259020-autoortho-streaming-ortho-imagery-for-x-plane-12-and-11/)
- Attempts to locate X-Plane installs automatically, letting you choose between the results or manually inputting an X-Plane install path
- Offers to carry over SCENERY_PACK_DISABLED tags from existing scenery_packs.ini
- Checks for Custom Airport overlaps and resolves them with user input
- Will warn you of folders-in-folder (It's more common than you'd think)
- Supports XP10/11's and XP12's Global Airports entry simultaneously


## Credits/Changelog
Any contributions (features or bugfixes) are very welcome :grin:. [Here's the project GitHub](https://github.com/iy4vet/SceneryPacksOrganiser/).\
Feel free to message me on Discord - my username is `iy4vet`. I'm also present in the X-Plane Community and Official servers.\
<br>
A huge thank-you to these awesome people:
- [@supercoder186](https://forums.x-plane.org/index.php?/profile/567626-supercoder186/)
- [@Brady](https://forums.x-plane.org/index.php?/profile/7654-brady/)
- [@carlos maida](https://forums.x-plane.org/index.php?/profile/113644-carlos-maida/)
- [@Birdy.dma](https://forums.x-plane.org/index.php?/profile/147165-birdydma/)
- [@cyl8](https://forums.x-plane.org/index.php?/profile/327870-cyl8/)

This project is licensed under the GNU GPL v2.
- 3.0r1 - Fix for shutil's new behaviour
- 3.0a3 - Add SimHeaven quirk handling. UI Improvements: improved spacing; wait a few seconds between each part. Minor bugfixes
- 3.0a2 - Move to argparser. Minor changes to program flow
- 3.0a1 - Major code refactor for improved flexibility and legibility
- 2.2r1 - Add shebang to allow double-clicking on Unix systems
- 2.2b2 - Now save results of DSF parse so future runs are faster
- 2.2b1 - Complete rewrite of airport overlap system. Minor bugfixes
- 2.1r6 - Hotfix for Windows .lnk shortcut parsing
- 2.1r5 - Removed `pkg_resources` following deprecation in Python 3.12. Added debugging CLI options
- 2.1r4 - Fixed bug in selection of DSF to be read. Restored option to install missing Python3 libraries. Performance improvement: removal of need to "scan" Custom Scenery folder. UI improvement: refer to Custom Airport conflicts as "overlaps"; made prompt message clearer
- 2.1r3 - Fixed some DSFs unable to be read. Rolled back to old method of installing missing libraries automatically. Silenced DSF errors for AutoOrtho
- 2.1r2 - Fixed X-Plane launches from within the program
- 2.1r1 - Added support for AutoOrtho. Patched breakage points in newer code. Now offer to launch X-Plane after completion. Now write packs as DISABLED if user doesn't want to use the unclassified packs. UI improvements: get user confirmation before installing missing libraries; warn and describe if packs could not be classified; list out DSF parse errors neatly
- 2.0r1 - Fix meshes being treated as overlays. Now offer to clean nonexistent X-Plane installs if found. Added code comments. UI improvement: retry user inputs whenever invalid
- 2.0b6 - Hotfix for multi-codec attempts
- 2.0b5 - Now offer to write unsorted packs. Now offer a choice to resolve airport conflicts. Fixed apt.dat files unable to be read. UI improvements: list out unsorted packs in one go; display the name of the pack currently being sorted; indent lists for easier reading
- 2.0b4 - Now offer to carry over DISABLED tags from existing ini. Fixed Windows shortcut support
- 2.0b3 - Now treat Prefab Airports as its own thing to avoid clashes with Default or Custom Airports
- 2.0b2 - Now check for Custom Airport conflicts and resolve with user input. Removed X-Plane 9 support (never worked to begin with). UI improvements: now leave gaps in console to differentiate stages; added timer for each stage
- 2.0b1 - Now parse apt.dat to verify if a pack is an airport. Now sort Default below Custom Overlays. Now alphabetically sort each layer. Now support "Earth Nav data" and other non-conventional capitalisations within packs
- 1.4b1 - Now attempt to locate XP installs (only available for direct downloads)
- 1.3.2 - Hotfix for syntax error
- 1.3.1 - Fixed packs getting jumbled
- 1.3.0 - Added XP12 support. Sort Default below Custom Airports
- 1.2 - Added Windows shortcut (.LNK) support and code comments
- 1.1 - UI improvement: wait for user confirmation before exiting
- 1.0 - Initial upload


## Known Issues
- macOS aliases do not get read
- Automatic location of X-Plane installs may not work for Steam users

## What's planned...
Naturally, fixing the above :grin:. I also want to really solidify AutoOrtho and SAM support - people have been telling me there's some extra witchcraft it does that messes up this one's output.\
<br>
There's also saving preferences of custom airport overlaps, so you can simply reuse what you did last time. I'm also considering potential options to let you decide how you want your packs sorted. Perhaps little text files you can copy-paste to your scenery pack would be a good option...\
<br>
If there's anything else you'd like to see added, send me a message or create a pull request on GitHub!
