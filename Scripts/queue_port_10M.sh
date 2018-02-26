#This script is build for OVS port modification: Creates 3 priority queues, Adds 20ms delay and 0.0001% loss.
#It is used at the end of Mininet Topology Creator Script.

# List all OVS switch-ports
allPorts="$(ifconfig -a | grep -v 'ovs' |sed 's/[ \t].*//;/^$/d' | grep -F '-' )"

for interface in $allPorts
do
	echo $interface
	
	#Priority pr:0 20M-30M pr:1 20M - 30M pr:2 40M-60M
	#sudo ovs-vsctl -- set port ${interface}  qos=@newqos -- --id=@newqos create qos type=linux-htb other-config:max-rate=100000000 queues:1=@newqueue1 queues:2=@newqueue2 queues:0=@newqueue0 -- --id=@newqueue1 create queue other-config:min-rate=20000000 other-config:max-rate=30000000 other-config:priority=1 -- --id=@newqueue2 create queue other-config:min-rate=40000000 other-config:max-rate=60000000 other-config:priority=2 -- --id=@newqueue0 create queue other-config:min-rate=20000000 other-config:max-rate=30000000 other-config:priority=0
	
	#JUST 3 PRIO WITH NO QUEUE SIZE
	sudo ovs-vsctl -- set port ${interface}  qos=@newqos -- --id=@newqos create qos type=linux-htb other-config:max-rate=100000000 queues:47=@newqueue2 queues:31=@newqueue1 queues:15=@newqueue0 -- --id=@newqueue1 create queue  other-config:priority=1 -- --id=@newqueue2 create queue other-config:priority=2 -- --id=@newqueue0 create queue other-config:priority=0
	
	#NO priority
	#sudo ovs-vsctl -- set port ${interface}  qos=@newqos -- --id=@newqos create qos type=linux-htb other-config:max-rate=100000000 queues:1=@newqueue queues:2=@newqueue1 queues:0=@newqueue0 -- --id=@newqueue create queue other-config:min-rate=20000000 other-config:max-rate=30000000 other-config:priority=0 -- --id=@newqueue1 create queue other-config:min-rate=40000000 other-config:max-rate=60000000 other-config:priority=0 -- --id=@newqueue0 create queue other-config:min-rate=20000000 other-config:max-rate=30000000 other-config:priority=0
	
done	

for interface in $allPorts
do
	echo $interface
	
	
	tc qdisc del dev ${interface} root
	# This line sets a HTB qdisc on the root of ${interface}, and it specifies that the class 1:30 is used by default. It sets the name of the root as 1:, for future references.
	tc qdisc add dev ${interface} root handle 1: htb default 30


	# This creates a class called 1:1, which is direct descendant of root (the parent is 1:), this class gets assigned also an HTB qdisc, and then it sets a max rate of 10mbits, with a burst of 15k
	tc class add dev ${interface} parent 1: classid 1:1 htb rate 10mbit burst 15k

	# The previous class has this branches:

	# Class 1:10, which has a rate of X mbit
	tc class add dev ${interface} parent 1:1 classid 1:10 htb rate 60kbit ceil 10mbit burst 15k prio 1

	# Class 1:20, which has a rate of X mbit
	tc class add dev ${interface} parent 1:1 classid 1:20 htb rate 60kbit ceil 10mbit burst 15k prio 2

	# Class 1:30, which has a rate of X mbit. This one is the default class.
	tc class add dev ${interface} parent 1:1 classid 1:30 htb rate 60kbit ceil 10mbit burst 15k prio 3
	
	# Add 20ms delay and 0.0001% loss
	tc qdisc add dev ${interface} parent 1:10 handle 10: netem delay 20000  loss 0.0001%
	tc qdisc add dev ${interface} parent 1:20 handle 20: netem delay 20000  loss 0.0001%
	tc qdisc add dev ${interface} parent 1:30 handle 30: netem delay 20000  loss 0.0001%


	
done
