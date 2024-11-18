#!/usr/bin/env python3

import argparse
import collections
import copy
import hashlib
import locale
import os
import pathlib
import re
import shutil
import struct
import sys
import tempfile
import time
import typing

# TODO: automate these later
import py7zr
import py7zr.exceptions
import yaml

# Global constant declarations
XP10_GLOBAL_AIRPORTS = "SCENERY_PACK Custom Scenery/Global Airports/\n"
XP12_GLOBAL_AIRPORTS = "SCENERY_PACK *GLOBAL_AIRPORTS*\n"
FILE_LINE_REL = "SCENERY_PACK Custom Scenery/"
FILE_LINE_ABS = "SCENERY_PACK "
FILE_DISAB_LINE_REL = "SCENERY_PACK_DISABLED Custom Scenery/"
FILE_DISAB_LINE_ABS = "SCENERY_PACK_DISABLED "
FILE_BEGIN = "I\n1000 Version\nSCENERY\n\n"
BUF_SIZE = 65536

# Named tuple declarations
SortPacksResult = collections.namedtuple("SortPacksResult", ["unsorted_registry", "quirks", "airports", "overlays", "meshes", "other"])
AirportData = collections.namedtuple("AirportData", ["icao_registry", "airport_registry"])


# TODO: Steam X-Plane support
class LocateXPlane:
    # Ref: https://developer.x-plane.com/article/how-to-programmatically-locate-x-plane-9-or-10/
    def __init__(self, verbose: int) -> None:
        # External variable declarations
        self.verbose = verbose
        # Internal variable declarations
        self.direct_lines = list()
        self.steam_lines = list()
        self.xplane_path = pathlib.Path()
        # Find the preferences folder - this varies by system
        self.prefs_folder = None
        if sys.platform == "win32":
            self.prefs_folder = pathlib.Path(os.path.expandvars("%USERPROFILE%/AppData/Local"))
        elif sys.platform == "darwin":
            self.prefs_folder = pathlib.Path(os.path.expanduser("~/Library/Preferences"))
        elif sys.platform == "linux":
            self.prefs_folder = pathlib.Path(os.path.expanduser("~/.x-plane"))
        if self.prefs_folder is None:
            print(f"Unsupported OS detected. Please report this error. Detected platform: {sys.platform}")
            if self.verbose >= 1:
                print(f"  [I] LocateXPlane init: unsupported OS")
        else:
            if self.verbose >= 1:
                print(f"  [I] LocateXPlane init: using {self.prefs_folder}")

    # Main code and return
    def main(self) -> pathlib.Path:
        # Fly my dear birds! Fly, and bring with you whatever X-Plane paths you could find!
        self.direct_search()
        self.direct_test()
        self.steam_search()
        # Now get user input
        self.get_choice()
        # Prepare data and return
        return self.xplane_path

    # Search direct X-Plane installs
    def direct_search(self) -> None:
        # Go through the text file for each X-Plane version...
        if self.prefs_folder and self.prefs_folder.exists():
            for version in ["_10", "_11", "_12"]:
                formatted_version = version.strip("_") if version else "9"
                try:
                    if self.verbose >= 2:
                        print(f"  [I] LocateXPlane direct_search: reading {formatted_version}")
                    install_file = self.prefs_folder / f"x-plane_install{version}.txt"
                    with open(install_file, "r", encoding="utf-8") as file:
                        # ...and read its lines to get potential install paths
                        for install_line in file.readlines():
                            self.direct_lines.append([f"X-Plane {formatted_version}", install_line, install_file])
                # In case the text file for this version doesn't exist
                except FileNotFoundError:
                    if self.verbose >= 1:
                        print(f"  [W] couldn't find {formatted_version}")
        elif self.verbose >= 1:
            print("  [I] LocateXPlane direct_search: folder doesn't exist")

    # Search Steam X-Plane installs
    def steam_search(self) -> None:
        pass

    # Test direct installs and remove stale paths
    def direct_test(self) -> None:
        # Create a copy of our record of direct lines to avoid errors with the iterable changing during iteration
        direct_lines_copy = copy.deepcopy(self.direct_lines)
        # Loop through the parsed lines...
        for version, install_line, install_file in direct_lines_copy:
            install_path = pathlib.Path(install_line.strip("\n"))
            # ...and test each path to ensure it's not "old and stale". if it is...
            if (install_path / "Custom Scenery").exists() and (install_path / "Resources").exists():
                if self.verbose >= 2:
                    print(f"  [I] LocateXPlane direct_test: validated {install_path}")
            else:
                # ...remove it from the text file!
                print(f"Removing stale path {install_path} from {install_file}")
                file_lines = list()
                with open(self.prefs_folder / install_file, "r+", encoding="utf-8") as file:
                    for file_line in file.readlines():
                        if file_line == install_line:
                            continue
                        file_lines.append(file_line)
                    file.seek(0)
                    file.writelines(file_lines)
                    file.truncate()
                # Oh and remove it from our record too :)
                self.direct_lines.remove([version, install_line, install_file])

    # Get user input
    def get_choice(self) -> None:
        # Add everything up to one list, then display it...
        compiled_lines = self.direct_lines + self.steam_lines
        if compiled_lines:
            print("I found the following X-Plane installs:")
            for i in range(len(compiled_lines)):
                xplane_version = compiled_lines[i][0]
                xplane_path = compiled_lines[i][1].strip("\n")
                print(f"    {i}: {xplane_version} at {xplane_path}")
            print("If you want to use one of these, enter its number as shown in the list.")
            print("Otherwise, enter the path to your X-Plane folder.")
        # ...or if we didn't find any paths, just ask the user to input a path
        else:
            if self.verbose >= 1:
                print(f"  [I] LocateXPlane get_choice: couldn't locate any x-plane folders automatically")
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
class SortPacks:
    def __init__(self, verbose: int, xplane_path: pathlib.Path, temp_path: pathlib.Path) -> None:
        # External variable declarations
        self.verbose = verbose
        self.xplane_path = xplane_path
        self.temp_path = temp_path
        # Internal variable declarations
        self.icao_registry = {}     # dict of ICAO codes and the number of packs serving each
        self.disable_registry = {}  # dict that holds the folder line and beginning line of disabled packs
        self.dsferror_registry = []  # list of errored dsfs
        self.unparsed_registry = []  # list of .lnk shortcuts that couldn't be parsed
        self.airport_registry = {"path": [], "line": [], "icaos": []}
        # Classification variable declarations
        self.unsorted_registry = []      # list of packs that couldn't be classified
        self.quirks = {"Prefab Apt": [], "AO Overlay": [], "AO Region": [], "AO Root": [], "SimHeaven": []}
        self.airports = {"Custom": [], "Default": [], "Global": []}
        self.overlays = {"Custom": [], "Default": []}
        self.meshes = {"Ortho": [], "Terrain": []}
        self.other = {"Plugin": [], "Library": []}
        # Misc functions declarations
        self.misc_functions = misc_functions(verbose)

    # Main code and return
    def main(self) -> tuple:
        # Run the sorting algorithms
        self.main_folders()
        print()
        self.main_shortcuts()
        print()
        self.main_aliases()
        print()
        # Clean up sort results
        self.main_cleanup()
        self.main_display()
        # Prepare data and return
        sort_result = SortPacksResult(self.unsorted_registry,
                                      self.quirks,
                                      self.airports,
                                      self.overlays,
                                      self.meshes,
                                      self.other)
        airport_data = AirportData(self.icao_registry, self.airport_registry)
        return (sort_result, airport_data)

    # Read old ini to get list of disabled packs
    def import_disabled(self) -> None:
        deployed_ini_path = self.xplane_path / "Custom Scenery" / "scenery_packs.ini"
        unsorted_ini_path = self.xplane_path / "Custom Scenery" / "scenery_packs_unsorted.ini"
        if deployed_ini_path.is_file():
            with open(deployed_ini_path, "r", encoding="utf-8") as deployed_ini_file:
                for line in deployed_ini_file.readlines():
                    for disabled in [FILE_DISAB_LINE_REL, FILE_DISAB_LINE_ABS]:
                        if line.startswith(disabled):
                            self.disable_registry[line.split(disabled, maxsplit=1)[1].strip("\n")[:-1]] = disabled
                            break
            if self.verbose >= 1:
                print("  [I] SortPacks import_disabled: loaded existing ini")
        elif self.verbose >= 1:
            print("  [I] SortPacks import_disabled: could not find ini")
        # Read unsorted ini to remove packs disabled for being unclassified
        if unsorted_ini_path.is_file():
            with open(unsorted_ini_path, "r", encoding="utf-8") as unsorted_ini_file:
                for line in unsorted_ini_file.readlines():
                    for disabled in [FILE_DISAB_LINE_REL, FILE_DISAB_LINE_ABS]:
                        if line.startswith(disabled):
                            try:
                                del self.disable_registry[line.split(disabled, maxsplit=1)[1].strip("\n")[:-1]]
                                break
                            except KeyError:
                                pass
            if self.verbose >= 1:
                print("  [I] SortPacks import_disabled: loaded unsorted ini")
        elif self.verbose >= 1:
            print("  [I] SortPacks import_disabled: could not find unsorted ini")
        # Ask if user wants to carry these disabled packs over
        if self.disable_registry:
            print("I see you've disabled some packs in the current scenery_packs.ini")
            while True:
                choice_disable = input("Would you like to carry it over to the new ini? (yes/no or y/n): ").lower()
                if choice_disable in ["y", "yes"]:
                    print("Ok, I will carry as much as possible over.")
                    break
                elif choice_disable in ["n", "no"]:
                    print("Ok, I will not carry any of them over.")
                    self.disable_registry = {}
                    break
                else:
                    print("  Sorry, I didn't understand.")

    # Read uncompresssed DSF
    # This code is adapted from https://gist.github.com/nitori/6e7be6c9f00411c12aacc1ee964aee88 - thank you very much!
    # Ref: https://developer.x-plane.com/article/dsf-file-format-specification/
    # Ref: https://developer.x-plane.com/article/dsf-usage-in-x-plane/
    def mesh_dsf_decode(self, filepath: pathlib.Path) -> typing.Union[list, str]:
        try:
            size = os.stat(filepath).st_size
        except FileNotFoundError:
            if self.verbose >= 2:
                print(f"  [E] SortPacks mesh_dsf_decode: expected dsf '{str(filepath.name)}'")
                print(f"                 extracted files from dsf: {self.misc_functions.dir_list(filepath.parent.absolute(), 'files')}")
            return "ERR: DCDE: NameMatch"
        footer_start = size - 16  # 16 byte (128bit) for md5 hash
        digest = hashlib.md5()
        try:
            with open(filepath, "rb") as dsf:
                # Read 8s = 8 byte string, and "i" = 1 32 bit integer (total: 12 bytes)
                raw_header = dsf.read(12)
                header, version = struct.unpack("<8si", raw_header)
                digest.update(raw_header)
                # Proceed only if the version and header match what we expect, else return a string
                if version == 1 and header == b"XPLNEDSF":
                    # Process dsf, updating digest and dsf_data
                    dsf_data = []
                    while dsf.tell() < footer_start:
                        raw_atom_header = dsf.read(8)
                        digest.update(raw_atom_header)
                        # 32bit atom id + 32 bit atom_size.. total: 8 byte
                        atom_id, atom_size = struct.unpack("<ii", raw_atom_header)
                        atom_id = struct.pack(">i", atom_id)  # "DAEH" -> "HEAD"
                        # Data size is atom_size excluding the just read 8 byte id+size header
                        atom_data = dsf.read(atom_size - 8)
                        digest.update(atom_data)
                        dsf_data.append((atom_id, atom_data))
                    # Remaining bit is the checksum, ensure it matches. If not, return a string
                    checksum = dsf.read()
                    if checksum != digest.digest():
                        if self.verbose >= 2:
                            print(f"  [E] SortPacks mesh_dsf_decode: checksum mismatch")
                        return "ERR: DCDE: !Checksum"
                    # Return dsf_data
                    return dsf_data
                # If something was wrong with the header
                elif header != b"XPLNEDSF":
                    if header.startswith(b"7z"):
                        if self.verbose >= 2:
                            print(f"  [E] SortPacks mesh_dsf_decode: got '7z' header. extraction failure?")
                        return "ERR: DCDE: NoExtract"
                    else:
                        if self.verbose >= 2:
                            print(f"  [E] SortPacks mesh_dsf_decode: unknown header. got '{header}'")
                        return "ERR: DCDE: !XPLNEDSF"
                # If something was wrong with the version
                elif version != 1:
                    if self.verbose >= 2:
                        print(f"  [E] SortPacks mesh_dsf_decode: unknown dsf version. got '{version}'")
                    return f"ERR: DCDE: v{((8 - len(str(version))) * ' ') + str(version)}"
        # Safety net
        except Exception as e:
            if self.verbose >= 2:
                print(f"  [E] SortPacks mesh_dsf_decode: unhandled error '{e}'")
            return "ERR: DCDE: BadDSFErr"

    # Caching stuff for DSF
    def mesh_dsf_cache(self, end_directory: pathlib.Path, tag: str, value: str = "", tile: str = "") -> typing.Union[str, None]:
        # Attempt to fetch cache
        try:
            with open(end_directory.parent.absolute() / "sporganiser_cache.yaml", "r") as yaml_file:
                dsf_cache_data = yaml.load(yaml_file, Loader=yaml.FullLoader)
                if self.verbose >= 2:
                    print(f"  [I] SortPacks mesh_dsf_cache: loaded cache")
        except FileNotFoundError:
            dsf_cache_data = {"version": 220}
        # If value given, operate in write mode
        if str(value) and str(tile):
            # Generate hashes
            sha1 = hashlib.sha1()
            md5 = hashlib.md5()
            with open(end_directory / tile, "rb") as dsf_file:
                while True:
                    data = dsf_file.read(BUF_SIZE)
                    if not data:
                        break
                    sha1.update(data)
                    md5.update(data)
            # Store result to speed up future runs
            dsf_cache_data_new = {f"{tile}": {tag: value, "md5": md5.hexdigest(), "sha1": sha1.hexdigest()}}
            dsf_cache_data.update(dsf_cache_data_new)
            with open(end_directory.parent.absolute() / "sporganiser_cache.yaml", "w") as yaml_file:
                yaml.dump(dsf_cache_data, yaml_file)
            if self.verbose >= 2:
                print(f"  [I] SortPacks mesh_dsf_cache: new cache written")
        # Otherwise, operate in read mode
        else:
            # Read cache
            dsf_cache_data_iter = copy.deepcopy(dsf_cache_data)
            try:
                for dsf in dsf_cache_data_iter:
                    # Check version
                    if dsf == "version":
                        if not dsf_cache_data[dsf] == 220:
                            if self.verbose >= 2:
                                print(f"  [W] SortPacks mesh_dsf_cache: unknown version tag. got '{dsf_cache_data[dsf]}'")
                            dsf_cache_data = {"version": 220}
                            break
                        continue
                    # Locate dsf cached and check that it exists
                    dsf_path = end_directory / dsf
                    if not dsf_path.exists():
                        if self.verbose >= 2:
                            print(f"  [W] SortPacks mesh_dsf_cache: cached dsf '{str(dsf_path)}' doesn't exist")
                        del dsf_cache_data[dsf]
                        continue
                    # Hash dsf to ensure cached data is still valid
                    sha1 = hashlib.sha1()
                    md5 = hashlib.md5()
                    with open(dsf_path, "rb") as dsf_file:
                        while True:
                            data = dsf_file.read(BUF_SIZE)
                            if not data:
                                break
                            sha1.update(data)
                            md5.update(data)
                    if not (dsf_cache_data[dsf]["md5"] == md5.hexdigest() and dsf_cache_data[dsf]["sha1"] == sha1.hexdigest()):
                        if self.verbose >= 2:
                            print(f"  [W] SortPacks mesh_dsf_cache: hash of cached dsf '{str(dsf_path)}' doesn't match")
                        del dsf_cache_data[dsf]
                        continue
                    # Attempt to get the tag data requested
                    try:
                        tag_data = dsf_cache_data[dsf][tag]
                        return tag_data
                    except KeyError:
                        pass
            # Safety net
            except Exception as e:
                if self.verbose >= 2:
                    print(f"  [E] SortPacks mesh_dsf_cache: unhandled error '{e}'")
                dsf_cache_data = {"version": 220}

    # Select and read DSF. Uncompress if needed and call mesh_dsf_decode()
    def mesh_dsf_read(self, end_directory: pathlib.Path, tag: str, dirname: str) -> typing.Union[bool, str]:
        data_flag = 0
        # Attempt to fetch results from cache
        dsf_read_result = self.mesh_dsf_cache(end_directory, tag)
        if dsf_read_result:
            data_flag = 3
        # Get list of potential tile directories to search
        list_dir = self.misc_functions.dir_list(end_directory, "dirs")
        tile_dir = []
        for dir in list_dir:
            if re.search(r"[+-]\d{2}[+-]\d{3}", dir):
                tile_dir.append(dir)
        if not tile_dir:
            if self.verbose >= 2:
                print(f"  [E] SortPacks mesh_dsf_read: earth nav dir is empty - '{end_directory}'")
            return "ERR: READ: NDirEmpty"
        # Going one tile at a time, attempt to extract a dsf from the tile
        dsf_data = None
        final_tile = None
        final_dsf = None
        for tile in tile_dir:
            dsfs = self.misc_functions.dir_list(end_directory / tile, "files")
            for dsf in dsfs:
                # Check it's really a DSF
                if not dsf.endswith(".dsf"):
                    continue
                # Space to do per-dsf stuff, eg. dsf size map
                pass
                # Check if we already got what we need
                if data_flag:
                    continue
                # If not, proceed to parse the DSF
                if self.verbose >= 2:
                    print(f"  [I] SortPacks mesh_dsf_read: extracting '{end_directory / tile / dsf}'")
                # Attempt to extract this DSF
                try:
                    shutil.unpack_archive(end_directory / tile / dsf, self.temp_path / dirname / dsf[:-4])
                    uncomp_path = self.temp_path / dirname / dsf[:-4] / dsf
                    data_flag = 2
                    if self.verbose >= 2:
                        print(f"  [I] SortPacks mesh_dsf_read: extracted")
                # If we ran into an exception...
                except Exception as e:
                    uncomp_path = end_directory / tile / dsf
                    # ...and the exception was in py7zr, it was probably uncompressed already
                    if isinstance(e, py7zr.exceptions.Bad7zFile) or isinstance(e, shutil.ReadError):
                        data_flag = 1
                        if self.verbose >= 2:
                            print(f"  [I] SortPacks mesh_dsf_read: not a 7z archive. working on dsf directly")
                    # Otherwise, hit the safety net
                    else:
                        self.dsferror_registry.append([f"{dsf}' in '{end_directory.parent.absolute()}", "ERR: READ: MiscError"])
                        data_flag = 0
                        if self.verbose >= 2:
                            print(f"  [E] SortPacks mesh_dsf_read: unhandled error '{e}'. working on dsf directly")
                # Now attempt to decode this DSF
                dsf_data = self.mesh_dsf_decode(uncomp_path)
                # If it returns an error, try the next one. Else, declare the final tile and dsf
                if str(dsf_data).startswith("ERR: ") or dsf_data is None:
                    self.dsferror_registry.append([f"{dsf} in {end_directory.parent.absolute()}", dsf_data])
                    data_flag = 0
                    if self.verbose >= 2:
                        print(f"  [W] SortPacks mesh_dsf_read: caught '{str(dsf_data)}' from mesh_dsf_decode")
                else:
                    final_tile = tile
                    final_dsf = dsf
            if data_flag:
                break
        # If data_flag is 3, we managed to read the cache. So return it
        if data_flag == 3:
            return dsf_read_result
        # If data_flag was never set, it means we couldn't read a dsf
        elif not data_flag:
            if self.verbose >= 2:
                print(f"  [E] SortPacks mesh_dsf_read: data flag never set, ie. no dsf could be read")
            return "ERR: READ: TileEmpty"
        # Search for sim/overlay in HEAD atom. If found, update cache and store result
        if tag == "sim/overlay 1":
            overlay = None
            for atom_id, atom_data in dsf_data:
                if atom_id == b"HEAD" and b"sim/overlay\x001" in atom_data:
                    overlay = True
                    break
            else:
                overlay = False
            # Update cache
            self.mesh_dsf_cache(end_directory, tag, overlay, f"{final_tile}/{final_dsf}")
            # Return result
            return overlay
        else:
            if self.verbose >= 2:
                print(f"  [E] SortPacks mesh_dsf_read: unspecified or unimplemented property to search - '{str(tag)}'")
            return "ERR: READ: NoSpecify"

    # Check if the pack is an airport
    # Ref: https://developer.x-plane.com/article/airport-data-apt-dat-12-00-file-format-specification/
    def process_type_apt(self, dirpath: pathlib.Path, dirname: str, file_line: str, disable: bool) -> str:
        # Basic checks before we move further
        apt_path = self.misc_functions.dir_contains(dirpath, None, "apt.dat")
        if not apt_path:
            if self.verbose >= 2:
                print("  [I] SortPacks process_type_apt: 'apt.dat' file not found")
            return
        # Attempt several codecs starting with utf-8 in case of obscure apt.dat files
        apt_lins = None
        for codec in ("utf-8", "charmap", "cp1252", "cp850"):
            try:
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_type_apt: reading apt.dat with '{codec}'")
                with open(apt_path, "r", encoding=codec) as apt_file:
                    apt_lins = apt_file.readlines()
                break
            except UnicodeDecodeError:
                pass
        else:
            if self.verbose >= 2:
                print(f"  [W] SortPacks process_type_apt: all codecs errored out")
        # Loop through lines
        apt_type = None
        for line in apt_lins:
            # Codes for airport, heliport, seaport
            if line.startswith("1 ") or line.startswith("16 ") or line.startswith("17 "):
                # Check if prefab, default, or global
                apt_prefab = self.process_quirk_prefab(dirname)
                if apt_prefab:
                    apt_type = apt_prefab
                    break
                elif self.misc_functions.str_contains(dirname, ["Demo Area", "X-Plane Airports", "X-Plane Landmarks", "Aerosoft"]):
                    apt_type = "Default"
                    if self.verbose >= 2:
                        print("  [I] SortPacks process_type_apt: found to be default airport")
                    break
                if apt_path and dirname == "Global Airports":
                    apt_type = "Global"
                    if self.verbose >= 2:
                        print("  [I] SortPacks process_type_apt: found to be global airport")
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
        # Return result
        return apt_type

    # Classify as AutoOrtho, Ortho, Mesh, or Overlay after reading DSF and scanning folders
    def process_type_mesh(self, dirpath: pathlib.Path, dirname: str) -> str:
        end_path = self.misc_functions.dir_contains(dirpath, None, "Earth nav data")
        # Basic check
        if not end_path:
            if self.verbose >= 2:
                print("  [I] SortPacks process_type_mesh: 'Earth nav data' folder not found")
            return
        # Read DSF and check for sim/overlay. If error or None returned, log in dsf error registry
        overlay = self.mesh_dsf_read(end_path, "sim/overlay 1", dirname)
        if str(overlay).startswith("ERR: ") or overlay is None:
            if self.verbose >= 2:
                print(f"  [W] SortPacks process_type_mesh: caught '{str(overlay)}' from mesh_dsf_read")
            self.dsferror_registry.append([dirpath, overlay])
            return
        # Check for AutoOrtho and SimHeaven quirks
        mesh_ao = self.process_quirk_ao(dirname)
        mesh_simheaven = self.process_quirk_simheaven(dirname)
        if overlay:
            if mesh_ao in ["AO Overlay"]:
                return mesh_ao
            elif mesh_simheaven in ["SimHeaven"]:
                return mesh_simheaven
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
    def process_type_other(self, dirpath: pathlib.Path, dirname: str) -> str:
        other_result = None
        if self.misc_functions.dir_contains(dirpath, ["library.txt"], "generic"):
            other_result = "Library"
            # Check for SimHeaven
            other_simheaven = self.process_quirk_simheaven(dirname)
            if other_simheaven:
                other_result = other_simheaven
        if self.misc_functions.dir_contains(dirpath, ["plugins"]):
            other_result = "Plugin"
        if self.verbose >= 2 and other_result:
            print(f"  [I] SortPacks process_type_other: found to be {other_result}")
        elif self.verbose >= 2:
            print(f"  [I] SortPacks process_type_other: neither library.txt nor plugins folder found")
        return other_result

    # Check if the pack is from AutoOrtho
    # Called in process_type_apt after pack is confirmed to be airport
    def process_quirk_ao(self, dirname: str) -> str:
        ao_regions = ["na", "sa", "eur", "afr", "asi", "aus_pac"]
        ao_result = None
        if self.misc_functions.str_contains(dirname, ["yAutoOrtho_Overlays"]):
            ao_result = "AO Overlay"
        elif self.misc_functions.str_contains(dirname, [f"z_ao_{region}" for region in ao_regions]):
            ao_result = "AO Region"
        elif self.misc_functions.str_contains(dirname, ["z_autoortho"]):
            ao_result = "AO Root"
        if self.verbose >= 2 and ao_result:
            print(f"    [I] SortPacks process_quirk_ao: found to be {ao_result}")
        return ao_result

    # Check if the pack is a Prefab Airport
    # Called in process_type_mesh and process_main
    def process_quirk_prefab(self, dirname: str) -> str:
        prefab_result = None
        if self.misc_functions.str_contains(dirname, ["prefab"], casesensitive=False):
            prefab_result = "Prefab Apt"
        if self.verbose >= 2 and prefab_result:
            print(f"    [I] SortPacks process_quirk_prefab: found to be {prefab_result}")
        return prefab_result

    # Check if the pack is from SimHeaven
    # Called in process_type_mesh and process_type_other
    def process_quirk_simheaven(self, dirname: str) -> str:
        simheaven_result = None
        if self.misc_functions.str_contains(dirname, ["simheaven"], casesensitive=False):
            simheaven_result = "SimHeaven"
        if self.verbose >= 2 and simheaven_result:
            print(f"    [I] SortPacks process_quirk_simheaven: found to be {simheaven_result}")
        return simheaven_result

    # Classify the pack
    def process_main(self, path, shortcut=False) -> None:
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
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_main: classified as '{pack_type} Airport'")
            # Quirk handling
            elif pack_type in ["Prefab Apt"]:
                self.quirks[pack_type].append(line)
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_main: classified as quirk '{pack_type}'")
            else:
                classified = False
        # Next, autortho, overlay, ortho or mesh
        if not classified:
            pack_type = self.process_type_mesh(abs_path, name)
            if not pack_type:
                pack_type = self.process_quirk_ao(name)
            classified = True
            # Standard definitions
            if pack_type in ["Default Overlay", "Custom Overlay"]:
                self.overlays[pack_type[:-8]].append(line)
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_main: classified as '{pack_type}'")
            elif pack_type in ["Ortho Mesh", "Terrain Mesh"]:
                self.meshes[pack_type[:-5]].append(line)
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_main: classified as '{pack_type}'")
            # Quirk handling
            elif pack_type in ["AO Overlay", "AO Region", "AO Root", "SimHeaven"]:
                self.quirks[pack_type].append(line)
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_main: classified as quirk '{pack_type}'")
            else:
                classified = False
        # Very lax checks for plugins and libraries
        if not classified:
            pack_type = self.process_type_other(abs_path, name)
            classified = True
            # Standard definitions
            if pack_type in ["Plugin", "Library"]:
                self.other[pack_type].append(line)
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_main: classified as '{pack_type}'")
            # Quirk handling
            elif pack_type in ["SimHeaven"]:
                self.quirks[pack_type].append(line)
                if self.verbose >= 2:
                    print(f"  [I] SortPacks process_main: classified as quirk '{pack_type}'")
            else:
                classified = False
        # Give up. Add this to the list of packs we couldn't sort
        if not classified:
            if self.verbose >= 2:
                print(f"  [W] SortPacks process_main: could not be classified")
            if line.startswith(FILE_DISAB_LINE_ABS):
                self.unsorted_registry.append(line[22:])
            elif line.startswith(FILE_LINE_ABS):
                self.unsorted_registry.append(line[13:])
            else:
                pass

    # Process folders and symlinks
    def main_folders(self) -> None:
        maxlength = 0
        folder_list = self.misc_functions.dir_list(self.xplane_path / "Custom Scenery", "dirs")
        folder_list.sort()
        for directory in folder_list:
            if self.verbose >= 1:
                print(f"Main: Starting dir: {directory}")
            else:
                # Whitespace padding to print in the shell
                progress_str = f"Processing: {directory}"
                if len(progress_str) <= maxlength:
                    progress_str = f"{progress_str}{' ' * (maxlength - len(progress_str))}"
                else:
                    maxlength = len(progress_str)
                print(f"\r{progress_str}", end="\r")
            self.process_main(directory)
            if self.verbose >= 1 and self.verbose < 2:
                print(f"Main: Finished dir: {directory}")

    # Process Windows Shortcuts
    def main_shortcuts(self) -> None:
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
                    if self.verbose >= 1:
                        print(f"Main: Starting shortcut: {folder_path}")
                    else:
                        # Whitespace padding to print in the shell
                        progress_str = f"Processing shortcut: {str(folder_path)}"
                        if len(progress_str) <= maxlength:
                            progress_str = f"{progress_str}{' ' * (maxlength - len(progress_str))}"
                        else:
                            maxlength = len(progress_str)
                        print(f"\r{progress_str}", end="\r")
                        printed = True
                    self.process_main(folder_path, shortcut=True)
                    if self.verbose >= 1 and self.verbose < 2:
                        print(f"Main: Finished shortcut: {folder_path}")
                    continue
                else:
                    if self.verbose >= 1:
                        print(f"Main: Failed shortcut: {folder_path}")
            # Safety net
            except Exception as e:
                if self.verbose >= 2:
                    print(f"  [E] SortPacks main_shortcuts: unhandled error '{e}'")
                if self.verbose >= 1:
                    print(f"Main: Failed shortcut: {shtcut_path}")
            self.unparsed_registry.append(shtcut_path)
        if printed:
            print()

    # Process macOS Aliases
    def main_aliases(self) -> None:
        pass

    # Cleanup after processing
    def main_cleanup(self) -> None:
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
            if self.verbose >= 1:
                print("  [I] SortPacks main_cleanup: XP10/11 global airports not found, injecting XP12 entry")
            self.airports["Global"].append(XP12_GLOBAL_AIRPORTS)

    # Display scary lists for the user
    def main_display(self) -> None:
        # Display all packs that errored when reading DSFs (if verbose)
        if self.dsferror_registry and self.verbose >= 1:
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
                if choice in ["y", "yes"]:
                    print("Ok, I will write them at the top of the ini.")
                    tmp_unsorted_registry = []
                    for line in self.unsorted_registry:
                        tmp_unsorted_registry.append(f"{FILE_LINE_ABS}{line}")
                    self.unsorted_registry = copy.deepcopy(tmp_unsorted_registry)
                    break
                elif choice in ["n", "no"]:
                    print("Ok, I will write them at the top of the ini as DISABLED packs.")
                    tmp_unsorted_registry = []
                    for line in self.unsorted_registry:
                        tmp_unsorted_registry.append(f"{FILE_DISAB_LINE_ABS}{line}")
                    self.unsorted_registry = copy.deepcopy(tmp_unsorted_registry)
                    break
                else:
                    print("  Sorry, I didn't understand.")


class OverlapResolve:
    def __init__(self, verbose: int, sort_result: SortPacksResult, airport_data=AirportData) -> None:
        # External variable declarations
        self.verbose = verbose
        # Copy of sort result
        self.sort_result = sort_result
        # External Airport related declarations
        self.icao_registry = airport_data.icao_registry
        self.airport_registry = airport_data.airport_registry
        self.airports = sort_result.airports
        # Internal Airport related declarations
        self.icao_overlaps = []
        self.airport_list = {}
        self.airport_list_num = 0
        self.airport_resolve_choice = False

    # Main code and return
    def main(self) -> SortPacksResult:
        # Airport overlap and resolution
        self.airport_search()
        self.airport_ask()
        print()
        self.airport_resolve()
        # Prepare data and return
        sort_result_new = SortPacksResult(self.sort_result.unsorted_registry,
                                          self.sort_result.quirks,
                                          self.airports,
                                          self.sort_result.overlays,
                                          self.sort_result.meshes,
                                          self.sort_result.other)
        return sort_result_new

    # Go through airport registries, list out conflicts and add to our records
    def airport_search(self) -> None:
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
    def airport_ask(self) -> None:
        if self.icao_overlaps:
            while True:
                choice = input(f"I've listed out all airport packs with their overlapping ICAOs. Would you like to sort them now? (yes/no or y/n): ").lower()
                if choice in ["y", "yes"]:
                    self.airport_resolve_choice = True
                    break
                elif choice in ["n", "no"]:
                    print("Alright, I'll skip this part.")
                    print("You may wish to manually go through the ini file for corrections.")
                    break
                else:
                    print("  Sorry, I didn't understand.")
        else:
            print("No airport overlaps found.")

    # Resolution algorithm
    # TODO: store and import preferences
    def airport_resolve(self) -> None:
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
            # There is no conceivable case in which this throws an error, but one can never be sure
            try:
                order = order.strip(" ").split(",")
                order[:] = [int(item) for item in order if item != ""]
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


class WriteINI:
    def __init__(self, verbose: int, xplane_path: pathlib.Path, sort_result: SortPacksResult) -> None:
        # External variable declarations
        self.verbose = verbose
        self.xplane_path = xplane_path
        self.unsorted_registry = sort_result.unsorted_registry
        self.quirks = sort_result.quirks
        self.airports = sort_result.airports
        self.overlays = sort_result.overlays
        self.meshes = sort_result.meshes
        self.other = sort_result.other
        # Internal variable declarations
        self.ini_path_deployed = pathlib.Path(self.xplane_path / "Custom Scenery" / "scenery_packs.ini")
        self.ini_path_unsorted = pathlib.Path(self.xplane_path / "Custom Scenery" / "scenery_packs_unsorted.ini")
        self.ini_path_backedup = pathlib.Path(f"{self.ini_path_deployed}.bak")

    # Main code and return
    def main(self) -> typing.Union[None, Exception]:
        # Attempt backing up. If we got an error, return it
        backup = self.backup()
        if backup:
            return backup
        # Write new ini
        self.write()

    # Clear old backup, move existing ini to backup
    def backup(self) -> typing.Union[None, Exception]:
        # Remove the old backup file, if present
        try:
            if self.ini_path_backedup.exists():
                print("I will now delete the old scenery_packs.ini.bak")
                self.ini_path_backedup.unlink()
        # Safety net
        except Exception as e:
            print(f"Failed to delete! Maybe check the file permissions? Error: '{e}'")
            return e
        # Back up the current scenery_packs.ini file
        try:
            if self.ini_path_deployed.exists():
                print("I will now back up the current scenery_packs.ini")
                self.ini_path_deployed.rename(self.ini_path_backedup)
        # Safety net
        except Exception as e:
            print(f"Failed to rename .ini to .ini.bak! Maybe check the file permissions? Error: '{e}'")
            return e

    # Write out new ini
    def write(self) -> None:
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
            "quirks: simheaven": self.quirks["SimHeaven"],
            "overlays: custom": self.overlays["Custom"],
            "overlays: default": self.overlays["Default"],
            "quirks: ao overlay": self.quirks["AO Overlay"],
            "meshes: ortho": self.meshes["Ortho"],
            "quirks: ao region": self.quirks["AO Region"],
            "quirks: ao root": self.quirks["AO Root"],
            "meshes: terrain": self.meshes["Terrain"]
        }
        # Write unsorted packs to scenery_packs_unsorted.ini
        with open(self.ini_path_unsorted, "w+", encoding="utf-8") as f:
            f.write(FILE_BEGIN)
            if packs["unsorted"]:
                f.writelines(packs["unsorted"])
        # Write everything to scenery_packs.ini
        with open(self.ini_path_deployed, "w+", encoding="utf-8") as f:
            f.write(FILE_BEGIN)
            for pack_type in packs:
                pack_list = packs[pack_type]
                if pack_list and self.verbose >= 1:
                    print(pack_type)
                    f.writelines(pack_list)
                    for pack in pack_list:
                        print(f"    {pack.strip()}")
                elif self.verbose >= 1:
                    print(pack_type)
                    print(f"    --empty--")
                elif pack_list:
                    f.writelines(pack_list)
        print("Done!")


class LaunchXPlane:
    def __init__(self, verbose: int, xplane_path: pathlib.Path) -> None:
        # External variable declarations
        self.verbose = verbose
        self.xplane_path = xplane_path

    # Get, set, go
    def main(self) -> None:
        # Get X-Plane executable name. If unsupported platform, exit
        xplane_exe = None
        if sys.platform == "win32":
            xplane_exe = "X-Plane.exe"
        elif sys.platform == "darwin":
            xplane_exe = "X-Plane.app"
        elif sys.platform == "linux":
            xplane_exe = "X-Plane-x86_64"

        if xplane_exe is None:
            input("Unsupported platform for X-Plane. Press enter to close")
            return
        # Get X-Plane executable path and check if present. If not, exit
        xplane_exe = self.xplane_path / xplane_exe
        if (sys.platform in ["win32", "linux"] and not xplane_exe.is_file()) or (sys.platform == "darwin" and not xplane_exe.is_dir()):
            input("X-Plane executable is invalid or could not be found. Press enter to close")
            return
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
                return
            else:
                print("  Sorry, I didn't understand.")
        # Launch X-Plane
        print("\n\n")
        if sys.platform in ["win32", "linux"]:
            os.system(f'"{str(xplane_exe)}"')
        elif sys.platform == "darwin":
            os.system(f'open -a "{str(xplane_exe)}"')


class misc_functions:
    def __init__(self, verbose: int) -> None:
        # External variable declarations
        self.verbose = verbose

    # Read Windows shortcuts
    # The non-Windows code is from https://gist.github.com/Winand/997ed38269e899eb561991a0c663fa49
    def parse_shortcut(self, sht_path: str) -> pathlib.Path:
        tgt_path = None
        if sys.platform == "win32":
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            tgt_path = shell.CreateShortCut(sht_path).Targetpath
        else:
            if self.verbose >= 1:
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
    def dir_list(self, directory: pathlib.Path, result: str) -> list:
        dirlist = []
        for _, dirnames, filenames in os.walk(directory):
            if result == "dirs":
                dirlist.extend(dirnames)
            elif result == "files":
                dirlist.extend(filenames)
            break
        return dirlist

    # Check if a directory contains a folder or file (case insensitive)
    # Ignore items list and return case-sensitive path for apt.dat or Earth nav data calls
    def dir_contains(self, directory: pathlib.Path, items: list, variant: str = None) -> typing.Union[pathlib.Path, bool]:
        # First find Earth nav data folder through recursion, then search for apt.dat file within it
        if variant == "apt.dat":
            end_folder = self.dir_contains(directory, None, variant="Earth nav data")
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
    def str_contains(self, searchstr: str, itemslist: list, casesensitive: bool = True) -> bool:
        for item in itemslist:
            if casesensitive and item in searchstr:
                return True
            elif not casesensitive and item.lower() in searchstr.lower():
                return True
        return False


# Pack importing
def __init__() -> None:
    shutil.register_unpack_format("7zip", [".7z", ".dsf"], py7zr.unpack_7zarchive)
    print("Scenery Pack Organiser: version 3.0r1")


# Main flow
def main_flow(verbose: int, temp_path: pathlib.Path) -> int:
    # Part 1: Locate X-Plane
    time.sleep(2)
    print("\nFirst, let's find X-Plane!\n")
    time.sleep(2)
    part1 = LocateXPlane(verbose)
    xplane_path = part1.main()

    # Part 2: Sort packs and get data required for Part 3
    time.sleep(2)
    print("\n\nCool!")
    time.sleep(2)
    print("\nNow hang tight while I go through your scenery packs...\n")
    part2 = SortPacks(verbose, xplane_path, temp_path)
    sort_result, airport_data = part2.main()

    # Part 3: Resolve overlaps in Airports
    print("\n\nNow that that's done, let's see if you have any overlapping airports!\n")
    time.sleep(2)
    part3 = OverlapResolve(verbose, sort_result, airport_data)
    sort_result = part3.main()

    # Part 4: Write the ini and store any exceptions encountered
    time.sleep(2)
    print("\n\nCool!")
    time.sleep(2)
    print("\nNow I'll write all this to the .ini!\n")
    time.sleep(2)
    part4 = WriteINI(verbose, xplane_path, sort_result)
    ini_error = part4.main()

    # Part 5: Launch X-Plane ONLY IF no errors in Part 4
    time.sleep(2)
    print("\n\nLast... launching X-Plane!\n")
    time.sleep(2)
    part5 = LaunchXPlane(verbose, xplane_path)
    if ini_error:
        return 255
    else:
        part5.main()
        return 0

def main() -> int:
    """Today's the day :D"""
    __init__()

    argparser = argparse.ArgumentParser()
    argparser.add_argument("-d", "--verbose", type=int, choices=[0, 1, 2], dest="verbose_level")

    args = argparser.parse_args()
    verbose_level = args.verbose_level
    if verbose_level is None:
        verbose_level = 0

    # create a temporary directory using the context manager
    with tempfile.TemporaryDirectory() as tmpdirname:
        if verbose_level >= 1:
            print("created temporary directory", tmpdirname)
        return_code = main_flow(verbose_level, pathlib.Path(tmpdirname))
    # temporary directory and contents have been removed
    return return_code

if __name__ == "__main__":
    sys.exit(main())
