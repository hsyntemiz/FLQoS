#To run this traffic generator, from Mininet CLI:
#mininet> py execfile("flowGenerator_10mb.py") 

import random
import numpy as np
import subprocess

#Node lists of Mininet
nodes=[h1,h2,h3]

subprocess.call("rm ./log/*", shell=True)
subprocess.call("rm ./logtxt/*", shell=True)

print './log and ./logtxt folders cleaned!'


BE_COUNT=60 # COUNT of Best Effort Flow (LOW PRIO Traffic)
BW_COUNT=10 # COUNT of BW Flow (MID PRIO Traffic)
DELAY_COUNT=10 # COUNT of Delay Flow (HIGH PRIO Traffic)
RUN_TIME=60 # Execution Time of Simulation.
MIN_DURATION=20 # Minimum duration for a flow
MAX_DURATION=30 # Maximum duration for a flow
NODE_COUNT=2 # Determine how many of nodes to be used. For this, Use 2 of 3 {h1,h2,h3} nodes.



f = open('myfile', 'w')

#Create Same Traffic Matrix by fixed seed.
random.seed(321) 
np.random.seed(42)


def myTraffic(start,src,dst,port,duration,delay):
	if 6000<port<7000:
		qos_type=1
	if 7000<port<8000:
		qos_type=0
	if 999<port<2001:
		qos_type=2
		
	print 'VOIP STARTS %s to %s: port:%s' % (src.IP(), dst.IP(),port)
	
	#Reciever Report File Name with characteristic SRC/DST IP and PORT.
	rec_report='./log/%s_reciever_reportVOIP_%s_to_%s_port_%s_%s.log' % (start,src.IP(), dst.IP(),port,qos_type)
	
	#Sender Report File Name with characteristic SRC/DST IP and PORT.
	send_report='./log/%s_sender_reportVOIP_%s_to_%s_port_%s_%s.log' % (start,src.IP(), dst.IP(),port,qos_type)
	
	#Signalling port for DITG
	signal_port=port+9000
	
	#Source node Command
	cmd_src='../D-ITG/bin/ITGSend -T UDP -rp %s -a %s -c 140 -C 100 -t %s -Sdp %s -x %s &' % (port,dst.IP(),duration*1000,signal_port,rec_report)
	#Destination node Command
	cmd_dst='../D-ITG/bin/ITGRecv -Sp %s &' % (signal_port)
	
	#Run the command on Mininet DST host.
	dst.cmd(cmd_dst)
	
	#Run the command on Mininet SRC host.
	src.cmd(cmd_src)
	
	#LOG executed commands to Screen.
	print cmd_dst
	print cmd_src
	
#Check if the socket is already created.
def socket_exist(traffic, src_host, dst_host, dst_port):
	#print 'traffic-socket: %s' % (traffic)
	
	lent=len(traffic)
	for   i in range(lent):
		pair=traffic[i]
		(start_time,src,dst,port,duration,delay)=pair
		
		if [dst_host==dst ] and dst_port==port:
			return 'match'
	
	return 'correct'
####################################################################
####################################################################
print '####################################################################'

traffic={}
sorted_start=sorted(np.random.randint(RUN_TIME, size=BE_COUNT))
durations=np.random.randint(low=MIN_DURATION,high=MAX_DURATION, size=BE_COUNT)
delays=np.random.randint(low=0,high=5, size=BE_COUNT)
j=0
while j < BE_COUNT:
    src = nodes[random.randint(0, NODE_COUNT-1)]
    dst = nodes[random.randint(0, NODE_COUNT-1)]
    port=np.random.randint(low=1000,high=2000)

    match='false'
    
    if socket_exist(traffic,src, dst,port) is 'match' or src == dst :
	print 'SOCKET_EXIST ERROR %s %s === j:%s' % (dst,port,j)
    else:
	    
	start_time=sorted_start[j]
	duration=durations[j]
	delay=delays[j]
	traffic[j]=(start_time,src,dst,port,duration,delay)
	j=j+1
	app='voip'
	str="%s, %s, %s %s, %s, %s, %s, %s\n" % (start_time,src,dst,port,duration,delay,app,match) 
	f.write(str) 

print '####################################################################'

####################################################################
# BW traffic port= 6200-6209

traffic1={}
sorted_start1=sorted(np.random.randint(RUN_TIME, size=BW_COUNT))
durations=np.random.randint(low=MIN_DURATION,high=MAX_DURATION, size=BW_COUNT)
delays=np.random.randint(low=0,high=5, size=BW_COUNT)

j=0
while j < BW_COUNT:
    src = nodes[random.randint(0, NODE_COUNT-1)]
    dst = nodes[random.randint(0, NODE_COUNT-1)]
    port=np.random.randint(low=6200,high=6210)

    match='false'
    
    if socket_exist(traffic1,src, dst,port) is 'match' or src == dst :
	print 'SOCKET_EXIST ERROR %s %s === j:%s' % (dst,port,j)
    else:
	    
	
	start_time=sorted_start1[j]
	duration=durations[j]
	delay=delays[j]
	traffic1[j]=(start_time,src,dst,port,duration,delay)
	j=j+1
	app='voip'
	str="%s, %s, %s %s, %s, %s, %s, %s\n" % (start_time,src,dst,port,duration,delay,app,match) 
	f.write(str) 

print '####################################################################'
####################################################################
# delay traffic port= 7200-7209
traffic2={}
sorted_start2=sorted(np.random.randint(RUN_TIME, size=DELAY_COUNT))
durations=np.random.randint(low=MIN_DURATION,high=MAX_DURATION, size=DELAY_COUNT)
delays=np.random.randint(low=0,high=5, size=DELAY_COUNT)

j=0
while j < DELAY_COUNT:
    src = nodes[random.randint(0, NODE_COUNT-1)]
    dst = nodes[random.randint(0, NODE_COUNT-1)]
    port=np.random.randint(low=7200,high=7210)

    match='false'
    
    if socket_exist(traffic2,src, dst,port) is 'match' or src == dst :
	print 'SOCKET_EXIST ERROR %s %s === j:%s' % (dst,port,j)
    else:
	    
	
	start_time=sorted_start2[j]
	duration=durations[j]
	delay=delays[j]
	traffic2[j]=(start_time,src,dst,port,duration,delay)
	j=j+1
	app='voip'
	str="%s, %s, %s %s, %s, %s, %s, %s\n" % (start_time,src,dst,port,duration,delay,app,match) 
	f.write(str) 

print '####################################################################'
f.close()
print '####################################################################'

#simulation schedule duration is currently 30  sec. Max Simulation 30+30 Sec.
j=0 # BE traffic
k=0
m=0
print sorted_start
print sorted_start1
print sorted_start2
for i in range(RUN_TIME+15):
	time.sleep(1)
	print 'Second: %s' % (i)
	
	if i in sorted_start:
		print '++++++ Best Effort'
		count=sorted_start.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic[j]

			myTraffic(start_time,src,dst,port,duration,delay)

			count=count-1
			j=j+1
			
	if i in sorted_start1:
		print '$$$$$$ BW Traffic'
		count=sorted_start1.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic1[k]

			myTraffic(start_time,src,dst,port,duration,delay)
			count=count-1
			k=k+1

	if i in sorted_start2:
		print '###### Delay Traffic'
		count=sorted_start2.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic2[m]

			myTraffic(start_time,src,dst,port,duration,delay)
			count=count-1
			m=m+1
	

print "flows are done !!!"

#Wait for completion of last flows.
time.sleep(45)

#Convert DITG log files to Readable format.
execfile("ditgDec.py")
print 'txt conversion completed!'
time.sleep(5)

#Combine all DITG logs into one summerized CSV file.
execfile("excel.py")

print 'Statistic.csv is created!'
print "Good bye!"





