How to Create Testing Environment in Linux! (Root Mode in Shell)

1- Create Mininet Topology

	ubuntu@PC#python MininetTopologyGenerator.py	

	This command creates 3 OVS switch 4 host. Each switch has different subnet. At the end of topology script, 
	queue_port_10M.sh script is called automatically and configure OVS switch-ports with 10 mbps link speed,
	queues, 20 ms delay and 0.0001% packet loss.
	
2- Run Traffic Generator from Mininet CLI.
	
	mininet> py execfile("repeaterOfFlowGen.py") 

	This script calls flowGenerator_10mb.py X times and replicate the simulation X times. (X can be set from script)
	
	flowGenerator_10mb.py script creates A times low prio traffic, B times mid prio traffic, C times high prio traffic
	between Mininet hosts. All flows are randomly start in execution time, and last for 30-40 seconds (uniformally dist).
	Flows are created by DITG. 
	