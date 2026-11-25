from __future__ import annotations

import cmd
import os
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from MoveMenu import MoveMenu
from ScheduleManager import ScheduleManager
from ScheduleState import NONE, ScheduleState
from SolutionEvaluator import SolutionEvaluator
from moves import (ChangeDriver, ChangeLoco, CoverTrip, Restore, SwapTasks, UncoverTrip,
                   random_move)
from moves.Move import random_drivers


def _parse_task(state: ScheduleState, token: str) -> int:
    if token.startswith("dh:"):
        _, trip_id, k = token.split(":")
        return -(state.trip_at[int(trip_id)] * state.max_dh + int(k)) - 1
    trip_id = int(token)
    if trip_id not in state.trip_at:
        raise ValueError(f"trip {trip_id} is not in this instance")
    return state.trip_at[trip_id]


def _task_label(state: ScheduleState, task: int) -> str:
    if task >= 0:
        return str(state.trip_order[task])
    j      = -task - 1
    trip   = j // state.max_dh
    k      = j % state.max_dh
    return f"dh:{state.trip_order[trip]}:{k}"


def _driver_label(state: ScheduleState, driver: int) -> str:
    return "NONE" if driver == NONE else str(state.drivers[driver])


def _parse_driver(state: ScheduleState, token: str) -> int:
    if token.upper() == "NONE":
        return NONE
    return state.driver_at[int(token)]


def _parse_loco(state: ScheduleState, token: str) -> int:
    return state.loco_at[int(token)]


def _task_phrase(state, task: int) -> str:
    if task >= 0:
        return f"trip {state.trip_order[task]}"
    j    = -task - 1
    trip = state.trip_order[j // state.max_dh]
    return f"repositioning {j % state.max_dh + 1} before trip {trip}"


def _with_driver(state, task: int) -> str:
    return f"{_task_phrase(state, task)} (driver {_driver_label(state, state.task_driver(task))})"


def _driver_list(state, drivers) -> str:
    return ", ".join(_driver_label(state, d) for d in drivers) or "none"


def _describe(state, move) -> str:
    if isinstance(move, ChangeDriver):
        return (f"move {_task_phrase(state, move.task)} from driver "
                f"{_driver_label(state, move.d_from)} to driver {_driver_label(state, move.d_to)}")
    if isinstance(move, SwapTasks):
        return (f"swap {_with_driver(state, move.task_a)} and "
                f"{_with_driver(state, move.task_b)}")
    if isinstance(move, CoverTrip):
        return (f"cover trip {state.trip_order[move.trip]} with locomotive "
                f"{state.locos[move.loco]}, drivers {_driver_list(state, move.drivers)}")
    if isinstance(move, UncoverTrip):
        return (f"cancel trip {state.trip_order[move.trip]} and free its resources")
    if isinstance(move, ChangeLoco):
        return (f"move trip {state.trip_order[move.trip]} from locomotive "
                f"{state.locos[move.old_loco]} to locomotive {state.locos[move.new_loco]}, "
                f"drivers {_driver_list(state, move.drivers)}")
    if isinstance(move, Restore):
        return f"restore trip {state.trip_order[move.record['trip']]} as it was"
    return str(move)


class MoveShell(cmd.Cmd):
    intro = "MoveShell. 'help' lists the commands, 'quit' exits."
    prompt = "(move) "

    def __init__(self, instance_id: str, state: ScheduleState, manager: ScheduleManager,
                instance, mapper, net, dis_start, dis_end, rng):
        super().__init__()
        self.rng          = rng
        self.instance_id = instance_id
        self.state        = state
        self.manager      = manager
        self.instance      = instance
        self.mapper        = mapper
        self.net           = net
        self.dis_start     = dis_start
        self.dis_end       = dis_end
        self.undo_stack    = []
        self.prompt        = f"({instance_id}) "

    def do_cost(self, arg):
        "cost: print the total cost and every component"
        cost = self.manager.cost_function_components(self.state)
        print(cost)
        for index, component in enumerate(self.manager.components):
            print(f"  {component.name:<26} is_hard={component.is_hard!s:<5} "
                  f"weight={component.weight:<8g} value={cost.all_components[index]:.3f}")

    def do_violations(self, arg):
        "violations: print_violations of every component, next to the validator"
        self.manager.print_violations(self.state)
        print("validator")
        from validator.Validator import validator
        run_info = {"instance_id": self.instance_id}
        solution = self.manager.to_solution(self.state, run_info)
        validator(self.instance, self.mapper, self.net, solution, self.dis_start, self.dis_end)

    def _drivers(self, tokens: list, n: int) -> tuple:
        if not tokens:
            return random_drivers(self.state, self.rng, n)
        return tuple(_parse_driver(self.state, token) for token in tokens)

    def _build(self, kind: str, rest: list):
        state = self.state
        if kind == "cd":
            task, driver = rest
            task = _parse_task(state, task)
            return ChangeDriver(task, state.task_driver(task), _parse_driver(state, driver))
        if kind == "swap":
            task_a, task_b = rest
            return SwapTasks(_parse_task(state, task_a), _parse_task(state, task_b))
        if kind == "cover":
            trip, loco = _parse_task(state, rest[0]), _parse_loco(state, rest[1])
            plan = state.cover_plan(trip, loco)
            n    = 0 if plan is None else len(plan[0]) + 1 + len(plan[2])
            return CoverTrip(trip, loco, self._drivers(rest[2:], n))
        if kind == "uncover":
            trip = _parse_task(state, rest[0])
            plan = None if state.trip_loco[trip] == NONE else state.uncover_plan(trip)
            n    = 0 if plan is None else len(plan[1])
            return UncoverTrip(trip, self._drivers(rest[1:], n))
        if kind == "cl":
            trip, loco = _parse_task(state, rest[0]), _parse_loco(state, rest[1])
            move  = ChangeLoco(trip, state.trip_loco[trip], loco, ())
            plans = None if state.trip_loco[trip] == NONE else move.plans(state)
            n     = 0 if plans is None else (len(plans[0][1]) + len(plans[1][0])
                                             + len(plans[1][2]))
            return ChangeLoco(trip, state.trip_loco[trip], loco, self._drivers(rest[2:], n))
        if kind == "random":
            move = random_move(state, self.rng)
            if move is None:
                raise ValueError("no move available on this state")
            return move
        raise ValueError(f"unknown move: {kind}")

    def _print_delta(self, before, after):
        change = after - before
        print(f"move cost: total={change.total:+.1f} violations={change.violations:+.1f} "
              f"objective={change.objective:+.1f}")
        for index, component in enumerate(self.manager.components):
            value = change.all_components[index]
            if value == 0.0:
                continue
            print(f"  {component.name:<26} is_hard={component.is_hard!s:<5} "
                  f"{before.all_components[index]:.3f} to {after.all_components[index]:.3f} "
                  f"({value:+.3f})")
        print(f"schedule cost: {after}")

    def do_apply(self, arg):
        "apply cd <task> <driver> | swap <task> <task> | cover <trip> <loco> [driver ...] | " \
        "uncover <trip> [driver ...] | cl <trip> <loco> [driver ...] | random  "\
        "(random drivers if omitted)"
        parts = shlex.split(arg)
        if not parts:
            print("a move is required: cd, swap, cover, uncover, cl")
            return
        try:
            move = self._build(parts[0], parts[1:])
        except (ValueError, KeyError, IndexError) as exc:
            print(f"error: {exc}")
            return
        if not move.feasible(self.state):
            print(f"move is not structurally admissible: {_describe(self.state, move)}")
            return
        description = _describe(self.state, move)
        before      = self.manager.cost_function_components(self.state)
        self.undo_stack.append(move.make_move(self.state))
        print(f"applied: {description}")
        self._print_delta(before, self.manager.cost_function_components(self.state))

    def do_delta(self, arg):
        "delta cd|swap|cover|uncover|cl|random [args]: cost of a move without keeping it applied"
        parts = shlex.split(arg)
        if not parts:
            print("a move is required: cd, swap, cover, uncover, cl, random")
            return
        try:
            move = self._build(parts[0], parts[1:])
        except (ValueError, KeyError, IndexError) as exc:
            print(f"error: {exc}")
            return
        if not move.feasible(self.state):
            print(f"move is not structurally admissible: {_describe(self.state, move)}")
            return
        description = _describe(self.state, move)
        before      = self.manager.cost_function_components(self.state)
        inverse     = move.make_move(self.state)
        after       = self.manager.cost_function_components(self.state)
        inverse.make_move(self.state)
        print(f"evaluated: {description}")
        self._print_delta(before, after)
        print(f"state left unchanged, cost back to {self.manager.cost_function_components(self.state)}")

    def _delta_manager(self):
        from DeltaManager import DeltaManager
        if getattr(self, "deltas", None) is None:
            self.deltas = DeltaManager.default(SolutionEvaluator(self.mapper, self.net))
        self.deltas.realign(self.state)
        return self.deltas

    def do_evaluate(self, arg):
        "evaluate cd|swap|cover|uncover|cl|random [args]: delta of a move with the state held still"
        parts = shlex.split(arg)
        if not parts:
            print("a move is required: cd, swap, cover, uncover, cl, random")
            return
        try:
            move = self._build(parts[0], parts[1:])
        except (ValueError, KeyError, IndexError) as exc:
            print(f"error: {exc}")
            return
        if not move.feasible(self.state):
            print(f"move is not structurally admissible: {_describe(self.state, move)}")
            return
        from deltas import candidate_duties
        manager = self._delta_manager()
        by_hand = candidate_duties(self.state, move) is not None
        delta   = manager.evaluate(self.state, move)
        print(f"evaluated: {_describe(self.state, move)}")
        print(f"  {'touched duties' if by_hand else 'apply and undo'}: "
              f"total={delta.total:+.3f} violations={delta.violations:+.3f} "
              f"objective={delta.objective:+.3f}")
        for index, component in enumerate(manager.components):
            value = delta.all_components[index]
            if value != 0.0:
                print(f"  {component.name:<26} {value:+.3f}")

    def do_deltas(self, arg):
        "deltas [n]: on n random moves compare evaluate with the full recomputation"
        rounds  = int(arg) if arg.strip() else 50
        from DeltaTests import check_deltas
        manager = self._delta_manager()
        problems, kinds, by_hand = check_deltas(self.state, manager, self.rng, rounds)
        print(f"{rounds} moves {kinds}: {by_hand} by touched duties, "
              f"{rounds - by_hand} by apply and undo")
        for problem in problems[:10]:
            print(f"  MISMATCH {problem}")
        if not problems:
            print("  every delta matches the full recomputation within 1e-6")

    def do_undo(self, arg):
        "undo: revert the last applied move"
        if not self.undo_stack:
            print("nothing to undo")
            return
        inverse     = self.undo_stack.pop()
        description = _describe(self.state, inverse)
        before      = self.manager.cost_function_components(self.state)
        inverse.make_move(self.state)
        print(f"reverted with: {description}")
        self._print_delta(before, self.manager.cost_function_components(self.state))

    def do_neighbors(self, arg):
        "neighbors <trip|dh:trip:k> [radius_km]: driver candidates, each with its full cost"
        parts = shlex.split(arg)
        if not parts:
            print("a task is required")
            return
        task      = _parse_task(self.state, parts[0])
        radius_km = float(parts[1]) if len(parts) > 1 else 50.0
        current   = self.state.task_driver(task)
        base       = self.manager.cost_function_components(self.state)
        print(f"task {_task_label(self.state, task)}: current driver "
              f"{_driver_label(self.state, current)}, base cost {base}")
        for driver in self.state.near_drivers(task, radius_km):
            move = ChangeDriver(task, current, driver)
            if not move.feasible(self.state):
                continue
            inverse   = move.make_move(self.state)
            candidate = self.manager.cost_function_components(self.state)
            inverse.make_move(self.state)
            print(f"  driver {self.state.drivers[driver]:<8} "
                  f"cost {candidate}  delta={candidate.total - base.total:+.3f}")

    def do_duty(self, arg):
        "duty <driver>: the tasks of the duty and its aggregates"
        (token,) = shlex.split(arg)
        driver = _parse_driver(self.state, token)
        if driver == NONE:
            print("a real driver is required")
            return
        for task in self.state.duty_tasks_list[driver]:
            print(f"  {_task_label(self.state, task):<12} "
                  f"{self.state.task_origin(task)}->{self.state.task_dest(task)} "
                  f"[{self.state.task_dep(task):.1f}, {self.state.task_arr(task):.1f}]")
        print(f"len={self.state.duty_len[driver]:.1f} "
              f"dh_m={self.state.duty_dh_m[driver]:.1f} "
              f"req_break={self.state.duty_req_break[driver]} "
              f"break_short={self.state.duty_break_short[driver]:.1f} "
              f"back_home={self.state.duty_back_home[driver]:.1f} "
              f"continuity={self.state.duty_continuity[driver]:.1f} "
              f"unreachable={self.state.duty_unreachable[driver]} "
              f"excess={self.state.duty_excess[driver]:.1f}")

    def do_check(self, arg):
        "check: check_consistency() of the manager"
        problems = self.manager.check_consistency(self.state)
        if problems:
            for p in problems:
                print(f"  PROBLEM: {p}")
        else:
            print("check_consistency: ok")

    def do_dump(self, arg):
        "dump: summary of the state and of the cost"
        cost = self.manager.cost_function_components(self.state)
        print(f"instance={self.instance_id}  trips={len(self.state.trip_order)} "
              f"locos={len(self.state.locos)} drivers={len(self.state.drivers)} "
              f"canceled={self.state.n_canceled}")
        print(cost)

    def do_export(self, arg):
        "export <path.json>: save the current Solution (to_solution) to a file"
        (path,) = shlex.split(arg)
        run_info = {"instance_id": self.instance_id}
        self.manager.to_solution(self.state, run_info).save(path)
        print(f"saved: {path}")

    def do_quit(self, arg):
        "quit: leave the shell"
        return True

    do_EOF = do_quit


if __name__ == "__main__":
    import argparse

    import RunConfig
    from rescheduling import IntegratedRescheduling as IR
    from rescheduling.LocoChecker import LocoChecker

    parser = argparse.ArgumentParser(description="Move shell, the equivalent of the MoveTester.")
    parser.add_argument("-i", "--instance", required=True)
    parser.add_argument("-seed", type=int, default=42)
    RunConfig.add_path_args(parser)
    args = parser.parse_args()

    RunConfig.resolve(args, parser).apply_to(IR)

    instance, mapper, net, dis_start, dis_end = IR.setup_instance(args.instance)
    result       = IR.solve_instance(instance, mapper, net, dis_start, dis_end, args.seed)
    loco_checker = LocoChecker(instance, net)
    state        = ScheduleState.from_solve_result(result, mapper, net, loco_checker=loco_checker)
    manager      = ScheduleManager.default(SolutionEvaluator(mapper, net))

    from rescheduling.RollingStockGreedy import CppMT19937

    shell = MoveShell(args.instance, state, manager, instance, mapper, net, dis_start, dis_end,
                      CppMT19937(args.seed))
    if sys.stdin.isatty():
        MoveMenu(shell).loop()
    else:
        shell.cmdloop()
