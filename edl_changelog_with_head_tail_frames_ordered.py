# created by Sebastian Riezler with ChatGpt
# c 2025

import streamlit as st
import pandas as pd
import re

def parse_edl(lines):
    events = {}
    i = 0
    while i < len(lines):
        match = re.match(r"^(\d{6})\s+(.+?)\s+V\s+C\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})", lines[i])
        if match:
            event_id = match.group(1)
            clip_name = match.group(2)
            src_in = match.group(3)
            src_out = match.group(4)
            rec_in = match.group(5)
            rec_out = match.group(6)
            from_clip = lines[i+1].strip().replace("*FROM CLIP NAME: ", "") if i+1 < len(lines) else ""
            
            # Sammle alle folgenden *-Zeilen
            locs = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("*"):
                if lines[j].startswith("*LOC"):
                    locs.append(lines[j].strip().replace("*LOC: ", ""))
                j += 1

            events[rec_in] = {
                "event_id": event_id,
                "clip_name": clip_name,
                "src_in": src_in,
                "src_out": src_out,
                "rec_in": rec_in,
                "rec_out": rec_out,
                "from_clip": from_clip,
                "locs": locs
            }
            i += 2
        else:
            i += 1
    return events

def tc_to_frames(tc):
    h, m, s, f = map(int, tc.split(":"))
    return (h * 3600 + m * 60 + s) * 25 + f

def duration_in_frames(tc_in, tc_out):
    return tc_to_frames(tc_out) - tc_to_frames(tc_in)

def head_tail_change(old_in, old_out, new_in, new_out):
    head = tail = ""
    head_diff = tail_diff = 0
    if old_in and new_in:
        old = tc_to_frames(old_in)
        new = tc_to_frames(new_in)
        if new < old:
            head = f"extend ({old - new}f)"
        elif new > old:
            head = f"trim ({new - old}f)"
    if old_out and new_out:
        old = tc_to_frames(old_out)
        new = tc_to_frames(new_out)
        if new > old:
            tail = f"extend ({new - old}f)"
        elif new < old:
            tail = f"trim ({old - new}f)"
    return head, tail

st.title("EDL Changelog Generator")

edl1_file = st.file_uploader("Upload EDL 1 (old version)", type=["edl"])
edl2_file = st.file_uploader("Upload EDL 2 (new version)", type=["edl"])

if edl1_file and edl2_file:
    edl1_lines = edl1_file.read().decode("utf-8", errors="ignore").splitlines()
    edl2_lines = edl2_file.read().decode("utf-8", errors="ignore").splitlines()

    events1 = parse_edl(edl1_lines)
    events2 = parse_edl(edl2_lines)

    all_keys = set(events1.keys()) | set(events2.keys())
    changelog = []

    for rec_in in sorted(all_keys):
        e1 = events1.get(rec_in)
        e2 = events2.get(rec_in)

        if e1 and not e2:
            changelog.append({
                "Timecode": e1["rec_in"],
                "Clip Name": e1["from_clip"],
                "Status": "Removed",
                "Comment": f"The clip {e1['from_clip']} was removed.",
                "LOC": ", ".join([l[-12:] if len(l) >= 12 else l for l in e1.get("locs", [])]),
                "Old Duration": duration_in_frames(e1["src_in"], e1["src_out"]),
                "Old Source In": e1["src_in"],
                "Old Source Out": e1["src_out"],
                "HEAD": "",
                "TAIL": ""
            })
        elif e2 and not e1:
            changelog.append({
                "Timecode": e2["rec_in"],
                "Clip Name": e2["from_clip"],
                "Status": "New",
                "Comment": f"The clip {e2['from_clip']} was added.",
                "LOC": ", ".join([l[-12:] if len(l) >= 12 else l for l in e2.get("locs", [])]),
                "New Duration": duration_in_frames(e2["src_in"], e2["src_out"]),
                "New Source In": e2["src_in"],
                "New Source Out": e2["src_out"],
                "HEAD": "",
                "TAIL": ""
            })
        elif e1 and e2:
            if (e1["from_clip"] != e2["from_clip"] or 
                e1["src_in"] != e2["src_in"] or 
                e1["src_out"] != e2["src_out"]):
                head, tail = head_tail_change(e1["src_in"], e1["src_out"], e2["src_in"], e2["src_out"])
                changelog.append({
                    "Timecode": e1["rec_in"],
                    "Clip Name": e1["from_clip"],
                    "Status": "Changed",
                    "Comment": f"The clip {e1['from_clip']} was modified. The source timecode changed.",
                    "LOC": ", ".join([l[-12:] if len(l) >= 12 else l for l in e2.get("locs", [])]),
                    "Old Duration": duration_in_frames(e1["src_in"], e1["src_out"]),
                    "New Duration": duration_in_frames(e2["src_in"], e2["src_out"]),
                    "Old Source In": e1["src_in"],
                    "Old Source Out": e1["src_out"],
                    "New Source In": e2["src_in"],
                    "New Source Out": e2["src_out"],
                    "HEAD": head,
                    "TAIL": tail
                })

    df = pd.DataFrame(changelog)

    # Neue Spaltenreihenfolge definieren
    preferred_order = [
        "Timecode", "LOC", "Status", "HEAD", "TAIL",
        "Old Duration", "New Duration"
    ]
    # Alle anderen Spalten, die nicht in preferred_order sind
    remaining_cols = [col for col in df.columns if col not in preferred_order]
    df = df[[*preferred_order, *remaining_cols]]
    df = df.rename(columns={"Timecode": "TC REC"})

    st.write("### Changelog")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "changelog.csv", "text/csv")
