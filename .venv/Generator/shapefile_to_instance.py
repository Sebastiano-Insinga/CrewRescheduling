#!/usr/bin/env python3
import geopandas as gpd
import networkx as nx
import os
import json
import argparse
import random
import time

def shapefile_to_network_json(shapefile_path, output_json_path, ow, maintenance_fraction, num_locomotive_classes):
  """
  Converts a shapefile to a network JSON format where:
    - Nodes are "stations" with numeric "id" and "name".
    - Links are "sections" with numeric "id", "name", "origin", "destination", and "distance".

  Parameters:
      shapefile_path (str): Path to the input shapefile.
      output_json_path (str): Path to save the output JSON file.
  """
  # Read the shapefile
  gdf = gpd.read_file(shapefile_path)
  
  # Create a unique set of stations
  stations = {}
  for _, row in gdf.iterrows():
    von_id = row['VON_ID']
    von_name = row['VON_BF']
    nach_id = row['NACH_ID']
    nach_name = row['NACH_BF']
    
    # Add both the origin and destination to the stations
    if von_id not in stations:
      stations[von_id] = {"id": von_id, "name": von_name}
    if nach_id not in stations:
      stations[nach_id] = {"id": nach_id, "name": nach_name}
    
  # Create the sections
  sections = []
  for index, row in gdf.iterrows():
    sections.append({
      "id": row['LINK_ID'],  # Unique link ID
      "name": row['NAME'],        # Name of the link
      "origin": row['VON_ID'],
      "destination":row['NACH_ID'],
      "distance": row['DISTANCE']
    })

  # Generate random locomotive classes
  locomotive_classes = []
  for i in range(1, num_locomotive_classes + 1):
      locomotive_classes.append({
          "id": "loc_"+ str(i),
          "name": f"LC_{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=2))}{i}",
          "max_kilometers_before_maintenance": random.uniform(15000, 25000),  # Random range
          "maintenance_duration": random.randint(7200, 14400),  # Between 2 and 4 hours in seconds
          "deadhead_speed": random.randint(50, 150)  # Speed between 50 and 150 km/h
      })
    
  loc_ids = [lc["id"] for lc in locomotive_classes]
  maintenance_points = []
  counter = 0
  if(maintenance_fraction > 0.0):
    # Randomly select maintenance points
    station_ids = list(stations.keys())
    num_maintenance_points = max(1, int(len(station_ids) * maintenance_fraction))
    maintenance_station_ids = random.sample(station_ids, num_maintenance_points)
    
    for idx, station_id in enumerate(maintenance_station_ids):
      maintenance_points.append({
        "id": str("man_"+station_id),  # Use the station's ID as the maintenance point ID
        "name": f"MaintenancePoint{idx}",
        "station": station_id,
        "maintainable_locomotive_classes": random.sample(loc_ids,random.randint(1, len(locomotive_classes)))
  
      })
    
    counter = counter + 1

  # Construct the JSON structure
  network = {
    "stations": list(stations.values()),
    "sections": sections
  }

  if(maintenance_fraction > 0):
    network["maintenance_points"] = maintenance_points
  if(num_locomotive_classes > 0):
    network["locomotive_classes"] = locomotive_classes
 
  
  if output_json_path is not None:
  #verify if args.output exists
    if os.path.exists(args.output) and not ow:
      print("Output file already exists. Please remove it or change the name.")
      return

    with open(args.output, "w") as json_file:
      json.dump(network, json_file, indent=2)
  else:
    print(json.dumps(network, indent=2))

  print(f"Stations: {len(stations)}, Sections: {len(sections)}")
  print(f"Network JSON saved to {output_json_path}")

  


if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Integrated Railway Rescheduling Generator')
  parser.add_argument('--shapefile', '-s', required=True, type=str, help='shapefile file')
  parser.add_argument('--output', '-o', required=False, type=str, help='output file, if not given prints instance on stdout')
  parser.add_argument('--overwrite', '-w', required=False, action='store_true', help='overwrite the output file if it exists')
  parser.add_argument('--maintenance_fraction', '-m', required=False, type=float, default = 0, help='maintenance stations')
  parser.add_argument('--num_locomotive_classes', '-l', required=False, type=int, default = 0, help='num_locomotive_classes')
  
  args = parser.parse_args()

  if args.maintenance_fraction > 0.0 and args.num_locomotive_classes == 0:
    print(f"maintenance_fraction > 0.0 but num_locomotive_classes == 0")
    exit(1)



  shapefile_to_network_json(args.shapefile,args.output,args.overwrite,args.maintenance_fraction,args.num_locomotive_classes)

  
  #f = '%(asctime)s|%(levelname)s|%(name)s|%(message)s'
  #logging.basicConfig(level=logging.INFO, format=f)
