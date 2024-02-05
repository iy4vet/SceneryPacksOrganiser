import copy
import hashlib
import locale
import os
import pathlib
import re
import shutil
import struct
import sys
import time

# Declare DEBUG constant - decides verbosity of the program
if "--debug-2" in sys.argv:
    DEBUG = 2
elif "--debug-1" in sys.argv:
    DEBUG = 1
else:
    DEBUG = 0

# Import non-standard libraries, if failed, install and try again
# py7zr
while True:
    try:
        import py7zr
        break
    except ModuleNotFoundError:
        while True:
            choice_install = input(f"I could not locate the py7zr Python library. Would you like me to install it now? (yes/no or y/n): ").lower()
            if choice_install in ["y", "yes"]:
                print("Ok, I will install it now. If the program quits or gives an error after this, please restart it.\n")
                os.system(f"pip install py7zr")
                print("\n")
                break
            elif choice_install in ["n", "no"]:
                print("Ok, I will not install it. You will need to install it yourself and run the program again.\n")
                input("Press enter to close")
                exit()
            else:
                print("  Sorry, I didn't understand.")
# pyyaml
while True:
    try:
        import yaml
        break
    except ModuleNotFoundError:
        while True:
            choice_install = input(f"I could not locate the pyyaml Python library. Would you like me to install it now? (yes/no or y/n): ").lower()
            if choice_install in ["y", "yes"]:
                print("Ok, I will install it now. If the program quits or gives an error after this, please restart it.\n")
                os.system(f"pip install pyyaml")
                print("\n")
                break
            elif choice_install in ["n", "no"]:
                print("Ok, I will not install it. You will need to install it yourself and run the program again.\n")
                input("Press enter to close")
                exit()
            else:
                print("  Sorry, I didn't understand.")
# pywin32
while True:
    if sys.platform != "win32":
        break
    try:
        import win32com.client
        break
    except ModuleNotFoundError:
        while True:
            choice_install = input(f"I could not locate the pywin32 Python library. Would you like me to install it now? (yes/no or y/n): ").lower()
            if choice_install in ["y", "yes"]:
                print("Ok, I will install it now. If the program quits or gives an error after this, please restart it.\n")
                os.system(f"pip install pywin32")
                print("\n")
                break
            elif choice_install in ["n", "no"]:
                print("Ok, I will not install it. You will need to install it yourself and run the program again.\n")
                input("Press enter to close")
                exit()
            else:
                print("  Sorry, I didn't understand.")


# Register py7zr unpacking with shutil
shutil.register_unpack_format('7zip', ['.7z', '.dsf'], py7zr.unpack_7zarchive)


# State version
if DEBUG:
    print(f"Debug level set to {DEBUG}. The program will be accordingly verbose during execution.")
    print("It will also display DSF errors and list packs as sorted in the end.")
    print()
print("Scenery Pack Organiser version 2.2b2\n")

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
        choice_path = input("Enter your selection here: ")
        try:
            xplane_path = install_locations[int(choice_path)][1]
            if "Steam" in install_locations[int(choice_path)][0]:
                path_from_steam = str(choice_path)
            else:
                path_from_direct = str(choice_path)
        except (ValueError, IndexError):
            xplane_path = choice_path
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
            choice_remove = input("  Would you like me to remove this location? You can do this if you deleted X-Plane from here. (yes/no or y/n): ").lower()
            if choice_remove in ["y","yes"]:
                print("  Ok, I will remove this location. I'll display an updated list of locations which you can pick from. ")
                reparse = True
                dct_path = install_locations[int(path_from_direct)][2]
                with open(dct_path, "r", encoding = "utf-8") as dct_file:
                    dct_lines = dct_file.readlines()
                    for end in ["/\n", "/", "\n", ""]:
                        try:
                            del dct_lines[dct_lines.index(str(xplane_path) + end)]
                        except KeyError:
                            pass
                with open(dct_path, "w", encoding = "utf-8") as dct_file:
                    dct_file.writelines(dct_lines)
                break
            elif choice_remove in ["n","no"]:
                print("  Ok, I will not remove this location. You'll still need to pick a different one. ")
                break
            else:
                print("    Sorry, I didn't understand.")
    else:
        print("I couldn't see a Custom Scenery folder here! Please recheck your path. ")


# constant declarations
SCENERY_PATH = scenery_path
XP10_GLOBAL_AIRPORTS = "SCENERY_PACK Custom Scenery/Global Airports/\n"
XP12_GLOBAL_AIRPORTS = "SCENERY_PACK *GLOBAL_AIRPORTS*\n"
FILE_LINE_REL = "SCENERY_PACK Custom Scenery/"
FILE_LINE_ABS = "SCENERY_PACK "
FILE_DISAB_LINE_REL = "SCENERY_PACK_DISABLED Custom Scenery/"
FILE_DISAB_LINE_ABS = "SCENERY_PACK_DISABLED "
FILE_BEGIN = "I\n1000 Version\nSCENERY\n\n"
BUF_SIZE = 65536

# global variable declarations
measure_time = []       # list to keep writing and popping times
icao_conflicts = []     # list of ICAO codes that have more than one pack serving it
icao_registry = {}      # dict of ICAO codes and the number of packs serving each
disable_registry = {}   # dict that holds the folder line and beginning line of disabled packs
dsferror_registry = []   # list of errored dsfs
unparsed_registry = []  # list of .lnk shortcuts that couldn't be parsed
airport_registry = {"path": [], "line": [], "icaos": []}    
                        # dict that holds the folder path, file line, and a list of ICAOs served
                        # to use, get the index via folder path and use that within each key-value

# classification variables
unsorted_registry = []          # list of packs that couldn't be classified
quirks = {"Prefab Apt": [], "AO Overlay": [], "AO Region": [], "AO Root": []}
airports = {"Custom": [], "Default": [], "Global": []}
overlays = {"Custom": [], "Default": []}
meshes = {"Ortho": [], "Terrain": []}
misc = {"Plugin": [], "Library": []}


# Read old ini to get list of disabled packs
ini_path = SCENERY_PATH / "scenery_packs.ini"
nay_path = SCENERY_PATH / "scenery_packs_unsorted.ini"
if ini_path.is_file():
    with open(ini_path, "r", encoding = "utf-8") as ini_file:
        for line in ini_file.readlines():
            for disabled in [FILE_DISAB_LINE_REL, FILE_DISAB_LINE_ABS]:
                if line.startswith(disabled):
                    disable_registry[line.split(disabled, maxsplit=1)[1].strip("\n")[:-1]] = disabled
                    break
# Read unsorted ini to remove packs disabled for being unclassified
if nay_path.is_file():
    with open(nay_path, "r", encoding = "utf-8") as nay_file:
        for line in nay_file.readlines():
            for disabled in [FILE_DISAB_LINE_REL, FILE_DISAB_LINE_ABS]:
                if line.startswith(disabled):
                    try:
                        del disable_registry[line.split(disabled, maxsplit=1)[1].strip("\n")[:-1]]
                        break
                    except KeyError:
                        pass
# Ask if user wants to carry these disabled packs over
if disable_registry:
    print("\nI see you've disabled some packs in the current scenery_packs.ini")
    while True:    
        choice_disable = input("Would you like to carry it over to the new ini? (yes/no or y/n): ").lower()
        if choice_disable in ["y","yes"]:
            print("Ok, I will carry as much as possible over.")
            break
        elif choice_disable in ["n","no"]:
            print("Ok, I will not carry any of them over.")
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
# The non-Windows code is from https://gist.github.com/Winand/997ed38269e899eb561991a0c663fa49
def process_shortcut_read(sht_path:str):
    tgt_path = None
    if sys.platform == "win32":
        shell = win32com.client.Dispatch("WScript.Shell")
        tgt_path = shell.CreateShortCut(sht_path).Targetpath
    else:
        with open(sht_path, "rb") as stream:
            content = stream.read()
            lflags = struct.unpack("I", content[0x14:0x18])[0]
            position = 0x18
            if (lflags & 0x01) == 1:
                position = struct.unpack("H", content[0x4C:0x4E])[0] + 0x4E
            last_pos = position
            position += 0x04
            length = struct.unpack("I", content[last_pos:position])[0]
            position += 0x0C
            lbpos = struct.unpack("I", content[position:position + 0x04])[0]
            position = last_pos + lbpos
            size = (length + last_pos) - position - 0x02
            content = content[position:position + size].split(b"\x00", 1)
            tgt_path = content[-1].decode("utf-16" if len(content) > 1 else locale.getdefaultlocale()[1])
    return pathlib.Path(tgt_path)


# DEF: Get the list of all directories inside a parent directory
def dir_list(directory:pathlib.Path, result:str):
    dirlist = []
    for dirpath, dirnames, filenames in os.walk(directory):
        if result == "dirs":
            dirlist.extend(dirnames)
        elif result == "files":
            dirlist.extend(filenames)
        break
    return dirlist


# DEF: Check if a directory contains a folder or file (case insensitive)
# Ignore items list and return case-sensitive path for apt.dat or Earth nav data calls
def dir_contains(directory:pathlib.Path, items:list, variant:str = None):
    # First find Earth nav data folder through recursion, then search for apt.dat file within it
    if variant == "apt.dat":
        end_folder = dir_contains(directory, None, variant = "Earth nav data")
        if end_folder:
            list_files = dir_list(end_folder, "files")
            for file in list_files:
                if file.lower() == "apt.dat":
                    return directory / end_folder / file
    # Find Earth nav data folder and return case-sensitive path
    elif variant == "Earth nav data":
        list_dirs = dir_list(directory, "dirs")
        for folder in list_dirs:
            if folder.lower() == "earth nav data":
                return directory / folder
    # Find if file or folder is present
    elif variant in [None, "generic"]:
        item_present = {}
        list_obj = dir_list(directory, "files" if variant == "generic" else "dirs")
        for item in items:
            item_present[item] = False
            for obj in list_obj:
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


# DEF: Read uncompresssed DSF
# This code is adapted from https://gist.github.com/nitori/6e7be6c9f00411c12aacc1ee964aee88 - thank you very much!
def mesh_dsf_decode(filepath:pathlib.Path, dirname):
    try:
        size = os.stat(filepath).st_size
    except FileNotFoundError:
        if DEBUG >= 2:
            print(f"  [E] decode dsf: expected dsf '{str(filepath.name)}'. extracted files from dsf: {dir_list(filepath.parent.absolute(), 'files')}")
        return "ERR: DCDE: NameMatch"
    footer_start = size - 16  # 16 byte (128bit) for md5 hash
    digest = hashlib.md5()
    try:
        with open(filepath, "rb") as dsf:
            # read 8s = 8 byte string, and "i" = 1 32 bit integer (total: 12 bytes)
            raw_header = dsf.read(12)
            header, version = struct.unpack("<8si", raw_header)
            digest.update(raw_header)
            # Proceed only if the version and header match what we expect, else return a string
            if version == 1 and header == b"XPLNEDSF":
                dsf_data = []
                while dsf.tell() < footer_start:
                    raw_atom_header = dsf.read(8)
                    digest.update(raw_atom_header)
                    # 32bit atom id + 32 bit atom_size.. total: 8 byte
                    atom_id, atom_size = struct.unpack("<ii", raw_atom_header)
                    atom_id = struct.pack(">i", atom_id) # "DAEH" -> "HEAD"
                    # data size is atom_size excluding the just read 8 byte id+size header
                    atom_data = dsf.read(atom_size - 8)
                    digest.update(atom_data)
                    dsf_data.append((atom_id, atom_size, atom_data))
                # remaining bit is the checksum, check if it matches
                checksum = dsf.read()
                if checksum != digest.digest():
                    if DEBUG >= 2:
                        print(f"  [E] mesh_dsf_decode: checksum mismatch")
                    return "ERR: DCDE: !Checksum"
                return dsf_data
            elif header != b"XPLNEDSF":
                if header.startswith(b"7z"):
                    if DEBUG >= 2:
                        print(f"  [E] mesh_dsf_decode: got '7z' header. extraction failure?")
                    return "ERR: DCDE: NoExtract"
                else:
                    if DEBUG >= 2:
                        print(f"  [E] mesh_dsf_decode: unknown header. got '{header}'")
                    return "ERR: DCDE: !XPLNEDSF"
            elif version != 1:
                if DEBUG >= 2:
                    print(f"  [E] mesh_dsf_decode: unknown dsf version. got '{version}'")
                return f"ERR: DCDE: v{((8 - len(str(version))) * ' ') + str(version)}"
    except Exception as e:
        if DEBUG >= 2:
            print(f"  [E] mesh_dsf_decode: unhandled error '{e}'")
        return "ERR: DCDE: BadDSFErr"


# DEF: Select and read DSF. Uncompress if needed and call mesh_dsf_decode(). Return HEAD atom
def mesh_dsf_read(end_directory:pathlib.Path, tag:str, dirname:str):
    # Attempt to fetch cached data
    try:
        with open(end_directory.parent.absolute() / "sporganiser_cache.yaml", "r") as yaml_file:
            dsf_cache_data = yaml.load(yaml_file, Loader = yaml.FullLoader)
            if DEBUG >= 2:
                print(f"  [I] mesh_dsf_read: loaded cached data")
    except FileNotFoundError:
        dsf_cache_data = {"version": 220}
    # Read cached data
    dsf_cache_data_iter = copy.deepcopy(dsf_cache_data)
    try:
        for dsf in dsf_cache_data_iter:
            # check version
            if dsf == "version":
                if not dsf_cache_data[dsf] == 220:
                    if DEBUG >= 2:
                        print(f"  [W] mesh_dsf_read: unknown version tag. got '{dsf_cache_data[dsf]}'")
                    dsf_cache_data = {"version": 220}
                    break
                continue
            # locate dsf cached and check that it exists
            dsf_path = end_directory / dsf
            if not dsf_path.exists():
                if DEBUG >= 2:
                    print(f"  [W] mesh_dsf_read: cached dsf '{str(dsf_path)}' doesn't exist")
                del dsf_cache_data[dsf]
                continue
            # hash dsf to ensure cached data is still valid
            sha1 = hashlib.sha1()
            md5 = hashlib.md5()
            with open(dsf_path, 'rb') as dsf_file:
                while True:
                    data = dsf_file.read(BUF_SIZE)
                    if not data:
                        break
                    sha1.update(data)
                    md5.update(data)
            if not (dsf_cache_data[dsf]["md5"] == md5.hexdigest() and dsf_cache_data[dsf]["sha1"] == sha1.hexdigest()):
                if DEBUG >= 2:
                    print(f"  [W] mesh_dsf_read: hash of cached dsf '{str(dsf_path)}' doesn't match")
                del dsf_cache_data[dsf]
                continue
            # attempt to get the tag data requested
            try:
                tag_data = dsf_cache_data[dsf][tag]
                return tag_data
            except KeyError:
                pass
    except Exception as e:
        if DEBUG >= 2:
            print(f"  [E] mesh_dsf_read: unhandled error '{e}'")
        dsf_cache_data = {"version": 220}        
    # Get list of potential tile directories to search
    list_dir = dir_list(end_directory, "dirs")
    tile_dir = []
    for dir in list_dir:
        if re.search(r"[+-]\d{2}[+-]\d{3}", dir):
            tile_dir.append(dir)
    if not tile_dir:
        if DEBUG >= 2:
            print(f"  [E] mesh_dsf_read: earth nav dir is empty - '{end_directory}'")
        return "ERR: READ: NDirEmpty"
    # Going one tile at a time, attempt to extract a dsf from the tile
    uncomp_flag = 0
    dsf_data = None
    final_tile = None
    final_dsf = None
    for tile in tile_dir:
        dsfs = dir_list(end_directory / tile, "files")
        for dsf in dsfs:
            # If not a dsf file, move on
            if not dsf.endswith(".dsf"):
                continue
            # Attempt to extrat this DSF. If it fails, the DSF was already uncompressed or is corrupt
            else:
                if DEBUG >= 2:
                    print(f"  [I] mesh_dsf_read: extracting '{end_directory / tile / dsf}'")
                try:
                    shutil.unpack_archive(end_directory / tile / dsf, TEMPORARY_PATH / dirname / dsf[:-4])
                    uncomp_path = TEMPORARY_PATH / dirname / dsf[:-4] / dsf
                    uncomp_flag = 2
                    if DEBUG >= 2:
                        print(f"  [I] mesh_dsf_read: extracted")
                except Exception as e: 
                    uncomp_path = end_directory / tile / dsf
                    if isinstance(e, py7zr.exceptions.Bad7zFile):
                        uncomp_flag = 1
                        if DEBUG >= 2:
                            print(f"  [I] mesh_dsf_read: not a 7z archive. working on dsf directly")
                    else:
                        dsferror_registry.append([f"{dsf}' in '{end_directory.parent.absolute()}", "ERR: READ: MiscError"])
                        uncomp_flag = 0
                        if DEBUG >= 2:
                            print(f"  [E] mesh_dsf_read: unhandled error '{e}'. working on dsf directly")
                # Now attempt to decode this DSF
                dsf_data = mesh_dsf_decode(uncomp_path, dirname)
                # If it returns an error, try the next one. Else, get out of the intra-tile loop
                if str(dsf_data).startswith("ERR: ") or dsf_data == None:
                    dsferror_registry.append([f"{dsf} in {end_directory.parent.absolute()}", dsf_data])
                    uncomp_flag = 0
                    if DEBUG >= 2:
                        print(f"  [W] mesh_dsf_read: caught '{str(dsf_data)}' from mesh_dsf_decode")
                    continue
                else:
                    final_tile = tile
                    final_dsf = dsf
                    break
        # If a DSF was successfully read, get out of the inter-tile loop. Else, move on to the next tile folder
        if uncomp_flag:
            break
        else:
            continue
    # If this for loop was never broken, it means we weren't able to read a DSF
    else:
        if DEBUG >= 2:
            print(f"  [E] mesh_dsf_read: tile loop was not broken, ie. no dsf could be read")
        return "ERR: READ: TileEmpty"
    # Search for sim/overlay in HEAD atom. If found, return True
    if tag == "sim/overlay 1":
        overlay = None
        for atom_id, atom_size, atom_data in dsf_data:
            if atom_id == b"HEAD" and b"sim/overlay\x001" in atom_data:
                overlay = True
                break
        else:
            overlay = False
        # Generate hashes
        sha1 = hashlib.sha1()
        md5 = hashlib.md5()
        with open(end_directory / tile / dsf, 'rb') as dsf_file:
            while True:
                data = dsf_file.read(BUF_SIZE)
                if not data:
                    break
                sha1.update(data)
                md5.update(data)
        # Store result to speed up future runs
        dsf_cache_data_new = {f"{final_tile}/{final_dsf}": {"sim/overlay 1": overlay, "md5": md5.hexdigest(), "sha1": sha1.hexdigest()}}
        dsf_cache_data.update(dsf_cache_data_new)
        with open(end_directory.parent.absolute() / "sporganiser_cache.yaml", "w") as yaml_file:
            yaml.dump(dsf_cache_data, yaml_file)
        if DEBUG >= 2:
            print(f"  [I] mesh_dsf_read: new cache written")
        # Return result
        return overlay
    else:
        if DEBUG >= 2:
            print(f"  [E] mesh_dsf_read: unspecified or unimplemented property to search - '{str(tag)}'")
        return "ERR: READ: NoSpecify"


# DEF: Check if the pack is an airport
def process_type_apt(dirpath:pathlib.Path, dirname:str, file_line:str, disable:bool):
    # Basic checks before we move further
    apt_path = dir_contains(dirpath, None, "apt.dat")
    if not apt_path:
        if DEBUG >= 2:
            print("  [I] process_type_apt: 'apt.dat' file not found")
        return
    # Attempt several codecs starting with utf-8 in case of obscure apt.dat files
    apt_lins = None
    for codec in ("utf-8", "charmap", "cp1252", "cp850"):
        try:
            if DEBUG >= 2:
                print(f"  [I] process_type_apt: reading apt.dat with '{codec}'")
            with open(apt_path, "r", encoding = codec) as apt_file:
                apt_lins = apt_file.readlines()
            break
        except UnicodeDecodeError:
            pass
    else:
        if DEBUG >= 2:
            print(f"  [W] process_type_apt: all codecs errored out")
    # Loop through lines
    apt_type = None
    for line in apt_lins:
        # Codes for airport, heliport, seaport
        if line.startswith("1 ") or line.startswith("16 ") or line.startswith("17 "):
            # Check if prefab, default, or global
            apt_prefab = process_quirk_prefab(dirpath, dirname)
            if apt_prefab:
                apt_type = apt_prefab
                break
            elif str_contains(dirname, ["Demo Area", "X-Plane Airports", "X-Plane Landmarks", "Aerosoft"]):
                apt_type = "Default"
                if DEBUG >= 2:
                    print("  [I] process_type_apt: found to be default airport")
                break
            if apt_path and dirname == "Global Airports":
                apt_type = "Global"
                if DEBUG >= 2:
                    print("  [I] process_type_apt: found to be global airport")
                break
            # Must be custom
            else:
                apt_type = "Custom"
                # If pack is not to be disabled, note ICAO code from this line
                if not disable:
                    splitline = line.split(maxsplit=5)
                    icao_code = splitline[4]
                    # Update icao registry
                    try:
                        icao_registry[icao_code] += 1
                    except KeyError:
                        icao_registry[icao_code] = 1
                    # Update airport registry
                    try:
                        reg_index = airport_registry["path"].index(dirpath)
                        airport_registry["icaos"][reg_index].append(icao_code)
                    except ValueError:
                        airport_registry["path"].append(dirpath)
                        airport_registry["line"].append(file_line)
                        airport_registry["icaos"].append([icao_code])
    return apt_type


# DEF: Classify as AutoOrtho, Ortho, Mesh, or Overlay after reading DSF and scanning folders
def process_type_mesh(dirpath:pathlib.Path, dirname:str):
    end_path = dir_contains(dirpath, None, "Earth nav data")
    # Basic check
    if not end_path:
        if DEBUG >= 2:
            print("  [I] process_type_mesh: 'Earth nav data' folder not found")
        return
    # Read DSF and check for sim/overlay. If error or None returned, log in dsf error registry
    overlay = mesh_dsf_read(end_path, "sim/overlay 1", dirname)
    if str(overlay).startswith("ERR: ") or overlay == None:
        if DEBUG >= 2:
            print(f"  [W] process_type_mesh: caught '{str(overlay)}' from mesh_dsf_read")
        dsferror_registry.append([dirpath, overlay])
        return
    mesh_ao = process_quirk_ao(dirpath, dirname)
    if overlay:
        if mesh_ao in ["AO Overlay"]:
            return mesh_ao
        elif str_contains(dirname, ["X-Plane Landmarks"]):
            return "Default Overlay"
        else:
            return "Custom Overlay"
    else:
        if mesh_ao in ["AO Region", "AO Root"]:
            return mesh_ao
        elif dir_contains(dirpath, ["textures", "terrain"]):
            return "Ortho Mesh"
        else:
            return "Terrain Mesh"


# DEF: Check misc types
def process_type_other(dirpath:pathlib.Path, dirname:str):
    other_result = None
    if dir_contains(dirpath, ["library.txt"], "generic"):
        other_result = "Library"
    if dir_contains(dirpath, ["plugins"]):
        other_result = "Plugin"
    if DEBUG >= 2 and other_result:
        print(f"  [I] process_type_other: found to be {other_result}")
    elif DEBUG >= 2:
        print(f"  [I] process_type_other: neither library.txt nor plugins folder found")
    return other_result


# DEF: Check if the pack is a prefab airport
def process_quirk_prefab(dirpath:pathlib.Path, dirname:str):
    prefab_result = None
    if str_contains(dirname, ["prefab"], casesensitive = False):
        prefab_result = "Prefab Apt"
    if DEBUG >= 2 and prefab_result:
        print(f"    [I] process_quirk_prefab: found to be {prefab_result}")
    return prefab_result


# DEF: Check if the pack is from autoortho
def process_quirk_ao(dirpath:pathlib.Path, dirname:str):
    ao_regions = ["na", "sa", "eur", "afr", "asi", "aus_pac"]
    ao_result = None
    if str_contains(dirname, ["yAutoOrtho_Overlays"]):
        ao_result = "AO Overlay"
    elif str_contains(dirname, [f"z_ao_{region}" for region in ao_regions]):
        ao_result = "AO Region"
    elif str_contains(dirname, ["z_autoortho"]):
        ao_result = "AO Root"
    if DEBUG >= 2 and ao_result:
        print(f"    [I] process_quirk_ao: found to be {ao_result}")
    return ao_result


# DEF: Classify the pack
def process_main(path, shortcut = False):
    abs_path = SCENERY_PATH / path
    name = str(path)
    classified = False
    # Define path formatted for ini
    if shortcut:
        ini_path = str(abs_path)
    else:
        ini_path = str(path)
    # Define line formatted for ini
    disable = ini_path in disable_registry
    if disable:
        del disable_registry[ini_path]
        if shortcut:
            line = f"{FILE_DISAB_LINE_ABS}{ini_path}/\n"
        else:
            line = f"{FILE_DISAB_LINE_REL}{ini_path}/\n"
    else:    
        if shortcut:
            line = f"{FILE_LINE_ABS}{ini_path}/\n"
        else:
            line = f"{FILE_LINE_REL}{ini_path}/\n"
    # First see if it's an airport
    if not classified:
        pack_type = process_type_apt(abs_path, name, line, disable)
        classified = True
        # Standard definitions
        if pack_type in ["Global", "Default", "Custom"]:
            airports[pack_type].append(line)
            if DEBUG >= 2:
                print(f"  [I] process_main: classified as '{pack_type.lower()} Airport'")
        # Quirk handling
        elif pack_type in ["Prefab Apt"]:
            quirks[pack_type].append(line)
            if DEBUG >= 2:
                print(f"  [I] process_main: classified as quirk '{pack_type.lower()}'")
        else:
            classified = False
    # Next, autortho, overlay, ortho or mesh
    if not classified:
        pack_type = process_type_mesh(abs_path, name)
        if not pack_type: 
            pack_type = process_quirk_ao(abs_path, name)
        classified = True
        # Standard definitions
        if pack_type in ["Default Overlay", "Custom Overlay"]:
            overlays[pack_type[:-8]].append(line)
            if DEBUG >= 2:
                print(f"  [I] process_main: classified as '{pack_type.lower()}'")
        elif pack_type in ["Ortho Mesh", "Terrain Mesh"]:
            meshes[pack_type[:-5]].append(line)
            if DEBUG >= 2:
                print(f"  [I] process_main: classified as '{pack_type.lower()}'")
        # Quirk handling
        elif pack_type in ["AO Overlay", "AO Region", "AO Root"]:
            quirks[pack_type].append(line)
            if DEBUG >= 2:
                print(f"  [I] process_main: classified as quirk '{pack_type.lower()}'")
        else:
            classified = False
    # Very lax checks for plugins and libraries
    if not classified:
        pack_type = process_type_other(abs_path, name)
        classified = True
        # Standard definitions
        if pack_type in ["Plugin", "Library"]:
            misc[pack_type].append(line)
            if DEBUG >= 2:
                print(f"  [I] process_main: classified as '{pack_type.lower()}'")
        # Quirk handling
        elif pack_type in []:
            quirks[pack_type].append(line)
            if DEBUG >= 2:
                print(f"  [I] process_main: classified as quirk '{pack_type.lower()}'")
        else:
            classified = False
    # Give up. Add this to the list of packs we couldn't sort
    if not classified:
        if DEBUG >= 2:
            print(f"  [W] process_main: could not be classified")
        if line.startswith(FILE_DISAB_LINE_ABS):
            unsorted_registry.append(line[22:])
        elif line.startswith(FILE_LINE_ABS):
            unsorted_registry.append(line[13:])
        else:
            pass


print("\nI will now classify each scenery pack...")
measure_time.append(time.time())


# Process each directory in the Custom Scenery folder
maxlength = 0
folder_list = dir_list(SCENERY_PATH, "dirs")
folder_list.sort()
for directory in folder_list:
    if DEBUG >= 1:
        print(f"Main: Starting dir: {directory}")
    else:
        # Whitespace padding to print in the shell
        progress_str = f"Processing: {directory}"
        if len(progress_str) <= maxlength:
            progress_str = f"{progress_str}{' ' * (maxlength - len(progress_str))}"
        else:
            maxlength = len(progress_str)
        print(f"\r{progress_str}", end = "\r")
    process_main(directory)
    if DEBUG >= 1 and DEBUG < 2:
        print(f"Main: Finished dir: {directory}")
print()

# Process each Windows shortcut in the Custom Scenery folder
maxlength = 0
printed = False
shtcut_list = [str(SCENERY_PATH / shtcut) for shtcut in dir_list(SCENERY_PATH, "files") if shtcut.endswith(".lnk")]
shtcut_list.sort()
if shtcut_list and sys.platform != "win32":
    print(f"\nI found Windows .LNK shortcuts, but I'm not on Windows! Detected platform: {sys.platform}")
    print("I will still attempt to read them, but I cannot guarantee anything. I would suggest you use symlinks instead.")
elif shtcut_list and sys.platform == "win32":
    print("\nReading .LNK shortcuts...")
# If the code raises an error internally or if we were given a garbled path, skip it and add to the list of unparsable shortcuts
for shtcut_path in shtcut_list:
    try:
        folder_path = process_shortcut_read(shtcut_path)
        if folder_path.exists():
            if DEBUG >= 1:
                print(f"Main: Starting shortcut: {folder_path}")
            else:
                # Whitespace padding to print in the shell
                progress_str = f"Processing shortcut: {str(folder_path)}"
                if len(progress_str) <= maxlength:
                    progress_str = f"{progress_str}{' ' * (maxlength - len(progress_str))}"
                else:
                    maxlength = len(progress_str)
                print(f"\r{progress_str}", end = "\r")
                printed = True
            process_main(folder_path, shortcut = True)
            if DEBUG >= 1 and DEBUG < 2:
                print(f"Main: Finished shortcut: {folder_path}")
            continue
        else: 
            if DEBUG >= 1:
                print(f"Main: Failed shortcut: {folder_path}")
    except Exception as e:
        print(e)
        if DEBUG >= 1:
            print(f"Main: Failed shortcut: {shtcut_path}")
    unparsed_registry.append(shtcut_path)
if printed:
    print()

# Destroy temp path
shutil.rmtree(TEMPORARY_PATH)

# Sort tiers alphabetically
unsorted_registry.sort()
for key in quirks:
    quirks[key].sort()
for key in airports:
    airports[key].sort()
for key in overlays:
    overlays[key].sort()
for key in meshes:
    meshes[key].sort()
for key in misc:
    misc[key].sort()

# Check to inject XP12 Global Airports
if not airports["Global"]:
    if DEBUG:
        print("  [I] Main: XP10/11 global airports not found, injecting XP12 entry")
    airports["Global"].append(XP12_GLOBAL_AIRPORTS)

# Display time taken in this operation
print(f"Done! Took me {time.time() - measure_time.pop()} seconds to classify.")


# Display all packs that errored when reading DSFs (if debugging enabled)
if dsferror_registry and DEBUG:
    print("\n[W] Main: I was unable to read DSF files from some scenery packs. Please check if they load correctly in X-Plane.")
    print("[^] Main: This does not necessarily mean that the pack could not be classified. Such packs will be listed separately.")
    print("[^] Main: I will list them out now with the error type.")
    for dsffail in dsferror_registry:
        print(f"[^]   {dsffail[1]} in '{dsffail[0]}'")


# Display all disabled packs that couldn't be found
if disable_registry:
    print("\nI was unable to find some packs that were tagged DISABLED in the old scenery_packs.ini.")
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


# Display all packs that couldn't be sorted and offer to write them at the top of the file
if unsorted_registry:
    measure_time.append(time.time())
    print("\nI was unable to classify some packs. Maybe the pack is empty? Otherwise, a folder-in-folder?")
    print("I will list them out now")
    for line in unsorted_registry:
        line_stripped = line.strip("\n")
        print(f"    {line_stripped}")
    print("Note that if you choose not to write them, they will be written as DISABLED packs to prevent unexpected errors.")
    while True:
        choice_unsorted = input("Should I still write them into the ini? (yes/no or y/n): ").lower()
        if choice_unsorted in ["y","yes"]:
            print("Ok, I will write them at the top of the ini.")
            tmp_unsorted_registry = []
            for line in unsorted_registry:
                tmp_unsorted_registry.append(f"{FILE_LINE_ABS}{line}")
            unsorted_registry = copy.deepcopy(tmp_unsorted_registry)
            break
        elif choice_unsorted in ["n","no"]:
            print("Ok, I will write them at the top of the ini as DISABLED packs.")
            tmp_unsorted_registry = []
            for line in unsorted_registry:
                tmp_unsorted_registry.append(f"{FILE_DISAB_LINE_ABS}{line}")
            unsorted_registry = copy.deepcopy(tmp_unsorted_registry)
            break
        else:
            print("  Sorry, I didn't understand.")
    print(f"Waited {time.time() - measure_time.pop()} seconds for your input")


# Time and variable declarations for printing
print("\nI will now check for Custom Airport overlaps...")
measure_time.append(time.time())
airport_list = {}
list_num = 0

# Check how many conflicting ICAOs we have and store them in icao_conflicts
for icao in icao_registry:
    if icao_registry[icao] > 1: 
        icao_conflicts.append(icao)

# Display conflicting packs in a list
for reg_index in range(len(airport_registry["path"])):
    airport_path = airport_registry["path"][reg_index]
    airport_line = airport_registry["line"][reg_index]
    airport_icaos = airport_registry["icaos"][reg_index]
    # Check if this airport's ICAOs are among the conflicting ones. If not, skip it
    airport_icaos_conflicting = list(set(airport_icaos) & set(icao_conflicts))
    airport_icaos_conflicting.sort()
    if airport_icaos_conflicting:
        pass
    else:
        continue
    # Print path and ICAOs
    airport_icao_string = ""
    for icao in airport_icaos_conflicting:
        airport_icao_string += f"{icao} "
    print(f"    {list_num}: '{airport_path}': {airport_icao_string[:-1]}")
    # Log this with the number in list
    airport_list[list_num] = airport_line
    # Incremenent i for the next pack
    list_num += 1

# Check if user wants to sort conflicts
if icao_conflicts:
    # TODO: Import preferences
    while True:
        resolve_conflicts = input(f"\nI've listed out all airport packs with their overlapping ICAOs. Would you like to sort them now? (yes/no or y/n): ").lower()
        if resolve_conflicts in ["y","yes"]:
            resolve_conflicts = True
            break
        elif resolve_conflicts in ["n","no"]:
            print("Alright, I'll skip this part.")
            resolve_conflicts = False
            break
        else:
            print("  Sorry, I didn't understand.")
    if not resolve_conflicts:
        print(f"Waited {time.time() - measure_time.pop()} seconds for your input")
    else:
        measure_time.pop()
else:
    print("No overlaps found.")
    resolve_conflicts = None
    measure_time.pop()

# Time declarations for sorting
measure_time.append(time.time())

# Sorting algorithm
if resolve_conflicts:
    tmp_valid_flag = True
    while True:
        # Get input if the user chose to resolve
        newline = "\n"
        order = input(f"{'' if tmp_valid_flag else newline}Enter the numbers in order of priority from higher to lower, separated by commas: ")
        tmp_valid_flag = True
        # There is no concievable case in which this throws an error, but one can never be sure
        try:
            order = order.strip(" ").split(",")
            order[:] = [int(item) for item in order if item != '']
        except:
            print("    I couldn't read this input!")
            tmp_valid_flag = False
        # Check if all the packs shown are present in this input
        if (set(order) != set(range(list_num))) and tmp_valid_flag:
            print("    Hmm, that wasn't what I was expecting...")
            tmp_valid_flag = False
        # If this was an invalid input, show the user what a possible input would look like
        if not tmp_valid_flag:
            print("    I recommend you read the instructions if you're not sure what to do.")
            print("    For now though, I will show a basic example for your case below.")
            example_str = ""
            for i in range(list_num):
                example_str += f"{i},"
            print(f"    {example_str[:-1]}")
            print("    You can copy-paste this as-is, or move the numbers as you wish.")
        # If this input's valid, move on
        else:
            break
    # Manipulate custom airports list
    tmp_customairports = copy.deepcopy(airports["Custom"])
    tmp_customoverlaps = list()
    for i in order:
        tmp_customoverlaps.append(tmp_customairports.pop(tmp_customairports.index(airport_list[i])))
    tmp_customoverlaps.extend(tmp_customairports)
    airports["Custom"] = copy.deepcopy(tmp_customoverlaps)

# Display time after this ordeal if chosen to resolve, else advise to go through the ini manually, else do nothing
    print(f"Done! Took me {time.time() - measure_time.pop()} seconds with your help.\n")
elif icao_conflicts:
    measure_time.pop()
    print("You may wish to manually go through the ini file for corrections.\n")
else:
    measure_time.pop()


scenery_ini_path_dep = pathlib.Path(SCENERY_PATH / "scenery_packs.ini")
scenery_ini_path_nay = pathlib.Path(SCENERY_PATH / "scenery_packs_unsorted.ini")
scenery_ini_path_bak = pathlib.Path(f"{scenery_ini_path_dep}.bak")

# Remove the old backup file, if present
try:
    if scenery_ini_path_bak.exists():
        print("I will now delete the old scenery_packs.ini.bak")
        scenery_ini_path_bak.unlink()
except Exception as e:
    print(f"Failed to delete! Maybe check the file permissions? Error: '{e}'")

# Back up the current scenery_packs.ini file
try:
    if scenery_ini_path_dep.exists():
        print("I will now back up the current scenery_packs.ini")
        scenery_ini_path_dep.rename(scenery_ini_path_bak)
except Exception as e:
    print(f"Failed to rename .ini to .ini.bak! Maybe check the file permissions? Error: '{e}'")

# Write out the new scenery_packs.ini file
print("I will now write the new scenery_packs.ini")


# These are our packs
packs = {
    "unsorted": unsorted_registry,
    "airports: custom": airports["Custom"],
    "airports: default": airports["Default"],
    "quirks: prefab apt": quirks["Prefab Apt"],
    "airports: global": airports["Global"],
    "misc: plugin": misc["Plugin"],
    "misc: library": misc["Library"],
    "overlays: custom": overlays["Custom"],
    "overlays: default": overlays["Default"],
    "quirks: ao overlay": quirks["AO Overlay"],
    "meshes: ortho": meshes["Ortho"],
    "quirks: ao region": quirks["AO Region"],
    "quirks: ao root": quirks["AO Root"],
    "meshes: terrain": meshes["Terrain"]
    }
# Write unsorted packs to scenery_packs_unsorted.ini
with open(scenery_ini_path_nay, "w+", encoding = "utf-8") as f:
    f.write(FILE_BEGIN)
    if packs["unsorted"]:
        f.writelines(packs["unsorted"])
# Write everything to scenery_packs.ini
with open(scenery_ini_path_dep, "w+", encoding = "utf-8") as f:
    f.write(FILE_BEGIN)
    for pack_type in packs:
        pack_list = packs[pack_type]
        if DEBUG:
            print(pack_type)
        if pack_list:
            f.writelines(pack_list)
            if DEBUG:
                for pack in pack_list:
                    print(f"    {pack.strip()}")
        elif DEBUG:
            print(f"    --empty--")
print("\nDone!")
print(f"Took me {time.time() - measure_time.pop()} seconds in total.")


# Get X-Plane executable name. If unsupported platform, exit
if sys.platform == "win32":
    xplane_exe = "X-Plane.exe"
elif sys.platform == "darwin":
    xplane_exe = "X-Plane.app"
elif sys.platform == "linux":
    xplane_exe = "X-Plane-x86_64"
else:
    input("Unsupported platform for X-Plane. Press enter to close")
    exit()

# Get X-Plane executable path and check if present. If not, exit
xplane_exe = SCENERY_PATH.parent.absolute() / xplane_exe
if (sys.platform in ["win32", "linux"] and not xplane_exe.is_file()) or (sys.platform in ["darwin"] and not xplane_exe.is_dir()):
    input("X-Plane executable is invalid or could not be found. Press enter to close")
    exit()

# Ask the user if they wish to launch X-Plane. If no, exit
choice_launch = None
while True:
    choice_launch = input(f"Would you like to launch X-Plane at '{str(xplane_exe)}'? (yes/no or y/n): ").lower()
    if choice_launch in ["y", "yes"]:
        print("Ok, I am launching X-Plane now. Do not close this window.")
        break
    elif choice_launch in ["n", "no"]:
        print("Ok, I will not launch X-Plane.")
        input("Press enter to close")
        exit()
    else:
        print("  Sorry, I didn't understand.")

# Launch X-Plane
print("\n\n")
if sys.platform in ["win32", "linux"]:
    os.system(f'"{str(xplane_exe)}"')
elif sys.platform in ["darwin"]:
    os.system(f'open -a "{str(xplane_exe)}"')
