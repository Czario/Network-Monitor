#!/usr/bin/env python2.7
# This script requires asound and espeak be installed in the system

import time
import datetime
import os
import sys
import select
import subprocess
import json
from pprint import pprint
import argparse
from scapy.all import *
import pyttsx
# from twilio.rest import TwilioRestClient

OKGREEN = '\033[92m'
FAIL = '\033[91m'
ENDC = '\033[0m'
ERROR = FAIL+"ERROR: "+ENDC
OKBLUE = '\033[94m'

connected = {} # { "MAC": "time connected"}
mac_defs = {} #  { "MAC": "device name"}
black_list = [] # MAC addresses to exclude from monitoring
disconnect_time = 900 # time to wait before client is rendered disconnected
log_file = "unknown_connections.log" # log file for unkown devices
checking = False
_speak = False

def speak(say_this):
  global _speak
  if _speak:
    os.system('aplay blip.wav -R 1')
    speech_engine = pyttsx.init()
    speech_engine.say(say_this)
    speech_engine.runAndWait()

def get_lan_ip():
  """
  Gets the current LAN's IP by connecting to google and extracting the IP from
  the socket.
  """
  s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  s.connect(("google.com", 80))
  ip = s.getsockname()
  s.close()
  return ip[0]

def get_gateway_ip(gateway_ip=None):
  # Gets the gateway ip. Returns [gateway_ip, ip_range]
  myip = get_lan_ip()
  ip_list = myip.split('.')
  del ip_list[-1]
  ip_list.append('*')
  ip_range = '.'.join(ip_list)
  del ip_list[-1]
  ip_list.append('1')# assumed default gateway is "XXX.XXX.XXX.1"
  if gateway_ip is not None:
    # print "Gateway IP provided as "+gateway_ip
    return [gateway_ip, ip_range]
  else:
    # print "Gateway IP provided as "+'.'.join(ip_list)
    return ['.'.join(ip_list), ip_range]

def get_ip_macs(ips):
  """
  Returns a list of tupples containing the (ip, mac address)
  of all of the computers on the network
  """
  answers, uans = arping(ips, verbose=0)
  res = []
  for answer in answers:
    mac = answer[1].hwsrc
    ip  = answer[1].psrc
    res.append((ip, mac))
    # res.append(specific_target)
  return res

def load_macs(filename):
    """
    Loads devics and their corresponding MAC addresses from a given json file
    """
    global mac_defs
    with open(filename) as data_file:
        data = json.load(data_file)
    for each in data:
        mac_defs[each['MAC'].lower()] = each['device']

def check_connected(gateway_ip,ip_range):
    global mac_defs, connected,checking, black_list
    devices = get_ip_macs(ip_range)
    subprocess.call('clear', shell=True) # clear the shell
    i = 0
    for device in devices:
        if device[1] not in black_list:
           if device[1] in mac_defs.keys():
               print '%s)\t%s\t%s\t%s%s' % (i, device[0],device[1],mac_defs[device[1]],ENDC)
               if device[1] not in connected.keys():
                   # notify
                   if checking:
                       print OKGREEN+mac_defs[device[1]] + " just connected!"+ENDC
                       speak(mac_defs[device[1]]+"\" ")
                # update time stamp
               connected[device[1]] = datetime.now()
           else:
            # unkown device
               print '%s)\t%s\t%s' % (i, device[0], device[1] )
               speak("foreign device detected")
               log_foreign_access(datetime.now().strftime("%Y-%m-%d %H:%M:%S")+" "+device[1])

           i+=1
    checking =True

def monitor_loop(gateway_ip, ip_range):
    while True:
        try:
            check_connected(gateway_ip, ip_range)
            time.sleep(5)
            check_for_disconnections()
        except KeyboardInterrupt:
            print "shutting down..."
            sys.exit()

def check_for_disconnections():
    """
    checks for disconnections
    """
    global connected, mac_defs, disconnect_time
    to_be_removed = []
    for each in connected:
        diff = datetime.now() - connected[each]
        diff = diff.total_seconds()
        print(OKBLUE +"%20s%20s"+ENDC) % (mac_defs[each], str(diff))
        if diff >= disconnect_time:
            to_be_removed.append(each)
    for each in to_be_removed:
        connected.pop(each)
        print FAIL+mac_defs[each] +" disconnected "+ENDC

def load_blacklist(filename):
    """
    loads MAC addresses from a file will be added to the black_list. entries in
    the text file should be 1 MAC address per line
    """
    global black_list
    with open(filename) as data_file:
        for each in data_file:
            black_list.append(each)


# def send_text(msg):
#     client = TwilioRestClient()
#     client.messages.create(from_='+16313537388',
#                        to='+15162590083',
#                        body=msg)

def log_foreign_access(entry):
    """
    logs access from foreign devices to a log file with timestamp and mac address
    """
    global log_file
    # create file if not exists
    if not os.path.exists(log_file):
        open(log_file, 'w').close()
    with open(log_file, "a") as myfile:
        myfile.write(entry+'\n')

if __name__=="__main__":
    gateway_ip = None
    ip_range = None
    parser = argparse.ArgumentParser()
    parser.add_argument("-g", help="specify a gateway. default gateway will be 192.168.1.1") #gateway
    parser.add_argument("-f", help='specify a JSON file with device names and their corresponding MAC addresses. Format should be [{"device": "some device", "MAC":"some mac"}]. default will be mac_addresses.json') #file with mac addresses
    parser.add_argument("-e", help='specify a text file containing MAC addresses to exclude from monitoring. text file must have one MAC address per line. default file will be blacklist.txt') #text file with mac address exclusions
    parser.add_argument("-t", help="time to wait before a given client is considered disconnected. (seconds)") #time to wait before client is considered discon.
    args = parser.parse_args()

    if args.g is not None:
        gateway_ip = args.g
        ip_range = ".".join(gateway_ip.split('.')[0:-1]) + '.'+'*'
    else:
        gateway_ip, ip_range = get_gateway_ip()
    if args.f is not None:
        load_macs(args.f)
    else:
        load_macs('mac_addresses.json')
    if args.e is not None:
        load_blacklist(args.e)
    if args.t is not None:
        global disconnect_time
        disconnect_time = args.t

    monitor_loop(gateway_ip,ip_range)
