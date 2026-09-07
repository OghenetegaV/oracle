# claude_ga_generator.py
import json
import os
from pathlib import Path
from config import OUTPUT_JSON_DIR, INPUT_DIR, get_api_key

ANTHROPIC_API_KEY = get_api_key()

if not ANTHROPIC_API_KEY:
    print("⚠️  ANTHROPIC_API_KEY not set. Get it from: https://console.anthropic.com/")
    print("   Either set it as an environment variable, or run oracle_wizard.py, "
          "which will ask for it once and save it locally.")

def load_parsed_geometry(json_file):
    """Load parsed DXF geometry"""
    path = OUTPUT_JSON_DIR / json_file
    with open(path, 'r') as f:
        return json.load(f)

def generate_ga_prompt(geometry, storey_height_m=3.0, slab_thickness_hint_mm=(150, 200),
                        engineer_notes=None, element_notes=None):
    """Create Claude prompt for GA generation"""
    thickness_lo, thickness_hi = slab_thickness_hint_mm
    notes_block = f"\nADDITIONAL REQUIREMENTS FROM THE ENGINEER (follow these, they override defaults below):\n{engineer_notes}\n" if engineer_notes else ""
    if element_notes:
        notes_block += (
            "\nPER-ELEMENT NOTES FROM THE ENGINEER (these reference names from a previous "
            "layout attempt -- keep using the same name for that element if it still applies "
            "to the same position/role):\n" +
            "\n".join(f"- {name}: {note}" for name, note in element_notes.items()) + "\n"
        )

    # Format geometry for Claude
    walls_summary = f"{len(geometry['walls'])} wall segments"
    columns_summary = f"{len(geometry['columns'])} columns"
    gridlines_summary = f"{len(geometry['gridlines'])} gridlines"
    
    walls_text = "\n".join([
        f"  Wall {i}: ({w['start'][0]}, {w['start'][1]}) → ({w['end'][0]}, {w['end'][1]})"
        for i, w in enumerate(geometry['walls'])
    ])
    
    columns_text = "\n".join([
        f"  Column {i}: center ({c['center'][0]}, {c['center'][1]})"
        for i, c in enumerate(geometry['columns'])
    ])
    
    gridlines_text = "\n".join([
        f"  Gridline {i}: ({g['start'][0]}, {g['start'][1]}) → ({g['end'][0]}, {g['end'][1]})"
        for i, g in enumerate(geometry['gridlines'])
    ])
    
    prompt = f"""You are a structural engineer creating a General Arrangement (GA) drawing.

ARCHITECTURAL GEOMETRY EXTRACTED FROM DRAWING:
Walls ({walls_summary}):
{walls_text}

Columns ({columns_summary}):
{columns_text}

Gridlines ({gridlines_summary}):
{gridlines_text}
{notes_block}
TASK: Generate a structural general arrangement with:
1. Optimally placed structural columns (use grid intersections as guidance)
2. Beams connecting columns (longest reasonable spans first)
3. Slabs on each storey
4. Dimensions, labels (C1, C2, B1, B2, S1, S2, etc.)

CONSTRAINTS:
- Column spacing should respect the architectural walls
- Beams should not intersect walls (except at bearing points)
- Slab thickness should be reasonable for a 5m × 5m bay (assume {thickness_lo}-{thickness_hi}mm)
- Assume {storey_height_m}m storey height
- All units in meters

OUTPUT: Provide the GA as a structured JSON with:
{{
  "columns": [
    {{"name": "C1", "x": 0, "y": 0}},
    {{"name": "C2", "x": 5, "y": 0}},
    {{"name": "C3", "x": 10, "y": 0}},
    {{"name": "C4", "x": 0, "y": 5}},
    {{"name": "C5", "x": 5, "y": 5}},
    {{"name": "C6", "x": 10, "y": 5}},
    {{"name": "C7", "x": 0, "y": 10}},
    {{"name": "C8", "x": 5, "y": 10}},
    {{"name": "C9", "x": 10, "y": 10}}
  ],
  "beams": [
    {{"name": "B1", "start_col": "C1", "end_col": "C2", "depth_mm": 500}},
    {{"name": "B2", "start_col": "C2", "end_col": "C3", "depth_mm": 500}},
    ...
  ],
  "slabs": [
    {{"name": "S1", "thickness_mm": 150, "vertices": [[0,0], [5,0], [5,5], [0,5]]}}
  ],
  "summary": "Brief description of the GA"
}}

Be concise. Output ONLY valid JSON, no preamble."""
    
    return prompt

def call_claude(prompt):
    """Call Claude API to generate GA. Raises on failure instead of printing and
    returning None -- under the GUI wizard (pythonw, no console) a swallowed
    print is invisible to everyone, caller included."""
    import anthropic

    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "No Claude API key is set up yet. Run oracle_wizard.py and enter one "
            "when asked, or set the ANTHROPIC_API_KEY environment variable."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=120.0)

    print("Calling Claude for GA generation...")

    try:
        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
    except Exception as e:
        raise RuntimeError(f"Couldn't reach Claude for the layout: {e}") from e

    for block in message.content:
        if hasattr(block, 'text') and block.text:
            return block.text

    raise RuntimeError(
        f"Claude's reply had no usable text (stop_reason={message.stop_reason!r}). "
        "If stop_reason is 'max_tokens', the layout was cut off -- try again."
    )

def save_ga(ga_json, output_file="ga_output.json"):
    """Save GA to JSON file. Raises on failure instead of printing and returning
    None, so the real cause is visible under the GUI wizard too."""
    output_path = OUTPUT_JSON_DIR / output_file

    # Strip markdown code fences if present
    if ga_json.startswith("```json"):
        ga_json = ga_json[7:]  # Remove ```json
    if ga_json.startswith("```"):
        ga_json = ga_json[3:]  # Remove ```
    if ga_json.endswith("```"):
        ga_json = ga_json[:-3]  # Remove trailing ```

    ga_json = ga_json.strip()

    try:
        ga_data = json.loads(ga_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Claude's layout reply wasn't valid JSON ({e}). First 300 chars:\n{ga_json[:300]}"
        ) from e

    with open(output_path, 'w') as f:
        json.dump(ga_data, f, indent=2)

    print(f"✓ GA saved to: {output_path}")
    return ga_data

def main():
    print("=== Oracle Phase 2: General Arrangement Generation ===\n")
    
    # Load parsed geometry
    geometry = load_parsed_geometry("test_floor_parsed.json")
    print(f"✓ Loaded geometry: {len(geometry['walls'])} walls, {len(geometry['columns'])} cols, {len(geometry['gridlines'])} gridlines")
    
    # Generate prompt
    prompt = generate_ga_prompt(geometry)
    print(f"\nPrompt length: {len(prompt)} chars")
    
    # Call Claude
    ga_response = call_claude(prompt)
    
    if not ga_response:
        print("❌ Failed to get response from Claude")
        return None
    
    # Save GA
    ga_data = save_ga(ga_response)
    
    if ga_data:
        print(f"\n✓ GA Generated:")
        print(f"  Columns: {len(ga_data.get('columns', []))}")
        print(f"  Beams: {len(ga_data.get('beams', []))}")
        print(f"  Slabs: {len(ga_data.get('slabs', []))}")
        print(f"  Summary: {ga_data.get('summary', 'N/A')}")
        return ga_data
    else:
        print("❌ GA generation failed")
        return None

if __name__ == "__main__":
    main()