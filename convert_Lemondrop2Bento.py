#Put this script in the same folder as where your Input folder of .nnl files is
#*Do not put it INDIDE the Input folder*
#The script will generate an output folder called UserPatches with a Granular subfolder 
#where the converted patch folders containing the .xml file and their related .wav files will be created
#It will also create a patchconfig.xml file wiith synth selected as the default tag

import os
import shutil
import xml.etree.ElementTree as ET

# --- CONFIGURATION ---
INPUT_FOLDER = "LemondropContent"       # Put *your* .nnl file folder here
OUTPUT_ROOT = "UserPatches"           # Output root folder
SUB_FOLDER = "Granular"               # Bento subfolder for these patches

# Update this path to where your Lemondrop samples actually are
# (Often they are in a folder named 'Samples' inside NanoboxPresets)
FACTORY_SAMPLES_PATH = r"C:\1010Bento\LemondropContent\Samples"

FULL_OUTPUT_PATH = os.path.join(OUTPUT_ROOT, SUB_FOLDER)

# Specific Track Params for Bento Granular Track
TRACK_PARAMS = {
    "selcellpos": "0", "celldisppos": "0", "cellname": "", "selseqpos": "0", 
    "out3gain": "0", "fx1send": "0", "fx2send": "0", "outputbus": "0", 
    "midiinport": "0", "midiinchan": "0", "cc1inport": "0", "cc1inchan": "0", 
    "cc2inport": "0", "midioutport": "0", "midioutchan": "0", "padrowoffset": "0"
}

FX_LEMON_PARAMS = {
    "flangeamount": "0", "flangelforate": "500", "flangefeedback": "600", 
    "distamount": "0", "phaseamount": "0", "phaselforate": "500", 
    "phasefeedback": "500", "chorusamount": "0", "chorusrate": "500", 
    "fx1send": "0", "fx2send": "0", "fx3type": "0"
}

def clean_and_parse_xml(filepath):
    with open(filepath, 'rb') as f:
        content = f.read()
    clean_content = content.replace(b'\x00', b'').decode('utf-8', errors='ignore').strip()
    end_tag = "</document>"
    if end_tag in clean_content:
        clean_content = clean_content.split(end_tag)[0] + end_tag
    return ET.fromstring(clean_content)

def find_file_recursively(root_folder, filename):
    target = os.path.basename(filename).lower()
    for dirpath, _, filenames in os.walk(root_folder):
        for f in filenames:
            if f.lower() == target:
                return os.path.join(dirpath, f)
    return None

def convert_lemondrop_to_bento():
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: Folder '{INPUT_FOLDER}' not found.")
        input("Press Enter to exit...")
        return

    if not os.path.exists(FULL_OUTPUT_PATH):
        os.makedirs(FULL_OUTPUT_PATH)

    # Look for .nnl files (Lemondrop)
    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.nnl')]
    print(f"Found {len(files)} Lemondrop patches to convert...")

    index_entries = []

    for filename in files:
        try:
            patch_name = os.path.splitext(filename)[0].strip()
            
            patch_folder = os.path.join(FULL_OUTPUT_PATH, patch_name)
            if not os.path.exists(patch_folder):
                os.makedirs(patch_folder)

            try:
                root = clean_and_parse_xml(os.path.join(INPUT_FOLDER, filename))
            except ET.ParseError as e:
                print(f"  [SKIP] Corrupt file {filename}: {e}")
                continue

            session = root.find("session")
            new_root = ET.Element("document")
            new_session = ET.SubElement(new_root, "session", version="1")
            
            # --- CHANGE 1: Track Type is 'grtrack' ---
            new_track = ET.SubElement(new_session, "track", type="grtrack")
            ET.SubElement(new_track, "params", **TRACK_PARAMS)

            has_external_wav = False

            if session is not None:
                cells = sorted(session.findall("cell"), key=lambda c: int(c.get("row", 0)))
                
                for cell in cells:
                    ctype = cell.get("type")
                    if ctype == "samtempl": continue

                    new_cell = ET.SubElement(new_track, "cell", type=ctype)
                    
                    # --- FILENAME FIX (Same logic as Wavetable) ---
                    source_filename = cell.get("filename", "")
                    
                    params = cell.find("params")
                    if params is not None:
                        attr = params.attrib.copy()
                        
                        if source_filename:
                            original_path = source_filename
                            clean_name = os.path.basename(original_path.replace("\\", "/"))
                            
                            attr["filename"] = clean_name
                            has_external_wav = True

                            # File Copy Logic
                            src_wav = os.path.join(INPUT_FOLDER, original_path)
                            
                            if not os.path.exists(src_wav):
                                # Check Factory/Samples Path
                                factory_wav = os.path.join(FACTORY_SAMPLES_PATH, clean_name)
                                if os.path.exists(factory_wav):
                                    src_wav = factory_wav
                                else:
                                    # Recursive Search
                                    found = find_file_recursively(INPUT_FOLDER, clean_name)
                                    if found:
                                        src_wav = found
                                    else:
                                        src_wav = None
                                        print(f"    [MISSING] Could not find wav: {clean_name}")

                            if src_wav:
                                try:
                                    shutil.copy2(src_wav, os.path.join(patch_folder, clean_name))
                                except Exception as e:
                                    print(f"    [COPY FAIL] {e}")
                        
                        ET.SubElement(new_cell, "params", **attr)

                    for mod in cell.findall("modsource"):
                        ET.SubElement(new_cell, "modsource", **mod.attrib)
                    
                    seq = cell.find("sequence")
                    if seq is not None:
                        new_seq = ET.SubElement(new_cell, "sequence")
                        for event in seq.findall("seqevent"):
                            ET.SubElement(new_seq, "seqevent", **event.attrib)

            # FX Lemon
            fx_cell = ET.SubElement(new_track, "cell", type="fxlemon")
            ET.SubElement(fx_cell, "params", **FX_LEMON_PARAMS)

            # Save XML
            output_xml_path = os.path.join(patch_folder, "patch.xml")
            from xml.dom import minidom
            xmlstr = minidom.parseString(ET.tostring(new_root)).toprettyxml(indent="  ")
            xmlstr = "\n".join([line for line in xmlstr.split('\n') if line.strip()])
            with open(output_xml_path, "w") as f:
                f.write(xmlstr)
            
            # Index Entry (Using UserPatches path)
            index_path = f"{OUTPUT_ROOT}\\{SUB_FOLDER}\\{patch_name}"
            # Using 'Synth' tag as requested, though 'Granular' might be useful too
            entry = f'  <patch path="{index_path}">\n    <tag>Synth</tag>\n  </patch>'
            index_entries.append(entry)

            status = "Wav Copied" if has_external_wav else "Internal/No Wav"
            print(f"  [OK] {patch_name} ({status})")

        except Exception as e:
            print(f"  [FAIL] {filename}: {e}")

    if index_entries:
        print("\nGenerating patchindex_lemondrop.xml...")
        index_content = "<PatchIndex>\n" + "\n".join(index_entries) + "\n</PatchIndex>"
        with open("patchindex_lemondrop.xml", "w") as f:
            f.write(index_content)
        print("Success!")
    
   # ... (rest of script above stays the same)

    if index_entries:
        target_file = "patchindex.xml"
        new_content = "\n".join(index_entries)
        
        if os.path.exists(target_file):
            # Read existing file
            with open(target_file, "r") as f:
                lines = f.readlines()
            
            # Remove the last line (</PatchIndex>)
            if lines and "</PatchIndex>" in lines[-1]:
                lines.pop()
            
            # Write everything back with new entries appended
            with open(target_file, "w") as f:
                f.writelines(lines)
                f.write(new_content + "\n")
                f.write("</PatchIndex>")
            print(f"Success! Appended {len(index_entries)} patches to '{target_file}'.")
            
        else:
            # Create new file if it doesn't exist
            full_content = "<PatchIndex>\n" + new_content + "\n</PatchIndex>"
            with open(target_file, "w") as f:
                f.write(full_content)
            print(f"Success! Created new '{target_file}'.")
    
    input("Press Enter to exit...")

if __name__ == "__main__":
    convert_lemondrop_to_bento()