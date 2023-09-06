import copy
import glob
import hashlib
import locale
import os
import pathlib
import pkg_resources
import struct
import sys
import time

# Require (and install) non-standard libraries
requirements = ["pyunpack", "patool"]
if sys.platform == "win32": requirements.append("pywin32")
for requirement in requirements:
    try:
        pkg_resources.require(requirement)
    except:
        print(f"I could not locate the {requirement} package. I will therefore install it for you.")
        print("If you see an error after this or if the window abruptly closes, please restart the script.\n")
        os.system(f"pip install {requirement}")
        print("\n")

# Import non-standard libraries
import pyunpack
if sys.platform == "win32": 
    import win32com.client


# State version
print("Scenery Pack Organiser version 2.0r1\n")


# Define where to look for direct X-Plane install traces
search_path = {}
if sys.platform == "win32":
    search_path["direct"] = pathlib.Path(os.path.expandvars("%USERPROFILE%/AppData/Local"))
elif sys.platform == "darwin":
    search_path["direct"] = pathlib.Path(os.path.expanduser("~/Library/Preferences"))
elif sys.platform == "linux":
    search_path["direct"] = pathlib.Path(os.path.expanduser("~/.x-plane"))
else:
    print(f"Unsupported OS detected. Please report this error. Detected platform: {sys.platform}")

# Attempt to programmatically locate X-Plane installs and offer to use those, otherwise take user input
# If the path was taken from the file and is found to be dead, offer to remove it
install_locations = []
reparse = True
while True:
    # Locating Direct X-Plane installs
    if search_path["direct"].exists() and reparse:
        install_locations = []
        for version in ["_10", "_11", "_12"]:
            try:
                dct_path = search_path["direct"] / f"x-plane_install{version}.txt"
                with open(dct_path, "r", encoding = "utf-8") as dct_file:
                    for dct_location in dct_file.readlines():
                        install_locations.append([f"X-Plane {version.strip('_') if version else '9 or earlier'}", dct_location.strip("\n"), dct_path])
            except FileNotFoundError:
                pass
    # TODO: Locating Steam X-Plane installs
    # Display locations
    if install_locations and reparse:
        print("I found the following X-Plane installs:")
        for i in range(len(install_locations)):
            print(f"    {i}: {install_locations[i][0]} at '{install_locations[i][1]}'")
    reparse = False
    # Get input
    path_from_direct = None
    path_from_steam = None
    if install_locations:
        print("If you would like to use one of these paths, enter its serial number as displayed in the above list.")
        print("Otherwise, paste the filepath in as normal.")
        path_choice = input("Enter your selection here: ")
        try:
            xplane_path = install_locations[int(path_choice)][1]
            if "Steam" in install_locations[int(path_choice)][0]:
                path_from_steam = str(path_choice)
            else:
                path_from_direct = str(path_choice)
        except (ValueError, IndexError):
            xplane_path = path_choice
    else:
        print("I could not find any X-Plane installs. You will need to enter a filepath manually.")
        xplane_path = input("Enter the path to the X-Plane folder: ")
    # Validate path. If invalid path taken from file, offer to remove
    xplane_path = pathlib.Path(xplane_path)
    scenery_path = xplane_path / "Custom Scenery"
    print(f"  Selected path: {xplane_path}")
    if scenery_path.exists():
        break
    elif path_from_direct:
        print("  This was automatically located as an X-Plane install, but I couldn't see a Custom Scenery folder! Perhaps a broken or deleted install?")
        while True:
            remove_choice = input("  Would you like me to remove this location? You can do this if you deleted X-Plane from here. (yes/no or y/n): ").lower()
            if remove_choice in ["y","yes"]:
                print("  Ok, I will remove this location. I'll display an updated list of locations which you can pick from. ")
                reparse = True
                dct_path = install_locations[int(path_from_direct)][2]
                with open(dct_path, "r", encoding = "utf-8") as dct_file:
                    dct_lines = dct_file.readlines()
                    for end in ["/\n", "/", "\n", ""]:
                        try:
                            del dct_lines[dct_lines.index(str(xplane_path) + end)]
                        except ValueError:
                            pass
                with open(dct_path, "w", encoding = "utf-8") as dct_file:
                    dct_file.writelines(dct_lines)
                break
            elif remove_choice in ["n","no"]:
                print("  Ok, I will not remove this location. You'll still need to pick a different one. ")
                break
            else:
                print("    Sorry, I didn't understand.")
    else:
        print("I couldn't see a Custom Scenery folder here! Please recheck your path. ")


# Constant and variable declarations
SCENERY_PATH = scenery_path
XP10_GLOBAL_AIRPORTS = "SCENERY_PACK Custom Scenery/Global Airports/\n"
XP12_GLOBAL_AIRPORTS = "SCENERY_PACK *GLOBAL_AIRPORTS*\n"
FILE_LINE_REL = "SCENERY_PACK Custom Scenery/"
FILE_LINE_ABS = "SCENERY_PACK "
FILE_DISAB_LINE_REL = "SCENERY_PACK_DISABLED Custom Scenery/"
FILE_DISAB_LINE_ABS = "SCENERY_PACK_DISABLED "
FILE_BEGIN = "I\n1000 Version\nSCENERY\n\n"

airport_registry = {}
disable_registry = {}
measure_time = []
unsorted_registry = []
unparsed_registry = []
customairports = []
defaultairports = []
prefabairports = []
globalairports = []
plugins = []
libraries = []
customoverlays = []
defaultoverlays = []
orthos = []
meshes = []


# Read old ini and store disabled packs. Ask user if they want to carry them forward
ini_path = SCENERY_PATH / "scenery_packs.ini"
if ini_path.is_file():
    with open(ini_path, "r", encoding = "utf-8") as ini_file:
        for line in ini_file.readlines():
            for disabled in [FILE_DISAB_LINE_REL, FILE_DISAB_LINE_ABS]:
                if line.startswith(disabled):
                    disable_registry[line.split(disabled, maxsplit=1)[1].strip("\n")[:-1]] = disabled
                    break
    if disable_registry:
        print("\nI see you've disabled some packs in the current scenery_packs.ini")
        while True:    
            disable_choice = input("Would you like to carry over the DISABLED tags to the new ini? (yes/no or y/n): ").lower()
            if disable_choice in ["y","yes"]:
                print("Ok, I will carry over whatever is possible to the new ini.")
                break
            elif disable_choice in ["n","no"]:
                print("Ok, I will not carry over any of the old DISABLED tags.")
                disable_registry = {}
                break
            else:
                print("  Sorry, I didn't understand.")


# Initial time record
measure_time.append(time.time())

# Create temp path
while True:
    try:
        TEMPORARY_PATH = pathlib.Path(f"organiser_temp_{time.time()}")
        os.mkdir(TEMPORARY_PATH)
        break
    except FileExistsError:
        continue


# DEF: Read Windows shorcuts
# The non-Windows code was taken from https://gist.github.com/Winand/997ed38269e899eb561991a0c663fa49
def read_shortcut_target(sht_path:str):
    tgt_path = None
    if sys.platform == "win32":
        shell = win32com.client.Dispatch("WScript.Shell")
        tgt_path = shell.CreateShortCut(sht_path).Targetpath
    else:
        with open(sht_path, 'rb') as stream:
            content = stream.read()
            lflags = struct.unpack('I', content[0x14:0x18])[0]
            position = 0x18
            if (lflags & 0x01) == 1:
                position = struct.unpack('H', content[0x4C:0x4E])[0] + 0x4E
            last_pos = position
            position += 0x04
            length = struct.unpack('I', content[last_pos:position])[0]
            position += 0x0C
            lbpos = struct.unpack('I', content[position:position + 0x04])[0]
            position = last_pos + lbpos
            size = (length + last_pos) - position - 0x02
            content = content[position:position + size].split(b'\x00', 1)
            tgt_path = content[-1].decode('utf-16' if len(content) > 1 else locale.getdefaultlocale()[1])
    return pathlib.Path(tgt_path)


# DEF: Read uncompresssed DSF
# This was taken from https://gist.github.com/nitori/6e7be6c9f00411c12aacc1ee964aee88 - thank you very much!
def decode_dsf(filename):
    size = os.stat(filename).st_size
    footer_start = size - 16  # 16 byte (128bit) for md5 hash
    digest = hashlib.md5()
    with open(filename, 'rb') as f:
        # read 8s = 8 byte string, and "i" = 1 32 bit integer (total: 12 bytes)
        raw_header = f.read(12)
        header, version = struct.unpack('<8si', raw_header)
        digest.update(raw_header)
        
        if header != b'XPLNEDSF':
            raise ValueError('Not a valid XPLNEDSF file')
        if version != 1:
            raise ValueError('Only version 1 supported')
        
        while f.tell() < footer_start:
            raw_atom_header = f.read(8)
            digest.update(raw_atom_header)
            # 32bit atom id + 32 bit atom_size.. total: 8 byte
            atom_id, atom_size = struct.unpack('<ii', raw_atom_header)
            atom_id = struct.pack('>i', atom_id) #'DAEH' -> 'HEAD'
            
            # data size is atom_size excluding the just read 8 byte id+size header
            atom_data = f.read(atom_size - 8)
            digest.update(atom_data)
            yield atom_id, atom_size, atom_data
        
        checksum = f.read()
        if checksum != digest.digest():
            raise ValueError('checksum mismatch!')


# DEF: Select and read DSF. Uncompress if needed and call decode_dsf(). Return HEAD atom
def read_dsf(end_directory:pathlib.Path):
    dir_walk = tuple(os.walk(end_directory))
    direct_path = pathlib.Path(os.path.join(dir_walk[1][0], dir_walk[1][2][0]))
    overlay = False
    # Attempt to extract 7z. If not 7z, work directly on the file
    try:
        pyunpack.Archive(direct_path).extractall(TEMPORARY_PATH)
        uncomp_path = TEMPORARY_PATH / direct_path.name
        uncomp_flag = True
    except pyunpack.PatoolError:
        uncomp_path = direct_path
        uncomp_flag = False
    # Search for sim/overlay tag in data
    try: 
        dsf_read = decode_dsf(uncomp_path)
    except ValueError:
        return "invalid"
    for atom_id, atom_size, atom_data in dsf_read:
        if atom_id == b'HEAD' and b'sim/overlay\x001' in atom_data:
            overlay = True
    # Delete uncompressed DSF once finished
    if uncomp_flag:
        uncomp_path.unlink()
    return overlay


# DEF: Check if a directory contains a folder or file (case insensitive)
# Ignore items list and return case-sensitive path for apt.dat or Earth nav data calls
def dir_contains(directory:pathlib.Path, items:list, type:str = None):
    dir_walk = tuple(os.walk(directory))
    fld_walk = dir_walk[0]
    # First find Earth nav data folder through recursion, then search for apt.dat file within it
    if type == "apt.dat":
        end_folder = dir_contains(directory, None, "Earth nav data")
        for path, folders, files in dir_walk:
            if path == str(end_folder):
                for file in files:
                    if file.lower() == "apt.dat":
                        return directory / end_folder / file
        return None
    # Find Earth nav data folder and return case-sensitive path
    elif type == "Earth nav data":
        for folder in fld_walk[1]:
            if folder.lower() == "earth nav data":
                return directory / folder
    # Find if file or folder is present
    elif type in [None, "generic"]:
        item_present = {}
        for item in items:
            item_present[item] = False
            for obj in fld_walk[2 if type == "generic" else 1]:
                if obj.lower() == item.lower():
                    item_present[item] = True
                    break
        for present in item_present.values():
            if not present:
                return False
        return True


# DEF: Check if any of the items in a list are present in a given string
# Used for checking if a scenery package is default
def str_contains(searchstr:str, itemslist:list, casesensitive:bool = True):
    for item in itemslist:
        if casesensitive and item in searchstr:
            return True
        elif not casesensitive and item.lower() in searchstr.lower():
            return True
    return False


# DEF: Check if the pack is an airport. If it has an apt.dat file, read and verify. Also check if default or prefab
def isAirport(dirpath:pathlib.Path, dirname:str, file_line:str):
    # Basic checks before we move further
    apt_path = dir_contains(dirpath, None, "apt.dat")
    if not apt_path: 
        return None
    if apt_path and dirname == "Global Airports": 
        return "Global"
    apt_lins = None
    # Attempt several codecs starting with utf-8 for obscure apt.dat files
    for codec in ('utf-8', 'charmap', 'cp1252', 'cp850'):
        try:
            with open(apt_path, "r", encoding = codec) as apt_file:
                apt_lins = apt_file.readlines()
            break
        except:
            pass
    apt_type = None
    # Check if airport or heliport or seaport, also check if default or prefab
    for line in apt_lins:
        if line.startswith("1 ") or line.startswith("16 ") or line.startswith("17 "):
            if str_contains(dirname, ["prefab"], casesensitive = False):
                apt_type = "Prefab"
                break
            elif str_contains(dirname, ["Demo Area", "X-Plane Airports", "X-Plane Landmarks", "Aerosoft"]):
                apt_type = "Default"
                break
            else:
                apt_type = "Custom"
                splitline = line.split(maxsplit=5)
                airport_entry = (splitline[5].strip("\n"), dirname, file_line)
                try:
                    airport_registry[splitline[4]].append(airport_entry)
                except KeyError:
                    airport_registry[splitline[4]] = [airport_entry]
    return apt_type


# DEF: Classify as Ortho, Mesh, or Overlay after reading DSF and scanning folders
# Open some DSF, if sim/overlay is 1, the pack is an overlay. Also check if default
# If folder contains textures and terrain folder, the pack is an ortho mesh
# If folder only has Earth nav data, the pack is a mesh
def isOrthoMeshOverlay(dirpath:pathlib.Path, dirname:str):
    end_path = dir_contains(dirpath, None, "Earth nav data")
    # Basic check
    if not end_path:
        return None
    # If overlay tag found, classify as default or custom. Else, mesh or ortho
    overlay = read_dsf(end_path)
    if overlay == "invalid":
        return None
    elif overlay:
        if str_contains(dirname, ["X-Plane Landmarks"]):
            return "Default Overlay"
        else:
            return "Custom Overlay"
    else:
        if dir_contains(dirpath, ["textures", "terrain"]):
            return "Ortho"
        else:
            return "Mesh"


# DEF: Check if the pack is a library. If it contains a library.txt file, is a library
def isLibrary(dirpath:pathlib.Path):
    return dir_contains(dirpath, ["library.txt"], "generic")


# DEF: Check if the pack is a scenery plugin. If it contains a plugins folder, it is a scenery plugin
def isPlugin(dirpath:pathlib.Path):
    return dir_contains(dirpath, ["plugins"])


# DEF: Format the line according to the required format for scenery_packs.ini
# Also check if this pack was previously disabled
def formatLine(ini_path:str, shortcut:bool):
    if ini_path in disable_registry:
        return_line = f"{disable_registry[ini_path]}{ini_path}/\n"
        del disable_registry[ini_path]
        return return_line
    if shortcut:
        return f"{FILE_LINE_ABS}{ini_path}/\n"
    else:
        return f"{FILE_LINE_REL}{ini_path}/\n"


# DEF: Classify the pack
def processType(path, shortcut = False):
    # Define values passed to functions
    abs_path = SCENERY_PATH / path
    name = str(path)
    if shortcut:
        ini_path = str(abs_path)
    else:
        ini_path = str(path)
    sorted = False
    line = formatLine(ini_path, shortcut)
    # First see if it's an airport
    if not sorted:
        type = isAirport(abs_path, name, line)
        if type == "Global":
            globalairports.append(line)
            sorted = True
        elif type == "Prefab":
            prefabairports.append(line)
            sorted = True
        elif type == "Default":
            defaultairports.append(line)
            sorted = True
        elif type == "Custom":
            customairports.append(line)
            sorted = True
    # Next, overlay, ortho or mesh
    if not sorted:
        type = isOrthoMeshOverlay(abs_path, name)
        if type == "Default Overlay":
            defaultoverlays.append(line)
            sorted = True
        elif type == "Custom Overlay":
            customoverlays.append(line)
            sorted = True
        elif type == "Ortho":
            orthos.append(line)
            sorted = True
        elif type == "Mesh":
            meshes.append(line)
            sorted = True
    # Very lax checks for plugins and libraries
    if not sorted:
        if isLibrary(abs_path):
            libraries.append(line)
            sorted = True
        elif isPlugin(abs_path):
            plugins.append(line)
            sorted = True
    # Give up. Add this to the list of packs we couldn't sort
    if not sorted:
        unsorted_registry.append(line)
     

print("\nI will now classify each scenery pack...")
measure_time.append(time.time())


# Process each directory in the Custom Scenery folder
maxlength = 0
for directory in tuple(os.walk(SCENERY_PATH))[0][1]:
    progress_str = f"Processing: {directory}"
    # Whitespace padding to print in the shell
    if len(progress_str) <= maxlength:
        progress_str = f"{progress_str}{' ' * (maxlength - len(progress_str))}"
    else:
        maxlength = len(progress_str)
    print(f"\r{progress_str}", end = "\r")
    processType(directory)
sys.stdout.write("\033[K")

# Process each Windows shortcut in the Custom Scenery folder
shtcut_list = [str(SCENERY_PATH / shtcut) for shtcut in tuple(os.walk(SCENERY_PATH))[0][2] if shtcut.endswith(".lnk")]
if shtcut_list and sys.platform != "win32":
    print(f"\nI found Windows .LNK shortcuts, but I'm not on Windows! Detected platform: {sys.platform}")
    print("I will still attempt to read them, but I cannot guarantee anything. I would suggest you use symlinks instead.")
elif shtcut_list and sys.platform == "win32":
    print("\nReading .LNK shortcuts...")
maxlength = 0
printed = False
# If the code raises an error internally or if we were given a garbled path, skip it and add to the list of unparsable shortcuts
for shtcut_path in shtcut_list:
    try:
        folder_path = read_shortcut_target(shtcut_path)
        if folder_path.exists():
            # More whitespace padding
            progress_str = f"Processing: {str(folder_path)}"
            if len(progress_str) <= maxlength:
                progress_str = f"{progress_str}{' ' * (maxlength - len(progress_str))}"
            else:
                maxlength = len(progress_str)
            print(f"\r{progress_str}", end = "\r")
            processType(folder_path, shortcut = True)
            continue
        else: 
            pass
    except:
        pass
    unparsed_registry.append(shtcut_path)
if printed:
    sys.stdout.write("\033[K")

# Destroy temp path
os.rmdir(TEMPORARY_PATH)

# Sort tiers alphabetically
unsorted_registry.sort()
customairports.sort()
defaultairports.sort()
prefabairports.sort()
globalairports.sort()
plugins.sort()
libraries.sort()
customoverlays.sort()
defaultoverlays.sort()
orthos.sort()
meshes.sort()

# Check to inject XP12 Global Airports
if not globalairports:
    globalairports.append(XP12_GLOBAL_AIRPORTS)


# Display all packs that couldn't be sorted and offer to write them at the top of the file
if unsorted_registry:
    measure_time.append(time.time())
    print("\nI was unable to classify some packs. I will show them formatted as per the ini:")
    for pack in unsorted_registry:
        pack_stripped = pack.strip('\n')
        print(f"    {pack_stripped}")
    while True:
        unsorted_choice = input("Should I still write them into the ini? (yes/no or y/n): ").lower()
        if unsorted_choice in ["y","yes"]:
            print("Ok, I will write them at the top of the ini.")
            break
        elif unsorted_choice in ["n","no"]:
            print("Ok, I will not write them in the ini.")
            unsorted_registry = None
            break
        else:
            print("  Sorry, I didn't understand.")
    unsorted_wait = time.time() - measure_time.pop()
    print(f"Waited {unsorted_wait} seconds for your input")
else:
    unsorted_wait = 0


# Display all disabled packs that couldn't be found
if disable_registry:
    print("\nSome packs were tagged DISABLED in the old scenery_packs.ini, but could not be found.")
    print("They have probably been deleted or renamed. I will list them out now:")
    for pack in disable_registry:
        print(f"    {pack}")


# Display all shortcuts that couldn't be read
if unparsed_registry:
    print("\nI was unable to parse these shortcuts:")
    for shortcut in unparsed_registry:
        print(f"    {shortcut}")
    print("You will need to manually paste the target location paths into the file in this format:")
    print(f"{FILE_LINE_ABS}<path-to-target-location>/")


# Display time taken in this operation
print(f"\nI've classified all packs other than the specified ones. ")
print(f"Took me {time.time() - measure_time.pop() - unsorted_wait} seconds to classify.")


# Check custom airport clashes using airport_registry and ask the user if they want to resolve
print("\nI will now check for Custom Airport conflicts...")
measure_time.append(time.time())
conflicts = 0
# Check how many conflicting airports we have
for icao in airport_registry:
    if len(airport_registry[icao]) > 1: 
        conflicts+=1
# Self-explanatory
if conflicts:
    while True:
        resolve_conflicts = input(f"Found {conflicts} Custom Airport conflicts. Would you like to resolve them now? (yes/no or y/n): ")
        if resolve_conflicts in ["y","yes"]:
            print("Ok, I will display them and resolve with your input.")
            resolve_conflicts = True
            break
        elif resolve_conflicts in ["n","no"]:
            print("Ok, I will only display them.")
            resolve_conflicts = False
            break
        else:
            print("  Sorry, I didn't understand.")
    print(f"Waited {time.time() - measure_time.pop()} seconds for your input")
else:
    measure_time.pop()
    resolve_conflicts = None


# Display (and if opted for, resolve) all custom airport clashes
measure_time.append(time.time())
for icao in airport_registry:
    # If this icao had only one pack, skip it
    if len(airport_registry[icao]) == 1: 
        continue
    # Display the conflicting packs in a list
    print(f"\nI found {len(airport_registry[icao])} airports for {icao}.")
    print("I'll list them out with a number, the airport name as per the pack, and the pack's folder's name.")
    airport_multiple = {}
    i = 0
    for airport in airport_registry[icao]:
        airport_multiple [i] = airport[2]
        print(f"    {i}: '{airport[0]}' in '{airport[1]}'")
        i+=1
    if not resolve_conflicts:
        continue
    tmp_valid_flag = True
    # Get user input.
    while True:
        newline = "\n"
        order = input(f"{'' if tmp_valid_flag else newline}Enter the serial numbers as per the list separated by commas. I will write them in that order: ")
        # Create a copy of the customairports list to work on
        tmp_customairports = copy.deepcopy(customairports)
        tmp_valid_flag = True
        # There is no concievable case in which this throws an error, but one can never be sure
        try:
            order = order.strip(" ").split(",")
        except:
            print("  I couldn't read this input!")
            tmp_valid_flag = False
        if not tmp_valid_flag:
            print("  Do read the instructions if you're unsure about how to input your preferences.")
            continue
        i = 0
        # Go through the input and see if they're all numbers
        while True:
            try:
                if order[i]:
                    i+=1
                    int(order[i])
                else:
                    del order[i]
            except IndexError:
                break
            except ValueError:
                tmp_valid_flag = False
        if not tmp_valid_flag:
            print("  Saw non-numeric characters between commas!")
            print("  Do read the instructions if you're unsure about how to input your preferences.")
            continue
        # Check the length of the input given
        input_difference = len(order) - len(airport_multiple)
        if input_difference > 0:
            print(f"  I got {input_difference} more {'entry' if input_difference == 1 else 'entries'} than I was expecting!")
            tmp_valid_flag = False
        elif input_difference < 0:
            print(f"  I got {-input_difference} {'less entry' if -input_difference == 1 else 'fewer entries'} than I was expecting!")
            tmp_valid_flag = False
        if not tmp_valid_flag:
            print("  Do read the instructions if you're unsure about how to input your preferences.")
            continue
        # Manipulate the customairports copy according to the user input. If it fails somehow, reset the copy and start over
        for sl in order:
            try:
                tmp_customairports.append(tmp_customairports.pop(tmp_customairports.index(airport_multiple[int(sl)])))
            except:
                print(f"  That didn't work. Resetting preferences for {icao}.")
                tmp_valid_flag = False
                break
        if not tmp_valid_flag:
            print("  Do read the instructions if you're unsure about how to input your preferences.")
            continue
        # If we've made it this far, then everything has gone well. We can now write the copy back into the main list
        print(f"  Preferences updated for {icao}!")
        customairports = copy.deepcopy(tmp_customairports)
        break
# Display time after this ordeal if chosen to resolve, else advise to go through the ini manually, else happily say we saw nothing
if resolve_conflicts:
    print(f"Took me {time.time() - measure_time.pop()} seconds to resolve conflicts with your help.\n")
elif conflicts:
    measure_time.pop()
    print("You may wish to manually go through the ini file for corrections.\n")
else:
    measure_time.pop()
    print("I didn't detect any conflicts.\n")


scenery_ini_path_dep = pathlib.Path(SCENERY_PATH / "scenery_packs.ini")
scenery_ini_path_bak = pathlib.Path(f"{scenery_ini_path_dep}.bak")


# Remove the old backup file, if present
if scenery_ini_path_bak.exists():
    print("I will now delete the old scenery_packs.ini.bak")
    scenery_ini_path_bak.unlink()

# Back up the current scenery_packs.ini file
if scenery_ini_path_dep.exists():
    print("I will now back up the current scenery_packs.ini")
    scenery_ini_path_dep.rename(scenery_ini_path_bak)

# Write out the new scenery_packs.ini file
print("I will now write the new scenery_packs.ini")


# Print packs as sorted (ONLY FOR DEVELOPMENT OR DEBUGGING USE)
if False:
    debug = {"unsorted":unsorted_registry, "customairports":customairports, "defaultairports":defaultairports, 
             "prefabairports":prefabairports, "globalairports":globalairports, "plugins":plugins, "libraries":libraries, 
             "customoverlays":customoverlays, "defaultoverlays":defaultoverlays, "orthos":orthos, "meshes":meshes}
    for i in debug:
        lst = debug[i]
        print(i)
        for j in lst:
            print(f"    {j.strip()}")


with open(scenery_ini_path_dep, "w+", encoding = "utf-8") as f:
    f.write(FILE_BEGIN)
    if unsorted_registry:
        f.writelines(unsorted_registry)
    f.writelines(customairports)
    f.writelines(defaultairports)
    f.writelines(prefabairports)
    f.writelines(globalairports)
    f.writelines(plugins)
    f.writelines(libraries)
    f.writelines(customoverlays)
    f.writelines(defaultoverlays)
    f.writelines(orthos)
    f.writelines(meshes)
print("\nDone!")
print(f"Took me {time.time() - measure_time.pop()} seconds in total.")
input("Press enter to close")
