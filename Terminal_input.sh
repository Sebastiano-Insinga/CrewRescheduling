# tutte le istanze, tutte le combinazioni (default)
python SequentialRescheduling.py

# istanza specifica, tutte le combinazioni
python SequentialRescheduling.py --instances S01

# RS method specifico
python SequentialRescheduling.py --rs-methods randomized_greedy
python SequentialRescheduling.py --rs-methods scored_greedy

# crew method specifico
python SequentialRescheduling.py --crew-methods calculateInitialSolution
python SequentialRescheduling.py --crew-methods calculateInitialSolution_slack

# combinazione esatta
python SequentialRescheduling.py --rs-methods randomized_greedy --crew-methods calculateInitialSolution
python SequentialRescheduling.py --rs-methods randomized_greedy --crew-methods calculateInitialSolution_slack
python SequentialRescheduling.py --rs-methods scored_greedy     --crew-methods calculateInitialSolution
python SequentialRescheduling.py --rs-methods scored_greedy     --crew-methods calculateInitialSolution_slack

# seed custom
python SequentialRescheduling.py --seed 123

# più istanze, combinazione specifica
python SequentialRescheduling.py --instances S01 S02 S03 --rs-methods scored_greedy --crew-methods calculateInitialSolution_slack --seed 99

#lanciare codice Java da Mac
java -Djava.library.path="/Users/sebastianoinsinga/Applications/CPLEX_Studio2212/cplex/bin/arm64_osx" -cp "bin:lib/cplex.jar" scripts.Main


# solo greedy (comportamento originale)
python SequentialRescheduling.py

# greedy + VNS con DP
python SequentialRescheduling.py --vns-method DP

# greedy + VNS, parametri custom
python SequentialRescheduling.py --vns-method DP --window-size 60 --runs-per-window 1 --max-dh-duration 45 --rand-iter 2

# greedy specifico + VNS model
python SequentialRescheduling.py --crew-methods calculateInitialSolution --vns-method model --window-size 240


python SequentialRescheduling.py --instances S01 --crew-methods calculateInitialSolution calculateInitialSolution_deadhead
