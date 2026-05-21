#!/usr/bin/env python3
import os
import json
import argparse
import random
import time



class Station:
  def __init__(self):
    self.id = room_id
    self.name = capacity
    self.x
    self.y 


class Section:
  def __init__(self):
    self.from
    self.to
    self.distance

class TrainSection:
def __init__(self):
    self.from
    self.to
    self.distance

class Train:
   

class instance_parameters:
   def __init__(self):
      self.density = 0.5

def random_instance_from_network(network, output_file, ow, num_trips,num_locomotivess, only_one_class,initial_km):
   print("parsed")
   return





if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Integrated Railway Rescheduling Generator')
  parser.add_argument('--network', '-n', required=True, type=str, help='network file')
  parser.add_argument('--output', '-o', required=False, type=str, help='output file, if not given prints instance on stdout')
  parser.add_argument('--overwrite', '-w', required=False, action='store_true', help='overwrite the output file if it exists')
  parser.add_argument('--trips', '-t', required=False, type=float, default = 0, help='num trips')
  parser.add_argument('--locomotives', '-l', required=False, type=int, default = 0, help='num locomotives')
  parser.add_argument('--only_one_class', '-c', required=False, action='store_true', help='only one class')
  parser.add_argument('--initial_km', '-i', required=False, type=int, default=-1, help='initial km (default = RANDOM)')


  args = parser.parse_args()


  random_instance_from_network(args.network,args.output,args.overwrite,args.trips,args.locomotives,args.only_one_class,args.initial_km)

  