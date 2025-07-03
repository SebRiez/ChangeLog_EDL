# created by Sebastian Riezler
# c 2025

import streamlit as st
import pandas as pd
import re

st.title("🎬 EDL Comparison – Source IN/OUT + LOC + Duration")

fps = st.selectbox("📽️ Frame Rate", [24, 25, 30], index=1)

def tc_to_frames(tc):
    h, m, s, f = map(int, tc.split(":"))
    return (h * 3600 + m * 60 + s) * fps + f

def extract_loc_tag(line):
    match = re.search(r"(\w{3}_\d{3}_\d{4})", line[-20:])
    return match.group(1) if match else ""

def parse_edl(lines):
    events = []
    i = 0
    while i < len(lines):
        match = re.match(r"^(\d{6})\s+(\S+)\s+V\s+C\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})\s+(\d{2}:\d{2}:\d{2}:\d{2})", lines[i])
        if match:
            event_id = match.group(1)
            tape_name = match.group(2)
            src_in = match.group(3)
            src_out = match.group(4)
            rec_in = match.group(5)
            from_clip = ""
            locs = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("*"):
                if lines[j].startswith("*FROM CLIP NAME:"):
                    from_clip = lines[j].replace("*FROM CLIP NAME:", "").strip()
                if lines[j].startswith("*LOC:"):
                    tag = extract_loc_tag(lines[j])
                    if tag:
                        locs.append(tag)
                j += 1
            events.append({
                "event_id": event_id,
                "clip_name": from_clip,
                "tape_name": tape_name,
                "src_in": src_in,
                "src_out": src_out,
                "rec_in": rec_in,
                "locs": locs
            })
            i = j
        else:
            i += 1
    return events

edl_old = st.file_uploader("📂 Upload OLD EDL", type=["edl"])
edl_new = st.file_uploader("📂 Upload NEW EDL", type=["edl"])

if edl_old and edl_new:
    edl_old_lines = edl_old.read().decode("utf-8", errors="ignore").splitlines()
    edl_new_lines = edl_new.read().decode("utf-8", errors="ignore").splitlines()

    events_old = parse_edl(edl_old_lines)
    events_new = parse_edl(edl_new_lines)

    old_index = {(e["clip_name"], e["tape_name"]): e for e in events_old}
    new_index = {(e["clip_name"], e["tape_name"]): e for e in events_new}

    results = []

    for key, old_event in old_index.items():
        new_event = new_index.get(key)
        if not new_event:
            old_duration = tc_to_frames(old_event["src_out"]) - tc_to_frames(old_event["src_in"])
            results.append({
                "Clip Name": old_event["clip_name"],
                "Tape Name": old_event["tape_name"],
                "Status": "Removed",
                "Old Src In": old_event["src_in"],
                "Old Src Out": old_event["src_out"],
                "New Src In": "",
                "New Src Out": "",
                "HEAD": "",
                "TAIL": "",
                "LOC": "",
                "REC IN": old_event["rec_in"],
                "Old Duration": old_duration,
                "New Duration": ""
            })
        else:
            head = ""
            tail = ""
            if old_event["src_in"] != new_event["src_in"]:
                diff = tc_to_frames(new_event["src_in"]) - tc_to_frames(old_event["src_in"])
                head = ("extend" if diff < 0 else "trim") + f" ({abs(diff)}f)"
            if old_event["src_out"] != new_event["src_out"]:
                diff = tc_to_frames(new_event["src_out"]) - tc_to_frames(old_event["src_out"])
                tail = ("extend" if diff > 0 else "trim") + f" ({abs(diff)}f)"
            if head or tail:
                old_duration = tc_to_frames(old_event["src_out"]) - tc_to_frames(old_event["src_in"])
                new_duration = tc_to_frames(new_event["src_out"]) - tc_to_frames(new_event["src_in"])
                results.append({
                    "Clip Name": old_event["clip_name"],
                    "Tape Name": old_event["tape_name"],
                    "Status": "Modified",
                    "Old Src In": old_event["src_in"],
                    "Old Src Out": old_event["src_out"],
                    "New Src In": new_event["src_in"],
                    "New Src Out": new_event["src_out"],
                    "HEAD": head,
                    "TAIL": tail,
                    "LOC": ", ".join([l[-12:] if len(l) >= 12 else l for l in new_event.get("locs", [])]),
                    "REC IN": new_event["rec_in"],
                    "Old Duration": old_duration,
                    "New Duration": new_duration
                })

    for key, new_event in new_index.items():
        if key not in old_index:
            new_duration = tc_to_frames(new_event["src_out"]) - tc_to_frames(new_event["src_in"])
            results.append({
                "Clip Name": new_event["clip_name"],
                "Tape Name": new_event["tape_name"],
                "Status": "New",
                "Old Src In": "",
                "Old Src Out": "",
                "New Src In": new_event["src_in"],
                "New Src Out": new_event["src_out"],
                "HEAD": "",
                "TAIL": "",
                "LOC": ", ".join([l[-12:] if len(l) >= 12 else l for l in new_event.get("locs", [])]),
                "REC IN": new_event["rec_in"],
                "Old Duration": "",
                "New Duration": new_duration
            })

    df = pd.DataFrame(results)
    df = df.sort_values(by="REC IN")
    # Reorder duration before HEAD
    columns = df.columns.tolist()
    for col in ["Old Duration", "New Duration"]:
        columns.remove(col)
    head_index = columns.index("HEAD")
    columns.insert(head_index, "New Duration")
    columns.insert(head_index, "Old Duration")
    df = df[columns]

    st.write("### ✨ Comparison Result")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download CSV", csv, "edl_src_changes.csv", "text/csv")
