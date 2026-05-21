# Perché MRV non funziona come greedy per il crew rescheduling

## Idea originale

MRV (Minimum Remaining Values) è un'euristica classica per i problemi di **Constraint Satisfaction (CSP)**:
assegna prima la variabile con meno valori legali rimasti (la più vincolata), riducendo il rischio di
creare conflitti irrisolvibili nelle assegnazioni successive.

Esempi canonici: N-Queens, graph coloring, Sudoku.

---

## Perché MRV funziona nei CSP classici

Nei CSP classici le assegnazioni sono **indipendenti**: assegnare un valore a variabile X cambia il
dominio di Y, ma non cambia la struttura temporale del problema. Si può calcolare il numero di valori
rimasti per ogni variabile e usarlo come guida globale.

---

## Struttura del problema di crew rescheduling

Nel crew rescheduling ogni driver costruisce una **catena sequenziale** di task:

```
D1: T1(A→B, dep=10, arr=50) → T2(B→C, dep=60, arr=100) → T3(C→D, dep=110, arr=200)
```

Le assegnazioni sono **temporalmente dipendenti**:
- assegnare T1 a D1 cambia lo stato di D1 (stazione corrente = B, tempo corrente = 50)
- solo dopo T1, D1 diventa eligible per T2
- T2 non è mai eligible per D1 all'inizio (D1 parte da A, non da B)

---

## Il problema concreto di MRV applicato qui

### Esempio numerico

**Stato iniziale:**
- D1: stazione A, t=0
- D2: stazione A, t=0

**Task:**
- T1: A→B, dep=10, arr=50
- T2: B→C, dep=60, arr=100
- T3: A→D, dep=15, arr=200

**Conteggio eligible all'inizio:**

| Task | Eligible | Count |
|------|----------|-------|
| T1   | D1, D2   | 2     |
| T2   | nessuno (nessun driver è a B) | **0** ← MRV seleziona |
| T3   | D1, D2   | 2     |

MRV sceglie T2 (count=0) → nessun driver eligible → **T2 uncovered**.

Poi assegna T1 a D1 → D1 si sposta a B, t=50. D1 **avrebbe potuto** prendere T2 dopo T1,
ma MRV ha già scartato T2.

**Greedy originale:**
D1 prende T1 → loop interno trova T2 feasible → D1 prende T2. D2 prende T3. **0 uncovered.**

---

## Root cause

MRV valuta i constraint in un **singolo snapshot temporale**. Non considera che:

1. Lo stato dei driver cambia dopo ogni assegnazione
2. Task con count=0 ora possono diventare feasibili dopo che un driver completa un task precedente
3. Le catene sequential sono la struttura naturale del problema: un driver deve prima essere
   al posto giusto nel momento giusto

Il re-ranking dinamico (ricalcolo dopo ogni assegnazione) non risolve il problema: T2 viene
scartato nell'iterazione 1 **prima** che D1 si sposti a B.

---

## Confronto con il greedy originale

| Aspetto | Greedy originale (driver-first) | MRV (task-first) |
|---------|--------------------------------|------------------|
| Loop esterno | per ogni driver | per ogni task (ordinato per count) |
| Loop interno | estende la catena del driver finché possibile | assegna un task, ricomincia |
| Chain building | naturale (inner while loop) | assente |
| Task con count=0 | vengono scoperti dopo che il driver si sposta | scartati immediatamente |
| Adatto a | problemi con catene temporali | CSP con decisioni indipendenti |

---

## Variante ibrida (MRV + chain extension): perché non aiuta

Una variante ibrida selezionerebbe il task più vincolato con MRV, poi estenderebbe la catena del
driver assegnato con il greedy interno. Il risultato:

- MRV agisce solo una volta per catena (all'inizio), non dopo ogni singola assegnazione
- Il benefit principale di MRV (re-valutare i constraint ad ogni step) viene perso
- In pratica equivale al greedy originale con un diverso criterio di ordinamento dei driver

---

## Conclusione

MRV è mal adatto al crew rescheduling perché il problema ha **dipendenze temporali sequenziali**,
non assegnazioni indipendenti. Il greedy driver-first con chain building è strutturalmente più
adatto: costruisce catene naturali sfruttando il fatto che un driver che completa T_k è
automaticamente eligible per T_{k+1} se T_{k+1} parte dalla stazione di arrivo di T_k.

Miglioramenti al greedy iniziale hanno più senso nell'**ordinamento dei driver** (es. slack-based
come in `calculateInitialSolution_slack`), non nell'ordinamento dei task.
