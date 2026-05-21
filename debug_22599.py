"""Debug: trace assign_maintenance_for_loco for loco 22550 with trip 22599"""
import json, os, sys
sys.path.insert(0, '.')
from RollingStockGreedy import (
    load_data, build_index, identify_disrupted_trips,
    build_initial_loco_state, assign_loco_to_trip, assign_maintenance_for_loco,
    compute_conflicts, compute_type_violations, compute_unmaintained_km,
    get_deadhead_info
)

INSTANCE_DIR = "single_type"
instance, network, sp = load_data(
    os.path.join(INSTANCE_DIR, "S01.json"),
    os.path.join(INSTANCE_DIR, "network.json"),
    os.path.join(INSTANCE_DIR, "network-shortestpaths.json"),
)
sections, loco_classes, maint_stations, trips_by_id, locos_by_id = build_index(instance, network)
disrupted = identify_disrupted_trips(instance, sections)
dis_start = instance['disruption_start']
dis_end   = instance['disruption_end']
print(f"dis_start={dis_start}, dis_end={dis_end}")

loco_init, initial_maint_pos = build_initial_loco_state(
    instance, sections, loco_classes, sp, dis_start, dis_end, disrupted,
    [t['id'] for t in instance['train_sections'] if t['id'] not in {t2['id'] for t2 in instance['train_sections'] if t2['arrival_time'] < dis_start} and t['id'] not in disrupted]
)

# Simulate the state just before processing trip 22599
# Loco 22550 has trips [22596, 22561, 22563, 22565, 22567, 22569] assigned
LOCO = 22550
existing_trips = [22596, 22561, 22563, 22565, 22567, 22569]

loco_trips = {}
trip_to_loco = {}
maintenance = {}

for tid in existing_trips:
    assign_loco_to_trip(tid, LOCO, loco_trips, trip_to_loco, trips_by_id)

# Re-run maintenance for the existing trips
assign_maintenance_for_loco(
    LOCO, loco_trips, maintenance, loco_init, initial_maint_pos,
    trips_by_id, locos_by_id, sections, loco_classes, maint_stations, sp
)
print(f"\n--- Before adding 22599 ---")
print(f"loco {LOCO} trips: {loco_trips[LOCO]}")
print(f"maintenance: {maintenance}")

# Print trip details
lc = loco_classes[locos_by_id[LOCO]['class']]
print(f"max_km={lc['max_kilometers_before_maintenance']}, maint_dur={lc['maintenance_duration']}, dh_speed={lc['deadhead_speed']}")
print(f"loco init: {loco_init[LOCO]}")
for tid in loco_trips[LOCO]:
    t = trips_by_id[tid]
    sec = sections[t['section']]
    print(f"  trip {tid}: {sec['origin']}->{sec['destination']}, dep={t['departure_time']}, arr={t['arrival_time']}, dist={sec['distance']}")

# Now add trip 22599
print(f"\n--- Adding 22599 ---")
trip_id = 22599
assign_loco_to_trip(trip_id, LOCO, loco_trips, trip_to_loco, trips_by_id)
print(f"After assign: {loco_trips[LOCO]}")

# Detailed trace of assign_maintenance_for_loco
print(f"\n--- Tracing assign_maintenance_for_loco ---")
trips_seq = loco_trips[LOCO]
loco = locos_by_id[LOCO]
lcc = loco_classes[loco['class']]
max_km = lcc['max_kilometers_before_maintenance']
dh_speed = lcc['deadhead_speed']

this_km = loco_init[LOCO]['km']
print(f"Initial km: {this_km}")

prev_trip_idx = -1
prev_pos = None
maint_result = {}

n = len(trips_seq)
for trip_idx in range(n):
    tid = trips_seq[trip_idx]
    sec = sections[trips_by_id[tid]['section']]

    for pos in (1, 2):
        # Accumulate km
        if prev_trip_idx == -1:
            _, dh_dist = get_deadhead_info(sp, loco_init[LOCO]['station'], sec['origin'], dh_speed)
            km_add = dh_dist if dh_dist != float('inf') else 0.0
            label = f"depot({loco_init[LOCO]['station']})->{sec['origin']}"
        else:
            prev_tid = trips_seq[prev_trip_idx]
            if prev_pos == 1:
                km_add = sections[trips_by_id[prev_tid]['section']]['distance']
                label = f"sec_dist({prev_tid})"
            else:
                prev_dest = sections[trips_by_id[prev_tid]['section']]['destination']
                _, dh_dist = get_deadhead_info(sp, prev_dest, sec['origin'], dh_speed)
                km_add = dh_dist if dh_dist != float('inf') else 0.0
                label = f"dh({prev_dest}->{sec['origin']})"
        this_km += km_add
        print(f"  ({tid},pos={pos}) add {km_add:.2f} [{label}] → this_km={this_km:.2f}")

        # Try initial maintenance
        init_m = initial_maint_pos.get(tid, 0)
        if init_m == pos:
            print(f"    [init maint check pos={pos} for trip {tid}]")

        # Check if km exceeded
        if this_km > max_km:
            print(f"  *** km {this_km:.2f} > max {max_km} → backtrack ***")
            if pos == 2:
                bt_idx, bt_pos = trip_idx, 1
            else:
                bt_idx, bt_pos = trip_idx - 1, 2
            print(f"  Start backtrack at ({bt_idx},{bt_pos}) = trip {trips_seq[bt_idx] if bt_idx>=0 else 'N/A'}")
            # Just show what station each bt position corresponds to
            while True:
                if bt_idx < 0:
                    print(f"  → no maintenance found (bt_idx<0)")
                    break
                bt_tid = trips_seq[bt_idx]
                bt_sec = sections[trips_by_id[bt_tid]['section']]
                station = bt_sec['origin'] if bt_pos == 1 else bt_sec['destination']
                feasible = station in maint_stations and loco['class'] in maint_stations.get(station, set())
                if feasible:
                    # Check time
                    if bt_pos == 1:
                        if bt_idx == 0:
                            prev_s = loco_init[LOCO]['station']
                            prev_a = loco_init[LOCO]['avail_time']
                        else:
                            pt = trips_seq[bt_idx-1]
                            prev_a = trips_by_id[pt]['arrival_time']
                            prev_s = sections[trips_by_id[pt]['section']]['destination']
                        dh_t, _ = get_deadhead_info(sp, prev_s, station, dh_speed)
                        time_ok = (dh_t != float('inf') and prev_a + dh_t + lcc['maintenance_duration'] <= trips_by_id[bt_tid]['departure_time'])
                        print(f"    bt ({bt_tid},pos={bt_pos}): station={station} MAINT_OK, time_ok={time_ok} (prev_arr={prev_a} + dh={dh_t:.0f} + maint={lcc['maintenance_duration']} <= dep={trips_by_id[bt_tid]['departure_time']})")
                        if time_ok:
                            maint_result[bt_tid] = bt_pos
                            this_km = 0.0
                            print(f"    → maintenance placed at ({bt_tid},{bt_pos}), km reset to 0")
                            break
                    else:
                        nt_idx = bt_idx + 1
                        if nt_idx >= n:
                            print(f"    bt ({bt_tid},pos={bt_pos}): station={station} MAINT_OK, last trip → OK")
                            maint_result[bt_tid] = bt_pos
                            this_km = 0.0
                            break
                        nt = trips_seq[nt_idx]
                        nt_orig = sections[trips_by_id[nt]['section']]['origin']
                        dh_t, _ = get_deadhead_info(sp, station, nt_orig, dh_speed)
                        time_ok = (dh_t != float('inf') and trips_by_id[bt_tid]['arrival_time'] + lcc['maintenance_duration'] + dh_t <= trips_by_id[nt]['departure_time'])
                        print(f"    bt ({bt_tid},pos={bt_pos}): station={station} MAINT_OK, time_ok={time_ok} (arr={trips_by_id[bt_tid]['arrival_time']} + maint={lcc['maintenance_duration']} + dh={dh_t:.0f} <= dep={trips_by_id[nt]['departure_time']})")
                        if time_ok:
                            maint_result[bt_tid] = bt_pos
                            this_km = 0.0
                            print(f"    → maintenance placed at ({bt_tid},{bt_pos}), km reset to 0")
                            break
                else:
                    print(f"    bt ({bt_tid},pos={bt_pos}): station={station} NOT maint")

                # Step back
                if bt_pos == 1:
                    bt_idx -= 1
                    bt_pos = 2
                else:
                    bt_pos = 1
                if bt_idx < 0:
                    print(f"  → no maintenance found")
                    break

        prev_trip_idx = trip_idx
        prev_pos = pos

print(f"\nFinal maintenance: {maint_result}")
print(f"Final km: {this_km:.2f}")
print(f"Threshold (max+buffer): {max_km + 200.0}")

# Now check the 3 checks:
assign_maintenance_for_loco(
    LOCO, loco_trips, maintenance, loco_init, initial_maint_pos,
    trips_by_id, locos_by_id, sections, loco_classes, maint_stations, sp
)
print(f"\n--- Full checks after adding 22599 ---")
c = compute_conflicts(loco_trips, maintenance, loco_init, trips_by_id, locos_by_id, sections, loco_classes, sp)
v = compute_type_violations(loco_trips, trips_by_id, locos_by_id)
u = compute_unmaintained_km(loco_trips, maintenance, loco_init, trips_by_id, locos_by_id, sections, loco_classes, sp, 200.0)
print(f"conflicts={c}, type_viol={v}, unmaint_km={u:.2f}")
print(f"maintenance={maintenance}")
