# design_module.py
import json
from pathlib import Path
from config import OUTPUT_JSON_DIR, get_api_key
import anthropic

ANTHROPIC_API_KEY = get_api_key()

def load_forces(json_file="staad_results.json"):
    """Load forces from mock Staad analysis"""
    path = OUTPUT_JSON_DIR / json_file
    with open(path, 'r') as f:
        return json.load(f)

def load_ga(json_file="ga_output.json"):
    """Load GA"""
    path = OUTPUT_JSON_DIR / json_file
    with open(path, 'r') as f:
        return json.load(f)

def _concrete_column_instructions(concrete_grade, exposure_note):
    return (
        f"COLUMNS -- reinforced concrete to BS 8110-1:1997, {concrete_grade}, T/Y high-yield "
        f"steel (fy=410 N/mm2) per BS 4449. Cover: 40mm{exposure_note} (50mm in foundation).\n"
        'Per column, output: {"name": "<name>", "material": "concrete", "load_kn": <value>, '
        '"section": "<width>x<depth mm>", "bars": "<qty>-<dia>mm"}'
    )


def _steel_column_instructions(steel_grade, standards):
    steel = standards["structural_steel"]
    fy = steel["grades"][steel_grade]["fy_n_mm2"]
    sections = ", ".join(steel["section_ranges"]["columns"])
    return (
        f"COLUMNS -- structural steel to BS 5950-1:2000, grade {steel_grade} (py={fy} N/mm2). "
        f"Choose a Universal Column (UC) serial size from this range (or a close standard "
        f"equivalent): {sections}. Check axial capacity Pc against the load (initial sizing "
        f"only -- ignore buckling length effects, state that assumption in capacity_check).\n"
        'Per column, output: {"name": "<name>", "material": "steel", "load_kn": <value>, '
        '"section": "<UC designation>", "grade": "' + steel_grade + '", '
        '"capacity_check": "<e.g. Pc=612kN > 500kN OK>"}'
    )


def _concrete_beam_instructions(concrete_grade, exposure_note):
    return (
        f"BEAMS -- reinforced concrete to BS 8110-1:1997, {concrete_grade}, T/Y high-yield "
        f"steel (fy=410 N/mm2) per BS 4449. Cover: 25mm{exposure_note}.\n"
        'Per beam, output: {"name": "<name>", "material": "concrete", '
        '"section": "<width>x<depth mm>", "main_bars": "<qty>-<dia>mm", "stirrups": "<dia>mm@<spacing mm>"}'
    )


def _steel_beam_instructions(steel_grade, standards):
    steel = standards["structural_steel"]
    fy = steel["grades"][steel_grade]["fy_n_mm2"]
    sections = ", ".join(steel["section_ranges"]["beams"])
    return (
        f"BEAMS -- structural steel to BS 5950-1:2000, grade {steel_grade} (py={fy} N/mm2). "
        f"Choose a Universal Beam (UB) serial size from this range (or a close standard "
        f"equivalent): {sections}. Check moment capacity Mc=py*Sx and shear capacity "
        f"Pv=0.6*py*Av against the loads (initial sizing only -- ignore lateral-torsional "
        f"buckling and deflection, state that assumption in capacity_check).\n"
        'Per beam, output: {"name": "<name>", "material": "steel", "section": "<UB designation>", '
        '"grade": "' + steel_grade + '", "capacity_check": "<e.g. Mc=95kNm > 78kNm OK, Pv=310kN > 125kN OK>"}'
    )


EXPOSURE_COVER_NOTE = {
    "Mild": "",
    "Moderate": " (+5mm for moderate exposure per a simplified BS 8110 Table 3.3 allowance)",
    "Severe": " (+10mm for severe exposure per a simplified BS 8110 Table 3.3 allowance)",
}


def generate_design_prompt(ga, forces, standards=None, column_material="concrete",
                            beam_material="concrete", concrete_grade="C25/30 (fcu=25 N/mm2)",
                            steel_grade="S275", exposure_class="Mild", engineer_notes=None,
                            element_notes=None):
    """Create Claude prompt for element design, built from the actual analysis results
    (forces['node_forces'] / forces['member_forces']) instead of fixed placeholder loads.
    column_material/beam_material are each independently "concrete" (BS 8110-1) or "steel"
    (BS 5950-1), so e.g. steel beams on concrete columns -- a common composite scheme -- is
    a normal choice, not a special case."""

    if standards is None:
        with open(Path(__file__).parent / "company_standards.json") as f:
            standards = json.load(f)

    storey_height_m = ga.get('dimensions', {}).get('storey_height_m', 3)
    column_names = [c['name'] for c in ga['columns']]
    beam_names = [b['name'] for b in ga['beams']]
    exposure_note = EXPOSURE_COVER_NOTE.get(exposure_class, "")

    loading_basis = forces.get('loading_basis', {})
    loading_line = (
        f"Loads derived per {loading_basis['standard']}: "
        f"factored ULS UDL = {loading_basis['factored_uls_udl_kn_m2']} kN/m^2 "
        f"(BS 8110 cl 2.4.3, 1.4Gk+1.6Qk)."
        if loading_basis else
        "Loads from the attached structural analysis (see forces below)."
    )

    column_load_lines = "\n".join(
        f"- {nf['column_name']}: {abs(nf['fy']):.1f} kN axial (fixed base, {storey_height_m}m height)"
        for nf in forces['node_forces'].values()
    )
    beam_force_lines = "\n".join(
        f"- {mf['beam_name']} (span {mf['span_m']}m, depth {mf['depth_mm']}mm): "
        f"Max moment {mf['max_moment_knm']:.1f} kNm, Max shear {mf['max_shear_kn']:.1f} kN"
        for mf in forces['member_forces'].values()
    )

    column_instructions = (
        _concrete_column_instructions(concrete_grade, exposure_note) if column_material == "concrete"
        else _steel_column_instructions(steel_grade, standards)
    )
    beam_instructions = (
        _concrete_beam_instructions(concrete_grade, exposure_note) if beam_material == "concrete"
        else _steel_beam_instructions(steel_grade, standards)
    )

    notes_block = f"\nADDITIONAL REQUIREMENTS FROM THE ENGINEER (follow these, they override defaults above):\n{engineer_notes}\n" if engineer_notes else ""
    if element_notes:
        notes_block += (
            "\nPER-ELEMENT NOTES FROM THE ENGINEER (apply to the named column/beam "
            "specifically; a note on a slab name is context only, since slabs aren't "
            "designed by this step):\n" +
            "\n".join(f"- {name}: {note}" for name, note in element_notes.items()) + "\n"
        )

    example_col = (
        '{"name": "%s", "material": "concrete", "load_kn": <value>, "section": "<w>x<d mm>", "bars": "<qty>-<dia>mm"}' % column_names[0]
        if column_material == "concrete" else
        '{"name": "%s", "material": "steel", "load_kn": <value>, "section": "<UC designation>", "grade": "%s", "capacity_check": "<text>"}' % (column_names[0], steel_grade)
    )
    example_beam = (
        '{"name": "%s", "material": "concrete", "section": "<w>x<d mm>", "main_bars": "<qty>-<dia>mm", "stirrups": "<dia>mm@<spacing mm>"}' % beam_names[0]
        if beam_material == "concrete" else
        '{"name": "%s", "material": "steel", "section": "<UB designation>", "grade": "%s", "capacity_check": "<text>"}' % (beam_names[0], steel_grade)
    )

    prompt = f"""Design the structural elements below, per material category.

{column_instructions}

{beam_instructions}

{loading_line}
{notes_block}
COLUMN LOADS:
{column_load_lines}

BEAM FORCES:
{beam_force_lines}

Design every column listed ({', '.join(column_names)}) and every beam listed ({', '.join(beam_names)}) -- one entry each, no omissions. Every column entry must have "material":"{column_material}" and every beam entry must have "material":"{beam_material}", matching the category instructions above exactly.

OUTPUT ONLY THIS JSON (repeat the pattern below for every column/beam listed above):
{{
  "columns": [
    {example_col}
  ],
  "beams": [
    {example_beam}
  ],
  "summary": "Brief description of the design basis used."
}}"""

    return prompt

def call_claude_design(prompt):
    """Call Claude for element design. Raises on failure instead of swallowing the
    real error into a print() -- under the GUI wizard (pythonw, no console) a
    swallowed print is invisible to everyone, caller included."""

    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "No Claude API key is set up yet. Run oracle_wizard.py and enter one "
            "when asked, or set the ANTHROPIC_API_KEY environment variable."
        )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=120.0)

    print("Calling Claude for element design...")

    try:
        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
    except Exception as e:
        raise RuntimeError(f"Couldn't reach Claude for the element design: {e}") from e

    for block in message.content:
        if hasattr(block, 'text') and block.text:
            return block.text

    raise RuntimeError(
        f"Claude's reply had no usable text (stop_reason={message.stop_reason!r}). "
        "If stop_reason is 'max_tokens', the design was cut off -- try again."
    )

def save_design(design_json, output_file="design_output.json"):
    """Save design to JSON file. Raises on failure instead of printing and
    returning None, so the real cause is visible under the GUI wizard too."""
    output_path = OUTPUT_JSON_DIR / output_file

    if design_json is None:
        raise RuntimeError("No design response from Claude to save.")

    # Strip markdown code fences if present
    if design_json.startswith("```json"):
        design_json = design_json[7:]
    if design_json.startswith("```"):
        design_json = design_json[3:]
    if design_json.endswith("```"):
        design_json = design_json[:-3]

    design_json = design_json.strip()

    try:
        design_data = json.loads(design_json)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Claude's design reply wasn't valid JSON ({e}). First 300 chars:\n"
            f"{design_json[:300]}"
        ) from e

    with open(output_path, 'w') as f:
        json.dump(design_data, f, indent=2)

    print(f"✓ Design saved to: {output_path}")
    return design_data

def display_design_summary(design_data):
    """Display design summary"""
    print("\n=== DESIGN SUMMARY ===\n")
    
    # Column summary
    if 'columns' in design_data:
        print(f"COLUMNS ({len(design_data['columns'])} total):")
        for col in design_data['columns'][:3]:  # Show first 3
            detail = col.get('bars') or col.get('capacity_check') or 'N/A'
            print(f"  {col['name']} [{col.get('material', 'concrete')}]: {col['section']}, {detail}")
        if len(design_data['columns']) > 3:
            print(f"  ... and {len(design_data['columns']) - 3} more")

    # Beam summary
    if 'beams' in design_data:
        print(f"\nBEAMS ({len(design_data['beams'])} total):")
        for beam in design_data['beams'][:3]:  # Show first 3
            if beam.get('material') == 'steel':
                detail = beam.get('capacity_check', 'N/A')
            else:
                detail = f"{beam.get('main_bars', 'N/A')}, Stirrups: {beam.get('stirrups', 'N/A')}"
            print(f"  {beam['name']} [{beam.get('material', 'concrete')}]: {beam['section']}, {detail}")
        if len(design_data['beams']) > 3:
            print(f"  ... and {len(design_data['beams']) - 3} more")
    
    summary = design_data.get('summary', '')
    if summary:
        print(f"\n{summary}")

def main():
    print("=== Oracle Phase 4: Element Design ===\n")
    
    # Load GA and forces
    ga = load_ga()
    forces = load_forces()
    
    print(f"✓ Loaded GA and forces\n")
    
    # Generate design prompt
    prompt = generate_design_prompt(ga, forces)
    print(f"Prompt length: {len(prompt)} chars\n")
    
    # Call Claude for design
    design_response = call_claude_design(prompt)
    
    if not design_response:
        print("❌ Failed to get design from Claude")
        return None
    
    # Save design
    design_data = save_design(design_response)
    
    if design_data:
        display_design_summary(design_data)
        print("\n✓ Design complete!")
        return design_data
    else:
        print("\n❌ Design failed")
        return None

if __name__ == "__main__":
    main()