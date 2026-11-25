from __future__ import annotations

MAIN = (
    ("Move menu", "move"),
    ("State menu", "state"),
    ("Cost menu", "cost"),
    ("Command shell", "shell"),
)

MOVE_ITEMS = (
    ("ChangeDriver", "cd", ("task", "new driver")),
    ("SwapTasks", "swap", ("first task", "second task")),
    ("CoverTrip", "cover", ("canceled trip", "locomotive", "drivers (empty for random)")),
    ("UncoverTrip", "uncover", ("covered trip", "drivers (empty for random)")),
    ("ChangeLoco", "cl", ("trip", "new locomotive", "drivers (empty for random)")),
)


class MoveMenu:
    def __init__(self, shell):
        self.shell = shell

    def loop(self):
        while True:
            self._show("MAIN MENU", [name for name, _ in MAIN], exit_label="Exit")
            choice = self._read()
            if choice is None or choice == "0":
                return
            page = self._page(MAIN, choice)
            if page == "move":
                self._move_menu()
            elif page == "state":
                self._state_menu()
            elif page == "cost":
                self._cost_menu()
            elif page == "shell":
                self.shell.cmdloop()
            else:
                print("no such entry")

    def _move_menu(self):
        while True:
            labels = [name for name, _, _ in MOVE_ITEMS] + ["Random move", "Undo last move"]
            self._show("MOVE MENU", labels)
            choice = self._read()
            if choice is None or choice == "0":
                return
            if choice == str(len(MOVE_ITEMS) + 1):
                self.shell.do_apply("random")
                continue
            if choice == str(len(MOVE_ITEMS) + 2):
                self.shell.do_undo("")
                continue
            try:
                name, kind, prompts = MOVE_ITEMS[int(choice) - 1]
            except (ValueError, IndexError):
                print("no such entry")
                continue
            args = []
            for prompt in prompts:
                value = self._read(f"{prompt}: ")
                if value is None:
                    return
                args.extend(value.split())
            self.shell.do_apply(" ".join([kind] + args))
            self.shell.do_cost("")

    def _state_menu(self):
        while True:
            self._show("STATE MENU", ["Summary", "Duty of one driver", "Consistency check",
                                      "Export the solution"])
            choice = self._read()
            if choice is None or choice == "0":
                return
            if choice == "1":
                self.shell.do_dump("")
            elif choice == "2":
                driver = self._read("driver: ")
                if driver is None:
                    return
                self.shell.do_duty(driver)
            elif choice == "3":
                self.shell.do_check("")
            elif choice == "4":
                path = self._read("file: ")
                if path is None:
                    return
                self.shell.do_export(path)
            else:
                print("no such entry")

    def _cost_menu(self):
        while True:
            self._show("COST MENU", ["Cost by component", "Violations against the validator",
                                     "Neighborhood of one task",
                                     "Deltas against the full recomputation"])
            choice = self._read()
            if choice is None or choice == "0":
                return
            if choice == "1":
                self.shell.do_cost("")
            elif choice == "2":
                self.shell.do_violations("")
            elif choice == "3":
                arg = self._read("task [radius km]: ")
                if arg is None:
                    return
                self.shell.do_neighbors(arg)
            elif choice == "4":
                arg = self._read("moves [50]: ")
                if arg is None:
                    return
                self.shell.do_deltas(arg)
            else:
                print("no such entry")

    def _page(self, items, choice):
        try:
            return items[int(choice) - 1][1]
        except (ValueError, IndexError):
            return None

    def _show(self, title, labels, exit_label="Back"):
        print(f"\n{title}:")
        for index, label in enumerate(labels, start=1):
            print(f"   ({index}) {label}")
        print(f"   (0) {exit_label}")

    def _read(self, prompt="choice: "):
        try:
            return input(prompt).strip()
        except EOFError:
            print()
            return None
