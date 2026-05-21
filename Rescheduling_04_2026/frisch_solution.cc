#include "frisch_solution.hh"

// Include for FRISCH_ILPSolution definition needed by ReadSolution overload
//#include "../model-frisch/frisch_ilp.hh"


FRISCH_Solution::FRISCH_Solution(const FRISCH_Input& in) : in(in)
{
  used_locomotive.resize(in.locomotive.size(),0);
  trip_locomotive.resize(in.train_trips.size(),-1);
  last_trip.resize(in.locomotive.size(),-1);  //-1 means that the locomotive is not used (the last trip is the starting node)
  first_trip.resize(in.locomotive.size(),-1);  //-1 means that the locomotive is not used (the first trip is the starting node)
  locomotive_trip_assignment.resize(in.locomotive.size(),vector<bool>(in.train_trips.size(),false));
  next_trip.resize(in.locomotive.size(),vector<int>(in.train_trips.size(),-2));
  previous_trip.resize(in.locomotive.size(),vector<int>(in.train_trips.size(),-2));
  is_maintenance_done_at_trip.resize(in.train_trips.size(),0);
  maintenance_at_departure.resize(in.train_trips.size(),false);
  maintenance_at_destination.resize(in.train_trips.size(),false);
  #ifdef RESCHEDULING_PROBLEM
  solved_conflicts_at_beginning = 0;
  only_maintenance_from_plan = false; //default
  #endif
  #ifdef LEAST_USED_LOCOMOTIVES
  least_used_locomotive.clear();
  least_used_locomotive_howmuch = in.train_trips.size();
  #endif
}


FRISCH_Solution::FRISCH_Solution(const FRISCH_Solution& sol) : in(sol.in)
{
  used_locomotive = sol.used_locomotive;
  locomotives_in_use_indices = sol.locomotives_in_use_indices;
  trip_locomotive = sol.trip_locomotive;
  last_trip = sol.last_trip;
  first_trip = sol.first_trip;
  locomotive_trip_assignment = sol.locomotive_trip_assignment;
  next_trip = sol.next_trip;
  previous_trip = sol.previous_trip;
  is_maintenance_done_at_trip = sol.is_maintenance_done_at_trip;
  #ifdef RESCHEDULING_PROBLEM
  solved_conflicts_at_beginning = sol.solved_conflicts_at_beginning;
  only_maintenance_from_plan = sol.only_maintenance_from_plan;
  #endif
  #ifdef LEAST_USED_LOCOMOTIVES
  least_used_locomotive = sol.least_used_locomotive;
  least_used_locomotive_howmuch = sol.least_used_locomotive_howmuch;
  #endif
}

void FRISCH_Solution::Clear()
{
  used_locomotive.clear();
  locomotives_in_use_indices.clear();
  trip_locomotive.clear();
  last_trip.clear();
  first_trip.clear();
  locomotive_trip_assignment.clear();
  next_trip.clear();
  previous_trip.clear();
  is_maintenance_done_at_trip.clear();
  maintenance_at_departure.clear();
  maintenance_at_destination.clear();
  #ifdef RESCHEDULING_PROBLEM
  solved_conflicts_at_beginning = 0;
  #endif
  #ifdef LEAST_USED_LOCOMOTIVES
  least_used_locomotive.clear();
  least_used_locomotive_howmuch = in.train_trips.size();
  #endif
  used_locomotive.resize(in.locomotive.size(),0);
  trip_locomotive.resize(in.train_trips.size(),-1);
  last_trip.resize(in.locomotive.size(),-1);
  first_trip.resize(in.locomotive.size(),-1);
  locomotive_trip_assignment.resize(in.locomotive.size(),vector<bool>(in.train_trips.size(),false));
  next_trip.resize(in.locomotive.size(),vector<int>(in.train_trips.size(),-2));
  previous_trip.resize(in.locomotive.size(),vector<int>(in.train_trips.size(),-2));
  is_maintenance_done_at_trip.resize(in.train_trips.size(),0);
  maintenance_at_departure.resize(in.train_trips.size(),false);
  maintenance_at_destination.resize(in.train_trips.size(),false);
}

void FRISCH_Solution::PrintJSON(std::ostream& os) const
{
  nlohmann::json j_sol;

  for(int i = 0; i < static_cast<int>(trip_locomotive.size()); i++)
  {
    nlohmann::json this_trip;
    this_trip["id_trip"] = in.train_trips[i].id;
    if(trip_locomotive[i] != -1)
    {
      this_trip["locomotive"] = in.locomotive[trip_locomotive[i]].id;
      if(is_maintenance_done_at_trip[i] == 1)
        this_trip["maintenance_at_departure"] = "true";
      else
        this_trip["maintenance_at_departure"] = "false";
      if(is_maintenance_done_at_trip[i] == 2)
        this_trip["maintenance_at_destination"] = "true";
      else
        this_trip["maintenance_at_destination"] = "false";
    }
    else
      this_trip["locomotive"] = "canceled";
    
    j_sol.push_back(this_trip);
  }
  os << j_sol.dump(3);
}


ostream& operator<<(std::ostream& os, const FRISCH_Solution& sol)
{
  for(int i = 0; i < static_cast<int>(sol.trip_locomotive.size()); i++)
  {
    #ifdef RESCHEDULING_PROBLEM
    os << sol.trip_locomotive[i] << "(" << sol.in.initial_solution_trips[sol.in.trip_index_in_initial_solution[i]] << ")";
    #else
    os << sol.trip_locomotive[i];
    #endif
    if(i < static_cast<int>(sol.trip_locomotive.size())-1)
      os << " ";
  }
  os << endl;
  for(int i = 0; i < static_cast<int>(sol.trip_locomotive.size()); i++)
  {
    #ifdef RESCHEDULING_PROBLEM
    os << sol.is_maintenance_done_at_trip[i]  << "(" << sol.in.initial_solution_maintenances[sol.in.trip_index_in_initial_solution[i]] << ")";
    #else
    os << sol.is_maintenance_done_at_trip[i];
    #endif
    if(i < static_cast<int>(sol.trip_locomotive.size())-1)
      os << " ";
  }
  os << endl;
  return os;
}

std::istream& operator>>(std::istream& is, FRISCH_Solution& sol) 
{
  if(is.peek() == '[')  //read json
  {
    nlohmann::json j_sol;
    is >> j_sol;
    
    for (auto this_trip : j_sol)
    {
      if(this_trip["locomotive"] != "canceled")
      {
        cerr << this_trip["id_trip"] << "/" << this_trip["locomotive"] << " = ";
        cerr << sol.in.FindTripByID(this_trip["id_trip"])  << "/" << sol.in.FindLocomotiveByID(this_trip["locomotive"]) << endl;
        sol.AssignLocomotive(sol.in.FindTripByID(this_trip["id_trip"]),sol.in.FindLocomotiveByID(this_trip["locomotive"]));
        if(this_trip["maintenance_at_departure"] == "true")
          sol.AssignMaintenanceAtTrip(sol.in.FindTripByID(this_trip["id_trip"]),1);
        else if (this_trip["maintenance_at_destination"] == "true")
         sol.AssignMaintenanceAtTrip(sol.in.FindTripByID(this_trip["id_trip"]),2);
      }
    }
  }
  else
  {
    is.clear();
    int loc;
    int maint;
    for(int i = 0; i < static_cast<int>(sol.in.train_trips.size()); i++)
    {
      is >> loc;
      if(loc == -1)
        sol.trip_locomotive[i] = -1;
      else
        sol.AssignLocomotive(i,loc);
    }
    
    // for(int i = 0; i < static_cast<int>(sol.in.train_trips.size()); i++)
    // {
    //   is >> maint;
    //   if(maint != 0)
    //     sol.AssignMaintenanceAtTrip(i,maint);
    // }
    sol.AssignFullMaintenance();
  }
  cerr << "Consistent: " << sol.CheckConsistency() <<  endl;
  return is;
}

bool operator==(const FRISCH_Solution& sol1, const FRISCH_Solution& sol2)
{
  return sol1.trip_locomotive == sol2.trip_locomotive;
}

FRISCH_Solution& FRISCH_Solution::operator=(const FRISCH_Solution& sol)
{
  used_locomotive = sol.used_locomotive;
  locomotives_in_use_indices = sol.locomotives_in_use_indices;
  trip_locomotive = sol.trip_locomotive;
  last_trip = sol.last_trip;
  first_trip = sol.first_trip;
  locomotive_trip_assignment = sol.locomotive_trip_assignment;
  next_trip = sol.next_trip;
  previous_trip = sol.previous_trip;
  is_maintenance_done_at_trip = sol.is_maintenance_done_at_trip;
  #ifdef RESCHEDULING_PROBLEM
  solved_conflicts_at_beginning = sol.solved_conflicts_at_beginning;
  #endif
  #ifdef LEAST_USED_LOCOMOTIVES
  least_used_locomotive = sol.least_used_locomotive;
  least_used_locomotive_howmuch = sol.least_used_locomotive_howmuch;
  #endif
  return *this;
}

bool FRISCH_Solution::CheckConsistency() const
{
  //Redundand data to check:
  bool consistent = true;

  #ifndef RESCHEDULING_PROBLEM
  //0. No trips have -1 in scheduling mode
  for(int i = 0; i < static_cast<int>(trip_locomotive.size()); i++)
    if(trip_locomotive[i] < 0)
    {
      cout << "Trip " << i << " has locomotive assigned =  " << trip_locomotive[i] << ", however not possible in scheduling mode" << endl;
      consistent = false;
    }
  #endif

  //1. For every trip, by which locomotive it is covered
  for(int i = 0; i < static_cast<int>(trip_locomotive.size()); i++)
    if(trip_locomotive[i] != -1 && !locomotive_trip_assignment[trip_locomotive[i]][i])
    {
      cout << "Trip " << i << " is covered by locomotive " << trip_locomotive[i] << " but it is not assigned to it" << endl;
      consistent = false;
    }
  
  //2. For every locomotive, which is the last trip it covers
  for(int l = 0; l < static_cast<int>(in.locomotive.size()); l++)
  {
    if(last_trip[l] != -1 && !locomotive_trip_assignment[l][last_trip[l]])
    {
      cout << "Locomotive " << l << " covers trip " << last_trip[l] << " but it is not assigned to it" << endl;
      consistent = false;
    }   
  }

  //3. For every locomotive, which is the first trip it covers
  for(int l = 0; l < static_cast<int>(in.locomotive.size()); l++)
  {
    if(first_trip[l] != -1 && !locomotive_trip_assignment[l][first_trip[l]])
    {
      cout << "Locomotive " << l << " covers trip " << first_trip[l] << " but it is not assigned to it" << endl;
      consistent = false;
    }   
  }

  //4. For every trip, the predecessor
  for(int l = 0; l < static_cast<int>(in.locomotive.size()); l++)
    for(int t = 0; t < static_cast<int>(in.train_trips.size()); t++)
    {
      if(previous_trip[l][t] == -1)
      {
        if(!(first_trip[l] == t))
        {
          cout << "previous_trip[" << l << "][" << t << "] = -1 but first_trip[" << l << "] = " << first_trip[l] << endl;
          consistent = false;
        }
      }
      else if(previous_trip[l][t] != -2 && !locomotive_trip_assignment[l][previous_trip[l][t]])
      {
        cout << "Locomotive " << l << " covers trip " << t << " but the predecessor " << previous_trip[l][t] << " is not assigned to it" << endl;
        consistent = false;
      }
    }
  
  //5. For every trip, the successor
  for(int l = 0; l < static_cast<int>(in.locomotive.size()); l++)
    for(int t = 0; t < static_cast<int>(in.train_trips.size()); t++)
    {
      if(next_trip[l][t] == -1)
      {
        if(!(last_trip[l] == t))
        {
          cout << "next_trip[" << l << "][" << t << "] = -1 but last_trip[" << l << "] = " << last_trip[l] << endl;
          consistent = false;
        }
      }
      else if(next_trip[l][t] != -2 && !locomotive_trip_assignment[l][next_trip[l][t]])
      {
        cout << "Locomotive " << l << " covers trip " << t << " but the successor " << next_trip[l][t] << " is not assigned to it" << endl;
        consistent = false;
      }
    }

  //6. For every trip, if the maintenance is done, it is a feasible maintenance
  for(int t = 0; t < static_cast<int>(in.train_trips.size()); t++)
  {
    int this_locomotive = trip_locomotive[t];
    if(is_maintenance_done_at_trip[t] != 0 && is_maintenance_done_at_trip[t] != 1 && is_maintenance_done_at_trip[t] != 2)
    {
      cout << "is_maintenance_done_at_trip[" << t << "] = " << is_maintenance_done_at_trip[t] << ", but admitted values are only 0, 1 and 2!" << endl;
      consistent = false;
    }
    
    if(this_locomotive == -1)
    {
      if(is_maintenance_done_at_trip[t] > 0)
      {
        cout << "trip " << t << " not assigned to any locomotive (-1), but is_maintenance_done_at_trip[" << t << "] = " << is_maintenance_done_at_trip[t] << " (maintenance assigned!)" << endl;
        consistent = false;
      }
    }
    else  //if a locomotive is actually assigned
    {
      if(is_maintenance_done_at_trip[t] > 0)
      {
        int this_station;
        int this_loc_class;
        int this_previous_trip = -2, this_next_trip = -2;
        int this_index_in_maintenance_point;
        bool found_maintenable_class;
        if(is_maintenance_done_at_trip[t] == 1)
        {
          this_station = in.section[in.train_trips[t].section].origin;
          this_previous_trip = previous_trip[this_locomotive][t];
        }
        else //if(is_maintenance_done_at_trip[t] == 2)
        {
          this_station = in.section[in.train_trips[t].section].destination;
          this_next_trip = next_trip[this_locomotive][t];
        }
        
        //I check if it is a maintenance station
        if(!in.station[this_station].is_maintenance)
        {
          cout << "trip " << t << " with is_maintenance_done_at_trip[" << t << "] = " << is_maintenance_done_at_trip[t] << " assigns maintenance to station " << this_station << ", howewer the station is not a maintenance point" << endl;
          consistent = false;
        }
        
        //I check if the locomotive class is maintenable at this station
        this_index_in_maintenance_point = in.station[this_station].index_in_maintenance_point;
        found_maintenable_class = false;
        for(unsigned int i = 0; i < in.maintenance_point[this_index_in_maintenance_point].maintainable_locomotive_classes.size(); i++)
        {
          this_loc_class = in.maintenance_point[this_index_in_maintenance_point].maintainable_locomotive_classes[i];
          if(in.locomotive[this_locomotive].locomotive_class == this_loc_class)
          {
            found_maintenable_class = true;
            break;
          }
        }

        if(!found_maintenable_class)
        {
          cout << "trip " << t << " assigned to locomotive " << this_locomotive << " from locomotive class " << in.locomotive[this_locomotive].locomotive_class <<  " has is_maintenance_done_at_trip[" << t << "] = " << is_maintenance_done_at_trip[t] << ", with maintenance done at station " << this_station << ", howewer locomotive class " << in.locomotive[this_locomotive].locomotive_class << " is not maintainable. Possible maintenable classes are : " << in.maintenance_point[this_index_in_maintenance_point].maintainable_locomotive_classes << endl;
          consistent = false;
        }

        //Only if I don't have conflicts, I check if the locomotive can reach the station

        if(ComputeConflicts() == 0)
        {
          bool time_for_maint = true;
          int this_this_trip1;
          int this_this_trip2;
          if(is_maintenance_done_at_trip[t] == 1)
          {
            this_this_trip1 = this_previous_trip;
            this_this_trip2 = t;
          }
          else if(is_maintenance_done_at_trip[t] == 2 && this_next_trip >= 0)
          {
            this_this_trip1 = t;
            this_this_trip2 = this_next_trip;
          }
          if(!in.TimeForMaintenanceBetweenTrips(this_locomotive,this_this_trip1,this_this_trip2))
              time_for_maint = false;
          
  
          if(!time_for_maint)
          {
            cout << "trip " << t << " assigned to locomotive " << this_locomotive 
            << " from locomotive class " << in.locomotive[this_locomotive].locomotive_class 
            << " with speed " << in.locomotive_class[in.locomotive[this_locomotive].locomotive_class].deadhead_speed/1000.0 << " km/h"  
            << " has is_maintenance_done_at_trip[" << t << "] = " << is_maintenance_done_at_trip[t] 
            << ", however there is not enough time for maintenance, indeed ";
            int station1,station2;
            long long int deadhead_departure_time;
            if(this_this_trip1 == -1) //If it is the first trip
            {
              station1 = in.locomotive[this_locomotive].initial_departure_station;
              #ifdef RESCHEDULING_PROBLEM
              deadhead_departure_time = in.locomotive[this_locomotive].availability_time;
              #else
              deadhead_departure_time = 0;
              #endif
            }
            else
            {
              station1 = in.section[in.train_trips[this_this_trip1].section].destination;
              deadhead_departure_time = in.train_trips[this_this_trip1].arrival_time;
            }
            station2 = in.section[in.train_trips[this_this_trip2].section].origin;
            int us1 = in.station[station1].index_in_used_station;
            int us2 = in.station[station2].index_in_used_station;
            
            cout << "trips are distanced in time by " << (in.train_trips[this_this_trip2].departure_time - deadhead_departure_time)/3600.0 << "hours ";
  
            long long int this_deadhead;
            #ifdef RESCHEDULING_PROBLEM
            if(in.DeadheadAffectedByDisruption(this_this_trip1,this_this_trip2))
            { 
              this_deadhead = in.disrupted_shortest_paths[us1][us2].weight;
            }
            else
            #else
            {
              this_deadhead = in.shortest_paths[us1][us2].weight;
            }
            #endif
            
            cout << ", shortest path is " << this_deadhead/1000.0 << " km " 
                 << ", which takes " << static_cast<double>(this_deadhead)/in.locomotive_class[in.locomotive[this_locomotive].locomotive_class].deadhead_speed << " hours "
                 << ", and maintenance lasts " << in.locomotive_class[in.locomotive[this_locomotive].locomotive_class].maintenance_duration/3600.0 << " hours "
                 << ", for a total of " << in.locomotive_class[in.locomotive[this_locomotive].locomotive_class].maintenance_duration/3600.0 + static_cast<double>(this_deadhead)/in.locomotive_class[in.locomotive[this_locomotive].locomotive_class].deadhead_speed << " hours "<< endl;
            
            consistent = false;
          } 
        }
        
      }
    }
  }



  //7. I check that locomotives_in_use_indices and used_locomotive match
  for(int l = 0; l < static_cast<int>(in.locomotive.size()); l++)
  {
    if(used_locomotive[l] > 0 && !Member<int>(locomotives_in_use_indices,l))
    {
      cout << "Locomotive " << l << " is used " << used_locomotive[l] << " times but it is not in locomotives_in_use_indices" << endl;
      consistent = false;
    }
    if(used_locomotive[l] == 0 && Member<int>(locomotives_in_use_indices,l))
    {
      cout << "Locomotive " << l << " is not used but it is in locomotives_in_use_indices" << endl;
      consistent = false;
    }
  }

  //8. I check that the counter of used locomotives is correct
  for(int l = 0; l < static_cast<int>(in.locomotive.size()); l++)
  {
    int counter_locomotive_trip_assignment= 0;
    int counter_previous_trip = 0;
    int counter_next_trip = 0;
    for(int t = 0; t < static_cast<int>(in.train_trips.size()); t++)
    {
      if(locomotive_trip_assignment[l][t])
        counter_locomotive_trip_assignment++;
      if(previous_trip[l][t] != -2)
        counter_previous_trip++;
      if(next_trip[l][t] != -2)
        counter_next_trip++;
    }
    if(counter_locomotive_trip_assignment != used_locomotive[l])
    {
      cout << "locomotive_trip_assignment: locomotive " << l << " is used " << used_locomotive[l] << " times but it is assigned to " << counter_locomotive_trip_assignment << " trips" << endl;
      consistent = false;
    }
    if(counter_previous_trip != used_locomotive[l])
    {
      cout << "previous_trip: locomotive " << l << " is used " << used_locomotive[l] << " times but it has " << counter_previous_trip << " predecessors" << endl;
      consistent = false;
    }
    if(counter_next_trip != used_locomotive[l])
    {
      cout << "next_trip: locomotive " << l << " is used " << used_locomotive[l] << " times but it has " << counter_next_trip << " successors" << endl;
      consistent = false;
    }
  }

  #ifdef LEAST_USED_LOCOMOTIVES
  //I check least_used_locomotive
  set<int> min_used;
  int how_much_used = in.train_trips.size();
  for(int l = 0; l < static_cast<int>(in.locomotive.size()); l++)
    if(used_locomotive[l] > 0 && used_locomotive[l] < how_much_used)
    {
        how_much_used = used_locomotive[l];
        min_used.clear();
        min_used.insert(l);
    }
    else if (used_locomotive[l] > 0 && used_locomotive[l] == how_much_used)
      min_used.insert(l);
  
  if(min_used != least_used_locomotive)
  {
    cout << "least_used_locomotive is " << least_used_locomotive << " but it should be " << min_used << endl;
    consistent = false;
  }

  if(how_much_used != least_used_locomotive_howmuch)
  {
    cout << "least_used_locomotive_howmuch is " << least_used_locomotive_howmuch << " but it should be " << how_much_used << endl;
    consistent = false;
  }

  #endif
  return consistent;

}

void FRISCH_Solution::ReadSolution(const pair<vector<int>,vector<int>>& sol)
{
  Clear();
  for(int i = 0; i < static_cast<int>(sol.first.size()); i++)
    if(sol.first[i] != -1)
    {
      AssignLocomotive(i,sol.first[i]);
      AssignMaintenanceAtTrip(i,sol.second[i]);
    }

  #ifdef LEAST_USED_LOCOMOTIVES
  UpdateLeastUsed();
  #endif
}

void FRISCH_Solution::ReadSolution(const struct FRISCH_ILPSolution& sol)
{
  Clear();
  for(int i = 0; i < static_cast<int>(sol.trip_locomotive.size()); i++)
  {
    if(sol.trip_locomotive[i] != -1)
    {
      AssignLocomotive(i, sol.trip_locomotive[i]);
      
      // Convert maintenance_at_departure/destination boolean flags to old format (0/1/2)
      // 0 = no maintenance, 1 = maintenance at departure, 2 = maintenance at destination
      int maint_flag = 0;
      if(sol.maintenance_at_departure[i])
        maint_flag = 1;
      else if(sol.maintenance_at_destination[i])
        maint_flag = 2;
      
      AssignMaintenanceAtTrip(i, maint_flag);
      
      // Also store the boolean flags
      maintenance_at_departure[i] = sol.maintenance_at_departure[i];
      maintenance_at_destination[i] = sol.maintenance_at_destination[i];
    }
  }

  #ifdef LEAST_USED_LOCOMOTIVES
  UpdateLeastUsed();
  #endif
}

pair<vector<int>,vector<int>> FRISCH_Solution::WriteSolution()
{
  return make_pair(trip_locomotive,is_maintenance_done_at_trip);
}

void FRISCH_Solution::RemoveLocomotive(int trip)
{
  int locomotive = trip_locomotive[trip];
  if(locomotive == -1)
    return;  //nothing to do
  trip_locomotive[trip] = -1;
  locomotive_trip_assignment[locomotive][trip] = false;
  if(next_trip[locomotive][trip] >= 0)  //If it was not the last trip
    //The predecessor of the next trip is the predecessor of the current trip
    previous_trip[locomotive][next_trip[locomotive][trip]] = previous_trip[locomotive][trip];  //The new predecessor of the successor is the predecessor of the current node

  if(previous_trip[locomotive][trip] >= 0)  //If it was not the first trip
    //The successor of the previous trip is the successor of the current trip
    next_trip[locomotive][previous_trip[locomotive][trip]] = next_trip[locomotive][trip];

  used_locomotive[locomotive]--;
  if(used_locomotive[locomotive] == 0)
    EfficientRemove<int>(locomotives_in_use_indices,FindIndex<int>(locomotives_in_use_indices,locomotive));

  if(last_trip[locomotive] == trip)    //Se era l'ultima
  {
    if(used_locomotive[locomotive] == 0)   //Se la locomotiva non è più usata
      last_trip[locomotive] = -1;          //L'ultima trip va a zero
    else                                   //Altrimenti il predecessore della corrente è la nuova ultima
      last_trip[locomotive] = previous_trip[locomotive][trip];
  }

  if(first_trip[locomotive] == trip)    //Se era la prima
  {
    if(used_locomotive[locomotive] == 0)   //Se la locomotiva non è più usata
      first_trip[locomotive] = -1;          //La prima trip va a zero
    else                                   //Altrimenti il successore della corrente è la nuova prima
      first_trip[locomotive] = next_trip[locomotive][trip];
  }

  previous_trip[locomotive][trip] = -2;
  next_trip[locomotive][trip] = -2;

  // if(used_locomotive[locomotive] > 0)
  // {
  //   if(used_locomotive[locomotive] < least_used_locomotive_howmuch)
  //   {
  //     least_used_locomotive_howmuch = used_locomotive[locomotive];
  //     least_used_locomotive.clear();
  //     least_used_locomotive.insert(locomotive);
  //   }
  //   else if (used_locomotive[locomotive] == least_used_locomotive_howmuch)
  //   {
  //     least_used_locomotive.insert(locomotive);
  //   }
  // }
  // else
  // {
  //   least_used_locomotive.erase(locomotive);
  //   if(least_used_locomotive.size() == 0)   //If it was the only one with only one trip...
  //   {
  //     least_used_locomotive_howmuch = in.train_trips.size();
  //     for(int l = 0; l < static_cast<int>(locomotives_in_use_indices.size()); l++)
  //     {
  //         if(used_locomotive[locomotives_in_use_indices[l]] < least_used_locomotive_howmuch)
  //         {
  //             least_used_locomotive_howmuch = used_locomotive[locomotives_in_use_indices[l]];
  //             least_used_locomotive.clear();
  //             least_used_locomotive.insert(locomotives_in_use_indices[l]);
  //         }
  //         else if (used_locomotive[locomotives_in_use_indices[l]] == least_used_locomotive_howmuch)
  //           least_used_locomotive.insert(locomotives_in_use_indices[l]);
  //     }
  //   }
  // }
  
  // cerr << "After remove, least_used_locomotive = " << least_used_locomotive << ", least_used_locomotive_howmuch = " << least_used_locomotive_howmuch << endl;


}



void FRISCH_Solution::AssignLocomotive(int trip, int locomotive)
{
  trip_locomotive[trip] = locomotive;
  locomotive_trip_assignment[locomotive][trip] = true;
  used_locomotive[locomotive]++;
  if(used_locomotive[locomotive] == 1 )
    locomotives_in_use_indices.push_back(locomotive);

  if(first_trip[locomotive] == -1)  //If it was the first trip
  {
    first_trip[locomotive] = trip;  //It's the first trip of the locomotive
    last_trip[locomotive] = trip;   //It's the last trip of the locomotive
    next_trip[locomotive][trip] = -1;  //It's the last trip of the locomotive
    previous_trip[locomotive][trip] = -1;  //It's the starting locomotive node
  }
  else
  {
    if(trip > last_trip[locomotive])
    {
      next_trip[locomotive][last_trip[locomotive]] = trip;
      previous_trip[locomotive][trip] = last_trip[locomotive];
      last_trip[locomotive] = trip;
      next_trip[locomotive][trip] = -1;
    }
    else if(trip < first_trip[locomotive])
    {
      previous_trip[locomotive][first_trip[locomotive]] = trip;
      next_trip[locomotive][trip] = first_trip[locomotive];
      first_trip[locomotive] = trip;  
      previous_trip[locomotive][trip] = -1;
    }
    else  // the general case in which it is not the first, nor the last
    {
      int what_is_next;
      for(int t = trip-1; t >= 0; t--) //I update the previous one
      {
        if(locomotive_trip_assignment[locomotive][t] == true)
        {
          previous_trip[locomotive][trip] = t;
          what_is_next = next_trip[locomotive][t];
          next_trip[locomotive][t] = trip;
          next_trip[locomotive][trip] = what_is_next;
          previous_trip[locomotive][what_is_next] = trip;
          break;
        }
      }
    }
  }

  // #ifdef RESCHEDULING_PROBLEM
  // if(locomotive == -1)
  //   RemoveMaintenanceAtTrip(trip);
  // #endif
  // //I update the least used locomotive
  // if(least_used_locomotive.size() == 0)
  // {
  //   least_used_locomotive.insert(locomotive);
  //   least_used_locomotive_howmuch = used_locomotive[locomotive];
  // } 
  // else if(used_locomotive[locomotive] < least_used_locomotive_howmuch) //For example, I have added a new locomotive that was not in the solution
  //   {
  //     least_used_locomotive.clear();
  //     least_used_locomotive.insert(locomotive);
  //     least_used_locomotive_howmuch = used_locomotive[locomotive];
  //   }
  // else if (used_locomotive[locomotive] == least_used_locomotive_howmuch)
  // {    
  //   least_used_locomotive.insert(locomotive);
  // }
  // else if (used_locomotive[locomotive] == least_used_locomotive_howmuch +1)
  // {
  //   least_used_locomotive.erase(locomotive);
  //   if(least_used_locomotive.size() == 0)   //If it was the only one at the bottom...
  //   {
  //     least_used_locomotive_howmuch = in.train_trips.size();
  //     for(int l = 0; l < static_cast<int>(locomotives_in_use_indices.size()); l++)
  //     {
  //         if(used_locomotive[locomotives_in_use_indices[l]] < least_used_locomotive_howmuch)
  //         {
  //             least_used_locomotive_howmuch = used_locomotive[locomotives_in_use_indices[l]];
  //             least_used_locomotive.clear();
  //             least_used_locomotive.insert(locomotives_in_use_indices[l]);
  //         }
  //         else if (used_locomotive[locomotives_in_use_indices[l]] == least_used_locomotive_howmuch)
  //           least_used_locomotive.insert(locomotives_in_use_indices[l]);
  //     }
  //   }
  // }

  // cerr << "After assign, least_used_locomotive = " << least_used_locomotive << ", least_used_locomotive_howmuch = " << least_used_locomotive_howmuch << endl;


}

#ifdef LEAST_USED_LOCOMOTIVES
void FRISCH_Solution::UpdateLeastUsed()
{
  int this_locomotive;
  least_used_locomotive.clear();
  least_used_locomotive_howmuch = in.train_trips.size();
  for(int l = 0; l < static_cast<int>(locomotives_in_use_indices.size()); l++)
  {
    this_locomotive = locomotives_in_use_indices[l];
    if(used_locomotive[this_locomotive] < least_used_locomotive_howmuch)
    {
        least_used_locomotive_howmuch = used_locomotive[this_locomotive];
        least_used_locomotive.clear();
        least_used_locomotive.insert(this_locomotive);
    }
    else if (used_locomotive[this_locomotive] == least_used_locomotive_howmuch)
      least_used_locomotive.insert(this_locomotive);
  }
}
#endif


#ifdef RESCHEDULING_PROBLEM
void FRISCH_Solution::RandomSolution(bool maintenance)
{

  RandomizedGreedy();
  #ifdef USE_OLD_REPAIR
  Clear();
  int i;
  for(int j = 0 ; j < static_cast<int>(in.trip_index_in_initial_solution.size()); j++)
  {
    i = in.trip_index_in_initial_solution[j];
    AssignLocomotive(j,in.initial_solution_trips[i]);
  }
  AssignFullMaintenance();
  SolveConflicts();
  #endif
}
#else
void FRISCH_Solution::RandomSolution(bool maintenance)
{
  cerr << "I enter RandomSolution" << endl;
  Clear();
  int which_locomotive;
  vector<int> deadhead_km(in.locomotive.size(),0);
  vector<vector<int>> node_assignment(in.locomotive.size());  //initially empty vectors with the assigment by locomotive
  
  bool restart;
  vector<int> candidates;
  
  do
  {
    Clear();
    restart = false;
    //For every trip, I assign the locomotive that will cover it
    for(int trip = 0; trip < static_cast<int>(in.train_trips.size()); trip++)
    {
      candidates.clear();
      for(int loc = 0; loc < static_cast<int>(in.locomotive.size()); loc++)
      {
        if(used_locomotive[loc] == 0)
          candidates.push_back(loc);
        else if(in.FeasibleByTimeTrips(last_trip[loc],trip,loc))
          candidates.push_back(loc);
      }
      if(candidates.size() == 0)
      {
        restart = true;
        break;
      }

      if(!restart)
      {
        which_locomotive = candidates[Random::Uniform<int>(0,candidates.size()-1)];
        AssignLocomotive(trip,which_locomotive);
      }
    }
  } while (restart);

  AssignFullMaintenance();
  #ifdef LEAST_USED_LOCOMOTIVES
  UpdateLeastUsed();
  #endif
  cerr << "I leave RandomSolution, consistent = " << CheckConsistency() << endl;
}
#endif

void FRISCH_Solution::AssignFullMaintenance()
{
  for(int loc = 0; loc < static_cast<int>(in.locomotive.size()); loc++)
  #ifdef RESCHEDULING_PROBLEM
    if(in.usable_locomotive[loc])
      AssignMaintenanceForLocomotive(loc);  
  #else
    AssignMaintenanceForLocomotive(loc);  
  #endif
}

#ifdef RESCHEDULING_PROBLEM
void FRISCH_Solution::RandomizedGreedy(long long int buffer_threshold)
{
  Clear();
  int i;
  vector<int> candidates;
  int l;

  for(int t = 0 ; t < static_cast<int>(in.trip_index_in_initial_solution.size()); t++)
  {
    //cerr << " t = " << t << " gets locomotive = ";
    i = in.trip_index_in_initial_solution[t];
    CandidateLocomotives(t,in.initial_solution_trips[i],buffer_threshold,candidates);
    if(candidates.size() > 0)
    {
      l = candidates[Random::Uniform<int>(0,candidates.size()-1)];
      AssignLocomotive(t,l);
      AssignFullMaintenance();
      //cerr << l;
    }
    //else
      //cerr << "-1";
    //cerr << ", previously = " << in.initial_solution_trips[i] << ", candidates = " << candidates.size() << endl;
  }
  //AssignFullMaintenance();
  //SolveConflicts();
  //cerr << "Finished!, solution is " << endl <<  * this << endl;
  
}

void FRISCH_Solution::CandidateLocomotives(int trip, int loc_initial_sol, long long int buffer_threshold, vector<int>& candidates)
{ 

  int l; int i;
  candidates.clear();
  //First, I try with the previously assigned locomotive
  AssignLocomotive(trip,loc_initial_sol);
  AssignFullMaintenance();
  //cerr << endl << "        I try " << loc_initial_sol << " on " << trip << ", ComputeConflicts() == " << ComputeConflicts() << " && ComputeTypeViolations() == " << ComputeTypeViolations() << "  && get<0>(ComputeUnmaintainedKm(0)) == " << get<0>(ComputeUnmaintainedKm(0)) << endl;
  if(ComputeConflicts() == 0 && ComputeTypeViolations() == 0 && get<0>(ComputeUnmaintainedKm(buffer_threshold)) == 0)
  {
    candidates.push_back(loc_initial_sol);
  }

  #ifdef __GREEDY_TRY_OTHER_LOCOMOTIVES
  //altrimenti...
  if(candidates.size() == 0)
  {
    for(i = 0; i < static_cast<int>(in.usable_locomotive_indices.size()); i++)
    {
      l = in.usable_locomotive_indices[i];
      if(l != loc_initial_sol)
      {
        RemoveLocomotive(trip);
        RemoveMaintenanceAtTrip(trip);
        AssignFullMaintenance();
        AssignLocomotive(trip,l);
        AssignFullMaintenance();
        //cerr << "        I try " << l << " on " << trip << ", ComputeConflicts() == " << ComputeConflicts() << " && ComputeTypeViolations() == " << ComputeTypeViolations() << "  && get<0>(ComputeUnmaintainedKm(0)) == " << get<0>(ComputeUnmaintainedKm(0)) << endl;
        if(ComputeConflicts() == 0 && ComputeTypeViolations() == 0 && get<0>(ComputeUnmaintainedKm(buffer_threshold)) == 0)
          candidates.push_back(l);
      }

    }
  }
  #endif

  
  RemoveLocomotive(trip);   //I restore it as it was
  RemoveMaintenanceAtTrip(trip);
  AssignFullMaintenance();
}


#endif


void FRISCH_Solution::AssignMaintenanceForLocomotive(int locomotive)
{
  int this_trip = first_trip[locomotive];
  int last_maintenance_trip = -1;
  int maintenable_trip;
  int maintenable_arrival_or_departure;
  int this_previous_trip = -1;
  int this_previous_arrival_or_departure = -1;

  #ifdef RESCHEDULING_PROBLEM
  if(locomotive == -1)
  {
    for(unsigned int i = 0; i < trip_locomotive.size(); i++)
      if(trip_locomotive[i] == -1)
        RemoveMaintenanceAtTrip(i);
    return;
  }
  #endif

  if(used_locomotive[locomotive] == 0)
    return;

  long long int this_km = in.locomotive[locomotive].initial_kilometers_since_last_BU;
  

  while(this_trip >= 0)
  {
    RemoveMaintenanceAtTrip(this_trip);
    this_trip = next_trip[locomotive][this_trip];
  }

  this_trip = first_trip[locomotive];
  int current_arrival_or_departure = 1;
  while(this_trip >= 0)
  {
    if(this_previous_trip == -1)
      this_km += ComputeDistanceBetween(locomotive,-1,-1,this_trip,current_arrival_or_departure);
    else
      this_km += ComputeDistanceBetween(locomotive,this_previous_trip,this_previous_arrival_or_departure,this_trip,current_arrival_or_departure);

    #ifdef RESCHEDULING_PROBLEM      
    if(in.initial_solution_maintenances[in.trip_index_in_initial_solution[this_trip]] == current_arrival_or_departure)
    {
      //I try to set a maintenance
      if(MaintenanceFeasibleAtStation(locomotive,this_trip,current_arrival_or_departure))
      {
        AssignMaintenanceAtTrip(this_trip,current_arrival_or_departure);
        this_km = 0;   //I reset the km
        last_maintenance_trip = this_trip;
      }
    }
    #endif
    //If a maintenance is due
    if(this_km > in.locomotive_class[in.locomotive[locomotive].locomotive_class].max_kilometers_before_BU)
    {
      if(current_arrival_or_departure == 2)
      {
        maintenable_trip = this_trip;
        maintenable_arrival_or_departure = 1;
      }
      else if (current_arrival_or_departure == 1)
      {
        maintenable_trip = previous_trip[locomotive][this_trip];
        maintenable_arrival_or_departure = 2;
      }
      //I backtrack to find the last maintenable trip

      
      while(maintenable_trip != last_maintenance_trip)
      {
        if(MaintenanceFeasibleAtStation(locomotive,maintenable_trip,maintenable_arrival_or_departure))
          break;
        if(maintenable_arrival_or_departure == 1)
        {
          maintenable_trip = previous_trip[locomotive][maintenable_trip];
          maintenable_arrival_or_departure = 2;
        }
        else
        {
          maintenable_arrival_or_departure = 1;
        }
      }

      if(maintenable_trip != last_maintenance_trip)
      {
        AssignMaintenanceAtTrip(maintenable_trip,maintenable_arrival_or_departure);
        this_km = 0;   //I reset the km
        last_maintenance_trip = maintenable_trip;
      }
    }

    if(current_arrival_or_departure == 1)
    {
      current_arrival_or_departure = 2;
      this_previous_trip = this_trip;
      this_previous_arrival_or_departure = 1;
    }
    else
    {
      this_trip = next_trip[locomotive][this_trip];
      current_arrival_or_departure = 1;
      this_previous_arrival_or_departure = 2;
    }
  }
}



bool FRISCH_Solution::MaintenanceFeasibleAtStation(int loc, int this_trip, int arrival_or_departure) const
{
  int this_station;
  int this_loc_class;
  int this_previous_trip, this_next_trip = -2;
  int this_index_in_maintenance_point;
  bool found_maintenable_class;

  if(arrival_or_departure == 1)
  {
    this_station = in.section[in.train_trips[this_trip].section].origin;
    this_previous_trip = previous_trip[loc][this_trip];
  }
  else if(arrival_or_departure == 2)
  {
    this_station = in.section[in.train_trips[this_trip].section].destination;
    this_next_trip = next_trip[loc][this_trip];
  }
  else
    throw runtime_error("arrival_or_departure must be 1 or 2");
  
  //I check if it is a maintenance station
  if(!in.station[this_station].is_maintenance)
    return false;
  
  //I check if the locomotive class is maintenable at this station
  this_index_in_maintenance_point = in.station[this_station].index_in_maintenance_point;
  found_maintenable_class = false;
  for(unsigned int i = 0; i < in.maintenance_point[this_index_in_maintenance_point].maintainable_locomotive_classes.size(); i++)
  {
    this_loc_class = in.maintenance_point[this_index_in_maintenance_point].maintainable_locomotive_classes[i];
    if(in.locomotive[loc].locomotive_class == this_loc_class)
    {
      found_maintenable_class = true;
      break;
    }
  }

  if(!found_maintenable_class)
    return false;

  //I check if the locomotive can reach the station

  if(arrival_or_departure == 1)
  {
    if(!in.TimeForMaintenanceBetweenTrips(loc,this_previous_trip,this_trip))
      return false;
  }
  else if(arrival_or_departure == 2 && this_next_trip >= 0)
  {
    if(!in.TimeForMaintenanceBetweenTrips(loc,this_trip,this_next_trip))
      return false;
  }
  
  return true;
  
  
}

long long int FRISCH_Solution::DeadheadKM() const
{
  int loc;
  long long int tot_deadhead_km = 0;
  int trip;
  for(int l = 0; l < static_cast<int>(locomotives_in_use_indices.size()); l++)   //for every locomotive
  {
    loc = locomotives_in_use_indices[l];
    // cerr << endl << "used locomotive " << loc << endl;
    //Deadhead km from the depot to the first trip
    tot_deadhead_km += in.GetDeadheadFromDepot(loc,first_trip[loc]);
    // cerr << "        (depot -> " << first_trip[loc] << ") deadhead_km = " << static_cast<double>(tot_deadhead_km)/_DISTANCE_SCALE_FACTOR << endl;
    trip = first_trip[loc];
    while(next_trip[loc][trip] >= 0) //finché non arrivo all'ultimo trip
    {
      if(in.FeasibleByTimeTrips(trip,next_trip[loc][trip],loc)) //if it's not an ongoing conflict
        tot_deadhead_km += in.GetDeadhead(trip,next_trip[loc][trip]);
      // cerr << "        (" << trip << " -> " << next_trip[loc][trip] << ") deadhead_km = " << static_cast<double>(tot_deadhead_km)/_DISTANCE_SCALE_FACTOR << endl;
      trip = next_trip[loc][trip];
    }
    // cerr << "        new tot_deadhead_km = " << static_cast<double>(tot_deadhead_km)/_DISTANCE_SCALE_FACTOR << endl;
  }
  return tot_deadhead_km;
}

int FRISCH_Solution::Maintenances() const
{
  int maintenances = 0;
  for(int i = 0; i < static_cast<int>(in.train_trips.size()); i++)
    if(is_maintenance_done_at_trip[i] != 0)
      maintenances++;
  return maintenances;
}

long long int FRISCH_Solution::ComputeDistanceBetween(int locomotive, int trip1, int departure_or_arrival_trip1, int trip2, int departure_or_arrival_trip2) const
{

  int this_current_trip;
  long long int this_km = 0;
  int this_beginning_or_end;
  int this_next_trip;

  if(trip1 == -1) //If it's depot
  {
    this_current_trip = first_trip[locomotive];
    this_beginning_or_end = 1;
    this_km += in.GetDeadheadFromDepot(locomotive, this_current_trip);
  } 
  else
  {
    this_current_trip = trip1;
    this_beginning_or_end = departure_or_arrival_trip1;
  }

  while(this_current_trip != trip2 || this_beginning_or_end != departure_or_arrival_trip2)
  {
    if(this_beginning_or_end == 1)
      this_km += in.section[in.train_trips[this_current_trip].section].distance;  
    else //if(this_internal_beginning_or_end == 2)
    {
      this_next_trip = next_trip[locomotive][this_current_trip];
      this_km += in.GetDeadhead(this_current_trip,this_next_trip);
    }
    if(this_beginning_or_end == 1)
      this_beginning_or_end = 2;
    else if (this_beginning_or_end == 2)
    {
      this_current_trip = next_trip[locomotive][this_current_trip];
      this_beginning_or_end = 1;
    }
  }
  return this_km;
}


int FRISCH_Solution::LocomotivesWithMaintenance() const
{
  int locomotives_with_maintenance = 0;
  vector<bool> locomotive_with_maintenance(in.locomotive.size(),false);
  for(int i = 0; i < static_cast<int>(in.train_trips.size()); i++)
  {
    if(trip_locomotive[i] != -1 && is_maintenance_done_at_trip[i] != 0)
      locomotive_with_maintenance[trip_locomotive[i]] = true;
  }
  for(int i = 0; i < static_cast<int>(in.locomotive.size()); i++)
    if(locomotive_with_maintenance[i])
      locomotives_with_maintenance++;
  return locomotives_with_maintenance;
}

long long int FRISCH_Solution::MinInitialKMWithMaintenance() const
{
  long long int min_initial_km_with_maintenance = -1;
  vector<bool> locomotive_with_maintenance(in.locomotive.size(),false);
  for(int i = 0; i < static_cast<int>(in.train_trips.size()); i++)
    if(trip_locomotive[i] != -1 && is_maintenance_done_at_trip[i] != 0)
    {
      if(in.locomotive[trip_locomotive[i]].initial_kilometers_since_last_BU < min_initial_km_with_maintenance || min_initial_km_with_maintenance == -1)
        min_initial_km_with_maintenance = in.locomotive[trip_locomotive[i]].initial_kilometers_since_last_BU;
    }
  return min_initial_km_with_maintenance;
}


pair<long long int,long long int> FRISCH_Solution::MinMaxKMPerUsedLocomotive() const
{
  long long int min_km = -1;
  long long int max_km = -1;
  vector<long long int> km_by_locomotive(in.locomotive.size(),0);
  int this_trip,last_trip;
  for(int loc = 0; loc < static_cast<int>(in.locomotive.size()); loc++)   //for every locomotive
    if(used_locomotive[loc] > 0)  //if it's used
    {
      last_trip = -1;
      this_trip = first_trip[loc];
      do
      {
        if(last_trip == -1)
          km_by_locomotive[loc] += in.GetDeadheadFromDepot(loc,this_trip);
        else
          km_by_locomotive[loc] += in.GetDeadhead(last_trip,this_trip);
        km_by_locomotive[loc] += in.section[in.train_trips[this_trip].section].distance;

        last_trip = this_trip;
        this_trip = next_trip[loc][this_trip];
        
      } while (this_trip >= 0);
    }

  // I get min and max
  for(int loc = 0; loc < static_cast<int>(in.locomotive.size()); loc++)   //for every locomotive
  {
    if(used_locomotive[loc] > 0)  //if it's used
    {
      if(km_by_locomotive[loc] < min_km || min_km == -1)
        min_km = km_by_locomotive[loc];
      if(km_by_locomotive[loc] > max_km)
        max_km = km_by_locomotive[loc];
    }
  }

  return {min_km,max_km};
}

long long int FRISCH_Solution::ComputeConflicts() const
{
  long long int conflicts = 0;
  int trip = -1;
  for(int loc = 0; loc < static_cast<int>(in.locomotive.size()); loc++)   //for every locomotive
  {
    trip = -1;
    //MANAGE THE CASE OF STARTING TRIPPPPP! (in reschedulingggg)
    if(loc != -1)
    {
      if(used_locomotive[loc] > 0)  //if it's used
      {
        #ifdef RESCHEDULING_PROBLEM
        if(trip == -1)
        {
          if(is_maintenance_done_at_trip[first_trip[loc]] == 1)
          {
            if(!in.FeasibleByTimeStart(loc, first_trip[loc],true))
              conflicts ++;
          }
          else
          {
            if(!in.FeasibleByTimeStart(loc, first_trip[loc]))
              conflicts ++;
          }
        }
        #endif
        trip = first_trip[loc];
        while(next_trip[loc][trip] >= 0) //finché non arrivo all'ultimo trip
        {
          if(is_maintenance_done_at_trip[trip] == 2 || is_maintenance_done_at_trip[next_trip[loc][trip]] == 1)
          {
            if(!in.TimeForMaintenanceBetweenTrips(loc,trip,next_trip[loc][trip]))
              conflicts ++;
          }
          else
          {
            if(!in.FeasibleByTimeTrips(trip,next_trip[loc][trip],loc))
              conflicts ++;
          }
          trip = next_trip[loc][trip];
        }
      }
    }
  }
  return conflicts;
}


tuple<long long int, long long int> FRISCH_Solution::ComputeUnmaintainedKm(long long int max_unmaintened_km_threshold) const
{

  long long int unmaintened_km = 0;     //Km that exceed maintenance threshold.
  long long int overdue_km = 0;         //Km that exceed maintenance threshold, but are inside the tolerance interval, only used in rescheduling
  long long int this_loc_km = 0;
  long long int this_loc_threshold;
  int current_trip;
  int current_arrival_or_departure;
  int this_previous_trip = -1;
  int this_previous_arrival_or_departure = -1;


  for(int locomotive = 0; locomotive < static_cast<int>(in.locomotive.size()); locomotive++)   //for every locomotive
    if(used_locomotive[locomotive] > 0)  //if it's used
    {
      this_previous_trip = -1;
      this_previous_arrival_or_departure = -1;
      this_loc_km = in.locomotive[locomotive].initial_kilometers_since_last_BU;  //initial kilometers
      this_loc_threshold = in.locomotive_class[in.locomotive[locomotive].locomotive_class].max_kilometers_before_BU;
      #ifdef RESCHEDULING_PROBLEM
      this_loc_threshold += max_unmaintened_km_threshold;
      #endif

      current_trip = first_trip[locomotive];
      current_arrival_or_departure = 1;

      while(current_trip >= 0)
      {
        if(this_previous_trip == -1)
          this_loc_km += ComputeDistanceBetween(locomotive,-1,-1,current_trip,current_arrival_or_departure);
        else
          this_loc_km += ComputeDistanceBetween(locomotive,this_previous_trip,this_previous_arrival_or_departure,current_trip,current_arrival_or_departure);
      
        if(is_maintenance_done_at_trip[current_trip] == current_arrival_or_departure)
        {
          #ifdef RESCHEDULING_PROBLEM
          overdue_km     += max(0LL,this_loc_km - in.locomotive_class[in.locomotive[locomotive].locomotive_class].max_kilometers_before_BU);
          #endif
          unmaintened_km += max(0LL,this_loc_km - this_loc_threshold); 
          this_loc_km = 0;  //I reset the kilometers
        }
        //cerr << "locomotive " << locomotive << ", after trip " << current_trip << "/" << current_arrival_or_departure << ", with maintenance status: " << is_maintenance_done_at_trip[current_trip] << " has km = " << this_loc_km << endl;

        if(current_arrival_or_departure == 1)
        {
          current_arrival_or_departure = 2;
          this_previous_trip = current_trip;
          this_previous_arrival_or_departure = 1;
        }
        else
        {
          current_trip = next_trip[locomotive][current_trip];
          current_arrival_or_departure = 1;
          this_previous_arrival_or_departure = 2;
        }
      }
      #ifdef RESCHEDULING_PROBLEM
      overdue_km     += max(0LL,this_loc_km - in.locomotive_class[in.locomotive[locomotive].locomotive_class].max_kilometers_before_BU);
      #endif
      unmaintened_km += max(0LL,this_loc_km - this_loc_threshold); 
      }

  return make_tuple(unmaintened_km,overdue_km);
}

long long int FRISCH_Solution::ComputeTypeViolations() const
{
  long long int cc = 0;
  int this_locomotive;
  for(int j = 0 ; j < static_cast<int>(in.train_trips.size()); j++)
  {
    this_locomotive = trip_locomotive[j];
    if(this_locomotive != -1 && !in.trip_class_compatible[j][in.locomotive[this_locomotive].locomotive_class])
      cc++;
  }
  return cc;
}

#ifdef RESCHEDULING_PROBLEM
void FRISCH_Solution::SolveConflicts()
{
  solved_conflicts_at_beginning = 0;
  bool found_conflict_violation;
  while(ComputeConflicts() > 0 || ComputeTypeViolations() > 0)
  {
    found_conflict_violation = false;
    int trip = -1;
    int loc = 0;
    while(loc < static_cast<int>(in.locomotive.size()))   //for every locomotive
    {
      trip = -1;
      //MANAGE THE CASE OF STARTING TRIPPPPP! (in reschedulingggg)
      if(loc != -1)
      {
        if(used_locomotive[loc] > 0)  //if it's used
        {
          #ifdef RESCHEDULING_PROBLEM
          if(trip == -1 && !in.FeasibleByTimeStart(loc, first_trip[loc]))
          {
            found_conflict_violation = true;
            break;
          }
          #endif
          trip = first_trip[loc];
          while(next_trip[loc][trip] >= 0) //finché non arrivo all'ultimo trip
          {
            if(!in.FeasibleByTimeTrips(trip,next_trip[loc][trip],loc) || !in.trip_class_compatible[trip][in.locomotive[loc].locomotive_class])
            { 
              found_conflict_violation = true;
              break;
            }
            trip = next_trip[loc][trip];
          }
          if(found_conflict_violation)
            break;
        }
      }
      if(found_conflict_violation)
        break;
      loc++;
    }
    if(found_conflict_violation)
    {
      solved_conflicts_at_beginning++;
      if(trip == -1)
        trip = first_trip[loc];
      else
        trip = next_trip[loc][trip];
      RemoveLocomotive(trip);
      RemoveMaintenanceAtTrip(trip);
      AssignMaintenanceForLocomotive(loc);
    }
  }
}
#endif