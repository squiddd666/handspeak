"""
Generate a comprehensive HTML report combining virtual camera test results
with existing evaluation data for all words shown in the user's screenshot.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent
REPORT_DIR = REPO / "reports" / "virtual-camera-all-words"

# Load virtual camera results
vc_results = json.loads((REPORT_DIR / "virtual-camera-results.json").read_text())

# Load existing evaluation data
motion_accuracy = json.loads((REPO / "models" / "motion-word-accuracy.json").read_text())

# Build word data from all sources
word_data = {}

# Helper to add word data
def add_word(word, correct, total, source, note=""):
    word_data[word] = {
        "correct": correct,
        "total": total,
        "source": source,
        "note": note,
        "accuracy": round(correct / total * 100, 1) if total > 0 else 0
    }

# From motion-word-accuracy.json (default 6-word model)
for word, data in motion_accuracy.get("profiles", {}).get("default", {}).get("words", {}).items():
    add_word(word, data["correct"], data["total"], "Recorded clip evaluation", "Default 6-word model")

# Expanded 7-word model
for word, data in motion_accuracy.get("profiles", {}).get("expanded", {}).get("words", {}).items():
    add_word(word, data["correct"], data["total"], "Recorded clip evaluation", "Expanded 7-word preview")

# Daily / research 5-word model
for word, data in motion_accuracy.get("profiles", {}).get("daily", {}).get("words", {}).items():
    add_word(word, data["correct"], data["total"], "Recorded clip evaluation", "Five-word server preview")

# Baby model
for word, data in motion_accuracy.get("profiles", {}).get("baby", {}).get("words", {}).items():
    add_word(word, data["correct"], data["total"], "Recorded clip evaluation", "Experimental BABY model")

# From single-word model index.json
single_models = json.loads((REPO / "models" / "motion-categories" / "index.json").read_text())
for group in single_models.get("groups", []):
    test = group.get("test", {})
    per_word = test.get("perWord", {})
    for word, data in per_word.items():
        add_word(word, data["correct"], data["total"], "Recorded clip evaluation", f"Single-word {group['name']} model")

# From capstone evaluation data (read from reports if available)
capstone_files = {
    "capstone-nine-20261021.json": "Capstone 100-word model",
}
for filename, label in capstone_files.items():
    path = REPO / "reports" / filename
    if path.exists():
        data = json.loads(path.read_text())
        for item in data.get("results", []):
            word = item.get("word")
            if word and word not in word_data:
                correct = 1 if item.get("top1") else 0
                add_word(word, correct, 1, "Capstone evaluation", label)

# Override with virtual camera results where available
for r in vc_results.get("results", []):
    word = r.get("word")
    if not word:
        continue
    if "error" in r:
        word_data[word] = {
            "correct": 0,
            "total": 1,
            "source": "Virtual camera test",
            "note": f"Error: {r['error']}",
            "accuracy": 0,
            "vc_error": True
        }
    else:
        recognized = r.get("unique_recognized", [])
        correct = 1 if word in recognized else 0
        total = 1
        # Some words were misrecognized as other words
        if recognized and word not in recognized:
            note = f"Misrecognized as: {', '.join(recognized)}"
        elif not recognized:
            note = r.get("final_status", "No match")
        else:
            note = "Virtual camera: matched"
        word_data[word] = {
            "correct": correct,
            "total": total,
            "source": "Virtual camera test",
            "note": note,
            "accuracy": round(correct / total * 100, 1),
            "vc_result": r
        }

# All words from the user's screenshot
ALL_WORDS = [
    "HELLO", "THANK YOU", "PLEASE", "YES", "NO", "FINISH",
    "DRINK", "WATER", "BOOK", "FOOD", "HUNGRY", "LIKE",
    "GO", "NAME", "HOME", "HAVE", "WANT", "LOVE",
    "BABY", "BELT", "EAT", "EMPTY", "PEG", "SOCCER",
    "SQUEEZE", "VLOG", "LOCK", "DUCK", "BASEBALLCAP", "OTHER",
    "WHATFOR", "DRAG", "MICROSCOPE", "PARTY", "DEMAND", "EDIT",
    "MECHANIC", "DEAF", "PAIN", "SICK", "SEE", "NIGHT",
    "FISH"
]

# Missing words from screenshot that we don't have data for
MISSING_WORDS = [w for w in ALL_WORDS if w not in word_data]
for word in MISSING_WORDS:
    word_data[word] = {
        "correct": 0,
        "total": 0,
        "source": "N/A",
        "note": "No local test video or evaluation data available",
        "accuracy": 0,
        "missing": True
    }

def accuracy_color(pct):
    if pct >= 90: return "#7ee787"
    if pct >= 75: return "#79c0ff"
    if pct >= 60: return "#ffa657"
    return "#f85149"

def status_badge(pct, missing=False, error=False):
    if missing: return "<span class='badge missing'>NO DATA</span>"
    if error: return "<span class='badge error'>ERROR</span>"
    if pct >= 90: return "<span class='badge excellent'>STRONG</span>"
    if pct >= 75: return "<span class='badge good'>GOOD</span>"
    if pct >= 60: return "<span class='badge fair'>FAIR</span>"
    return "<span class='badge poor'>NEEDS WORK</span>"

# Build grid cells
cells = []
for word in ALL_WORDS:
    data = word_data[word]
    pct = data["accuracy"]
    correct = data["correct"]
    total = data["total"]
    source = data["source"]
    note = data["note"]
    missing = data.get("missing", False)
    error = data.get("vc_error", False)

    if missing:
        pct_str = "—"
        count_str = "No data"
    elif error:
        pct_str = "0%"
        count_str = "Error"
    else:
        pct_str = f"{pct}%"
        count_str = f"{correct}/{total}"

    color = accuracy_color(pct) if not missing and not error else "#8b949e"
    border_color = color if not missing else "#30363d"

    cells.append(f"""
    <div class="card" style="border-left-color: {border_color}">
        <div class="card-word">{word}</div>
        <div class="card-pct" style="color: {color}">{pct_str}</div>
        <div class="card-count">{count_str}</div>
        <div class="card-note" title="{note}">{note[:35]}{'...' if len(note) > 35 else ''}</div>
        <div class="card-source">{source}</div>
        {status_badge(pct, missing, error)}
    </div>
    """)

# Summary stats
tested = [w for w in ALL_WORDS if w in word_data and not word_data[w].get("missing", False)]
vc_tested = [w for w in ALL_WORDS if w in word_data and word_data[w].get("source") == "Virtual camera test"]
vc_correct = [w for w in vc_tested if word_data[w]["correct"] > 0]
known_correct = sum(1 for w in tested if word_data[w]["correct"] > 0)

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>HandSpeak — Virtual Camera Word Test Results</title>
<style>
:root {{ color-scheme: dark; }}
body {{
    font-family: 'DM Sans', 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: #0d1117;
    color: #c9d1d9;
    margin: 0;
    padding: 2rem;
    line-height: 1.5;
}}
h1 {{
    color: #f0f6fc;
    font-weight: 800;
    font-size: 1.8rem;
    margin-bottom: 0.3rem;
    letter-spacing: -0.02em;
}}
.subtitle {{
    color: #8b949e;
    font-size: 0.95rem;
    margin-bottom: 1.5rem;
}}
.summary-bar {{
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    margin-bottom: 2rem;
}}
.summary-pill {{
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 999px;
    padding: 0.5rem 1rem;
    font-size: 0.85rem;
    color: #c9d1d9;
}}
.summary-pill b {{
    color: #7ee787;
    font-weight: 700;
}}
.grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 0.75rem;
}}
.card {{
    background: #161b22;
    border: 1px solid #30363d;
    border-left: 3px solid #30363d;
    border-radius: 8px;
    padding: 0.9rem 0.8rem;
    text-align: center;
    transition: transform 0.15s, border-color 0.2s;
    position: relative;
}}
.card:hover {{
    transform: translateY(-2px);
    border-color: #58a6ff;
}}
.card-word {{
    font-weight: 700;
    font-size: 0.9rem;
    color: #f0f6fc;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.3rem;
}}
.card-pct {{
    font-size: 1.3rem;
    font-weight: 800;
    margin-bottom: 0.15rem;
}}
.card-count {{
    font-size: 0.75rem;
    color: #8b949e;
    margin-bottom: 0.4rem;
}}
.card-note {{
    font-size: 0.7rem;
    color: #6e7681;
    margin-bottom: 0.3rem;
    min-height: 1.1em;
}}
.card-source {{
    font-size: 0.65rem;
    color: #484f58;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 0.4rem;
}}
.badge {{
    display: inline-block;
    font-size: 0.6rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
}}
.badge.excellent {{ background: rgba(126,231,135,0.15); color: #7ee787; }}
.badge.good {{ background: rgba(121,192,255,0.15); color: #79c0ff; }}
.badge.fair {{ background: rgba(255,166,87,0.15); color: #ffa657; }}
.badge.poor {{ background: rgba(248,81,73,0.15); color: #f85149; }}
.badge.missing {{ background: rgba(139,148,158,0.1); color: #8b949e; }}
.badge.error {{ background: rgba(255,166,87,0.15); color: #ffa657; }}
.legend {{
    margin-top: 2rem;
    padding-top: 1.5rem;
    border-top: 1px solid #30363d;
    font-size: 0.8rem;
    color: #8b949e;
}}
.legend h3 {{
    color: #f0f6fc;
    font-size: 0.9rem;
    margin-bottom: 0.5rem;
}}
.legend-item {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.3rem;
}}
.dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
}}
</style>
</head>
<body>
<h1>HandSpeak Virtual Camera Test Results</h1>
<div class="subtitle">
    Combined report: live virtual-camera playback tests + recorded-clip evaluation data
    &middot; {len(vc_tested)} words tested with virtual camera &middot; {len(vc_correct)} passed
    &middot; {len(tested)} words with known accuracy data
</div>
<div class="summary-bar">
    <div class="summary-pill"><b>{len(vc_correct)}</b> / {len(vc_tested)} virtual camera passes</div>
    <div class="summary-pill"><b>{len([w for w in tested if word_data[w]['accuracy'] >= 90])}</b> words at ≥90%</div>
    <div class="summary-pill"><b>{len([w for w in tested if word_data[w]['accuracy'] >= 75])}</b> words at ≥75%</div>
    <div class="summary-pill"><b>{len(MISSING_WORDS)}</b> words missing data</div>
</div>
<div class="grid">
    {''.join(cells)}
</div>
<div class="legend">
    <h3>Legend</h3>
    <div class="legend-item"><span class="dot" style="background:#7ee787"></span> <b>≥90%</b> Strong recognition</div>
    <div class="legend-item"><span class="dot" style="background:#79c0ff"></span> <b>75–89%</b> Good recognition</div>
    <div class="legend-item"><span class="dot" style="background:#ffa657"></span> <b>60–74%</b> Fair recognition</div>
    <div class="legend-item"><span class="dot" style="background:#f85149"></span> <b>&lt;60%</b> Needs improvement</div>
    <div class="legend-item"><span class="dot" style="background:#8b949e"></span> <b>No data</b> No local video or evaluation available</div>
    <p style="margin-top:1rem">
        <b>Virtual camera method:</b> Local MP4 videos played through a 640×480 canvas captureStream at 30 fps,
        processed by the browser's MediaPipe hand tracker and motion-word classifier with automatic segmentation.
        Face tracking was disabled. Results reflect the actual browser camera pipeline.
        <br><br>
        <b>Note:</b> Capstone words (BELT, EAT, EMPTY, etc.) and research words (NAME, HOME, HAVE, WANT, LOVE)
        require server-side models or specific recording modes not available in this local browser-only test.
        Their displayed accuracy comes from held-out recorded-clip evaluations.
        The THANK YOU video had a format error during virtual camera playback.
    </p>
</div>
</body>
</html>
"""

output_path = REPORT_DIR / "combined-test-report.html"
output_path.write_text(html, encoding="utf-8")
print(f"Combined report saved to: {output_path}")
