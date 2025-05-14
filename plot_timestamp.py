import json, re, matplotlib.pyplot as plt, pandas as pd
import os
from pathlib import Path

# Create outputs directory if it doesn't exist
os.makedirs('outputs', exist_ok=True)

# Get all JSON files from inputs directory
input_files = list(Path('inputs').glob('*.json'))
print(f"Found {len(input_files)} JSON files to process")

for input_file in input_files:
    print(f"Processing {input_file}")
    try:
        # Read JSON
        data = json.loads(input_file.read_text())
        
        # Extract timestamps from WEBVTT section instead of Shot line
        webvtt_pat = re.compile(r"(\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}\.\d{3})")
        def to_ms(t):
            """mm:ss.mmm → ms（支持 hh:mm:ss.mmm）"""
            parts = t.split(":")
            if len(parts) == 2: h, m, s = 0, *parts
            else: h, m, s = parts
            s, ms = s.split(".")
            return (int(h)*3600 + int(m)*60 + int(s)) * 1000 + int(ms)

        rows = []
        for i, seg in enumerate(data["result"]["contents"]):
            # Search the entire markdown content for WEBVTT timestamps
            m = webvtt_pat.search(seg["markdown"])
            if m:
                webvtt_start, webvtt_end = map(to_ms, m.groups())
                rows.append(dict(
                    idx=i,
                    struct_start=seg["startTimeMs"],
                    struct_end=seg["endTimeMs"],
                    md_start=webvtt_start,
                    md_end=webvtt_end,
                ))
        
        if not rows:
            print(f"No valid WEBVTT data found in {input_file}")
            continue
            
        df = pd.DataFrame(rows)
        df["struct_dur"] = df.struct_end - df.struct_start
        df["md_dur"] = df.md_end - df.md_start
        df["start_diff"] = df.md_start - df.struct_start
        df["end_diff"] = df.md_end - df.struct_end
        df["start_mismatch"] = df.start_diff.abs() > 20   # Threshold can be adjusted as needed
        df["end_mismatch"] = df.end_diff.abs() > 20

        print(df[["idx","struct_start","md_start","start_diff",
                "struct_end","md_end","end_diff",
                "start_mismatch","end_mismatch"]])

        # Visualization
        fig, ax = plt.subplots(figsize=(10, 0.45*len(df)))
        for y, r in df.iterrows():
            ax.broken_barh([(r.struct_start, r.struct_dur)], (y-0.2, 0.3))
            ax.broken_barh([(r.md_start,     r.md_dur)],     (y+0.2, 0.3))
        ax.set_xlabel("Time (ms)")
        ax.set_yticks(range(len(df)))
        ax.set_yticklabels([f"Seg {i}" for i in df.idx])
        ax.set_title(f"Structured (lower) vs WEBVTT (upper) - {input_file.stem}")
        plt.tight_layout()
        
        # Save figure instead of showing it
        output_path = Path('outputs') / f"{input_file.stem}_comparison.png"
        plt.savefig(output_path, dpi=300)
        plt.close()
        print(f"Saved plot to {output_path}")
        
    except Exception as e:
        print(f"Error processing {input_file}: {e}")
