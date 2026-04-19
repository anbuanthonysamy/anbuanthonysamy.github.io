"""Generate the business-team overview flow diagram.

Emits three artefacts into ``docs/``:

* ``business-overview.svg`` — editable vector, opens in any browser
* ``business-overview.pdf`` — printable handout (A3 landscape)
* ``business-overview.lucid.csv`` — Lucidchart import CSV

The diagram is a left-to-right swim-lane flow covering the PoC scope for a
business audience: sources, ingestion, shared spine, per-module logic,
outputs, human review and feedback. Shape and colour convey scope
(public / client / shared), status (mocked fixture vs live adapter) and
governance (human-in-the-loop gates).
"""
from __future__ import annotations

import csv
import pathlib
import subprocess
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DOCS.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Colour + shape conventions (kept in one place so the legend can't drift)
# ---------------------------------------------------------------------------
COL_PUBLIC = "#D6E9FF"    # CS1 / CS2 — public data only
COL_CLIENT = "#FFE3D6"    # CS3 / CS4 — client-uploaded data
COL_SHARED = "#E8E8E8"    # shared spine
COL_OUTPUT = "#E4F7E1"    # user-facing outputs
COL_REVIEW = "#FFF5BA"    # human-in-the-loop
COL_FEEDBK = "#F0D6FF"    # feedback / learning
COL_OOS    = "#FADBD8"    # out-of-scope
COL_NOTE   = "#FFFFFF"

EDGE_MAIN = "#333333"
EDGE_FEED = "#8E44AD"

# ---------------------------------------------------------------------------
# Node specs. Each tuple: (id, label, colour, shape, style-extras)
# ``shape=diamond`` = HITL gate. ``style=dashed`` = mocked/fixture source.
# ---------------------------------------------------------------------------

NODES_SOURCES = [
    ("src_edgar",  "SEC EDGAR filings\n(10-K, 8-K, S-1)",           COL_PUBLIC, "cylinder", "solid"),
    ("src_news",   "News feeds\n(RSS / press releases)",            COL_PUBLIC, "cylinder", "solid"),
    ("src_market", "Market data\n(prices, indices)",                COL_PUBLIC, "cylinder", "dashed"),
    ("src_xbrl",   "XBRL peer benchmarks\n(public filings)",        COL_PUBLIC, "cylinder", "solid"),
    ("src_upload", "Client uploads\n(AR / AP / inventory / KPIs)",  COL_CLIENT, "cylinder", "solid"),
    ("src_kpi",    "Deal KPI plans\n(targets + curves)",            COL_CLIENT, "cylinder", "solid"),
]

NODES_INGEST = [
    ("ing_adapter", "Source adapter\n(pluggable, rate-limited)",       COL_SHARED, "box",    "solid"),
    ("ing_fetch",   "Fetch + cache\n(retrieved_at stamped)",           COL_SHARED, "box",    "solid"),
    ("ing_parse",   "Parse + normalise\n(parsed_at stamped)",          COL_SHARED, "box",    "solid"),
    ("ing_chunk",   "Chunk + embed\n(RAG index per source)",           COL_SHARED, "box",    "solid"),
]

NODES_SPINE = [
    ("sp_canon",    "Canonical entities\n(Company, Deal, Person)",     COL_SHARED, "box",    "solid"),
    ("sp_evid",     "Evidence store\n(every claim is cite-able)",      COL_SHARED, "box",    "solid"),
    ("sp_signals",  "Signal handlers\n(declarative, per domain)",      COL_SHARED, "box",    "solid"),
    ("sp_score",    "Weighted scoring\n(tunable per module)",          COL_SHARED, "box",    "solid"),
    ("sp_explain",  "Evidence-grounded\nexplanation layer",            COL_SHARED, "box",    "solid"),
    ("sp_critic",   "Unsupported-claims\ncritic (blocks in CI)",       COL_SHARED, "box",    "solid"),
    ("sp_llm",      "LLM router\nHaiku: extract / classify\nSonnet: synthesis / explain", COL_SHARED, "note", "solid"),
]

NODES_MODULES = [
    ("m_cs1", "CS1 — M&A Origination\npublic only · 12-24m\n>$1bn equity",     COL_PUBLIC, "box3d", "solid"),
    ("m_cs2", "CS2 — Carve-Out Detection\npublic only · 6-18m\n>$750m equity", COL_PUBLIC, "box3d", "solid"),
    ("m_cs3", "CS3 — Post-Deal Value Tracker\nclient + public · 0-24m",        COL_CLIENT, "box3d", "solid"),
    ("m_cs4", "CS4 — Working-Capital Diagnostic\nclient + XBRL peers · 3-9m",  COL_CLIENT, "box3d", "solid"),
]

NODES_OUTPUTS = [
    ("out_queue",  "Ranked situation queue\n(score + confidence)",         COL_OUTPUT, "folder", "solid"),
    ("out_heat",   "Sector heatmap\n(CS1 / CS2)",                          COL_OUTPUT, "folder", "solid"),
    ("out_kpi",    "KPI trend-band charts\n(CS3: in / above / below band)",COL_OUTPUT, "folder", "solid"),
    ("out_wc",     "Working-capital diagnostic\n(DSO / DPO / DIO vs peers)",COL_OUTPUT, "folder", "solid"),
    ("out_expl",   "Per-item explanation\n+ evidence panel + caveats",     COL_OUTPUT, "folder", "solid"),
]

NODES_REVIEW = [
    ("rv_queue",   "Human review queue\n(analyst triage)",                 COL_REVIEW, "box",     "solid"),
    ("rv_gate",    "Approve?\nrequires reviewer +\nts + reason",           COL_REVIEW, "diamond", "solid"),
    ("rv_out",     "Approved recommendation\n(surfaced to business)",      COL_OUTPUT, "box",     "solid"),
]

NODES_FEEDBACK = [
    ("fb_labels", "Reviewer labels\n(accept / edit / reject)", COL_FEEDBK, "box", "solid"),
    ("fb_tune",   "Weight tuning\n+ calibration",              COL_FEEDBK, "box", "solid"),
    ("fb_cover",  "Coverage + label dashboards\n(/eval)",      COL_FEEDBK, "box", "solid"),
]

EDGES_MAIN = [
    # Sources -> Ingestion
    ("src_edgar",  "ing_adapter"),
    ("src_news",   "ing_adapter"),
    ("src_market", "ing_adapter"),
    ("src_xbrl",   "ing_adapter"),
    ("src_upload", "ing_adapter"),
    ("src_kpi",    "ing_adapter"),
    # Ingestion pipeline
    ("ing_adapter","ing_fetch"),
    ("ing_fetch",  "ing_parse"),
    ("ing_parse",  "ing_chunk"),
    # Ingestion -> Spine
    ("ing_chunk",  "sp_canon"),
    ("sp_canon",   "sp_evid"),
    ("sp_evid",    "sp_signals"),
    ("sp_signals", "sp_score"),
    ("sp_score",   "sp_explain"),
    ("sp_explain", "sp_critic"),
    # Spine -> Modules (each module consumes the spine)
    ("sp_critic",  "m_cs1"),
    ("sp_critic",  "m_cs2"),
    ("sp_critic",  "m_cs3"),
    ("sp_critic",  "m_cs4"),
    # Modules -> Outputs
    ("m_cs1", "out_queue"),
    ("m_cs2", "out_queue"),
    ("m_cs1", "out_heat"),
    ("m_cs2", "out_heat"),
    ("m_cs3", "out_kpi"),
    ("m_cs4", "out_wc"),
    ("m_cs1", "out_expl"),
    ("m_cs2", "out_expl"),
    ("m_cs3", "out_expl"),
    ("m_cs4", "out_expl"),
    # Outputs -> Review
    ("out_queue", "rv_queue"),
    ("out_kpi",   "rv_queue"),
    ("out_wc",    "rv_queue"),
    ("out_expl",  "rv_queue"),
    ("rv_queue",  "rv_gate"),
    ("rv_gate",   "rv_out"),
]

EDGES_FEEDBACK = [
    ("rv_gate",  "fb_labels"),
    ("fb_labels","fb_tune"),
    ("fb_tune",  "sp_score"),
    ("fb_labels","fb_cover"),
]

# ---------------------------------------------------------------------------
# DOT emission
# ---------------------------------------------------------------------------

def _node_line(n):
    nid, label, fill, shape, style = n
    penwidth = "2" if style == "dashed" else "1"
    return (
        f'  {nid} [label="{label}", shape={shape}, style="filled,{style}", '
        f'fillcolor="{fill}", penwidth={penwidth}, fontname="Helvetica", fontsize=11];'
    )


def _cluster(cid: str, title: str, nodes, bg: str) -> str:
    lines = [
        f"  subgraph cluster_{cid} {{",
        f'    label=<<b>{title}</b>>; labelloc=t; labeljust=l;',
        f'    style="filled,rounded"; fillcolor="{bg}"; color="#666666"; fontname="Helvetica"; fontsize=13;',
        f'    margin=14;',
    ]
    for n in nodes:
        lines.append("  " + _node_line(n))
    lines.append("  }")
    return "\n".join(lines)


def build_dot() -> str:
    parts: list[str] = []
    parts.append("digraph BusinessOverview {")
    parts.append('  rankdir=LR;')
    parts.append('  splines=ortho;')
    parts.append('  nodesep=0.35;')
    parts.append('  ranksep=0.9;')
    parts.append('  graph [fontname="Helvetica", bgcolor="white", pad="0.3", size="16.5,11.7!", ratio=fill];')
    parts.append('  node  [fontname="Helvetica"];')
    parts.append('  edge  [fontname="Helvetica", fontsize=10, color="' + EDGE_MAIN + '"];')

    parts.append(_cluster("sources",  "1. Data sources (public vs client)", NODES_SOURCES, "#F7FBFF"))
    parts.append(_cluster("ingest",   "2. Ingestion pipeline",              NODES_INGEST,  "#FAFAFA"))
    parts.append(_cluster("spine",    "3. Shared spine (models, evidence, scoring, explain, critic)", NODES_SPINE, "#FAFAFA"))
    parts.append(_cluster("modules",  "4. Module logic (CS1 / CS2 public · CS3 / CS4 client)", NODES_MODULES, "#FAFAFA"))
    parts.append(_cluster("outputs",  "5. User-facing outputs",             NODES_OUTPUTS, "#F3FBF2"))
    parts.append(_cluster("review",   "6. Human-in-the-loop review",        NODES_REVIEW,  "#FFFBE6"))
    parts.append(_cluster("feedback", "7. Feedback + learning loop",        NODES_FEEDBACK,"#FBF3FF"))

    # Main edges
    for a, b in EDGES_MAIN:
        parts.append(f'  {a} -> {b} [color="{EDGE_MAIN}"];')
    # Feedback edges (styled distinctly)
    for a, b in EDGES_FEEDBACK:
        parts.append(f'  {a} -> {b} [color="{EDGE_FEED}", style=dashed, constraint=false, penwidth=1.4];')

    # --- Side panels (legend, scope, out-of-scope, model routing, AI mapping, controls)
    legend = textwrap.dedent(f"""\
        <<table border="0" cellborder="0" cellspacing="2">
          <tr><td colspan="2" align="left"><b>Legend</b></td></tr>
          <tr><td bgcolor="{COL_PUBLIC}" width="28">&#160;</td><td align="left">Public-data scope (CS1 / CS2)</td></tr>
          <tr><td bgcolor="{COL_CLIENT}">&#160;</td><td align="left">Client-data scope (CS3 / CS4)</td></tr>
          <tr><td bgcolor="{COL_SHARED}">&#160;</td><td align="left">Shared spine / ingestion</td></tr>
          <tr><td bgcolor="{COL_OUTPUT}">&#160;</td><td align="left">User-facing output</td></tr>
          <tr><td bgcolor="{COL_REVIEW}">&#160;</td><td align="left">Human-in-the-loop</td></tr>
          <tr><td bgcolor="{COL_FEEDBK}">&#160;</td><td align="left">Feedback / learning</td></tr>
          <tr><td>&#9671;</td><td align="left">Diamond = HITL gate</td></tr>
          <tr><td>- - -</td><td align="left">Dashed border = mocked/fixture source (no live feed yet)</td></tr>
          <tr><td>- - -</td><td align="left">Purple dashed arrow = feedback path</td></tr>
        </table>>
    """)
    parts.append(f'  legend [shape=plaintext, label={legend}];')

    oos = textwrap.dedent("""\
        <<table border="1" cellborder="0" cellspacing="2" bgcolor="%s">
          <tr><td align="left"><b>Explicitly OUT of scope for this PoC</b></td></tr>
          <tr><td align="left">&#8226; SSO / enterprise identity</td></tr>
          <tr><td align="left">&#8226; Production security hardening</td></tr>
          <tr><td align="left">&#8226; Multi-tenancy / row-level isolation beyond scope tag</td></tr>
          <tr><td align="left">&#8226; Mobile UI</td></tr>
          <tr><td align="left">&#8226; Outbound automation (emails, CRM writes)</td></tr>
          <tr><td align="left">&#8226; Paywall / ToS-restricted scraping</td></tr>
          <tr><td align="left">&#8226; Real client data (synthetic fixtures only)</td></tr>
        </table>>
    """) % COL_OOS
    parts.append(f'  out_of_scope [shape=plaintext, label={oos}];')

    ai_map = textwrap.dedent("""\
        <<table border="1" cellborder="0" cellspacing="2" bgcolor="#FFFFFF">
          <tr><td colspan="2" align="left"><b>AI / platform considerations &rarr; where they live</b></td></tr>
          <tr><td align="left">RAG &amp; chunking</td><td align="left">Ingestion (step 2)</td></tr>
          <tr><td align="left">LLM routing (Haiku / Sonnet)</td><td align="left">Shared spine (step 3)</td></tr>
          <tr><td align="left">Evidence grounding + citations</td><td align="left">Evidence store + explain layer</td></tr>
          <tr><td align="left">Unsupported-claims critic</td><td align="left">Shared spine, blocks merge in CI</td></tr>
          <tr><td align="left">Weighted, tunable scoring</td><td align="left">Shared spine + feedback loop</td></tr>
          <tr><td align="left">HITL governance</td><td align="left">Review step (6)</td></tr>
          <tr><td align="left">Offline-default LLM client</td><td align="left">Tests + CI run deterministic</td></tr>
          <tr><td align="left">Source adapters (pluggable)</td><td align="left">Ingestion (step 2)</td></tr>
          <tr><td align="left">Data segregation (AST-checked)</td><td align="left">Module boundary (step 4)</td></tr>
        </table>>
    """)
    parts.append(f'  ai_map [shape=plaintext, label={ai_map}];')

    controls = textwrap.dedent("""\
        <<table border="1" cellborder="0" cellspacing="2" bgcolor="#FFFFFF">
          <tr><td align="left"><b>Quality controls shipped in the PoC</b></td></tr>
          <tr><td align="left">&#8226; Every score cites &#8805; 1 Evidence row</td></tr>
          <tr><td align="left">&#8226; Unsupported-claims check runs in CI</td></tr>
          <tr><td align="left">&#8226; No approval without reviewer + ts + reason</td></tr>
          <tr><td align="left">&#8226; Module imports enforced by AST test</td></tr>
          <tr><td align="left">&#8226; Mocked sources flagged visibly in UI</td></tr>
          <tr><td align="left">&#8226; Deterministic offline LLM in tests</td></tr>
          <tr><td align="left">&#8226; Coverage + label dashboards at /eval</td></tr>
        </table>>
    """)
    parts.append(f'  controls [shape=plaintext, label={controls}];')

    # Invisibly anchor the side panels so they sit to the right
    parts.append('  { rank=sink; legend; out_of_scope; ai_map; controls; }')
    parts.append('  legend -> out_of_scope [style=invis];')
    parts.append('  out_of_scope -> ai_map [style=invis];')
    parts.append('  ai_map -> controls [style=invis];')

    parts.append('  labelloc="t";')
    parts.append('  label=<<b>Deals Platform PoC &#8212; Business-Team Overview</b><br/>'
                 '<font point-size="11">Four modules, one shared spine. Evidence-grounded, human-reviewed, offline-testable.</font>>;')
    parts.append('  fontsize=18;')
    parts.append("}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Lucid CSV (Lucidchart "Standard import" format)
# ---------------------------------------------------------------------------

LUCID_STAGE = {
    "sources":  "1. Sources",
    "ingest":   "2. Ingestion",
    "spine":    "3. Shared spine",
    "modules":  "4. Modules",
    "outputs":  "5. Outputs",
    "review":   "6. Review",
    "feedback": "7. Feedback",
}

LUCID_SHAPE = {
    "cylinder": "Cylinder",
    "box":      "Process",
    "box3d":    "Process",
    "folder":   "Document",
    "note":     "Note",
    "diamond":  "Decision",
}

LUCID_NODES = [
    ("sources",  NODES_SOURCES),
    ("ingest",   NODES_INGEST),
    ("spine",    NODES_SPINE),
    ("modules",  NODES_MODULES),
    ("outputs",  NODES_OUTPUTS),
    ("review",   NODES_REVIEW),
    ("feedback", NODES_FEEDBACK),
]


def build_lucid_csv(path: pathlib.Path) -> None:
    id_of = {}
    rows = []
    # Header — Lucid "Standard" import
    header = [
        "Id", "Name", "Shape Library", "Page ID", "Contained By",
        "Line Source", "Line Destination", "Source Arrow", "Destination Arrow",
        "Text Area 1", "Text Area 2", "Fill",
    ]
    rows.append(header)
    next_id = 1
    # Nodes
    for stage_key, nodes in LUCID_NODES:
        for n in nodes:
            nid, label, fill, shape, style = n
            id_of[nid] = next_id
            lucid_shape = LUCID_SHAPE.get(shape, "Process")
            note = ""
            if style == "dashed":
                note = "Mocked / fixture source"
            text2 = f"{LUCID_STAGE[stage_key]}"
            if note:
                text2 += f" | {note}"
            rows.append([
                next_id, label.replace("\n", " / "), "Shapes", "1", "",
                "", "", "", "",
                label.replace("\n", " / "),
                text2,
                fill,
            ])
            next_id += 1
    # Edges
    for a, b in EDGES_MAIN:
        rows.append([
            next_id, "", "Shapes", "1", "",
            id_of[a], id_of[b], "None", "Arrow",
            "", "main flow", "",
        ])
        next_id += 1
    for a, b in EDGES_FEEDBACK:
        rows.append([
            next_id, "", "Shapes", "1", "",
            id_of[a], id_of[b], "None", "Arrow",
            "", "feedback (dashed)", "",
        ])
        next_id += 1
    with path.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    dot_src = build_dot()
    dot_path = DOCS / "business-overview.dot"
    svg_path = DOCS / "business-overview.svg"
    pdf_path = DOCS / "business-overview.pdf"
    csv_path = DOCS / "business-overview.lucid.csv"

    dot_path.write_text(dot_src, encoding="utf-8")
    subprocess.run(["dot", "-Tsvg", str(dot_path), "-o", str(svg_path)], check=True)
    subprocess.run(["dot", "-Tpdf", str(dot_path), "-o", str(pdf_path)], check=True)
    build_lucid_csv(csv_path)

    print(f"wrote {svg_path.relative_to(ROOT)}")
    print(f"wrote {pdf_path.relative_to(ROOT)}")
    print(f"wrote {csv_path.relative_to(ROOT)}")
    print(f"wrote {dot_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
