#from netaddr import IPNetwork
#from netaddr import *
import netaddr as net
import ipaddress
import random
import numpy as np
import subprocess


#All mininet Nodes
nodes=[h1,h1a,h1b,h2,h2a,h2b,h3,h3a,h3b,h4,h4a,h4b,h5,h5a,h5b,h6,h6a,h6b,h7,h7a,h7b,h8,h8a,h8b,h9,h9a,h9b,h10,h10a,h10b,h11,h11a,h11b,h12,h12a,h12b]
src_nodes=[h3,h3a,h3b]
dst_nodes=[h10,h10a,h10b]

subprocess.call("rm ./log/*", shell=True)
subprocess.call("rm ./logtxt/*", shell=True)
#os.system('rm -rf ./logtxt/ && mkdir ./logtxt/')

print './log and ./logtxt folders cleaned!'

#print net.IPNetwork("128.233.17.12/255.255.0.0") 


BE_COUNT=0
BW_COUNT=0
DELAY_COUNT=0

BE_COUNT_A=12
BW_COUNT_A=12
DELAY_COUNT_A=0

RUN_TIME_A=60
RUN_TIME=60

MIN_DURATION=60
MAX_DURATION=70

NODE_COUNT=36
NODE_COUNT_A=3

f = open('myfile', 'w')



#Create Same Traffic Matrix
random.seed(321)
np.random.seed(42)

def voip2(start,src,dst,port,duration,delay):
	if 4000<port<5000:
		qos_type=1
	if 8000<=port<=9000:
		qos_type=0
	if 999<port<2001:
		qos_type=2
	test=False
        if 4899<port<5000:
                test=True
        elif 8899<port<=9000:
                test=True
        elif 1899<port<2001:
                test=True
	
	if test:

		print 'VOIP STARTS %s to %s: port:%s' % (src.IP(), dst.IP(),port)
		rec_report='./log/X%s_reciever_reportVOIP_%s_to_%s_port_%s_%s.log' % (start,src.IP(), dst.IP(),port,qos_type)
		send_report='./log/X%s_sender_reportVOIP_%s_to_%s_port_%s_%s.log' % (start,src.IP(), dst.IP(),port,qos_type)
	
	else:
		print 'VOIP STARTS %s to %s: port:%s' % (src.IP(), dst.IP(),port)
                rec_report='./log/%s_reciever_reportVOIP_%s_to_%s_port_%s_%s.log' % (start,src.IP(), dst.IP(),port,qos_type)
                send_report='./log/%s_sender_reportVOIP_%s_to_%s_port_%s_%s.log' % (start,src.IP(), dst.IP(),port,qos_type)


	signal_port=port+9000
	
	#cmd_src='../D-ITG/bin/ITGSend -T UDP -rp %s -a %s -c 2000  -C 200 -t %s -Sdp %s -l %s -x %s &' % (port,dst.IP(),duration*1000,signal_port, send_report,rec_report)
	cmd_src='../D-ITG/bin/ITGSend -T UDP -rp %s -a %s -c 1000 -C 60 -t %s -Sdp %s -x %s &' % (port,dst.IP(),duration*1000,signal_port,rec_report)

	
	#cmd_dst='../D-ITG/bin/ITGRecv -Sp %s &' % (signal_port)
	cmd_dst='../D-ITG/bin/ITGRecv -Sp %s &' % (signal_port)
	
	dst.cmd(cmd_dst)
	src.cmd( cmd_src)
	




global socket_exist
def socket_exist(traffic, src_host, dst_host, dst_port):


	lent=len(traffic)
	for   i in range(lent):
		pair=traffic[i]
		(start_time,src,dst,port,duration,delay)=pair
		#src_host == src or 
		if [dst_host==dst ] and dst_port==port:
			return 'match'
	
	return 'correct'
		
	
	

####################################################################
####################################################################




####################################################################
####################################################################
print '####################################################################'

traffic={}
sorted_start=sorted(np.random.randint(RUN_TIME, size=BE_COUNT))
durations=np.random.randint(low=MIN_DURATION,high=MAX_DURATION, size=BE_COUNT)
delays=np.random.randint(low=0,high=5, size=BE_COUNT)
print '1'
j=0
while j < BE_COUNT:
    #print net.IPNetwork("128.233.17.12/255.255.0.0") 

    src = nodes[random.randint(0, NODE_COUNT-1)]
    dst = nodes[random.randint(0, NODE_COUNT-1)]
    port=np.random.randint(low=1000,high=1899)

    match='false'
    src_=src.IP()+"/255.255.255.0"
    dst_=dst.IP()+"/255.255.255.0"
    
 
    
    if socket_exist(traffic,src, dst,port) is 'match' or src == dst or net.IPNetwork(src_) == net.IPNetwork(dst_):
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
	print '1 OK' 

print '####################################################################'
print '####################################################################'

####################################################################
####################################################################
print '####################################################################'

traffic_a={}
sorted_start_a=sorted(np.random.randint(RUN_TIME_A, size=BE_COUNT_A))
durations=np.random.randint(low=MIN_DURATION,high=MAX_DURATION, size=BE_COUNT_A)
delays=np.random.randint(low=0,high=5, size=BE_COUNT_A)
print '1a'
j=0
while j < BE_COUNT_A:
    #print net.IPNetwork("128.233.17.12/255.255.0.0") 

    src = src_nodes[random.randint(0, NODE_COUNT_A-1)]
    dst = dst_nodes[random.randint(0, NODE_COUNT_A-1)]
    port=np.random.randint(low=1900,high=2000)

    match='false'
    src_=src.IP()+"/255.255.255.0"
    dst_=dst.IP()+"/255.255.255.0"
    
 
    
    if socket_exist(traffic_a,src, dst,port) is 'match' or src == dst or net.IPNetwork(src_) == net.IPNetwork(dst_):
	print 'SOCKET_EXIST ERROR %s %s === j:%s' % (dst,port,j)
    else:
	    
	start_time=sorted_start_a[j]
	duration=durations[j]
	delay=delays[j]
	traffic_a[j]=(start_time,src,dst,port,duration,delay)
	j=j+1
	app='voip'
	str="%s, %s, %s %s, %s, %s, %s, %s\n" % (start_time,src,dst,port,duration,delay,app,match) 
	f.write(str) 

print '####################################################################'
print '####################################################################'

####################################################################
####################################################################
####################################################################
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
    port=np.random.randint(low=4000,high=4899)

    match='false'
    src_=src.IP()+"/255.255.255.0"
    dst_=dst.IP()+"/255.255.255.0"
    
    if socket_exist(traffic1,src, dst,port) is 'match' or src == dst or net.IPNetwork(src_) == net.IPNetwork(dst_):
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
####################################################################
# BW traffic port= 6200-6209

traffic1_a={}

sorted_start1_a=sorted(np.random.randint(RUN_TIME_A, size=BW_COUNT_A))
durations=np.random.randint(low=MIN_DURATION,high=MAX_DURATION, size=BW_COUNT_A)
delays=np.random.randint(low=0,high=5, size=BW_COUNT_A)

j=0
while j < BW_COUNT_A:
    src = src_nodes[random.randint(0, NODE_COUNT_A-1)]
    dst = dst_nodes[random.randint(0, NODE_COUNT_A-1)]
    port=np.random.randint(low=4900,high=4999)

    match='false'
    src_=src.IP()+"/255.255.255.0"
    dst_=dst.IP()+"/255.255.255.0"
    
    if socket_exist(traffic1_a,src, dst,port) is 'match' or src == dst or net.IPNetwork(src_) == net.IPNetwork(dst_):
	print 'SOCKET_EXIST ERROR %s %s === j:%s' % (dst,port,j)
    else:
	    
	
	start_time=sorted_start_a[j]
	duration=durations[j]
	delay=delays[j]
	traffic1_a[j]=(start_time,src,dst,port,duration,delay)
	j=j+1
	app='voip'
	str="%s, %s, %s %s, %s, %s, %s, %s\n" % (start_time,src,dst,port,duration,delay,app,match) 
	f.write(str) 

print '####################################################################'
####################################################################
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
    port=np.random.randint(low=8000,high=8899)

    match='false'
    src_=src.IP()+"/255.255.255.0"
    dst_=dst.IP()+"/255.255.255.0"
    
    if socket_exist(traffic2,src, dst,port) is 'match' or src == dst or net.IPNetwork(src_) == net.IPNetwork(dst_):
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

####################################################################
####################################################################
# delay traffic port= 7200-7209
traffic2_a={}

sorted_start2_a=sorted(np.random.randint(RUN_TIME_A, size=DELAY_COUNT_A))
durations=np.random.randint(low=MIN_DURATION,high=MAX_DURATION, size=DELAY_COUNT_A)
delays=np.random.randint(low=0,high=5, size=DELAY_COUNT_A)

j=0
while j < DELAY_COUNT_A:
    src = src_nodes[random.randint(0, NODE_COUNT_A -1)]
    dst = dst_nodes[random.randint(0, NODE_COUNT_A -1)]
    port=np.random.randint(low=8900,high=8999)

    match='false'
    src_=src.IP()+"/255.255.255.0"
    dst_=dst.IP()+"/255.255.255.0"
    
    if socket_exist(traffic2_a,src, dst,port) is 'match' or src == dst or net.IPNetwork(src_) == net.IPNetwork(dst_):
	print 'SOCKET_EXIST ERROR %s %s === j:%s' % (dst,port,j)
    else:
	    
	
	start_time=sorted_start2_a[j]
	duration=durations[j]
	delay=delays[j]
	traffic2_a[j]=(start_time,src,dst,port,duration,delay)
	j=j+1
	app='voip'
	str="%s, %s, %s %s, %s, %s, %s, %s\n" % (start_time,src,dst,port,duration,delay,app,match) 
	f.write(str) 

print '####################################################################'
f.close()
print '####################################################################'
#print traffic2 
####################################################################
####################################################################
####################################################################

#simulation schedule duration is currently 30  sec. Max Simulation 30+30 Sec.
j=0 # BE traffic
j_=0
k=0
k_=0
m=0
m_=0

print 'BE_base:%s' % sorted_start
print 'BE_test:%s' % sorted_start_a
print 'MQ_base:%s' % sorted_start1
print 'MQ_test:%s' % sorted_start1_a
print 'HQ_base:%s' % sorted_start2
print 'HQ_test:%s' % sorted_start2_a
for i in range(RUN_TIME):
	time.sleep(1)
	print 'Second: %s' % (i)
	######################################

	if i in sorted_start:
		print '++++++ Best Effort'
		count=sorted_start.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic[j]

			voip2(start_time,src,dst,port,duration,delay)
			count=count-1
			j=j+1
			
	if i in sorted_start_a:
		print '++++++ Best Effort'
		count=sorted_start_a.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic_a[j_]

			voip2(start_time,src,dst,port,duration,delay)
			count=count-1
			j_=j_+1
	######################################
	if i in sorted_start1:
		print '$$$$$$ BW Traffic'
		count=sorted_start1.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic1[k]

			voip2(start_time,src,dst,port,duration,delay)
			count=count-1
			k=k+1
			
	if i in sorted_start1_a:
		print '$$$$$$ BW Traffic'
		count=sorted_start1_a.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic1_a[k_]

			voip2(start_time,src,dst,port,duration,delay)
			count=count-1
			k_=k_+1
	######################################

	if i in sorted_start2:
		print '###### Delay Traffic'
		count=sorted_start2.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic2[m]

			voip2(start_time,src,dst,port,duration,delay)
			count=count-1
			m=m+1
	
	if i in sorted_start2_a:
		print '###### Delay Traffic'
		count=sorted_start2_a.count(i)
		while 0<count:
			(start_time,src,dst,port,duration,delay)=traffic2_a[m_]

			voip2(start_time,src,dst,port,duration,delay)
			count=count-1
			m_=m_+1
	######################################


print "flows are done !!!"



while False:
	#time.sleep(5)
	output = subprocess.check_output("ps aux | grep ITGSend |  wc -l", shell=True)
	numos=int(output.split()[0])

	print numos
	if numos<4:
		break
		


time.sleep(90)

execfile("ditgDec.py")
print 'txt conversion completed!'
time.sleep(5)
execfile("excel.py")
print 'Statistic.csv is created!'
print "Good bye!"





