#ifndef __FRISCH_SOLUTION_HH
#define __FRISCH_SOLUTION_HH

#include <easylocal.hh>
#include "frisch_input.hh"
#include "../utils/inlines.hh"
#include <algorithm>

using namespace EasyLocal::Core;



class FRISCH_Solution
{
  friend std::ostream& operator<<(std::ostream& os, const FRISCH_Solution& sol);
  friend std::istream& operator>>(std::istream& is, FRISCH_Solution& sol);
  friend bool operator==(const FRISCH_Solution& sol1, const FRISCH_Solution& sol2);
public:
//constructors
  FRISCH_Solution(const FRISCH_Input& in);
  FRISCH_Solution(const FRISCH_Solution& sol);
  // = operator
  FRISCH_Solution& operator=(const FRISCH_Solution& sol);
  void Clear();
  bool CheckConsistency() const;
  void ReadSolution(const pair<vector<int>,vector<int>>& sol);
  void ReadSolution(const struct FRISCH_ILPSolution& sol);
  pair<vector<int>,vector<int>> WriteSolution();

  //Updater of data structures
  void RemoveLocomotive(int trip);   //removes locomotive from trip 
  void AssignLocomotive(int trip, int locomotive);
  void AssignMaintenanceAtTrip(int trip, int station) {is_maintenance_done_at_trip[trip] = station;}  //arrival or departure station
  void RemoveMaintenanceAtTrip(int trip) {is_maintenance_done_at_trip[trip] = 0;}
  void AssignMaintenanceForLocomotive(int locomotive);
  void AssignFullMaintenance();
  #ifdef RESCHEDULING_PROBLEM
  void SolveConflicts();   //Procedures that solves the conflicts and produces a feasible solution
  #endif
  #ifdef LEAST_USED_LOCOMOTIVES
  void UpdateLeastUsed();
  #endif
  //Initial solution
  void RandomSolution(bool maintenance);

  long long int ComputeDistanceBetween(int locomotive, int trip1, int departure_or_arrival_trip1, int trip2, int departure_or_arrival_trip2) const;
  bool MaintenanceFeasibleAtStation(int loc, int trip, int arrival_or_departure) const;

  long long int ComputeConflicts() const;
  tuple<long long int, long long int> ComputeUnmaintainedKm(long long int max_unmaintened_km_threshold = 0) const;
  long long int ComputeTypeViolations() const;
  //Statistics
  int UsedLocomotives() const {return locomotives_in_use_indices.size();}
  long long int DeadheadKM() const;
  int Maintenances() const;
  int LocomotivesWithMaintenance() const;
  long long int MinInitialKMWithMaintenance() const;
  pair<long long int,long long int> MinMaxKMPerUsedLocomotive() const;

  void PrintJSON(std::ostream& os) const;
  
  #ifdef RESCHEDULING_PROBLEM
  void RandomizedGreedy(long long int buffer_threshold = 0);
  void CandidateLocomotives(int trip, int loc_initial_sol,long long int buffer_threshold,vector<int>& candidates);
  #endif

  //data class members
  const FRISCH_Input& in;

  //solution data
  vector<int> used_locomotive; //used_locomotive[k] == true if locomotive k is used, and how many times
  vector<int> locomotives_in_use_indices; //vector of indices of used locomotives
  vector<int> last_trip; //For every locomotive, which is the last trip it covers
  vector<int> first_trip; //For every locomotive, which is the first trip it covers
  vector<vector<bool>> locomotive_trip_assignment; //locomotive_trip_assignment[k][t] == true if locomotive k covers trip t
  vector<vector<int>> previous_trip;   // == -2 if the trip is not assigned to locomotive, otherwise the predecessor: -1 if it is the locomotive starting node, otherwise the index of the trip
  vector<vector<int>> next_trip;   // == -2 if the trip is not assigned to locomotive, -1 if it is the last trip, otherwise the index of the successor trip
  vector<int> trip_locomotive;   //for every trip, by which locomotive it is covered
  vector<int> is_maintenance_done_at_trip;   //if the maintenance is done before the trip. 1: at the departure station; 2 at the arrival station, 0 no maintenance
  vector<bool> maintenance_at_departure;  //for rescheduling: maintenance before trip
  vector<bool> maintenance_at_destination; //for rescheduling: maintenance after trip
  #ifdef RESCHEDULING_PROBLEM
  int solved_conflicts_at_beginning;
  bool only_maintenance_from_plan;
  void SetOnlyMaintenanceFromPlan(bool only_from_plan) {only_maintenance_from_plan = only_from_plan;}
  #endif
  #ifdef LEAST_USED_LOCOMOTIVES
  set<int> least_used_locomotive; //locomotive with the least number of trips, among the used ones
  int least_used_locomotive_howmuch; //index of the least used locomotive
  #endif

};


#endif