import numpy as np
import csv
import subprocess

from datetime import datetime
#Average_bitrate.txt  Average_delay.txt  Average_jitter.txt  avg_jitter.txt  Bytes_received.txt  Packets_dropped.txt  total_packets.txt


#Adding interface Queue
print "start"
subprocess.call("bash ./datamine.sh", shell=True)
print "end"
    
with open('./results/Flow_desc.txt') as f0:
    lines0= [line.rstrip('\n') for line in open('./results/Flow_desc.txt')]

with open('./results/Average_bitrate.txt') as f1:
    lines1= [line.rstrip('\n') for line in open('./results/Average_bitrate.txt')]
    
with open('./results/Average_delay.txt') as f2:
    lines2 = [line.rstrip('\n') for line in open('./results/Average_delay.txt')]
    
with open('./results/Average_jitter.txt') as f3:
    lines3 = [line.rstrip('\n') for line in open('./results/Average_jitter.txt')]

with open('./results/Bytes_received.txt') as f4:
    lines4 = [line.rstrip('\n') for line in open('./results/Bytes_received.txt')]

with open('./results/Packets_dropped_n.txt') as f5:
    lines5 = [line.rstrip('\n') for line in open('./results/Packets_dropped_n.txt')]
    
with open('./results/Packets_dropped_p.txt') as f6:
    lines6 = [line.rstrip('\n') for line in open('./results/Packets_dropped_p.txt')]
    
with open('./results/total_packets.txt') as f7:
    lines7 = [line.rstrip('\n') for line in open('./results/total_packets.txt')]
    
with open('./results/qos_type.txt') as f8:
    lines8 = [line.rstrip('\n') for line in open('./results/qos_type.txt')]



filename='statistics_%s.csv' %( datetime.now().strftime('%Y-%m-%d--%H.%M.%S'))


header='Flow_Desc,Average_bitrate(Kbit/s),Average_delay(sec),Average_jitter(sec),Bytes_received,Packets_dropped,Packets_drop(%),total_packets,qos_type'
np.savetxt(filename, np.column_stack((lines0,lines1, lines2,lines3,lines4,lines5,lines6,lines7,lines8)), delimiter=",", fmt='%s', header=header)

