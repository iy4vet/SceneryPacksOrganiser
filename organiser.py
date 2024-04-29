#!/usr/bin/env python3

import argparse
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


# TODO: automate these later
import py7zr
import yaml
if sys.platform == "win32":
    import win32com.client


# Global variable declarations
XP10_GLOBAL_AIRPORTS = "SCENERY_PACK Custom Scenery/Global Airports/\n"
XP12_GLOBAL_AIRPORTS = "SCENERY_PACK *GLOBAL_AIRPORTS*\n"
FILE_LINE_REL = "SCENERY_PACK Custom Scenery/"
FILE_LINE_ABS = "SCENERY_PACK "
FILE_DISAB_LINE_REL = "SCENERY_PACK_DISABLED Custom Scenery/"
FILE_DISAB_LINE_ABS = "SCENERY_PACK_DISABLED "
FILE_BEGIN = "I\n1000 Version\nSCENERY\n\n"
BUF_SIZE = 65536


# TODO: Steam X-Plane support
class locate_xplane:
    # Ref: https://developer.x-plane.com/article/how-to-programmatically-locate-x-plane-9-or-10/
    def __init__(self, debug:int) -> None:
        # External variable declarations
        self.debug = debug
        # Internal variable declarations
        self.direct_lines = list()
        self.steam_lines = list()
        self.xplane_path = pathlib.Path()
        # Find the preferences folder - this varies by system
        self.prefs_folder = pathlib.Path()
        if sys.platform == "win32":
            self.prefs_folder = pathlib.Path(os.path.expandvars("%USERPROFILE%/AppData/Local"))
        elif sys.platform == "darwin":
            self.prefs_folder = pathlib.Path(os.path.expanduser("~/Library/Preferences"))
        elif sys.platform == "linux":
            self.prefs_folder = pathlib.Path(os.path.expanduser("~/.x-plane"))
        else:
            print(f"Unsupported OS detected. Please report this error. Detected platform: {sys.platform}")
        if self.debug >= 1:
            print(f"  [I] locate_xplane init: using {self.prefs_folder}")            
    
    def direct_search(self):
        # Go through the text file for each X-Plane version...
        if self.prefs_folder.exists():
            for version in ["_10", "_11", "_12"]:
                formatted_version = version.strip('_') if version else '9'
                try:
                    if self.debug >= 2:
                        print(f"  [I] locate_xplane direct_search: reading {formatted_version}")
                    install_file = self.prefs_folder / f"x-plane_install{version}.txt"
                    with open(install_file, "r", encoding = "utf-8") as file:
                        # ...and read its lines to get potential install paths
                        for install_line in file.readlines():
                            self.direct_lines.append([f"X-Plane {formatted_version}", install_line, install_file])
                # In case the text file for this version doesn't exist
                except FileNotFoundError:
                    if self.debug >= 1:
                        print(f"  [W] couldn't find {formatted_version}")
        elif self.debug >= 1:
            print("  [I] locate_xplane direct_search: folder doesn't exist")
    
    def steam_search(self):
        pass
    
    def direct_test(self):
        # Create a copy of our record of direct lines to avoid errors with the iterable changing during iteration
        direct_lines_copy = copy.deepcopy(self.direct_lines)
        # Loop through the parsed lines...
        for version, install_line, install_file in direct_lines_copy:
            install_path = pathlib.Path(install_line.strip("\n"))
            # ...and test each path to ensure it's not "old and stale". if it is...
            if (install_path / "Custom Scenery").exists() and (install_path / "Resources").exists():
                if self.debug >= 2:
                    print(f"  [I] locate_xplane direct_test: validated {install_path}")
            else:
                # ...remove it from the text file!
                print(f"Removing stale path {install_path} from {install_file}")
                file_lines = list()
                with open(self.prefs_folder / install_file, "r+") as file:
                    for file_line in file.readlines():
                        if file_line == install_line:
                            continue
                        file_lines.append(file_line)
                    file.seek(0)
                    file.writelines(file_lines)
                    file.truncate()
                # Oh and remove it from our record too :)
                self.direct_lines.remove([version, install_line, install_file])
    
    def finalise_path(self):
        # Fly my dear birds! Fly, and bring with you whatever X-Plane paths you could find!
        print()
        self.direct_search()
        self.direct_test()
        self.steam_search()
        print()
        # Add everything up to one list, then display it...
        compiled_lines = self.direct_lines + self.steam_lines
        if compiled_lines:
            print("I found the following X-Plane installs:")
            for i in range(len(compiled_lines)):
                xplane_version = compiled_lines[i][0]
                xplane_path = compiled_lines[i][1].strip('\n')
                print(f"    {i}: {xplane_version} at {xplane_path}")
            print("If you want to use one of these, enter its number as shown in the list.")
            print("Otherwise, enter the path to your X-Plane folder.")
        # ...or if we didn't find any paths, just ask the user to input a path
        else:
            if self.debug >= 1:
                print(f"  [I] locate_xplane finalise_path: couldn't locate any x-plane folders automatically")
            print("Please enter the path to your X-Plane folder.")
        # Get the user's selection, then validate it
        while True:
            choice = input("Enter selection here: ")
            # See if it corresponds to our list. If not, treat it as its own path
            try:
                self.xplane_path = pathlib.Path(compiled_lines[int(choice)][1].strip("\n"))
            except (ValueError, IndexError):
                self.xplane_path = pathlib.Path(choice)
            # Validate the path
            if (self.xplane_path / "Custom Scenery").exists():
                print(f"  Selected path: {self.xplane_path}")
                break
            else:
                print("  I couldn't see a Custom Scenery folder here! Please recheck your path. ")


# TODO: macOS Alias support
class sort_packs:
    def __init__(self, debug:int, xplane_path:pathlib.Path, temp_path:str) -> None:
        # External variable declarations
        self.debug = debug
        self.xplane_path = xplane_path
        self.temp_path = temp_path
        # Internal variable declarations
        self.icao_registry = {}     # dict of ICAO codes and the number of packs serving each
        self.disable_registry = {}  # dict that holds the folder line and beginning line of disabled packs
        self.dsferror_registry = [] # list of errored dsfs
        self.unparsed_registry = [] # list of .lnk shortcuts that couldn't be parsed
        self.airport_registry = {"path": [], "line": [], "icaos": []}    
                                    # dict that holds the folder path, file line, and a list of ICAOs served
                                    # to use, get the index via folder path and use that within each key-value
        # Classification variable declarations
        self.unsorted_registry = []      # list of packs that couldn't be classified
        self.quirks = {"Prefab Apt": [], "AO Overlay": [], "AO Region": [], "AO Root": []}
        self.airports = {"Custom": [], "Default": [], "Global": []}
        self.overlays = {"Custom": [], "Default": []}
        self.meshes = {"Ortho": [], "Terrain": []}
        self.other = {"Plugin": [], "Library": []}
        # Misc functions declarations
        self.misc_functions = misc_functions(debug)
    
    # Read old ini to get list of disabled packs
    def import_disabled(self):
        deployed_ini_path = self.xplane_path / "Custom Scenery" / "scenery_packs.ini"
        unsorted_ini_path = self.xplane_path / "Custom Scenery" / "scenery_packs_unsorted.ini"
        if deployed_ini_path.is_file():
            with open(deployed_ini_path, "r", encoding = "utf-8") as deployed_ini_file:
                for line in deployed_ini_file.readlines():
                    for disabled in [FILE_DISAB_LINE_REL, FILE_DISAB_LINE_ABS]:
                        if line.startswith(disabled):
                            self.disable_registry[line.split(disabled, maxsplit=1)[1].strip("\n")[:-1]] = disabled
                            break
            if self.debug >= 1:
                print("  [I] sort_packs import_disabled: loaded existing ini")
        elif self.debug >= 1:
            print("  [I] sort_packs import_disabled: could not find ini")
        # Read unsorted ini to remove packs disabled for being unclassified
        if unsorted_ini_path.is_file():
            with open(unsorted_ini_path, "r", encoding = "utf-8") as unsorted_ini_file:
                for line in unsorted_ini_file.readlines():
                    for disabled in [FILE_DISAB_LINE_REL, FILE_DISAB_LINE_ABS]:
                        if line.startswith(disabled):
                            try:
                                del self.disable_registry[line.split(disabled, maxsplit=1)[1].strip("\n")[:-1]]
                                break
                            except KeyError:
                                pass
            if self.debug >= 1:
                print("  [I] sort_packs import_disabled: loaded unsorted ini")
        elif self.debug >= 1:
            print("  [I] sort_packs import_disabled: could not find unsorted ini")
        # Ask if user wants to carry these disabled packs over
        if self.disable_registry:
            print("I see you've disabled some packs in the current scenery_packs.ini")
            while True:    
                choice_disable = input("Would you like to carry it over to the new ini? (yes/no or y/n): ").lower()
                if choice_disable in ["y","yes"]:
                    print("Ok, I will carry as much as possible over.")
                    break
                elif choice_disable in ["n","no"]:
                    print("Ok, I will not carry any of them over.")
                    self.disable_registry = {}
                    break
                else:
                    print("  Sorry, I didn't understand.")
            
    # Read uncompresssed DSF
    # This code is adapted from https://gist.github.com/nitori/6e7be6c9f00411c12aacc1ee964aee88 - thank you very much!
    def mesh_dsf_decode(self, filepath:pathlib.Path, dirname):
        try:
            size = os.stat(filepath).st_size
        except FileNotFoundError:
            if self.debug >= 2:
                print(f"  [E] sort_packs mesh_dsf_decode: expected dsf '{str(filepath.name)}'")
                print(f"                 extracted files from dsf: {self.misc_functions.dir_list(filepath.parent.absolute(), 'files')}")
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
                        if self.debug >= 2:
                            print(f"  [E] sort_packs mesh_dsf_decode: checksum mismatch")
                        return "ERR: DCDE: !Checksum"
                    return dsf_data
                elif header != b"XPLNEDSF":
                    if header.startswith(b"7z"):
                        if self.debug >= 2:
                            print(f"  [E] sort_packs mesh_dsf_decode: got '7z' header. extraction failure?")
                        return "ERR: DCDE: NoExtract"
                    else:
                        if self.debug >= 2:
                            print(f"  [E] sort_packs mesh_dsf_decode: unknown header. got '{header}'")
                        return "ERR: DCDE: !XPLNEDSF"
                elif version != 1:
                    if self.debug >= 2:
                        print(f"  [E] sort_packs mesh_dsf_decode: unknown dsf version. got '{version}'")
                    return f"ERR: DCDE: v{((8 - len(str(version))) * ' ') + str(version)}"
        except Exception as e:
            if self.debug >= 2:
                print(f"  [E] sort_packs mesh_dsf_decode: unhandled error '{e}'")
            return "ERR: DCDE: BadDSFErr"

    # Select and read DSF. Uncompress if needed and call mesh_dsf_decode(). Return HEAD atom
    def mesh_dsf_read(self, end_directory:pathlib.Path, tag:str, dirname:str):
        # Attempt to fetch cached data
        try:
            with open(end_directory.parent.absolute() / "sporganiser_cache.yaml", "r") as yaml_file:
                dsf_cache_data = yaml.load(yaml_file, Loader = yaml.FullLoader)
                if self.debug >= 2:
                    print(f"  [I] sort_packs mesh_dsf_read: loaded cached data")
        except FileNotFoundError:
            dsf_cache_data = {"version": 220}
        # Read cached data
        dsf_cache_data_iter = copy.deepcopy(dsf_cache_data)
        try:
            for dsf in dsf_cache_data_iter:
                # check version
                if dsf == "version":
                    if not dsf_cache_data[dsf] == 220:
                        if self.debug >= 2:
                            print(f"  [W] sort_packs mesh_dsf_read: unknown version tag. got '{dsf_cache_data[dsf]}'")
                        dsf_cache_data = {"version": 220}
                        break
                    continue
                # locate dsf cached and check that it exists
                dsf_path = end_directory / dsf
                if not dsf_path.exists():
                    if self.debug >= 2:
                        print(f"  [W] sort_packs mesh_dsf_read: cached dsf '{str(dsf_path)}' doesn't exist")
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
                    if self.debug >= 2:
                        print(f"  [W] sort_packs mesh_dsf_read: hash of cached dsf '{str(dsf_path)}' doesn't match")
                    del dsf_cache_data[dsf]
                    continue
                # attempt to get the tag data requested
                try:
                    tag_data = dsf_cache_data[dsf][tag]
                    return tag_data
                except KeyError:
                    pass
        except Exception as e:
            if self.debug >= 2:
                print(f"  [E] sort_packs mesh_dsf_read: unhandled error '{e}'")
            dsf_cache_data = {"version": 220}        
        # Get list of potential tile directories to search
        list_dir = self.misc_functions.dir_list(end_directory, "dirs")
        tile_dir = []
        for dir in list_dir:
            if re.search(r"[+-]\d{2}[+-]\d{3}", dir):
                tile_dir.append(dir)
        if not tile_dir:
            if self.debug >= 2:
                print(f"  [E] sort_packs mesh_dsf_read: earth nav dir is empty - '{end_directory}'")
            return "ERR: READ: NDirEmpty"
        # Going one tile at a time, attempt to extract a dsf from the tile
        uncomp_flag = 0
        dsf_data = None
        final_tile = None
        final_dsf = None
        for tile in tile_dir:
            dsfs = self.misc_functions.dir_list(end_directory / tile, "files")
            for dsf in dsfs:
                # If not a dsf file, move on
                if not dsf.endswith(".dsf"):
                    continue
                # Attempt to extrat this DSF. If it fails, the DSF was already uncompressed or is corrupt
                else:
                    if self.debug >= 2:
                        print(f"  [I] sort_packs mesh_dsf_read: extracting '{end_directory / tile / dsf}'")
                    try:
                        shutil.unpack_archive(end_directory / tile / dsf, self.temp_path / dirname / dsf[:-4])
                        uncomp_path = self.temp_path / dirname / dsf[:-4] / dsf
                        uncomp_flag = 2
                        if self.debug >= 2:
                            print(f"  [I] sort_packs mesh_dsf_read: extracted")
                    except Exception as e: 
                        uncomp_path = end_directory / tile / dsf
                        if isinstance(e, py7zr.exceptions.Bad7zFile):
                            uncomp_flag = 1
                            if self.debug >= 2:
                                print(f"  [I] sort_packs mesh_dsf_read: not a 7z archive. working on dsf directly")
                        else:
                            self.dsferror_registry.append([f"{dsf}' in '{end_directory.parent.absolute()}", "ERR: READ: MiscError"])
                            uncomp_flag = 0
                            if self.debug >= 2:
                                print(f"  [E] sort_packs mesh_dsf_read: unhandled error '{e}'. working on dsf directly")
                    # Now attempt to decode this DSF
                    dsf_data = self.mesh_dsf_decode(uncomp_path, dirname)
                    # If it returns an error, try the next one. Else, get out of the intra-tile loop
                    if str(dsf_data).startswith("ERR: ") or dsf_data == None:
                        self.dsferror_registry.append([f"{dsf} in {end_directory.parent.absolute()}", dsf_data])
                        uncomp_flag = 0
                        if self.debug >= 2:
                            print(f"  [W] sort_packs mesh_dsf_read: caught '{str(dsf_data)}' from mesh_dsf_decode")
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
            if self.debug >= 2:
                print(f"  [E] sort_packs mesh_dsf_read: tile loop was not broken, ie. no dsf could be read")
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
            if self.debug >= 2:
                print(f"  [I] sort_packs mesh_dsf_read: new cache written")
            # Return result
            return overlay
        else:
            if self.debug >= 2:
                print(f"  [E] sort_packs mesh_dsf_read: unspecified or unimplemented property to search - '{str(tag)}'")
            return "ERR: READ: NoSpecify"

    # Check if the pack is an airport
    def process_type_apt(self, dirpath:pathlib.Path, dirname:str, file_line:str, disable:bool):
        # Basic checks before we move further
        apt_path = self.misc_functions.dir_contains(dirpath, None, "apt.dat")
        if not apt_path:
            if self.debug >= 2:
                print("  [I] sort_packs process_type_apt: 'apt.dat' file not found")
            return
        # Attempt several codecs starting with utf-8 in case of obscure apt.dat files
        apt_lins = None
        for codec in ("utf-8", "charmap", "cp1252", "cp850"):
            try:
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_type_apt: reading apt.dat with '{codec}'")
                with open(apt_path, "r", encoding = codec) as apt_file:
                    apt_lins = apt_file.readlines()
                break
            except UnicodeDecodeError:
                pass
        else:
            if self.debug >= 2:
                print(f"  [W] sort_packs process_type_apt: all codecs errored out")
        # Loop through lines
        apt_type = None
        for line in apt_lins:
            # Codes for airport, heliport, seaport
            if line.startswith("1 ") or line.startswith("16 ") or line.startswith("17 "):
                # Check if prefab, default, or global
                apt_prefab = self.process_quirk_prefab(dirpath, dirname)
                if apt_prefab:
                    apt_type = apt_prefab
                    break
                elif self.misc_functions.str_contains(dirname, ["Demo Area", "X-Plane Airports", "X-Plane Landmarks", "Aerosoft"]):
                    apt_type = "Default"
                    if self.debug >= 2:
                        print("  [I] sort_packs process_type_apt: found to be default airport")
                    break
                if apt_path and dirname == "Global Airports":
                    apt_type = "Global"
                    if self.debug >= 2:
                        print("  [I] sort_packs process_type_apt: found to be global airport")
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
                            self.icao_registry[icao_code] += 1
                        except KeyError:
                            self.icao_registry[icao_code] = 1
                        # Update airport registry
                        try:
                            reg_index = self.airport_registry["path"].index(dirpath)
                            self.airport_registry["icaos"][reg_index].append(icao_code)
                        except ValueError:
                            self.airport_registry["path"].append(dirpath)
                            self.airport_registry["line"].append(file_line)
                            self.airport_registry["icaos"].append([icao_code])
        return apt_type

    # Classify as AutoOrtho, Ortho, Mesh, or Overlay after reading DSF and scanning folders
    def process_type_mesh(self, dirpath:pathlib.Path, dirname:str):
        end_path = self.misc_functions.dir_contains(dirpath, None, "Earth nav data")
        # Basic check
        if not end_path:
            if self.debug >= 2:
                print("  [I] sort_packs process_type_mesh: 'Earth nav data' folder not found")
            return
        # Read DSF and check for sim/overlay. If error or None returned, log in dsf error registry
        overlay = self.mesh_dsf_read(end_path, "sim/overlay 1", dirname)
        if str(overlay).startswith("ERR: ") or overlay == None:
            if self.debug >= 2:
                print(f"  [W] sort_packs process_type_mesh: caught '{str(overlay)}' from mesh_dsf_read")
            self.dsferror_registry.append([dirpath, overlay])
            return
        mesh_ao = self.process_quirk_ao(dirpath, dirname)
        if overlay:
            if mesh_ao in ["AO Overlay"]:
                return mesh_ao
            elif self.misc_functions.str_contains(dirname, ["X-Plane Landmarks"]):
                return "Default Overlay"
            else:
                return "Custom Overlay"
        else:
            if mesh_ao in ["AO Region", "AO Root"]:
                return mesh_ao
            elif self.misc_functions.dir_contains(dirpath, ["textures", "terrain"]):
                return "Ortho Mesh"
            else:
                return "Terrain Mesh"

    # Check misc types
    def process_type_other(self, dirpath:pathlib.Path, dirname:str):
        other_result = None
        if self.misc_functions.dir_contains(dirpath, ["library.txt"], "generic"):
            other_result = "Library"
        if self.misc_functions.dir_contains(dirpath, ["plugins"]):
            other_result = "Plugin"
        if self.debug >= 2 and other_result:
            print(f"  [I] sort_packs process_type_other: found to be {other_result}")
        elif self.debug >= 2:
            print(f"  [I] sort_packs process_type_other: neither library.txt nor plugins folder found")
        return other_result

    # Check if the pack is a prefab airport
    def process_quirk_prefab(self, dirpath:pathlib.Path, dirname:str):
        prefab_result = None
        if self.misc_functions.str_contains(dirname, ["prefab"], casesensitive = False):
            prefab_result = "Prefab Apt"
        if self.debug >= 2 and prefab_result:
            print(f"    [I] sort_packs process_quirk_prefab: found to be {prefab_result}")
        return prefab_result

    # Check if the pack is from autoortho
    def process_quirk_ao(self, dirpath:pathlib.Path, dirname:str):
        ao_regions = ["na", "sa", "eur", "afr", "asi", "aus_pac"]
        ao_result = None
        if self.misc_functions.str_contains(dirname, ["yAutoOrtho_Overlays"]):
            ao_result = "AO Overlay"
        elif self.misc_functions.str_contains(dirname, [f"z_ao_{region}" for region in ao_regions]):
            ao_result = "AO Region"
        elif self.misc_functions.str_contains(dirname, ["z_autoortho"]):
            ao_result = "AO Root"
        if self.debug >= 2 and ao_result:
            print(f"    [I] sort_packs process_quirk_ao: found to be {ao_result}")
        return ao_result

    # Check if the pack is a prefab airport
    def process_quirk_prefab(self, dirpath:pathlib.Path, dirname:str):
        prefab_result = None
        if self.misc_functions.str_contains(dirname, ["prefab"], casesensitive = False):
            prefab_result = "Prefab Apt"
        if self.debug >= 2 and prefab_result:
            print(f"    [I] sort_packs process_quirk_prefab: found to be {prefab_result}")
        return prefab_result

    # Check if the pack is from autoortho
    def process_quirk_ao(self, dirpath:pathlib.Path, dirname:str):
        ao_regions = ["na", "sa", "eur", "afr", "asi", "aus_pac"]
        ao_result = None
        if self.misc_functions.str_contains(dirname, ["yAutoOrtho_Overlays"]):
            ao_result = "AO Overlay"
        elif self.misc_functions.str_contains(dirname, [f"z_ao_{region}" for region in ao_regions]):
            ao_result = "AO Region"
        elif self.misc_functions.str_contains(dirname, ["z_autoortho"]):
            ao_result = "AO Root"
        if self.debug >= 2 and ao_result:
            print(f"    [I] sort_packs process_quirk_ao: found to be {ao_result}")
        return ao_result

    # Classify the pack
    def process_main(self, path, shortcut = False):
        # Make sure we're not processing our own temp folder
        if str(self.temp_path) in str(path):
            return
        # Bring data to formats required by classifier functions
        abs_path = self.xplane_path / "Custom Scenery" / path
        name = str(path)
        classified = False
        # Define path formatted for ini
        if shortcut:
            ini_path = str(abs_path)
        else:
            ini_path = str(path)
        # Define line formatted for ini
        disable = ini_path in self.disable_registry
        if disable:
            del self.disable_registry[ini_path]
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
            pack_type = self.process_type_apt(abs_path, name, line, disable)
            classified = True
            # Standard definitions
            if pack_type in ["Global", "Default", "Custom"]:
                self.airports[pack_type].append(line)
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_main: classified as '{pack_type.lower()} Airport'")
            # Quirk handling
            elif pack_type in ["Prefab Apt"]:
                self.quirks[pack_type].append(line)
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_main: classified as quirk '{pack_type.lower()}'")
            else:
                classified = False
        # Next, autortho, overlay, ortho or mesh
        if not classified:
            pack_type = self.process_type_mesh(abs_path, name)
            if not pack_type: 
                pack_type = self.process_quirk_ao(abs_path, name)
            classified = True
            # Standard definitions
            if pack_type in ["Default Overlay", "Custom Overlay"]:
                self.overlays[pack_type[:-8]].append(line)
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_main: classified as '{pack_type.lower()}'")
            elif pack_type in ["Ortho Mesh", "Terrain Mesh"]:
                self.meshes[pack_type[:-5]].append(line)
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_main: classified as '{pack_type.lower()}'")
            # Quirk handling
            elif pack_type in ["AO Overlay", "AO Region", "AO Root"]:
                self.quirks[pack_type].append(line)
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_main: classified as quirk '{pack_type.lower()}'")
            else:
                classified = False
        # Very lax checks for plugins and libraries
        if not classified:
            pack_type = self.process_type_other(abs_path, name)
            classified = True
            # Standard definitions
            if pack_type in ["Plugin", "Library"]:
                self.other[pack_type].append(line)
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_main: classified as '{pack_type.lower()}'")
            # Quirk handling
            elif pack_type in []:
                self.quirks[pack_type].append(line)
                if self.debug >= 2:
                    print(f"  [I] sort_packs process_main: classified as quirk '{pack_type.lower()}'")
            else:
                classified = False
        # Give up. Add this to the list of packs we couldn't sort
        if not classified:
            if self.debug >= 2:
                print(f"  [W] sort_packs process_main: could not be classified")
            if line.startswith(FILE_DISAB_LINE_ABS):
                self.unsorted_registry.append(line[22:])
            elif line.startswith(FILE_LINE_ABS):
                self.unsorted_registry.append(line[13:])
            else:
                pass
    
    # Process folders and symlinks
    def main_folders(self):
        maxlength = 0
        folder_list = self.misc_functions.dir_list(self.xplane_path / "Custom Scenery", "dirs")
        folder_list.sort()
        for directory in folder_list:
            if self.debug >= 1:
                print(f"Main: Starting dir: {directory}")
            else:
                # Whitespace padding to print in the shell
                progress_str = f"Processing: {directory}"
                if len(progress_str) <= maxlength:
                    progress_str = f"{progress_str}{' ' * (maxlength - len(progress_str))}"
                else:
                    maxlength = len(progress_str)
                print(f"\r{progress_str}", end = "\r")
            self.process_main(directory)
            if self.debug >= 1 and self.debug < 2:
                print(f"Main: Finished dir: {directory}")
    
    # Process Windows Shortcuts
    def main_shortcuts(self):
        maxlength = 0
        printed = False
        shtcut_list = [str(self.xplane_path / "Custom Scenery" / shtcut) for shtcut in 
                       self.misc_functions.dir_list(self.xplane_path / "Custom Scenery", "files") if shtcut.endswith(".lnk")]
        shtcut_list.sort()
        if shtcut_list and sys.platform != "win32":
            print(f"I found Windows .LNK shortcuts, but I'm not on Windows! Detected platform: {sys.platform}")
            print("I will still attempt to read them, but I cannot guarantee anything. I would suggest you use symlinks instead.")
        elif shtcut_list and sys.platform == "win32":
            print("Reading .LNK shortcuts...")
        # If the code raises an error internally or if we were given a garbled path, skip it and add to the list of unparsable shortcuts
        for shtcut_path in shtcut_list:
            try:
                folder_path = self.misc_functions.parse_shortcut(shtcut_path)
                if folder_path.exists():
                    if self.debug >= 1:
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
                    self.process_main(folder_path, shortcut = True)
                    if self.debug >= 1 and self.debug < 2:
                        print(f"Main: Finished shortcut: {folder_path}")
                    continue
                else: 
                    if self.debug >= 1:
                        print(f"Main: Failed shortcut: {folder_path}")
            except Exception as e:
                if self.debug >= 2:
                    print(f"  [E] sort_packs main_shortcuts: unhandled error '{e}'")
                if self.debug >= 1:
                    print(f"Main: Failed shortcut: {shtcut_path}")
            self.unparsed_registry.append(shtcut_path)
        if printed:
            print()
    
    # Process macOS Aliases
    def main_aliases(self):
        pass

    # Cleanup after processing
    def main_cleanup(self):
        # Sort tiers alphabetically
        self.unsorted_registry.sort()
        for key in self.quirks:
            self.quirks[key].sort()
        for key in self.airports:
            self.airports[key].sort()
        for key in self.overlays:
            self.overlays[key].sort()
        for key in self.meshes:
            self.meshes[key].sort()
        for key in self.other:
            self.other[key].sort()
        # Check to inject XP12 Global Airports
        if not self.airports["Global"]:
            if self.debug >= 1:
                print("  [I] sort_packs main_cleanup: XP10/11 global airports not found, injecting XP12 entry")
            self.airports["Global"].append(XP12_GLOBAL_AIRPORTS)
    
    # Display scary lists for the user
    def main_display(self):
        # Display all packs that errored when reading DSFs (if debugging enabled)
        if self.dsferror_registry and self.debug >= 1:
            print("\n[W] Main: I was unable to read DSF files from some scenery packs. Please check if they load correctly in X-Plane.")
            print("[^] Main: This does not necessarily mean that the pack could not be classified. Such packs will be listed separately.")
            print("[^] Main: I will list them out now with the error type.")
            for dsffail in self.dsferror_registry:
                print(f"[^]   {dsffail[1]} in '{dsffail[0]}'")
        # Display all disabled packs that couldn't be found
        if self.disable_registry:
            print("\nI was unable to find some packs that were tagged DISABLED in the old scenery_packs.ini.")
            print("They have probably been deleted or renamed. I will list them out now:")
            for pack in self.disable_registry:
                print(f"    {pack}")
        # Display all shortcuts that couldn't be read
        if self.unparsed_registry:
            print("\nI was unable to parse these shortcuts:")
            for shortcut in self.unparsed_registry:
                print(f"    {shortcut}")
            print("You will need to manually paste the target location paths into the file in this format:")
            print(f"{FILE_LINE_ABS}<path-to-target-location>/")
        # Display all packs that couldn't be sorted and offer to write them at the top of the file
        if self.unsorted_registry:
            print("\nI was unable to classify some packs. Maybe the pack is empty? Otherwise, a folder-in-folder?")
            print("I will list them out now")
            for line in self.unsorted_registry:
                line_stripped = line.strip("\n")
                print(f"    {line_stripped}")
            print("Note that if you choose not to write them, they will be written as DISABLED packs to prevent unexpected errors.")
            while True:
                choice = input("Should I still write them into the ini? (yes/no or y/n): ").lower()
                if choice in ["y","yes"]:
                    print("Ok, I will write them at the top of the ini.")
                    tmp_unsorted_registry = []
                    for line in self.unsorted_registry:
                        tmp_unsorted_registry.append(f"{FILE_LINE_ABS}{line}")
                    self.unsorted_registry = copy.deepcopy(tmp_unsorted_registry)
                    break
                elif choice in ["n","no"]:
                    print("Ok, I will write them at the top of the ini as DISABLED packs.")
                    tmp_unsorted_registry = []
                    for line in self.unsorted_registry:
                        tmp_unsorted_registry.append(f"{FILE_DISAB_LINE_ABS}{line}")
                    self.unsorted_registry = copy.deepcopy(tmp_unsorted_registry)
                    break
                else:
                    print("  Sorry, I didn't understand.")


class overlap_resolve:
    def __init__(self, debug:int, icao_registry:dict, airport_registry:dict, airports:dict) -> None:
        # External variable declarations
        self.debug = debug
        # External Airport related declarations
        self.icao_registry = icao_registry
        self.airport_registry = airport_registry
        self.airports = airports
        # Internal Airport related declarations
        self.icao_overlaps = []
        self.airport_list = {}
        self.airport_list_num = 0
        self.airport_resolve_choice = False
    
    # Go through airport registries, list out conflicts and add to our records
    def airport_search(self):
        # Check how many conflicting ICAOs we have and store them in icao_overlaps
        for icao in self.icao_registry:
            if self.icao_registry[icao] > 1: 
                self.icao_overlaps.append(icao)
        # Display conflicting packs in a list
        for reg_index in range(len(self.airport_registry["path"])):
            airport_path = self.airport_registry["path"][reg_index]
            airport_line = self.airport_registry["line"][reg_index]
            airport_icaos = self.airport_registry["icaos"][reg_index]
            # Check if this airport's ICAOs are among the conflicting ones. If not, skip it
            airport_icaos_conflicting = list(set(airport_icaos) & set(self.icao_overlaps))
            airport_icaos_conflicting.sort()
            if airport_icaos_conflicting:
                pass
            else:
                continue
            # Print path and ICAOs
            airport_icao_string = ""
            for icao in airport_icaos_conflicting:
                airport_icao_string += f"{icao} "
            print(f"    {self.airport_list_num}: '{airport_path}': {airport_icao_string[:-1]}")
            # Log this with the number in list
            self.airport_list[self.airport_list_num] = airport_line
            # Incremenent i for the next pack
            self.airport_list_num += 1
    
    # Ask the user if they want to resolve airport overlaps
    def airport_ask(self):
        if self.icao_overlaps:
            while True:
                choice = input(f"I've listed out all airport packs with their overlapping ICAOs. Would you like to sort them now? (yes/no or y/n): ").lower()
                if choice in ["y","yes"]:
                    self.airport_resolve_choice = True 
                    break
                elif choice in ["n","no"]:
                    print("Alright, I'll skip this part.")
                    print("You may wish to manually go through the ini file for corrections.")
                    break
                else:
                    print("  Sorry, I didn't understand.")
        else:
            print("No airport overlaps found.")
    
    # Resolution algorithm
    # TODO: store and import preferences
    def airport_resolve(self):
        # Make sure the user wanted to resolve
        if not self.airport_resolve_choice:
            return
        # Keep looping till we manage to get a working order
        valid_flag = True
        while True:
            # Get input if the user chose to resolve
            newline = "\n"
            order = input(f"{'' if valid_flag else newline}Enter the numbers in order of priority from higher to lower, separated by commas: ")
            valid_flag = True
            # There is no concievable case in which this throws an error, but one can never be sure
            try:
                order = order.strip(" ").split(",")
                order[:] = [int(item) for item in order if item != '']
            except:
                print("    I couldn't read this input!")
                valid_flag = False
            # Check if all the packs shown are present in this input
            if (set(order) != set(range(self.airport_list_num))) and valid_flag:
                print("    Hmm, that wasn't what I was expecting...")
                valid_flag = False
            # If this was an invalid input, show the user what a possible input would look like
            if not valid_flag:
                print("    I recommend you read the instructions if you're not sure what to do.")
                print("    For now though, I will show a basic example for your case below.")
                example_str = ""
                for i in range(self.airport_list_num):
                    example_str += f"{i},"
                print(f"    {example_str[:-1]}")
                print("    You can copy-paste this as-is, or move the numbers around as you like.")
            # If this input's valid, move on
            else:
                break
        # Manipulate custom airports list
        tmp_customairports = copy.deepcopy(self.airports["Custom"])
        tmp_customoverlaps = list()
        for i in order:
            tmp_customoverlaps.append(tmp_customairports.pop(tmp_customairports.index(self.airport_list[i])))
        tmp_customoverlaps.extend(tmp_customairports)
        self.airports["Custom"] = copy.deepcopy(tmp_customoverlaps)


class write_ini:
    def __init__(self, debug:int, xplane_path:pathlib.Path, unsorted_registry:dict, quirks:dict, airports:dict, overlays:dict, meshes:dict, other:dict) -> None:
        # External variable declarations
        self.debug = debug
        self.xplane_path = xplane_path
        self.unsorted_registry = unsorted_registry
        self.quirks = quirks
        self.airports = airports
        self.overlays = overlays
        self.meshes = meshes
        self.other = other
        # Internal variable declarations
        self.ini_path_deployed = pathlib.Path(self.xplane_path / "Custom Scenery" / "scenery_packs.ini")
        self.ini_path_unsorted = pathlib.Path(self.xplane_path / "Custom Scenery" / "scenery_packs_unsorted.ini")
        self.ini_path_backedup = pathlib.Path(f"{self.ini_path_deployed}.bak")
    
    # Clear old backup, move existing ini to backup
    def backup(self):
        # Remove the old backup file, if present
        try:
            if self.ini_path_backedup.exists():
                print("I will now delete the old scenery_packs.ini.bak")
                self.ini_path_backedup.unlink()
        except Exception as e:
            print(f"Failed to delete! Maybe check the file permissions? Error: '{e}'")
        # Back up the current scenery_packs.ini file
        try:
            if self.ini_path_deployed.exists():
                print("I will now back up the current scenery_packs.ini")
                self.ini_path_deployed.rename(self.ini_path_backedup)
        except Exception as e:
            print(f"Failed to rename .ini to .ini.bak! Maybe check the file permissions? Error: '{e}'")
    
    # Write out new ini
    def write(self):
        print("I will now write the new scenery_packs.ini")
        # These are our packs
        packs = {
            "unsorted": self.unsorted_registry,
            "airports: custom": self.airports["Custom"],
            "airports: default": self.airports["Default"],
            "quirks: prefab apt": self.quirks["Prefab Apt"],
            "airports: global": self.airports["Global"],
            "other: plugin": self.other["Plugin"],
            "other: library": self.other["Library"],
            "overlays: custom": self.overlays["Custom"],
            "overlays: default": self.overlays["Default"],
            "quirks: ao overlay": self.quirks["AO Overlay"],
            "meshes: ortho": self.meshes["Ortho"],
            "quirks: ao region": self.quirks["AO Region"],
            "quirks: ao root": self.quirks["AO Root"],
            "meshes: terrain": self.meshes["Terrain"]
            }
        # Write unsorted packs to scenery_packs_unsorted.ini
        with open(self.ini_path_unsorted, "w+", encoding = "utf-8") as f:
            f.write(FILE_BEGIN)
            if packs["unsorted"]:
                f.writelines(packs["unsorted"])
        # Write everything to scenery_packs.ini
        with open(self.ini_path_deployed, "w+", encoding = "utf-8") as f:
            f.write(FILE_BEGIN)
            for pack_type in packs:
                pack_list = packs[pack_type]
                if pack_list and self.debug >= 1:
                    print(pack_type)
                    f.writelines(pack_list)
                    for pack in pack_list:
                        print(f"    {pack.strip()}")
                elif self.debug >= 1:
                    print(pack_type)
                    print(f"    --empty--")
                elif pack_list:
                    f.writelines(pack_list)
        print("Done!")


class launch_xp:
    def __init__(self, debug:int, xplane_path:pathlib.Path) -> None:
        # External variable declarations
        self.debug = debug
        self.xplane_path = xplane_path
    
    # Get, set, go
    def getsetgo(self):
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
        xplane_exe = self.xplane_path / xplane_exe
        if (sys.platform in ["win32", "linux"] and not xplane_exe.is_file()) or (sys.platform in ["darwin"] and not xplane_exe.is_dir()):
            input("X-Plane executable is invalid or could not be found. Press enter to close")
            exit()
        # Ask the user if they wish to launch X-Plane. If no, exit
        choice_launch = None
        while True:
            choice_launch = input(f"Would you like to launch X-Plane at '{str(xplane_exe)}'? (yes/no or y/n): ").lower()
            if choice_launch in ["y", "yes"]:
                print("Ok, I am launching X-Plane now. Don't close this window.")
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


class misc_functions:
    def __init__(self, debug:int) -> None:
        # External variable declarations
        self.debug = debug

    # Read Windows shorcuts
    # The non-Windows code is from https://gist.github.com/Winand/997ed38269e899eb561991a0c663fa49
    def parse_shortcut(self, sht_path:str):
        tgt_path = None
        if sys.platform == "win32":
            shell = win32com.client.Dispatch("WScript.Shell")
            tgt_path = shell.CreateShortCut(sht_path).Targetpath
        else:
            if self.debug >= 1:
                print(f"  [W] misc_functions parse_shortcut: not on windows but made to parse {sht_path}")
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


    # Get the list of all directories inside a parent directory
    def dir_list(self, directory:pathlib.Path, result:str):
        dirlist = []
        for dirpath, dirnames, filenames in os.walk(directory):
            if result == "dirs":
                dirlist.extend(dirnames)
            elif result == "files":
                dirlist.extend(filenames)
            break
        return dirlist


    # Check if a directory contains a folder or file (case insensitive)
    # Ignore items list and return case-sensitive path for apt.dat or Earth nav data calls
    def dir_contains(self, directory:pathlib.Path, items:list, variant:str = None):
        # First find Earth nav data folder through recursion, then search for apt.dat file within it
        if variant == "apt.dat":
            end_folder = self.dir_contains(directory, None, variant = "Earth nav data")
            if end_folder:
                list_files = self.dir_list(end_folder, "files")
                for file in list_files:
                    if file.lower() == "apt.dat":
                        return directory / end_folder / file
        # Find Earth nav data folder and return case-sensitive path
        elif variant == "Earth nav data":
            list_dirs = self.dir_list(directory, "dirs")
            for folder in list_dirs:
                if folder.lower() == "earth nav data":
                    return directory / folder
        # Find if file or folder is present
        elif variant in [None, "generic"]:
            item_present = {}
            list_obj = self.dir_list(directory, "files" if variant == "generic" else "dirs")
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


    # Check if any of the items in a list are present in a given string
    # Used for checking if a scenery package is default
    def str_contains(self, searchstr:str, itemslist:list, casesensitive:bool = True):
        for item in itemslist:
            if casesensitive and item in searchstr:
                return True
            elif not casesensitive and item.lower() in searchstr.lower():
                return True
        return False


# Pack importing
def pack_import():
    pass


# Main flow
def main_flow():
    argparser = argparse.ArgumentParser()
    argparser.add_argument('-d', '--debug', action='store_true', dest='debug')

    args = argparser.parse_args()
    if args.debug >= 2:
        debug = 2
    elif args.debug == 1:
        debug = 1
    else:
        debug = 0

    # Create temp path
    while True:
        try:
            temp_path = pathlib.Path(f"organiser_temp_{time.time()}")
            os.mkdir(temp_path)
            break
        except FileExistsError:
            continue
    # First, locate X-Plane
    part1 = locate_xplane(debug)
    part1.finalise_path()
    xplane_path = part1.xplane_path
    # Second, run the sorting algorithms
    part2 = sort_packs(debug, xplane_path, temp_path)
    part2.main_folders()
    part2.main_shortcuts()
    part2.main_aliases()
    # Destroy temp path
    shutil.rmtree(temp_path)
    # Clean up sort results and store them
    part2.main_cleanup()
    part2.main_display()
    unsorted_registry = part2.unsorted_registry
    quirks = part2.quirks
    airports = part2.airports
    overlays = part2.overlays
    meshes = part2.meshes
    other = part2.other
    # Store internal data to pass on to overlap_resolve
    icao_registry = part2.icao_registry
    airport_registry = part2.airport_registry
    # Third, run the overlap resolution algorithms
    part3 = overlap_resolve(debug, icao_registry, airport_registry, airports)
    part3.airport_search()
    part3.airport_ask()
    part3.airport_resolve()
    # Store new airport data
    airports = part3.airports
    # Fourth, write to ini
    part4 = write_ini(debug, xplane_path, unsorted_registry, quirks, airports, overlays, meshes, other)
    part4.backup()
    part4.write()
    # Fifth, offer to launch X-Plane
    part5 = launch_xp(debug, xplane_path)
    part5.getsetgo()

def main() -> int:
    """Today's the day :D"""
    pack_import()
    main_flow()
    return 0

if __name__ == '__main__':
    sys.exit(main())
