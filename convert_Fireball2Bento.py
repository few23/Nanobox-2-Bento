#Put this script in the same folder as where your Input folder of .nnf files is
#*Do not put it INDIDE the Input folder*
#The script will generate an output folder called UserPatches with a Wavetable subfolder 
#where the converted patch folders containing the .xml file and their related .wav files will be created
#It will also create a patchconfig.xml file wiith synth selected as the default tag

import os
import shutil
import xml.etree.ElementTree as ET

# --- CONFIGURATION ---
INPUT_FOLDER = "FireballContent"
OUTPUT_ROOT = "UserPatches"
SUB_FOLDER = "Wavetable"

# Ensure this matches *your* exact path to the wav files
FACTORY_SAMPLES_PATH = r"C:\1010Bento\FireballContent\Factory"

FULL_OUTPUT_PATH = os.path.join(OUTPUT_ROOT, SUB_FOLDER)

# Default Bento Track Parameters
TRACK_PARAMS = {
    "selcellpos": "0", "celldisppos": "0", "cellname": "", "selseqpos": "0",
    "seqplayenable": "1", "trkgain": "0", "trkpan": "0", "trkmute": "0",
    "trksolo": "0", "trkfx1send": "0", "trkfx2send": "0", "outputbus": "0",
    "midiinport": "0", "midiinchan": "0", "cc1inport": "0", "cc1inchan": "0",
    "cc2inport": "0", "midioutport": "0", "midioutchan": "0", "padrowoffset": "0",
    "recactive": "0", "recinput": "0", "recgain": "0", "recautoplay": "0",
    "recpresetlen": "0", "recquant": "3", "recmonmode": "1", "recusethres": "0",
    "recthresh": "-30000"
}

FX_LEMON_PARAMS = {
    "flangeamount": "0", "flangelforate": "124", "flangefeedback": "-731",
    "distamount": "0", "phaseamount": "0", "phaselforate": "500",
    "phasefeedback": "500", "chorusamount": "0", "chorusrate": "500",
    "fx1send": "255", "fx2send": "0", "fx3type": "0"
}

def clean_and_parse_xml(filepath):
    # Reads file as binary to strip invisible garbage characters
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

def convert_nanobox_to_bento():
    if not os.path.exists(INPUT_FOLDER):
        print(f"Error: Folder '{INPUT_FOLDER}' not found.")
        input("Press Enter to exit...")
        return

    if not os.path.exists(FULL_OUTPUT_PATH):
        os.makedirs(FULL_OUTPUT_PATH)

    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.nnf')]
    print(f"Found {len(files)} patches to convert...")

    index_entries = []

    for filename in files:
        try:
            # FIX 1: Strip whitespace from filename
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
            new_track = ET.SubElement(new_session, "track", type="wttrack")
            ET.SubElement(new_track, "params", **TRACK_PARAMS)

            has_external_wav = False

            if session is not None:
                cells = sorted(session.findall("cell"), key=lambda c: int(c.get("row", 0)))
                
                for cell in cells:
                    ctype = cell.get("type")
                    if ctype == "samtempl": continue

                    new_cell = ET.SubElement(new_track, "cell", type=ctype)
                    
                    # --- FIX 2: GET FILENAME FROM CELL TAG ---
                    # Nanobox keeps it here: <cell filename="...">
                    source_filename = cell.get("filename", "")
                    
                    params = cell.find("params")
                    if params is not None:
                        attr = params.attrib.copy()
                        
                        # --- FIX 3: MOVE TO PARAMS TAG ---
                        # Bento needs it here: <params filename="...">
                        if source_filename:
                            original_path = source_filename
                            clean_name = os.path.basename(original_path.replace("\\", "/"))
                            
                            # Inject into Bento params
                            attr["filename"] = clean_name
                            has_external_wav = True

                            # --- FILE COPY LOGIC ---
                            src_wav = os.path.join(INPUT_FOLDER, original_path)
                            
                            if not os.path.exists(src_wav):
                                factory_wav = os.path.join(FACTORY_SAMPLES_PATH, clean_name)
                                if os.path.exists(factory_wav):
                                    src_wav = factory_wav
                                else:
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

                        # Fix Delay Parameter Name
                        if ctype == "delay" and "cutoff" in attr:
                            attr["cutoffFx"] = attr.pop("cutoff")
                        
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
            
            # Index Entry
            index_path = f"{OUTPUT_ROOT}\\{SUB_FOLDER}\\{patch_name}"
            entry = f'  <patch path="{index_path}">\n    <tag>Synth</tag>\n  </patch>'
            index_entries.append(entry)

            status = "Wav Copied" if has_external_wav else "Internal Audio"
            print(f"  [OK] {patch_name} ({status})")

        except Exception as e:
            print(f"  [FAIL] {filename}: {e}")

    if index_entries:
        print("\nGenerating patchindex.xml...")
        index_content = "<PatchIndex>\n" + "\n".join(index_entries) + "\n</PatchIndex>"
        with open("patchindex.xml", "w") as f:
            f.write(index_content)
        print("Success!")
    
    input("Press Enter to exit...")

if __name__ == "__main__":
    convert_nanobox_to_bento()