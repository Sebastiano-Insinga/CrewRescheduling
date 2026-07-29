# VNS — Note di design

- [VNS_design.md](VNS_design.md) — architettura VNS: setup/solve, `SolveResult`, `all_candidates`, forced assignment, invariante di stato, `SolutionEvaluator`, `VNSRescheduler`.
- [SwapStrategies_design.md](SwapStrategies_design.md) — strategy pattern per lo shaking (`swap`): contratto delle strategie, selezione per nome da CLI, strategie implementate.
- [VNS_implementation_plan.md](VNS_implementation_plan.md) — piano di implementazione a stage del loop BVNS completo (`VNSController`): forced assignment generalizzato a k trip, objective come componente isolato, ciclo shake/accept con reset e escalation di k.
- [VNS_BVNS_implementation.md](VNS_BVNS_implementation.md) — traccia operativa derivata dal piano, allineata al codice attuale: stage 1-4 con file e righe da toccare, decisioni prese (refactor di `run_loop` in place, `select_k`, pesi da CLI) e checklist di verifica manuale.
- [VNS_research_brief.md](VNS_research_brief.md) — prompt di ricerca per posizionare il metodo in letteratura: definizione del problema, stato del codice, domande aperte (vicinato strutturato, swap vs ruin-and-recreate nei problemi integrati loco+crew, feasibility incrementale).
- [piano_operativo_VNS_2026-07-24.md](piano_operativo_VNS_2026-07-24.md) — piano di sviluppo derivato dalla rassegna di letteratura (24/07/2026): ridisegno del vicinato su grafo di accoppiamento, accettazione con peggioramenti, protocollo di valutazione multi-seed, scaling via VNDS.
- [VNS_decisioni_design.md](VNS_decisioni_design.md) — registro incrementale delle decisioni di design (ADR): scelte prese durante l'implementazione con contesto, motivo e stato. Attualmente: `select_random_k` (DD-1), campionamento a finestre temporali (DD-2), accumulo del forced
ed esclusione dal pool (DD-3).
