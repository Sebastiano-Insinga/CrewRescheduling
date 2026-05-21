"""
Deadhead visualizer for run_instance("S01", method='calculateInitialSolution_deadhead').

Steps:
1. Run the instance and collect existing_duties + raw inputs
2. Post-hoc: find deadheads as consecutive task pairs where destination != next origin
3. Look up SP path for each deadhead
4. Extract subnetwork (only stations/edges appearing in deadhead paths)
5. Spring-layout via networkx → Plotly figure saved as HTML
"""

import os, sys, json, math, colorsys
import networkx as nx
import plotly.graph_objects as go

# ── run from project root ─────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# ── local imports ─────────────────────────────────────────────────────────────
from SequentialRescheduling import (
    run_instance, NETWORK_FILE, SHORTESTPATHS_FILE, INSTANCE_DIR, epoch_to_minutes
)
from RollingStockGreedy import load_data, compute_disrupted_sp

# ── 1. run instance ───────────────────────────────────────────────────────────
print("[1/5] Running instance S01 with calculateInitialSolution_deadhead …")

# We need duties AND raw data — patch run_instance return to expose them,
# or reload data ourselves after the call.
result = run_instance("S01", method='calculateInitialSolution_deadhead')
print(f"      done: {result['crew_duties']} duties, {result['crew_uncovered']} uncovered, "
      f"{result['crew_dh_km']:.1f} km deadhead")

# Reload duties from saved JSON
duties_path = os.path.join("output", "crew_solution", "S01.json")
with open(duties_path) as f:
    raw = json.load(f)
existing_duties = {int(k): v for k, v in raw.items()}

# Reload network + SP
instance_file = os.path.join(INSTANCE_DIR, "S01.json")
instance, network, sp = load_data(instance_file, NETWORK_FILE, SHORTESTPATHS_FILE)

stations_by_id = {s['id']: s for s in network['stations']}
sections_list  = network['sections']

# ── 2. find deadheads ─────────────────────────────────────────────────────────
print("[2/5] Detecting deadheads from duties …")

deadheads = []  # list of dicts
for driver_id, duty in existing_duties.items():
    for i in range(len(duty) - 1):
        t_cur  = duty[i]
        t_next = duty[i + 1]
        frm = t_cur['destination']
        to  = t_next['origin']
        if frm == to:
            continue
        entry = sp.get(str(frm), {}).get(str(to))
        if entry is None:
            dh_min = float('inf')
            path_nodes = []
        else:
            dist_m  = entry['weight']
            dh_min  = (dist_m / 1000.0 / 57.0) * 60.0
            path_nodes = [frm] + [int(n) for n in entry.get('path', [])] + [to]
        deadheads.append({
            'driver':      driver_id,
            'from':        frm,
            'to':          to,
            'minutes':     round(dh_min, 1),
            'matrix':      'SP',          # dsp=None always in run_instance
            'path_nodes':  path_nodes,
        })

print(f"      {len(deadheads)} deadhead legs found")
if not deadheads:
    print("No deadheads — nothing to visualise.")
    sys.exit(0)

# ── 3. extract subnetwork: all deadhead endpoint stations ─────────────────────
print("[3/5] Extracting subnetwork (all deadhead endpoints) …")

# All nodes: SP-path intermediate nodes + endpoints
sub_station_ids = set()
sp_path_edges   = set()   # physical rail edges (solid)
dh_direct_edges = set()   # deadhead from→to arcs (dashed)

for dh in deadheads:
    nodes = dh['path_nodes']           # [from, ...intermediates..., to]
    for n in nodes:
        sub_station_ids.add(n)
    for j in range(len(nodes) - 1):
        sp_path_edges.add((nodes[j], nodes[j + 1]))
    dh_direct_edges.add((dh['from'], dh['to']))

print(f"      stations (incl. intermediate): {len(sub_station_ids)}")
print(f"      SP path edges (solid):          {len(sp_path_edges)}")
print(f"      deadhead arcs (dashed):         {len(dh_direct_edges)}")

# ── 4. spring layout ──────────────────────────────────────────────────────────
print("[4/5] Computing spring layout …")

G = nx.DiGraph()
G.add_nodes_from(sub_station_ids)
G.add_edges_from(sp_path_edges)   # layout driven by physical topology

k_val = 2.0 / math.sqrt(max(len(sub_station_ids), 1))
pos   = nx.spring_layout(G, seed=42, k=k_val, iterations=80)

# ── 5. plotly figure ──────────────────────────────────────────────────────────
print("[5/5] Building Plotly figure …")

# Colour per driver
drivers = sorted({dh['driver'] for dh in deadheads})
n_drv   = max(len(drivers), 1)
def driver_colour(idx):
    h = idx / n_drv
    r, g, b = colorsys.hsv_to_rgb(h, 0.78, 0.85)
    return f"rgb({int(r*255)},{int(g*255)},{int(b*255)})"

driver_colour_map = {d: driver_colour(i) for i, d in enumerate(drivers)}

fig = go.Figure()

# ── trace 1: SP physical path edges (solid grey) ─────────────────────────────
ex, ey = [], []
for (u, v) in sp_path_edges:
    if u in pos and v in pos:
        ex += [pos[u][0], pos[v][0], None]
        ey += [pos[u][1], pos[v][1], None]

fig.add_trace(go.Scatter(
    x=ex, y=ey, mode='lines',
    line=dict(color='#aab0b8', width=1.2),
    hoverinfo='none', showlegend=True,
    name='Percorso SP (solido)',
))

# ── trace 2: deadhead arcs per driver (dashed) ───────────────────────────────
for driver_id in drivers:
    col    = driver_colour_map[driver_id]
    drvdhs = [dh for dh in deadheads if dh['driver'] == driver_id]

    dx, dy = [], []
    hx, hy, htxt = [], [], []

    for dh in drvdhs:
        u, v = dh['from'], dh['to']
        if u in pos and v in pos:
            dx += [pos[u][0], pos[v][0], None]
            dy += [pos[u][1], pos[v][1], None]
            # hover point at midpoint
            hx.append((pos[u][0] + pos[v][0]) / 2)
            hy.append((pos[u][1] + pos[v][1]) / 2)
            htxt.append(
                f"<b>Driver {driver_id}</b><br>"
                f"{dh['from']} → {dh['to']}<br>"
                f"{dh['minutes']} min | {dh['matrix']}<br>"
                f"hops SP: {len(dh['path_nodes'])-1}"
            )

    if not dx:
        continue

    fig.add_trace(go.Scatter(
        x=dx, y=dy, mode='lines',
        line=dict(color=col, width=2.5, dash='dash'),
        hoverinfo='none',
        name=f'Driver {driver_id} (deadhead)',
    ))
    fig.add_trace(go.Scatter(
        x=hx, y=hy, mode='markers',
        marker=dict(size=12, color=col, opacity=0.0),
        text=htxt,
        hovertemplate='%{text}<extra></extra>',
        showlegend=False,
    ))

# ── trace 3: nodes ────────────────────────────────────────────────────────────
dh_endpoints = {dh['from'] for dh in deadheads} | {dh['to'] for dh in deadheads}
nx_pts = list(sub_station_ids)
node_colors = ['#e74c3c' if n in dh_endpoints else '#7f8c8d' for n in nx_pts]
node_sizes  = [11 if n in dh_endpoints else 4 for n in nx_pts]
node_labels = [stations_by_id.get(n, {}).get('name', str(n)) for n in nx_pts]
node_text   = [str(n) if n in dh_endpoints else '' for n in nx_pts]

fig.add_trace(go.Scatter(
    x=[pos[n][0] for n in nx_pts],
    y=[pos[n][1] for n in nx_pts],
    mode='markers+text',
    marker=dict(color=node_colors, size=node_sizes, line=dict(color='white', width=0.5)),
    text=node_text,
    textposition='top center',
    textfont=dict(size=8),
    hovertext=node_labels,
    hovertemplate='%{hovertext}<extra></extra>',
    name='Stazioni',
))

# ── layout ────────────────────────────────────────────────────────────────────
fig.update_layout(
    title=dict(
        text=(f"<b>Deadhead subnetwork — S01 / calculateInitialSolution_deadhead</b><br>"
              f"<sub>{len(deadheads)} deadhead legs | {len(drivers)} drivers | "
              f"{len(sub_station_ids)} stazioni | "
              f"solido = percorso SP, tratteggiato = deadhead</sub>"),
        font=dict(size=14),
    ),
    showlegend=True,
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    plot_bgcolor='white',
    hovermode='closest',
    margin=dict(l=20, r=20, t=90, b=20),
    height=800,
)

# ── save & open ───────────────────────────────────────────────────────────────
out_path = os.path.join(ROOT, "output", "deadhead_subnetwork_S01.html")
os.makedirs(os.path.dirname(out_path), exist_ok=True)
fig.write_html(out_path)
print(f"\nSaved → {out_path}")

# Print summary table
print("\n── Deadhead summary ──────────────────────────────────────────────────")
print(f"{'Driver':<12} {'From':>6} {'To':>6} {'Min':>7} {'Matrix':>6} {'Hops':>5}")
print("-" * 48)
for dh in sorted(deadheads, key=lambda d: (d['driver'], d['minutes'])):
    hops = len(dh['path_nodes']) - 1 if dh['path_nodes'] else -1
    print(f"{str(dh['driver']):<12} {dh['from']:>6} {dh['to']:>6} "
          f"{dh['minutes']:>7.1f} {dh['matrix']:>6} {hops:>5}")
