from ReadSolution_Twan import readSolution_Twan_txt_Format
from ReschedulingPreprocessor import generateReschedulingInput
from IDMappingReader import readIDMapping


class DriverStatusMapper:
    """
    Loads the original crew schedule and produces driver_status, original_schedule,
    and id_mapping needed by the rescheduling algorithms.

    Corresponds to Step 2 of SequentialRescheduling.run_instance().

    Usage:
        mapper = DriverStatusMapper(crew_schedule_file, crew_task_file,
                                    id_mapping_file, instance_file)
        # all properties available immediately after construction
    """

    def __init__(self,
                 crew_schedule_file: str,
                 crew_task_file: str,
                 id_mapping_file: str,
                 instance_file: str):

        self._id_mapping: dict = readIDMapping(id_mapping_file)

        original_schedule, duty_breaks_orig = readSolution_Twan_txt_Format(
            crew_schedule_file, crew_task_file
        )
        self._original_schedule:   dict = original_schedule
        self._duty_breaks_original: dict = duty_breaks_orig

        driver_status, _, _ = generateReschedulingInput(
            original_schedule, duty_breaks_orig, instance_file, self._id_mapping
        )
        self._driver_status: dict = driver_status

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def driver_status(self) -> dict:
        """
        {duty_id: {available_from_station, available_at_time, duty_length,
                   break30done, break45done}}
        """
        return self._driver_status

    @property
    def original_schedule(self) -> dict:
        """Pre-disruption crew schedule: {duty_id: list[task]}."""
        return self._original_schedule

    @property
    def id_mapping(self) -> dict:
        """Task ID → metadata dict (loco, section, trip, ...)."""
        return self._id_mapping

    @property
    def duty_breaks_original(self) -> dict:
        """Pre-disruption break assignments: {duty_id: (start, end)}."""
        return self._duty_breaks_original
