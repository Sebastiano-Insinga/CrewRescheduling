def walk(state, driver: int):
    tasks = state.duty_tasks_list[driver]
    if not tasks:
        return
    status   = state.mapper.driver_status[state.drivers[driver]]
    position = status["available_from_station"]
    ready    = status["available_at_time"]
    for index, task in enumerate(tasks):
        origin    = state.task_origin(task)
        departure = state.task_dep(task)
        if position == origin:
            start, arrival = ready, ready
            dh_metres      = 0
        else:
            dh_metres      = state._sp_metres(position, origin)
            start, arrival = state.crew_arrival(position, ready, origin, departure)
        dh_minutes = float("inf") if arrival == float("inf") else arrival - start
        gap        = None if arrival == float("inf") else departure - arrival
        yield index, task, position, start, origin, departure, dh_minutes, dh_metres, gap
        position = state.task_dest(task)
        ready    = state.task_arr(task)
