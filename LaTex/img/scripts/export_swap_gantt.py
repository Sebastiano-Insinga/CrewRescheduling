import sys, os, argparse
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "VNS/scripts"))
import plotly.graph_objects as go
go.Figure.show = lambda self, *a, **k: None
from rescheduling import IntegratedRescheduling as IR
import RunConfig
from VNS.scripts.VNSRescheduler import VNSRescheduler
from VNS.scripts.SwapStrategies import SwapStrategies
from viz.LocoCrewViz import plot_loco_crew_gantt

iid, out_dir = sys.argv[1], sys.argv[2]
os.makedirs(out_dir, exist_ok=True)
p = argparse.ArgumentParser(); RunConfig.add_path_args(p)
RunConfig.resolve(p.parse_args(['--chain', 'java/cap180', '--instance-dir',
                  'Instances/single_type/validation/single_type']), p).apply_to(IR)

vns = VNSRescheduler(iid, seed=42)
after = vns.run_once(SwapStrategies.swap_first_in_time, export_gantt=False)
before, obj_before = vns.current_result, vns.current_obj
obj_after = vns._evaluate(after)
forced = SwapStrategies.swap_first_in_time(before.all_candidates, vns.instance['train_sections'])
tid, pair = next(iter(forced.items()))

def loco_of(r):
    return next(l for l, segs in r.loco_duties.items() if any(t.get('rs_trip_id') == tid for t, _ in segs))
changed = sorted(l for l in set(before.loco_duties) | set(after.loco_duties)
                 if before.loco_duties.get(l) != after.loco_duties.get(l))
xs = [t[k] for r, o in ((before, after), (after, before)) for l in changed
      for t, d in r.loco_duties.get(l, []) if (t, d) not in o.loco_duties.get(l, []) for k in ('departure', 'arrival')]
lo, hi = min(xs) - 150, max(xs) + 150
print(f"forced trip {tid}: loco {loco_of(before)} -> {loco_of(after)} (pair loco {pair['loco']}), changed locos {changed}")
print(f"objective {obj_before:.1f} -> {obj_after:.1f}, cancelled {len(before.canceled_tasks)} -> {len(after.canceled_tasks)}")
print(f"crew DH {before.dh_stats['crew_dh_m']} -> {after.dh_stats['crew_dh_m']}, loco DH {before.dh_stats['loco_dh_m']} -> {after.dh_stats['loco_dh_m']}")
print(f"zoom {lo:.0f}-{hi:.0f}, disruption {vns.dis_start}-{vns.dis_end}")

for r, obj, tag, label in ((before, obj_before, 'before', 'Before swap'), (after, obj_after, 'after', 'After swap')):
    fig = plot_loco_crew_gantt(
        r.loco_duties, title=f"{label} [{iid}], trip {tid} forced", output_html=None,
        metrics={'total_trips': len(r.solution), 'cancellations': len(r.canceled_tasks),
                 'loco_dh_m': r.dh_stats['loco_dh_m'], 'crew_dh_m': r.dh_stats['crew_dh_m'],
                 'disruption_start_min': vns.dis_start, 'disruption_end_min': vns.dis_end,
                 'obj_value': obj},
        xaxis='time', disruption_start_min=vns.dis_start, canceled=r.canceled_tasks)
    fig.update_xaxes(range=[lo, hi])
    path = os.path.join(out_dir, f"sls_gantt_{iid}_cap180_{tag}_swap_trip{tid}.png")
    fig.write_image(path, width=1800, height=fig.layout.height, scale=2)
    print(path)
