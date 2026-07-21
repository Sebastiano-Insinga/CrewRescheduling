# VNS — Note di design

- [VNS_design.md](VNS_design.md) — architettura VNS: setup/solve, `SolveResult`, `all_candidates`, forced assignment, invariante di stato, `SolutionEvaluator`, `VNSRescheduler`.
- [SwapStrategies_design.md](SwapStrategies_design.md) — strategy pattern per lo shaking (`swap`): contratto delle strategie, selezione per nome da CLI, strategie implementate.
- [VNS_implementation_plan.md](VNS_implementation_plan.md) — piano di implementazione a stage del loop BVNS completo (`VNSController`): forced assignment generalizzato a k trip, objective come componente isolato, ciclo shake/accept con reset e escalation di k.
- [VNS_BVNS_implementation.md](VNS_BVNS_implementation.md) — traccia operativa derivata dal piano, allineata al codice attuale: stage 1-4 con file e righe da toccare, decisioni prese (refactor di `run_loop` in place, `select_k`, pesi da CLI) e checklist di verifica manuale.
