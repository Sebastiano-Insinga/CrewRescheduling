# Research brief: VNS state-of-the-art per Crew/Loco Rescheduling ferroviario

> Prompt di ricerca per posizionare il lavoro descritto in [VNS_BVNS_implementation.md](VNS_BVNS_implementation.md)
> all'interno della letteratura VNS. **Aggiornato allo stato attuale del codice** (Stage 1-3b
> implementati): le domande aperte qui sotto sono quelle che restano davvero aperte, non quelle già
> risolte.

---

## 1. Il problema

**Railway crew and locomotive rescheduling after a disruption.**

Dato un piano operativo giornaliero già costruito (assegnazione di locomotive e turni dei
macchinisti a un insieme di corse) e una **disruption** che ne invalida una parte — una tratta
interrotta in una finestra temporale nota `[disruption_start, disruption_end]` — si vuole ricostruire
un piano eseguibile che devii il meno possibile da quello originale.

### Entità

- **Trip (corsa)**: origine, destinazione, orario di partenza e di arrivo. Fisso: gli orari non si
  riprogrammano, una corsa o viene coperta o viene **cancellata**.
- **Locomotiva**: deve essere fisicamente presente all'origine della corsa. Se si trova altrove,
  serve un **deadhead** (trasferimento a vuoto) che costa distanza e tempo.
- **Macchinista**: ogni corsa e ogni deadhead va guidato. Un driver ha una stazione di partenza
  (`available_from_station`), una disponibilità oraria, e vincoli di turno:
  - durata massima del turno (`max_duty_length = 720` min),
  - pausa obbligatoria oltre una certa soglia di guida continuativa,
  - spostamento passivo fra stazioni a velocità limitata (`CREW_SPEED_KMH = 57`).

### Accoppiamento loco-crew

È l'elemento che distingue il problema dal crew scheduling puro: riposizionare una locomotiva
**genera lavoro per il crew** (qualcuno deve guidare il deadhead), e può richiedere una **catena di
più driver** in sequenza (handoff) se un solo turno non basta a coprire trasferimento + corsa.
Locomotive e turni non sono quindi ottimizzabili in modo indipendente.

### Obiettivo

Minimizzare una combinazione lineare pesata di:

| termine | significato |
|---|---|
| corse cancellate | servizio non erogato |
| deadhead locomotive (km) | chilometri a vuoto del materiale rotabile |
| deadhead crew (km) | spostamenti passivi dei macchinisti |
| return-to-home (km) | quanto lontano ogni driver termina la giornata rispetto al deposito di partenza |

### Istanze

Da ~65 a ~2.000 corse (S01–S18). La dimensione è rilevante per le domande sotto: le strutture di
vicinato che funzionano sulle istanze piccole non scalano automaticamente.

> **Nota sul perimetro della ricerca.** Interessa la letteratura **ferroviaria**. La *airline crew
> recovery* è metodologicamente vicina e alcune tecniche sono trasferibili, ma non è il target: se
> emergono lavori aerei, vanno segnalati solo quando la struttura di vicinato o il meccanismo di
> feasibility è direttamente riusabile qui.

---

## 2. Metodo implementato (stato attuale del codice)

### Soluzione iniziale

Costruzione **greedy sequenziale** trip-by-trip in ordine di `departure_time`
(`IntegratedRescheduler`), con stato crew/loco aggiornato progressivamente e RNG deterministico
(`CppMT19937`, seed-based) per la selezione fra candidati feasible. Per ogni corsa viene conservata
la lista di **tutte** le coppie `(loco, driver_chain)` feasible in quel momento:
`all_candidates[trip_id][0]` è la scelta effettuata, `[1:]` le alternative scartate.

### Perturbazione: ruin-and-recreate, non local swap

**Questo è il punto centrale da confrontare con la letteratura.** La mossa non è uno scambio locale
fra due assegnazioni: si **fissano** k decisioni (`forced = {trip_id: pair}`) e si **ricostruisce
l'intera soluzione da zero** con il greedy, che ripara tutto il resto attorno ai vincoli imposti.

Conseguenze misurate: forzare una sola corsa modifica cancellazioni, deadhead loco, deadhead crew e
return-to-home dell'intero piano. Non esiste valutazione delta — ogni mossa costa una ricostruzione
completa.

### Gestione della feasibility per k > 1

Meccanismo a due regimi, dipendente dalla **posizione nello sweep**, non dal contenuto:

- il **primo** trip forzato (in ordine di partenza) può riusare un'alternativa pre-calcolata **senza
  ricontrollarla**: poiché il seed è fisso, lo sweep fino a quel punto riproduce esattamente la run in
  cui l'alternativa era stata raccolta, quindi lo stato è identico e la feasibility è ereditata per
  costruzione;
- dal **secondo** in poi l'invariante si rompe (la prima forzatura ha già alterato lo stato), quindi i
  candidati vengono **ricalcolati on-the-fly** contro lo stato committed reale.

Se una forzatura non è realizzabile, l'iterazione viene **scartata senza valutarla**
(`forced_failures`): una soluzione con vicinato di dimensione indeterminata non è confrontabile con le
altre. Ordine di grandezza: forzando 40 corse su S01, 19 forzature falliscono.

### Loop BVNS

k = **numero di corse forzate**. Reset a `k=1` sull'accettazione, incremento sul fallimento, wrap a
`k_max`. Incumbent e best-so-far tracciati separatamente. Accettazione attuale: solo miglioramenti
stretti. Riproducibilità completa dalla coppia `(seed, vns_seed)`.

### Risultato preliminare (S01, 65 corse)

Objective da 9747.2 a 9059.8 (−7%) in 6 iterazioni, con recupero di una corsa prima cancellata
(11 → 10). Tempo di sola ricerca ~0.5 s.

---

## 3. Domande aperte — cosa cercare

### 3.1 Struttura di vicinato (priorità alta)

`k` è oggi una **cardinalità su un prefisso temporale**: si forzano le prime k corse in ordine di
partenza che abbiano alternative. Limite noto e misurato: su un'istanza da 2.000 corse la
perturbazione tocca ~0.15% del piano, sempre a inizio giornata.

- Come definiscono $N_k$ i lavori applicati? Cardinalità, **raggio** su una struttura di
  accoppiamento (stessa locomotiva, stesso turno, adiacenza temporale/spaziale), finestre mobili,
  ricombinazione di duty?
- Esistono definizioni di vicinato **annidato** ($N_1 \subset N_2 \subset \dots$) nel rescheduling
  ferroviario, come la teoria VNS richiederebbe?
- Come si sceglie il punto di innesco della perturbazione: casuale, guidato dal contributo
  all'obiettivo, guidato dalla disruption?

### 3.2 Swap vs. ruin-and-recreate nei problemi *integrati* loco+crew (priorità alta)

La letteratura VNS parla prevalentemente di **swap** / mosse locali con valutazione incrementale. Il
metodo qui implementato è invece un **ruin-and-recreate** (più vicino all'ALNS). **La domanda centrale
è se questa differenza dipenda dall'accoppiamento loco-crew.**

Ragione tecnica per cui uno swap "puro" è problematico in questo problema: i **deadhead non sono dati
in input, sono derivati** dall'assegnazione delle locomotive. Spostare una locomotiva da una corsa a
un'altra cambia quali trasferimenti a vuoto servono, e quei trasferimenti sono task che un macchinista
deve guidare. Uno scambio di sole locomotive quindi **riscrive il lavoro del crew** e può renderlo
infeasible: non è una mossa autocontenuta.

Da verificare in letteratura:

- Nei lavori su **crew scheduling puro** (task dati, si riassegna solo chi li copre) le mosse sono
  swap locali — atteso. Ma nei lavori su **rescheduling integrato rolling stock + crew**, quale
  schema prevale: swap con riparazione locale, oppure LNS/ruin-and-recreate proprio a causa
  dell'accoppiamento?
- Chi *usa* swap in contesti integrati, **come gestisce la ricaduta sul crew**: restringe le coppie
  candidate a scambi che preservano la struttura dei deadhead, oppure ammette una riparazione parziale
  del livello crew dopo lo scambio?
- Esistono mosse **stratificate**, che agiscono su un solo livello per volta (es. riassegnare
  macchinisti tenendo fisse le locomotive, quindi a task invariati)? Come vengono combinate con mosse
  che toccano il materiale rotabile?
- Trattamento dei duty delle locomotive come **route** e uso di mosse in stile vehicle routing
  (2-opt, cross-exchange di code di turno): applicato nel rescheduling ferroviario? Come si gestiscono
  i deadhead ricalcolati ai punti di giunzione?
- Confronto **a parità di tempo di calcolo** e non di iterazioni: una ricostruzione completa può
  costare 10²–10³ volte una mossa locale, quindi un confronto a pari numero di iterazioni
  favorirebbe artificialmente il ruin-and-recreate. Qual è la prassi?
- Ibridi: shake ruin-and-recreate seguito da local search a mosse locali (GVNS)?

**Nota di contesto per la ricerca.** Le tre famiglie di mossa considerate qui, in ordine di
invasività: (i) swap di soli macchinisti a locomotive fisse — task invariati, feasibility da
verificare solo lato crew (posizione, durata turno, pause); (ii) swap di locomotive ristretto a corse
compatibili che preservano i deadhead; (iii) scambio di code di turno in stile cross-exchange.
Interessa sapere quali di queste sono documentate e con quali risultati.

### 3.3 Feasibility incrementale

L'invariante "stato identico fino alla prima modifica, grazie all'RNG seedato" permette di saltare
del tutto il controllo di feasibility sulla prima forzatura.

- È una tecnica documentata? Termini da cercare: *incremental feasibility check*, *delta evaluation*,
  *warm start*, *state invariance under deterministic replay*.
- Come gestiscono gli altri il fallimento di una mossa forzata: riparazione, rifiuto, penalizzazione?

### 3.4 Criteri di accettazione

Attualmente solo miglioramenti stretti.

- Quanto è diffusa in pratica l'accettazione di peggioramenti (threshold, skewed VNS,
  simulated-annealing-like) in questo dominio, e con quale beneficio misurato?

### 3.5 Diversificazione e valutazione sperimentale

Osservazione: sulle istanze piccole seed diversi producono traiettorie quasi identiche, perché la
casualità agisce su un solo punto (quale alternativa per la prima corsa forzata).

- Qual è la prassi per la valutazione multi-seed in questi lavori: quante run, quali statistiche?
- Come garantiscono che la perturbazione diversifichi davvero?

### 3.6 Funzione obiettivo e benchmark

- Quali termini sono standard nel crew/loco rescheduling (cancellazioni, deadheading, straordinari,
  return-to-base)? Il termine *return-to-home* è comune o è una scelta specifica?
- Come vengono **scalati e calibrati** i pesi fra termini eterogenei (un conteggio di cancellazioni vs
  chilometri)? Qui è stato necessario portare tutte le distanze in km e assegnare a una cancellazione
  un costo equivalente in km, altrimenti il termine cancellazioni risultava numericamente irrilevante.
- Esistono istanze benchmark pubbliche per il railway crew/rolling stock recovery?

---

## 4. Output desiderato

- Mappa dei lavori rilevanti (preferibilmente ultimi 5 anni, più i capisaldi): riferimento, problema,
  struttura di vicinato, criterio di accettazione, gestione della feasibility, scala delle istanze.
- Confronto esplicito fra lo schema qui implementato (ruin-and-recreate con feasibility ereditata sul
  primo forcing e ricalcolo on-the-fly sui successivi) e le tecniche trovate: **scelta comune,
  variante originale, o esiste un'alternativa standard più efficiente?**
- Indicazioni su come definire un vicinato strutturato che scali su istanze da migliaia di corse.
- Suggerimenti di posizionamento (novità, gap coperto) per una sezione *related work*.
