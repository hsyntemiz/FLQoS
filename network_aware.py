# conding=utf-8
import logging
import struct
import copy

import requests
import json
import networkx as nx
from time import sleep
from operator import attrgetter
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet
from ryu.lib.packet import ethernet
from ryu.lib.packet import ipv4
from ryu.lib.packet import arp
from ryu.lib import hub
import MySQLdb
from ryu.topology import event, switches
from ryu.topology.api import get_switch, get_link
###
from ryu.ofproto import inet
import time
import thread

from ryu.controller import dpset

# import shortest_route
#from shortest_route import SLEEP_PERIOD

SLEEP_PERIOD = 3
IS_UPDATE = True
###SHOW_LOG = LINK DELAY SW DELAY ICIN LOG PRINT ENABLE DISABLE
SHOW_LOG=False

NETQX=nx.DiGraph()
##SHOW TOPO= SW TO SW LINK CONNECTION MATRIX
SHOW_TOPO=False
SHOW_TOPO_DPSET=False

# links   :(src_dpid,src_port)->(dst_dpid) AND (dst_dpid,dst_port)->(src_dpid)
link_to_neighbor = {}

class Network_Aware(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _NAME = 'network_aware'

    # _CONTEXTS = { "dpset": dpset.DPSet }
    # _CONTEXTS = { "shortest_route": shortest_route.Shortest_Route }



    def __init__(self, *args, **kwargs):

        super(Network_Aware, self).__init__(*args, **kwargs)
        self.name = "Network_Aware"

        self.dpsetim = dpset.DPSet()


        self.logger.info(" Network_aware created ----------------")

        self.topology_api_app = self

        # links   :(src_dpid,dst_dpid)->(src_port,dst_port)
        self.link_to_port={}

        # {(sw,port) :[host1_ip,host2_ip,host3_ip,host4_ip]}
        self.access_table = {}
        self.access_table_mac = {}

        # ports
        self.switch_port_table = {}  # dpid->port_num

        # dpid->port_num (access ports)
        self.access_ports = {}

        # dpid->port_num(interior ports)
        self.interior_ports = {}

        self.outer_ports = {}

        self.graph = {}

        self.pre_link_to_port = {}
        self.pre_graph = {}
        self.pre_access_table = {}
        #
        self.netx = nx.Graph()

        self.swCount=0


        self.FLAG = True
        self.FIRST_SLEEP_GET_TOPOLOGY = True

        self.db = MySQLdb.connect(host="localhost",  # your host, usually localhost
                                  user="root",  # your username
                                  passwd="1234",  # your password
                                  db="POLICYDB")  # name of the data base
        # cur = db.cursor()

        ################qos metric fields#####
        self.sw_delay = {}
        self.sw_delay_RTT = {}

        #Link Delay is not used since Delay beacon part is cancelled!
        self.link_delay={}

        self.datapaths = {}

        # self._run_periodic_thread = hub.spawn(self._run_periodic)

        self.discover_thread = hub.spawn(self._discover)

    # show topo ,and get topo again
    def _discover(self):
        i = 0
        while True:

            if SHOW_TOPO:
                self.show_topology()

            if i == 5:
                self.get_topology(None)
                i = 0

            hub.sleep(SLEEP_PERIOD)
            i = i + 1

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        msg = ev.msg
        self.logger.info("switch:%s connected ----- datapath:%s", datapath.id,datapath)

        # install table-miss flow entry
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self.add_flow(datapath, 1, match, actions)

        self.swCount=self.swCount+1




    @set_ev_cls(dpset.EventDP, MAIN_DISPATCHER)
    def _event_dp_handler(self, ev):
        self.logger.info("XXXXXXXXXXXXX dp.id=%i, dp.address=%s", ev.dp.id, ev.dp.address)

        if SHOW_TOPO_DPSET:
            for p in ev.ports:
                self.logger.info("port_no= %s, hw_addr= %s, interface= %s", p.port_no, p.hw_addr, p.name)



    def add_flow(self, dp, p, match, actions, idle_timeout=0, hard_timeout=0):
        ofproto = dp.ofproto
        parser = dp.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=dp, priority=p,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
                                match=match, instructions=inst)
        dp.send_msg(mod)


    def get_switches(self):
        return self.switches

    def get_links(self):
        return self.link_to_port

    def add_link_to_db(self):
        #links = get_link(self.topology_api_app, None)
        links=self.link_to_port.keys()

        for link in links:
            (src,dst)=link


    # get Adjacency matrix from link_to_port
    def get_graph(self, link_list, opt2=None):

        cur = self.db.cursor()

        for src in self.switches:
            self.netx.add_node(src)
            NETQX.add_node(src)
            self.logger.info("NETQX =====  %s node:%s", NETQX.number_of_nodes(),src)


            for dst in self.switches:


                self.graph.setdefault(src, {dst: float('inf')})


                if src == dst:
                    self.graph[src][src] = 0
                elif (src, dst) in link_list:
                    self.graph[src][dst] = 1
                    self.netx.add_edge(src, dst, bandwidth=1,reserved_bw=1, residual_bw=300000000, delay=float('inf'))
                    NETQX.add_edge(src,dst,bandwidth=100,reserved_bw=200, residual_bw=300000000, delay=float('inf'),queue_id_0=(0,0,0,1000),queue_id_15=(0,0,0,1000),queue_id_31=(0,0,0,1000),queue_id_47=(0,0,0,1000))


                    self.link_delay[(src,dst)]=1000

                    (src_port,dst_port) = self.link_to_port[src, dst]

                    link_to_neighbor[src,src_port] = dst
                    link_to_neighbor[dst,dst_port] = src


                    sql_request = "INSERT INTO links ( srcid, dstid, srcport, dstport ) VALUES ( '%s', '%s' , '%s' , '%s') " % (
                        src, dst, src_port, dst_port )
                    cur.execute(sql_request)
                    #self.logger.info("SQL REQUEST: %s",sql_request)


                else:
                    self.graph[src][dst] = float('inf')


        if len(self.switches)==3:
            self.logger.info("NETQX ===== TOPOLOGY COMPLETE !!!!")
        else:
            self.logger.info("NETQX ===== TOPOLOGY Failed - missing switch -")


        self.db.commit()
        self.logger.info("\n \n&&&&&&& TOPOLOGY READY TO SEND TRAFFIC ! &&&&&&& %s",link_to_neighbor)

        return self.graph

    def create_port_map(self, switch_list):
        for sw in switch_list:
            dpid = sw.dp.id
            self.switch_port_table.setdefault(dpid, set())
            self.interior_ports.setdefault(dpid, set())
            self.access_ports.setdefault(dpid, set())

            for p in sw.ports:
                self.switch_port_table[dpid].add(p.port_no)

    # get links`srouce port to dst port  from link_list,
    # link_to_port:(src_dpid,dst_dpid)->(src_port,dst_port)
    def create_interior_links(self, link_list):
        for link in link_list:
            src = link.src
            dst = link.dst
            self.link_to_port[
                (src.dpid, dst.dpid)] = (src.port_no, dst.port_no)

            # find the access ports and interiorior ports
            if link.src.dpid in self.switches:
                self.interior_ports[link.src.dpid].add(link.src.port_no)
            if link.dst.dpid in self.switches:
                self.interior_ports[link.dst.dpid].add(link.dst.port_no)

    # get ports without link into access_ports
    def create_access_ports(self):
        # we assume that the access ports include outer port.
        # Todo: find the outer ports by filter.
        for sw in self.switch_port_table:
            self.access_ports[sw] = self.switch_port_table[
                                        sw] - self.interior_ports[sw]

    def create_outer_port(self):
        pass

    events = [event.EventSwitchEnter,
              event.EventSwitchLeave, event.EventPortAdd,
              event.EventPortDelete, event.EventPortModify,
              event.EventLinkAdd, event.EventLinkDelete]

    @set_ev_cls(events)
    def get_topology(self, ev):
        switch_list = get_switch(self.topology_api_app, None)
        self.create_port_map(switch_list)
        self.switches = self.switch_port_table.keys()
        links = get_link(self.topology_api_app, None)



        if self.FIRST_SLEEP_GET_TOPOLOGY:
            sleep(2)
            self.FIRST_SLEEP_GET_TOPOLOGY = False

        self.create_interior_links(links)
        self.create_access_ports()

        #self.logger.info("&&&&&&&&&&&&&&&&&&&&&&&&&&&: GET TOPOLOGY in ICINDEyiIIIIIIIIIIIIM") #Eski KODDAN
        # if self.FLAG:
        #     self.get_graph(self.link_to_port.keys())
        #     self.FLAG = False


        if self.FLAG and len(self.switches)>=self.swCount:
            self.get_graph(self.link_to_port.keys())
            self.logger.info("&&&&&&&&&&&&&&&&&&&&&&&&&&&: FLAG TRUE GET TOPOLOGY in ICINDEYIIIIIIIM %s", self.link_to_port.keys())
            self.FLAG = False

    def register_access_info(self, dpid, in_port, ip, mac):
        #self.logger.info("teeeeeeeeeeeeeeeeeeeeeeeeeexy %s",ip)

        if in_port in self.access_ports[dpid]:
            if (dpid, in_port) in self.access_table:
                if ip != self.access_table[(dpid, in_port)]:
                    self.access_table[(dpid, in_port)] = ip
                    self.access_table_mac[ip] = mac

                    cur = self.db.cursor()
                    sql_request = "INSERT INTO hosts ( host_name, host_ip, host_mac ,connected_sw,sw_port) VALUES ( '%s', '%s', '%s', '%s', '%s' ) " % (
                        ip, ip, mac, dpid, in_port)
                    #self.logger.info("SQL REQUEST: %s",sql_request)
                    cur.execute(sql_request)
                    self.db.commit()


            else:
                self.access_table[(dpid, in_port)] = ip
                self.access_table_mac[ip] = mac
                cur = self.db.cursor()
                sql_request = "INSERT INTO hosts ( host_name, host_ip, host_mac ,connected_sw,sw_port) VALUES ( '%s', '%s', '%s', '%s', '%s' ) " % (
                    ip, ip, mac, dpid, in_port)
                cur.execute(sql_request)
                self.db.commit()

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)

        eth_type = pkt.get_protocols(ethernet.ethernet)[0].ethertype
        mac = pkt.get_protocols(ethernet.ethernet)[0].src
        # self.logger.info("&&&&&&&&&&&&&&&&&&&&&&&&&&&: MAC address: %s",mac)

        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)

        if arp_pkt:
            arp_src_ip = arp_pkt.src_ip
            arp_dst_ip = arp_pkt.dst_ip

            # record the access info
            self.register_access_info(datapath.id, in_port, arp_src_ip, mac)
        if ip_pkt:
            ip_src = ip_pkt.src
            self.register_access_info(datapath.id, in_port, ip_src, mac)


        ##Bu kismi delay icin baska methodu buraya gomdum
        if eth_type == 2688:

            payload = bytearray(pkt.data)
            payload1 = pkt[-1]
            recieve_time=time.time() * 1000
            sent_time_str=payload1.split("##")[2]
            #
            total_delay=recieve_time-float(sent_time_str)

            src_dpid,dst_dpid= int(payload1.split("##")[0]),int(payload1.split("##")[1])

            try:
            #if src_dpid in self.datapaths and dst_dpid in self.datapaths:

                src_sw_delay=0.5*self.sw_delay_RTT[self.datapaths[src_dpid]]
                dst_sw_delay=0.5*self.sw_delay_RTT[self.datapaths[dst_dpid]]
                delay=total_delay-src_sw_delay-dst_sw_delay
                if SHOW_LOG:
                    self.logger.info("SENSED! linK DELAY (%s==%s) ====> %f ===== Total_link delay: %f ",src_dpid,dst_dpid,delay,total_delay)

                self.link_delay[(src_dpid,dst_dpid)]=delay

            except:
            #else:
                self.sw_delay_RTT[self.datapaths[src_dpid]]=0
                self.sw_delay_RTT[self.datapaths[dst_dpid]]=0


        if eth_type == 2689:

            payload = bytearray(pkt.data)
            payload1 = pkt[-1]

            recieve_time=time.time() * 1000
            sent_time_str=payload1.split("##")[1]

            sw_delay=recieve_time-float(sent_time_str)

            dpid= int(payload1.split("##")[0])
            self.sw_delay_RTT[self.datapaths[dpid]]=sw_delay

            #self.logger.info("GERCEK SW == DELAY %s = ====> %f",dpid,sw_delay)

    # show topo
    def show_topology(self):
        switch_num = len(self.graph)
        if self.pre_graph != self.graph or IS_UPDATE:
            print "---------------------Topo Link---------------------"
            print '%10s' % ("switch"),
            for i in xrange(1, switch_num + 1):
                print '%10d' % i,
            print ""
            for i in self.graph.keys():
                print '%10d' % i,
                for j in self.graph[i].values():
                    print '%10.0f' % j,
                print ""
            self.pre_graph = copy.deepcopy(self.graph)
        # show link
        if self.pre_link_to_port != self.link_to_port or IS_UPDATE:
            print "---------------------Link Port---------------------"
            print '%10s' % ("switch"),
            for i in xrange(1, switch_num + 1):
                print '%10d' % i,
            print ""
            for i in xrange(1, switch_num + 1):
                print '%10d' % i,
                for j in xrange(1, switch_num + 1):
                    if (i, j) in self.link_to_port.keys():
                        print '%10s' % str(self.link_to_port[(i, j)]),
                    else:
                        print '%10s' % "No-link",
                print ""
            self.pre_link_to_port = copy.deepcopy(self.link_to_port)

        # each dp access host
        # {(sw,port) :[host1_ip,host2_ip,host3_ip,host4_ip]}
        if self.pre_access_table != self.access_table or IS_UPDATE:
            print "----------------Access Host-------------------"
            print '%10s' % ("switch"), '%12s' % "Host"
            if not self.access_table.keys():
                print "    NO found host"
            else:
                for tup in self.access_table:
                    print '%10d:    ' % tup[0], self.access_table[tup]
            self.pre_access_table = copy.deepcopy(self.access_table)




    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])



    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]




    @set_ev_cls(ofp_event.EventOFPDescStatsReply, MAIN_DISPATCHER)
    def desc_stats_reply_handler(self, ev):
        var = 0
        msg = ev.msg
        datapath = msg.datapath
        ofp = datapath.ofproto
        zaman = time.time() * 1000

        recv, sent = self.sw_delay[datapath]
        self.sw_delay[datapath] = (zaman, sent)

        delay = zaman - sent
        self.sw_delay_RTT[datapath] = delay
        if SHOW_LOG:
            self.logger.info('STAT oriented RTT DELAY  : %016x  ==== %f', datapath.id, self.sw_delay_RTT[datapath])

    ############# ################## ################## ################## ##################
    ############# ################## ################## ################## ##################

    #this method is alternative sw rtt calculation based on send-recv stat req
    def send_sw_packet_RTT(self, datapath):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPDescStatsRequest(datapath, 0)
        datapath.send_msg(req)


        zaman = time.time() * 1000
        #self.logger.info('SSfend stats request: : %016x  ==== %f', datapath.id, zaman)

        self.sw_delay[datapath] = (0, zaman)

    def calc_sw_controller_RTT(self):

        for dp in self.datapaths:
            try:


                thread_name="Thread_ %s _" % dp
                datapath = self.datapaths[dp]
                if SHOW_LOG:
                    print " BEACON SENT TO SW %s: %s" % ( thread_name, time.ctime(time.time()) )

                thread.start_new_thread( self.send_sw_packet_RTT, (datapath, ) )


                #self.send_sw_packet_RTT(datapath)


            except:
                print "Error: unable to start thread"
            #########

    #This method calcs the ALL SW RTT
    def calc_sw_controller_RTT2(self):
        flag=True
        for dp in self.datapaths:
            if flag:
                #flag=False
                datapath = self.datapaths[dp]

                #self.logger.info("XXXPPPPPPP BU SWITHC E CUSTOM PAKET YOLLADIM--------%s", datapath)
                self.send_sw_packet_RTT(datapath)


    #This method create and send the packet between src sw and dst sw
    def send_sw_packet(self, src_dp, dst_dp):

        src_port, dst_port = self.link_to_port[(src_dp.id, dst_dp.id)]

        # mac-assignment!!
        ###self.logger.info('NETWORK_AWARE___DPSET INFO =#%s == COK COK COK ONEMLI ----', self.dpsetim)

        src_port_info = self.dpsetim.get_port(src_dp.id, src_port)

        src_mac = src_port_info.hw_addr

        dst_port_info = self.dpsetim.get_port(dst_dp.id, dst_port)
        dst_mac = dst_port_info.hw_addr

        #self.logger.info('NETWORK_AWARE___MAC INFO =#%s# =# %s#== COK COK COK ONEMLI ---- : %s', src_dp, dst_dp,dst_mac)

        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=0x0a80,
                                           dst=dst_mac,
                                           src=src_mac))

        sent_time=time.time() * 1000
        sent_time_str=repr(sent_time)
        pkt.add_protocol(bytearray(str(src_dp.id) + '##' + str(dst_dp.id))+'##' +sent_time_str)

        self._send_packet(src_dp, src_port, pkt)

    #This method send the given packet to given port of given sw
    def _send_packet(self, datapath, port, pkt):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt.serialize()
        ####self.logger.info("packet-out %s" % (pkt,))
        data = pkt.data
        actions = [parser.OFPActionOutput(port=port)]
        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)

    #This method calcs the link delays (send packets)
    def link_delay_calc_all(self):

        links = self.get_links()

        for link in links:
            src, dst = link

            self.send_sw_packet(self.datapaths[src], self.datapaths[dst])
