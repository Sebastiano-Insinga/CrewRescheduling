import plotly.graph_objects as go
from plotly.colors import qualitative


def plot_loco_crew_gantt(loco_duties: dict, title: str = "Loco-Crew Assignment",
                         output_html: str = "loco_crew_gantt.html",
                         metrics: dict = None,
                         xaxis: str = 'index',
                         disruption_start_min: int = 0,
                         canceled: list = None,
                         canceled_per_trip: bool = False) -> go.Figure:
    all_drivers = sorted({
        driver_id
        for segments in loco_duties.values()
        for _, driver_id in segments
    })
    palette = qualitative.Plotly + qualitative.D3 + qualitative.G10
    color_map = {d: palette[i % len(palette)] for i, d in enumerate(all_drivers)}

    canceled = canceled or []
    if canceled_per_trip:
        canc_rows = [[ct] for ct in sorted(canceled, key=lambda t: t.get('departure', 0))]
        canc_row_names = [f"CANC {row[0].get('rs_trip_id')}" for row in canc_rows]
    else:
        # Greedy interval packing: minimum pseudo-rows with no overlapping bars
        canc_rows = []  # list of lists of task dicts
        for ct in sorted(canceled, key=lambda t: t.get('departure', 0)):
            for row in canc_rows:
                if row[-1].get('arrival', 0) <= ct.get('departure', 0):
                    row.append(ct)
                    break
            else:
                canc_rows.append([ct])
        canc_row_names = [f"CANC-{i + 1}" for i in range(len(canc_rows))]

    if xaxis == 'station':
        all_origins = sorted({
            task.get('origin')
            for segs in loco_duties.values()
            for task, _ in segs
            if task.get('origin') is not None
        } | {
            ct.get('origin') for ct in canceled
            if ct.get('origin') is not None
        })
        station_pos = {s: i for i, s in enumerate(all_origins)}
        xaxis_layout = dict(
            title="Origin station",
            tickmode='array',
            tickvals=list(range(len(all_origins))),
            ticktext=[str(s) for s in all_origins],
        )
    elif xaxis == 'time':
        station_pos = None
        _all_arrivals = [task.get('arrival', disruption_start_min)
                         for segs in loco_duties.values() for task, _ in segs]
        _all_arrivals += [ct.get('arrival', disruption_start_min) for ct in canceled]
        t_max = max(_all_arrivals) * 1.02 if _all_arrivals else disruption_start_min + 7200
        xaxis_layout = dict(title="Minutes (absolute)",
                            range=[disruption_start_min, t_max])
    else:
        station_pos = None
        xaxis_layout = dict(title="Task sequence", tickmode='linear', tick0=0, dtick=1)

    locos = sorted(loco_duties.keys())
    seen_drivers = set()
    traces = []

    for loco_id in locos:
        segments = loco_duties[loco_id]
        for seq_idx, (task, driver_id) in enumerate(segments):
            dep = task.get('departure', 0)
            arr = task.get('arrival',   dep)
            if xaxis == 'time':
                bar_base  = dep
                bar_width = max(arr - dep, 1)
            elif station_pos is not None:
                bar_base  = station_pos[task.get('origin')]
                bar_width = 1
            else:
                bar_base  = seq_idx
                bar_width = 1

            color = color_map[driver_id]
            first_occurrence = driver_id not in seen_drivers
            seen_drivers.add(driver_id)

            task_type = task.get('type', '')
            is_deadhead = task_type == 'loco_deadhead'
            rs_trip_id = task.get('rs_trip_id')
            origin = task.get('origin', '?')
            dest   = task.get('destination', '?')
            trip_line = f"Trip: {rs_trip_id}<br>" if rs_trip_id is not None else ""
            hover  = (
                f"{trip_line}"
                f"Driver: {driver_id}<br>"
                f"Type: {task_type}<br>"
                f"{origin} → {dest}<br>"
                f"Dep: {dep} min | Arr: {arr}"
            )

            traces.append(go.Bar(
                orientation='h',
                x=[bar_width],
                y=[str(loco_id)],
                base=bar_base,
                marker=dict(
                    color=color,
                    line=dict(color='black', width=1.5) if is_deadhead else dict(width=0),
                    pattern_shape='/' if is_deadhead else '',
                ),
                name=str(driver_id),
                legendgroup=str(driver_id),
                showlegend=first_occurrence,
                hovertemplate=hover + "<extra></extra>",
                text=str(rs_trip_id) if rs_trip_id is not None else None,
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(size=9),
                width=0.6,
            ))

    canc_legend_shown = False
    for row_name, row_tasks in zip(canc_row_names, canc_rows):
        for seq_idx, task in enumerate(row_tasks):
            dep = task.get('departure', 0)
            arr = task.get('arrival',   dep)
            if xaxis == 'time':
                bar_base  = dep
                bar_width = max(arr - dep, 1)
            elif station_pos is not None:
                bar_base  = station_pos[task.get('origin')]
                bar_width = 1
            else:
                bar_base  = seq_idx
                bar_width = 1

            rs_trip_id = task.get('rs_trip_id')
            origin = task.get('origin', '?')
            dest   = task.get('destination', '?')
            stats  = task.get('cancel_stats') or {}
            stats_line = (
                f"Loco candidates: {stats.get('n_candidates', '?')}, "
                f"no driver chain: {stats.get('no_chain', '?')}"
            )
            hover = (
                f"Trip: {rs_trip_id} (CANCELED)<br>"
                f"{origin} → {dest}<br>"
                f"Dep: {dep} | Arr: {arr} <br>"
                f"{stats_line}"
            )

            traces.append(go.Bar(
                orientation='h',
                x=[bar_width],
                y=[row_name],
                base=bar_base,
                marker=dict(
                    color='#d62728',
                    line=dict(width=0),
                    pattern_shape='x',
                ),
                name='Canceled',
                legendgroup='canceled',
                showlegend=not canc_legend_shown,
                hovertemplate=hover + "<extra></extra>",
                text=str(rs_trip_id) if rs_trip_id is not None else None,
                textposition='inside',
                insidetextanchor='middle',
                textfont=dict(size=9),
                width=0.6,
            ))
            canc_legend_shown = True

    if metrics:
        d_start = metrics.get('disruption_start_min', '')
        d_end   = metrics.get('disruption_end_min', '')
        disrup  = f" | Disruption: {d_start}–{d_end} min" if d_start != '' else ""
        parts = [
            f"Trips: {metrics['total_trips']}",
            f"Canceled: {metrics['cancellations']}",
        ]
        if 'loco_dh_m' in metrics:
            parts.append(f"Loco DH: {metrics['loco_dh_m']:,.0f} m")
        if 'crew_dh_m' in metrics:
            parts.append(f"Crew DH: {metrics['crew_dh_m']:,.0f} m")
        if 'compute_time_sec' in metrics:
            parts.append(f"Compute time: {metrics['compute_time_sec']:.1f}s")
        if 'obj_value' in metrics:
            parts.append(f"Obj: {metrics['obj_value']:.2f}")
        subtitle = " | ".join(parts) + disrup
        display_title = f"{title}<br><sup>{subtitle}</sup>"
    else:
        display_title = title

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=display_title,
        barmode='overlay',
        xaxis=xaxis_layout,
        yaxis=dict(title="Locomotive", autorange='reversed',
                   categoryorder='array',
                   categoryarray=[str(l) for l in locos] + canc_row_names),
        legend=dict(title="Driver"),
        height=max(400, 40 * (len(locos) + len(canc_rows)) + 150),
    )

    if output_html:
        fig.write_html(output_html)
        print(f"[LocoCrewViz] saved {output_html}")

    fig.show()
    return fig
