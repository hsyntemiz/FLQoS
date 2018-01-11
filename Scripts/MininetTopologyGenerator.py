#!/usr/bin/python

"""Topology with 3 switches and 4 hosts
"""

from mininet.cli import CLI
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.node import Controller, RemoteController, OVSController
import subprocess 
import time
import random
import numpy as np



def int2dpid( dpid ):
	try:
		dpid = hex( dpid )[ 2: ]
		dpid = '0' * ( 16 - len( dpid ) ) + dpid
		return dpid
	except IndexError:
		raise Exception( 'Unable to derive default datapath ID - '
			'please either specify a dpid or use a '
			'canonical switch name such as s23.' )

class CSLRTopo( Topo ):

	def __init__( self ):
			"Create Topology"

			# Initialize topology
			Topo.__init__( self )

			# Add hosts

			h1 = self.addHost( 'h1' )
			h1a = self.addHost( 'h1a' )
			h2 = self.addHost( 'h2' )
			h3 = self.addHost( 'h3' )
			

			# Add switches

			oslo = self.addSwitch( 'oslo', dpid=int2dpid(1))
			stockholm = self.addSwitch( 'stockholm', dpid=int2dpid(2))
			copenhagen = self.addSwitch( 'copenhagen', dpid=int2dpid(3))


			# Add links between hosts and switches
		
			self.addLink( h1, oslo ) # h1-eth0 <-> oslo-eth1
			self.addLink( h1a, oslo ) # h1-eth0 <-> oslo-eth2
			self.addLink( h2, stockholm ) # h2-eth0 <-> stockholm-eth1
			self.addLink( h3, copenhagen ) # h3-eth0 <-> copenhagen-eth1
			


			# Add links between switches, with bandwidth 100Mbps
		  
			self.addLink( oslo, stockholm) # oslo-eth3 <-> stockholm-eth3, Bandwidth = 100Mbps
			self.addLink( oslo, copenhagen ) # oslo-eth3 <-> stockholm-eth3, Bandwidth = 100Mbps
			self.addLink( stockholm, copenhagen ) # stockholm-eth4 <-> copenhagen-eth2, Bandwidth = 100Mbps
	
def run():
	"Create and configure network"
	topo = CSLRTopo()
	#net = Mininet( topo=topo, link=TCLink, controller=None )
	net = Mininet( topo=topo, link=TCLink, controller=RemoteController )

	# Set interface IP and MAC addresses for hosts
	
	h1 = net.get( 'h1' )
	h1.intf( 'h1-eth0' ).setIP( '10.0.1.2', 24 )
	h1.intf( 'h1-eth0' ).setMAC( '0A:00:01:02:00:00' )

	h1a = net.get( 'h1a' )
	h1a.intf( 'h1a-eth0' ).setIP( '10.0.1.3', 24 )
	h1a.intf( 'h1a-eth0' ).setMAC( '0A:00:01:03:00:00' )

	h2 = net.get( 'h2' )
	h2.intf( 'h2-eth0' ).setIP( '10.0.2.2', 24 )
	h2.intf( 'h2-eth0' ).setMAC( '0A:00:02:02:00:00' )

	h3 = net.get( 'h3' )
	h3.intf( 'h3-eth0' ).setIP( '10.0.3.2', 24 )
	h3.intf( 'h3-eth0' ).setMAC( '0A:00:03:02:00:00' )



	# Set interface MAC address for switches (NOTE: IP
	# addresses are not assigned to switch interfaces)

	oslo = net.get( 'oslo' )
	#oslo.intf( 'oslo-eth1' ).setIP( '10.0.1.1', 24 )
	oslo.intf( 'oslo-eth1' ).setMAC( '0A:00:01:01:00:01' )
	oslo.intf( 'oslo-eth2' ).setMAC( '0A:00:0A:FE:00:02' )
	oslo.intf( 'oslo-eth3' ).setMAC( '0A:00:0C:01:00:03' )
	oslo.intf( 'oslo-eth4' ).setMAC( '0A:00:0A:01:01:04' )

	stockholm = net.get( 'stockholm' )
	stockholm.intf( 'stockholm-eth1' ).setMAC( '0A:00:02:01:00:01' )
	#stockholm.intf( 'stockholm-eth2' ).setMAC( '0A:00:0B:FE:00:02' )
	stockholm.intf( 'stockholm-eth2' ).setMAC( '0A:00:0D:01:00:03' )
	stockholm.intf( 'stockholm-eth3' ).setMAC( '0A:00:0C:FE:00:04' )

	copenhagen = net.get( 'copenhagen' )
	#copenhagen.intf( 'copenhagen-eth1' ).setIP( '10.0.3.1', 24 )
	copenhagen.intf( 'copenhagen-eth1' ).setMAC( '0A:00:03:01:00:01' )
	copenhagen.intf( 'copenhagen-eth2' ).setMAC( '0A:00:0D:FE:00:02' )
	copenhagen.intf( 'copenhagen-eth3' ).setMAC( '0A:00:0E:01:00:03' )
	

	net.start()

	# Add routing table entries for hosts (NOTE: The gateway
	# IPs 10.0.X.1 are not assigned to switch interfaces)

	h1.cmd( 'route add default gw 10.0.1.1 dev h1-eth0' )
	h1a.cmd( 'route add default gw 10.0.1.1 dev h1a-eth0' )
	h2.cmd( 'route add default gw 10.0.2.1 dev h2-eth0' )
	h3.cmd( 'route add default gw 10.0.3.1 dev h3-eth0' )


	# Add arp cache entries for hosts

	h1.cmd( 'arp -s 10.0.1.1 0A:00:01:01:00:01 -i h1-eth0' )
	h1a.cmd( 'arp -s 10.0.1.1 0A:00:01:01:00:01 -i h1a-eth0' )
	h2.cmd( 'arp -s 10.0.2.1 0A:00:02:01:00:01 -i h2-eth0' )
	h3.cmd( 'arp -s 10.0.3.1 0A:00:03:01:00:01 -i h3-eth0' )
	


	#Adding Port Queue
	print "start"
	
	subprocess.call("./queue_port_10M.sh", shell=True)
	print "end"

	# Open Mininet Command Line Interface
	CLI(net)

	# Teardown and cleanup
	net.stop()
	

if __name__ == '__main__':
    setLogLevel('info')
    run()

    
