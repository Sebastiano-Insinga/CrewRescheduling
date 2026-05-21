#! /usr/bin/env python3
from rrspgenerator import RRSPGenerator
import argparse
import os
import json
import math

#2024-04-03: only a mask for the future generator, still to be written

def main(args):
  """Execute the generator """ 
  generator = IHGenerator()
  if args.patients_density is not None:
    generator.set_parameter("rolling_stocks", args.rolling_stocks)
  elif args.patients is not None:
    generator.set_parameter("crew_members", args.crew_members)
  if args.rescheduling is not None:
    generator.set_parameter("rescheduling", args.rescheduling)
    if args.operating_theaters is not None:
      generator.set_parameter("disruption_time", args.disruption_time)
    if args.rooms is not None:
      generator.set_parameter("disruption_severity", args.disruption_severity)
    
  generated_data = generator.generate_random_data()
  
  if args.output is not None:
    #verify if args.output exists
    if os.path.exists(args.output) and not args.overwrite:
      print("Output file already exists. Please remove it or change the name.")
      return

    with open(args.output, "w") as json_file:
      json.dump(generated_data, json_file, indent=2)
  else:
    print(json.dumps(generated_data, indent=2))

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Integrated Railway Rescheduling Generator')
  
  parser.add_argument('--output', '-o', required=False, type=str, help='output file, if not given prints instance on stdout')
  #scheduling parameters
  parser.add_argument('--rolling_stocks', '-r', required=False, type=int, help='number of available rolling stock')
  parser.add_argument('--crew_members', '-c', required=False, type=int, help='number of crew members')
  parser.add_argument('--rescheduling', '-rescheduling', required=False, action='store_true', help='if it is set, the instance is for the RESCHEDULING problem. Otherwile it is for the SCHEDULING problem.')
  #rescheduling parameters
  parser.add_argument('--disruption_time', '-dt', required=False, type=int, help='time at which the disruption happened') 
  parser.add_argument('--disruption_severity', '-ds', required=False, type=int, help='ratio of trips affected by the disruption')
  
  parser.add_argument('--overwrite', '-ow', required=False, action='store_true', help='overwrite the output file if it exists')
  
  #f = '%(asctime)s|%(levelname)s|%(name)s|%(message)s'
  #logging.basicConfig(level=logging.INFO, format=f)
  main(args)
