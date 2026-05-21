import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import plotly.graph_objects as go

def plotStepwiseImprovement(functions):
    # Plotting
    plt.figure(figsize=(12, 6))

    for window, iter_count, data in functions:
        if len(data) == 0:
            continue
        # Unpack (x, y)
        x_vals, y_vals = zip(*data)

        # Build a stepwise function: extend each x to the next x, repeat y
        x_plot = []
        y_plot = []
        for i in range(len(data) - 1):
            x_plot += [x_vals[i], x_vals[i + 1]]
            y_plot += [y_vals[i], y_vals[i]]
        # Add the last point
        x_plot.append(x_vals[-1])
        y_plot.append(y_vals[-1])

        plt.plot(x_plot, y_plot, label=f"Win={window}, Iter={iter_count}", drawstyle='steps-post')

    # Styling
    plt.xlabel("Time")
    plt.ylabel("Number uncovered tasks")
    plt.title("Analysis of window-based LNS: Instance 5")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    #plt.show()
    plt.savefig("C://Users//mschlenk//OneDrive - WU Wien//Dokumente//EURO_Conference_Leeds//Images//Stepwise450.png", dpi=300)  # You can change the filename and dpi as needed

def visualizeTasks(tasks):
    print(tasks)
    # Extract task ids and the length of each task (difference between arrival and departure)
    task_ids = [task['id'] for task in tasks.values()]
    task_lengths = [task['arrival'] - task['departure'] for task in tasks.values()]

    # Create figure and axis
    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot the tasks as horizontal bars starting from 0
    for i, task in enumerate(tasks.values()):
        ax.barh(task['id'], task['arrival'] - task['departure'], left=0, height=0.8, color='skyblue')

    # Add a red vertical line at 8 hours (480 minutes)
    ax.axvline(x=480, color='red', linestyle='--', label='8 Hours (480 min)')

    # Labeling the axes and the plot
    ax.set_xlabel('Time (minutes)')
    ax.set_ylabel('Task ID')
    ax.set_title('Task Duration Comparison')

    # Show the legend for the 8-hour line
    ax.legend()

    # Show the plot
    plt.show()


def plot_gantt_chart_locomotives_plotly(duties, id_mapping, unique_locomotives):
    """
    Create a Gantt chart of duties using Plotly.

    Args:
        duties (dict): Mapping duty_id -> list of tasks, each task has 'id', 'departure', 'arrival'
        id_mapping (dict): Mapping task_id -> info dict with 'locomotive'
        unique_locomotives (list): List of locomotive IDs

    Returns:
        fig: Plotly figure
    """

    # Generate colors for locomotives
    from plotly.colors import qualitative
    palette = qualitative.Plotly  # built-in discrete color palette
    color_map = {loco: palette[i % len(palette)] for i, loco in enumerate(unique_locomotives)}

    fig = go.Figure()

    # Iterate over duties and tasks
    for i, (duty_id, tasks) in enumerate(duties.items()):
        for task in tasks:
            loco_id = id_mapping[task['id']]["locomotive"]
            color = color_map.get(loco_id, "gray")

            fig.add_trace(go.Bar(
                x=[task['arrival'] - task['departure']],  # duration
                y=[f"Duty {duty_id}"],
                base=[task['departure']],  # start time
                orientation='h',
                marker_color=color,
                text=str(loco_id),
                textposition='inside',
                insidetextanchor='middle',
                hovertemplate=f"Locomotive: {loco_id}<br>Start: {task['departure']}<br>End: {task['arrival']}<extra></extra>"
            ))

    fig.update_layout(
        barmode='stack',
        xaxis_title="Time (minutes)",
        yaxis_title="Duties",
        yaxis=dict(autorange="reversed"),  # reverse y-axis like matplotlib
        bargap=0.2,
        height=max(400, len(duties) * 30),  # scale height dynamically
        template="plotly_white"
    )

    return fig

def plot_gantt_chart_locomotives(filename, duties, id_mapping, unique_locomotives):
    fig, ax = plt.subplots(figsize=(36, max(18, len(duties) * 0.2)))
    colormap = plt.cm.get_cmap("tab20", len(unique_locomotives))
    locomotive_colors = {loco: colormap(i) for i, loco in enumerate(unique_locomotives)}

    for i, (duty, tasks) in enumerate(duties.items()):
        for task in tasks:
            loco_id = id_mapping[task['id']]["locomotive"]
            color = locomotive_colors.get(loco_id, "gray")  # Default to gray if no match
            bars = [(task['departure'], task['arrival'] - task['departure'])]
            ax.broken_barh(bars, (i - 0.4, 0.8), facecolors=color)

            # Display locomotive ID on the bar with a smaller font size
            mid_time = (task['departure'] + task['arrival']) / 2
            ax.text(mid_time, i, str(loco_id), ha='center', va='center', fontsize=6, color='black', weight='bold')

    ax.set_xlabel("Time (minutes)")
    ax.set_ylabel("Duties")
    ax.set_yticks(range(len(duties)))
    ax.set_yticklabels([f"Duty {d}" for d in duties.keys()], fontsize=6)
    ax.grid(True, linestyle="--", alpha=0.6)
    #plt.title("Gantt Chart of Duties")
    #plt.savefig("Greedy_GantCharts//NEW_GantChart-Greedy-"+filename.replace(".tsv",""), dpi=500, bbox_inches='tight')
    #plt.close()
    #plt.show()
    return fig, ax

def group_nodes_by_duty(nodes):
    duty_groups = {}
    for node in nodes.values():
        if node.duty_id != -1:
            duty_id = id(node.duty_id)  # use id to group by object identity
            if duty_id not in duty_groups:
                duty_groups[duty_id] = []
            duty_groups[duty_id].append(node)
    return duty_groups

def plot_nodes_and_arcs(nodes, arcs):
    duty_groups = group_nodes_by_duty(nodes)
    fig, ax = plt.subplots(figsize=(14, 6))

    Y_SPACING = 1.5

    # --- Middle nodes and global departure order
    all_middle_nodes = [node for node in nodes.values() if node.node_type == 1]
    if not all_middle_nodes:
        print("No middle nodes (type 1) found.")
        return

    # Scale middle node x-position by departure
    departures = [node.node_task["departure"] for node in all_middle_nodes]
    min_dep = min(departures)
    max_dep = max(departures)

    def scale_departure(dep):
        if max_dep == min_dep:
            return 5
        return (dep - min_dep) / (max_dep - min_dep) * 10 + 1

    x_middle_map = {
        node.node_id: scale_departure(node.node_task["departure"])
        for node in all_middle_nodes
    }

    # Unassigned nodes (no duty)
    unassigned_nodes = [node for node in nodes.values() if node.duty_id == -1]

    # --- Node positions
    positions = {}
    y = 0
    for duty_nodes in duty_groups.values():
        start_node = next(n for n in duty_nodes if n.node_type in (2, 3))
        end_node = next(n for n in duty_nodes if n.node_type in (4, 5))
        middle_nodes = [n for n in duty_nodes if n.node_type == 1]

        positions[start_node.node_id] = (0, y)
        positions[end_node.node_id] = (12, y)
        for node in middle_nodes:
            positions[node.node_id] = (x_middle_map[node.node_id], y)

        y -= Y_SPACING

    # Add unassigned nodes in a middle line (e.g. y = 0.5)
    UNASSIGNED_Y = 0.5
    for node in unassigned_nodes:
        dep = node.node_task["departure"]
        x = scale_departure(dep)
        positions[node.node_id] = (x, UNASSIGNED_Y)

    # --- Draw arcs
    arc_styles = {
        1: {"color": "black", "linestyle": "-", "arrowstyle": "->", "alpha": 1.0},
        2: {"color": "gray", "linestyle": "--", "arrowstyle": "->", "alpha": 0.3},
        3: {"color": "darkgreen", "linestyle": "--", "arrowstyle": "->", "alpha": 1.0},
        4: {"color": "darkred", "linestyle": "--", "arrowstyle": "->", "alpha": 1.0},
    }

    for arc in arcs.values():
        if arc.start_node not in positions or arc.end_node not in positions:
            continue  # skip invalid arcs

        x1, y1 = positions[arc.start_node]
        x2, y2 = positions[arc.end_node]

        style = arc_styles.get(arc.arc_type, {"color": "gray", "linestyle": ":", "arrowstyle": "->"})

        ax.annotate(
            "",
            xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle=style["arrowstyle"],
                color=style["color"],
                linestyle=style["linestyle"],
                shrinkA=6, shrinkB=6,
                lw=1.5,
                alpha=style.get("alpha", 1.0)
            )
        )

    # --- Draw nodes
    for node_id, (x, y) in positions.items():
        node = nodes[node_id]

        if node.duty_id == -1:
            color = 'orange'
        else:
            color = {
                2: 'limegreen',
                3: 'darkgreen',
                1: 'blue',
                4: 'orangered',
                5: 'darkred'
            }.get(node.node_type, 'gray')
        ax.plot(x, y, 'o', color=color, markersize=10)
        ax.text(x, y + 0.2, f"{node.node_id}", ha='center')

    ax.axhline(UNASSIGNED_Y, color='orange', linestyle=':', linewidth=1)

    # --- Axis config
    ax.set_yticks([])
    ax.set_xlim(-1, 13)
    ax.set_title("Graph nodes and arcs for selected time window")
    ax.set_xlabel("Departure Time")
    ax.set_xticks([1, 6, 11])
    ax.set_xticklabels([f"{min_dep}", f"{(min_dep + max_dep)//2}", f"{max_dep}"])
    plt.tight_layout()
    plt.show()

def plot_nodes(nodes):
    duty_groups = group_nodes_by_duty(nodes)
    fig, ax = plt.subplots(figsize=(14, 6))

    Y_SPACING = 1.5

    # Extract all middle nodes (type 1)
    all_middle_nodes = [node for node in nodes.values() if node.node_type == 1]

    if not all_middle_nodes:
        print("No middle nodes (type 1) found.")
        return

    # Get min and max departure times
    departures = [node.node_task["departure"] for node in all_middle_nodes]
    min_dep = min(departures)
    max_dep = max(departures)

    # Map node IDs to x positions scaled by departure
    def scale_departure(dep):
        if max_dep == min_dep:
            return 5  # arbitrary fallback if all departures are equal
        return (dep - min_dep) / (max_dep - min_dep) * 10 + 1  # stretch between x=1 and x=11

    x_middle_map = {
        node.node_id: scale_departure(node.node_task["departure"])
        for node in all_middle_nodes
    }

    y = 0
    for duty_nodes in duty_groups.values():
        start_node = next(n for n in duty_nodes if n.node_type == 2 or n.node_type == 3)
        end_node = next(n for n in duty_nodes if n.node_type == 4 or n.node_type == 5)
        middle_nodes = [n for n in duty_nodes if n.node_type == 1]

        positions = {}
        positions[start_node.node_id] = (0, y)
        positions[end_node.node_id] = (12, y)
        for node in middle_nodes:
            x = x_middle_map[node.node_id]
            positions[node.node_id] = (x, y)

        # Draw nodes
        for node in [start_node] + middle_nodes + [end_node]:
            x, y_pos = positions[node.node_id]
            color = {
                2: 'limegreen',
                3: 'darkgreen',
                1: 'blue',
                4: 'orangered',
                5: 'darkred'
            }.get(node.node_type, 'gray')
            ax.plot(x, y_pos, 'o', color=color, markersize=10)
            ax.text(x, y_pos + 0.2, f"{node.node_id}", ha='center')

        # Connect nodes
        ordered_nodes = [start_node] + sorted(middle_nodes, key=lambda n: x_middle_map[n.node_id]) + [end_node]
        for i in range(len(ordered_nodes) - 1):
            x1, y1 = positions[ordered_nodes[i].node_id]
            x2, y2 = positions[ordered_nodes[i+1].node_id]
            ax.plot([x1, x2], [y1, y2], 'k--', linewidth=1)

        y -= Y_SPACING

    # Adjust axis
    ax.set_yticks([])
    ax.set_xlim(-1, 13)
    ax.set_title("Graph nodes for selected time window")
    ax.set_xlabel("Departure time")
    ax.set_xticks([1, 6, 11])
    ax.set_xticklabels([f"{min_dep}", f"{(min_dep + max_dep)//2}", f"{max_dep}"])

    plt.tight_layout()
    plt.show()
