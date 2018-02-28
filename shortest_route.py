# conding=utf-8
import networkx as nx
from ryu.base import app_manager
from ryu.controller import dpset
from ryu.controller import ofp_event
from ryu.controller import event
from ryu.controller import handler

from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.ofproto import ofproto_parser
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import arp
from ryu.lib.packet import ethernet
from ryu.ofproto import ether
from ryu.lib.packet import ipv4
from ryu.lib.packet import tcp
from ryu.lib.packet import icmp
from ryu.lib.packet import udp
from ryu.lib.packet import packet
from ryu.lib.packet import ether_types
from ryu.lib.packet import in_proto as inet
import MySQLdb
import thread
import time
# json queue isleri
import logging
import struct
import pycurl
import requests

import urllib
import json
import csv
import sys, os
from ryu.app.rest_qos import *
from ryu.app.rest_conf_switch import *
#
# links   :(src_dpid,src_port)->(dst_dpid) AND (dst_dpid,dst_port)->(src_dpid)

from collections import defaultdict, deque

from network_aware import NETQX
from network_aware import link_to_neighbor

from ryu.ofproto import ofproto_v1_3
from netaddr import *
import csv
import network_aware
import network_monitor

from network_monitor import SLEEP_PERIOD


#import qos_metric
MIN_HOP_ROUTING=False
PRIO_QUEUEING_ENABLED=True
# PORT_QUEUEING=False
#SLEEP_PERIOD = 3
SHOW_ADD_FLOW = True
SHOW_ACCESS_TABLE=False
Q15_BUF=30000000
Q31_BUF=30000000
Q47_BUF=60000000
LINK_SPEED=10000000


class Shortest_Route(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {
        "Network_Aware": network_aware.Network_Aware,
        "Network_Monitor": network_monitor.Network_Monitor,
        "dpset": dpset.DPSet
    }

    # "Qos_Metric": qos_metric.Qos_Metric,

    def __init__(self, *args, **kwargs):

        super(Shortest_Route, self).__init__(*args, **kwargs)

        self.logger.info("----############### args:%s  -----", args)
        self.logger.info("----############### kwargs:%s--",kwargs)
        self.logger.info("----############### kwargs:%s--",kwargs['dpset'])

        for term in kwargs:
            self.logger.info("----############### INIT TErm   ------%s === %s", term, kwargs[term])

        self.network_aware = kwargs["Network_Aware"]
        self.network_monitor = kwargs["Network_Monitor"]
        self.dpset = kwargs['dpset']
        #
        self.mac_to_port = {}
        self.datapaths = {}
        self.flowPathMap={} #  self.flowPathMap[myflow] = (path_, version_, lock_flag_, policy)



        # links   :(src_dpid,dst_dpid)->(src_port,dst_port)
        self.link_to_port = self.network_aware.link_to_port

        # {sw :[host1_ip,host2_ip,host3_ip,host4_ip]}
        self.access_table = self.network_aware.access_table
        self.access_table_mac = self.network_aware.access_table_mac
        self.network_aware.dpsetim = self.dpset



        self.logger.info("&&&&&&&&&&  SHORTEST ROUTE ICI &&&&&&&&DPSET : %s &&&&&&&&&----------------", self.network_aware.dpsetim)
        self.network_aware.dpsetim = self.dpset
        self.logger.info("&&&&&&&&&&SHORTEST ROUTE ICI &&&&&&&&DPSET : %s &&&&AYARLI&&&&&----------------",
                         self.dpset)


        self.flows_on_link = {} # # self.flows_on_link[(link)] = (flow_tuple,rate, uptime)
        self.flowStats = {} # self.flowStats[(dp.id, flow_tuple)] = (rate, uptime)

        self.pre_flowStats = {}



        # dpid->port_num (ports without link)
        self.access_ports = self.network_aware.access_ports
        ##self.graph = self.network_aware.graph
        self.db = self.network_aware.db

        #
        self.port_speed = self.network_monitor.port_speed
        self.netx = self.network_aware.netx

        self.flag = False

        self._flush__db()

        #self.pX = nx.shortest_path_length(NETQX)


        #Bunu disable ettim. create_bw_graph kullanmiyorum simdilik
        self.discover_thread = hub.spawn(self._run_periodicals)

    # Decoratorler sw'lerin register ve unregister olmalirini dinliyor.
    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):

        datapath = ev.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
                # self.clearAllFlowsAndGroups(datapath)

        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    def flow_on_link_init(self):
        self.flows_on_link= {}
        for link in self.link_to_port.keys():
            #self.logger.info("xx LINK: %s", link)

            self.flows_on_link.setdefault(link, [])

        for flow_tuple in self.flowPathMap.keys():
            #self.logger.info('********FlowStats: FLOW_222222222: %s', self.flowPathMap[flow_tuple])
            path_ = self.flowPathMap[flow_tuple][0]
            i = 0

            for i in xrange(0, len(path_) - 1):
                link = (path_[i], path_[i + 1])
                #print link

                if not flow_tuple in self.flows_on_link[link]:
                    self.flows_on_link[link].append(flow_tuple)
                    ##self.logger.info('********FlowStats: FLOW_3: %s', self.flows_on_link[link])

    #Currently UNUSED
    def _run_periodicals(self):

        while True:
            #self.create_bw_graph(self.link_to_port, self.port_speed)
            self.flow_on_link_init()
            #self.logger.info("FLOWS ON LINK: %s", self.flows_on_link)

            hub.sleep(SLEEP_PERIOD)

            # self.periodic_qos_fail_detect()




    def _flush__db(self):
        cur = self.db.cursor()
        sql_request = "TRUNCATE TABLE hosts;"
        cur.execute(sql_request)

        sql_request = "TRUNCATE TABLE switches;"
        cur.execute(sql_request)

        sql_request = "TRUNCATE TABLE activeflows;"
        cur.execute(sql_request)

        sql_request = "TRUNCATE TABLE links;"
        cur.execute(sql_request)

        sql_request = "TRUNCATE TABLE ports;"
        cur.execute(sql_request)

        sql_request = "TRUNCATE TABLE portstat;"
        cur.execute(sql_request)


        self.logger.info("DB _ HOST_db AND SW_db FLUSHED: %s", sql_request)

        self.db.commit()

    # NETQX'IN PORT global bandwidth, residual_bw,delay degerlerini dolduruyor
    #Ama henuz kullanmiyoruz o degiskenleri-
    def create_bw_graph(self, link2port, bw_dict):

        for link in link2port:

            (src_dpid, dst_dpid) = link
            (src_port, dst_port) = link2port[link]

            try:
                if (src_dpid, dst_dpid) in bw_dict.keys():
                    # if src_dpid in bw_dict and dst_dpid in bw_dict:

                    bw_src = self.port_speed[(src_dpid, src_port)][-1]
                    bw_dst = self.port_speed[(dst_dpid, dst_port)][-1]

                    # self.netx[src_dpid][dst_dpid]['bandwidth'] = min(bw_src, bw_dst)
                    # self.netx[src_dpid][dst_dpid]['residual_bw'] = 104857600 - (min(bw_src, bw_dst) * 8)
                    # self.netx[src_dpid][dst_dpid]['delay'] = 8 * 1024 * min(bw_src, bw_dst) / (
                    # 104857600 - (min(bw_src, bw_dst) * 8))

                    NETQX[src_dpid][dst_dpid]['bandwidth'] = min(bw_src, bw_dst)
                    NETQX[src_dpid][dst_dpid]['residual_bw'] = 104857600 - (min(bw_src, bw_dst) * 8)
                    NETQX[src_dpid][dst_dpid]['delay'] = 8 * 1024 * min(bw_src, bw_dst) / (
                        104857600 - (min(bw_src, bw_dst) * 8))




                else:
                    pass
                    # print ("warning: LNKnotdtCTD")

            except KeyError:

                print ("Key is not exist!-#create_bw_graph#")
                # graph[src_dpid][dst_dpid]['bandwidth'] = 0

    @set_ev_cls(dpset.EventDP, MAIN_DISPATCHER)
    def _event_dp_handler(self, ev):
        temp_name = (ev.ports[0]).name
        swname = temp_name.split('-', 2)[0]

        (address,port)=ev.dp.address
        cur = self.db.cursor()
        sql_request = "INSERT INTO switches ( dpid, address,port,swname) VALUES ( '%s', '%s', '%s', '%s') " % (
            ev.dp.id, address,port,swname)

        cur.execute(sql_request)
        #self.db.commit()


        for p in ev.ports:

            cur = self.db.cursor()
            sql_request = "INSERT INTO ports (  port_name, dpid, port_no, port_mac) VALUES ( '%s', '%s' , '%s' , '%s') " % (
                p.name, ev.dp.id, p.port_no, p.hw_addr )

            cur.execute(sql_request)
            if int(p.port_no)<100:
                dpid = format(ev.dp.id, '016')
                sql_request = "INSERT INTO portstat ( datapath, port ) VALUES ( '%s', '%s' ) " % (
                    dpid,  p.port_no )
                cur.execute(sql_request)



        self.db.commit()


    def add_flow(self, dp, p, match, actions, routing_mode=None, idle_timeout=0, hard_timeout=0):
        # I make all added flows priority to 1
        #        p=1
        if SHOW_ADD_FLOW:
            self.logger.info("ADD FLOW to (SW_%s)-(%s)(priority=%s)", dp.id, match,p)

        ofproto = dp.ofproto
        parser = dp.ofproto_parser

        if PRIO_QUEUEING_ENABLED:
            #Best Effort Traffic
            if routing_mode is None:
                actions.insert(0, parser.OFPActionSetQueue(47))
            #Best Effort Traffic
            if routing_mode is 'bw':
                actions.insert(0, parser.OFPActionSetQueue(31))
            #Delay sesnsitive
            if routing_mode is 'delay' or routing_mode is'combined' :
                actions.insert(0, parser.OFPActionSetQueue(15))
        else:
            actions.insert(0, parser.OFPActionSetQueue(47))

        self.logger.info("ACTIONS %s", actions)

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=dp, priority=p,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
                                match=match, instructions=inst,
                                flags=ofproto.OFPFF_SEND_FLOW_REM)
        dp.send_msg(mod)

    def install_flow_unidirect_version2(self, dp_first, dp_last, flow_info, path, path_version ,routing_mode=None, policy=None):

        in_port = flow_info['in_port']

        try:
            datapath_first = self.datapaths[dp_first]
            datapath_last = self.datapaths[dp_last]

            parser = datapath_first.ofproto_parser
            ofproto = datapath_first.ofproto

            if dp_first == dp_last:
                path=[dp_first]

            ########version jobs##########################
            myflow=self.dict_to_tuple(flow_info)
            self.logger.info("=========================================================")
            self.logger.info("====UDP FLOW DETECTED!!!============ %s",myflow)
            self.logger.info("====UDP TRAFFIC = ROUTING MODE: %s===%s", routing_mode,path_version)


            ##########################
            ##TECHICAL JOBS
            ##FLOW ADDITION TO SWITCHES

            # inter_link
            if len(path) > 2:

                for i in xrange(1, len(path) - 1):
                    port = self.get_link2port(path[i - 1], path[i])
                    port_next = self.get_link2port(path[i], path[i + 1])

                    if port:
                        src_port, dst_port = port[1], port_next[0]
                        datapath = self.datapaths[path[i]]
                        ofproto = datapath.ofproto
                        parser = datapath.ofproto_parser
                        actions = []

                        ##############3
                        src_port_info = self.dpset.get_port(path[i], port_next[0])
                        src_mac = src_port_info.hw_addr

                        dst_port_info = self.dpset.get_port(path[i + 1], port_next[1])
                        dst_mac = dst_port_info.hw_addr

                        set_mac1 = parser.OFPActionSetField(eth_src=EUI(src_mac))
                        set_mac2 = parser.OFPActionSetField(eth_dst=EUI(dst_mac))

                        actions = [set_mac1, set_mac2, parser.OFPActionOutput(dst_port)]

                        # actions.append(parser.OFPActionOutput(dst_port))

                        flow_info['in_port'] = src_port
                        match = parser.OFPMatch(**flow_info)

                        priority_= 5 + path_version
                        self.add_flow(
                            datapath, priority_, match, actions, routing_mode,
                            idle_timeout=10, hard_timeout=0)



            if len(path) > 1:

                # the  first flow entry

                port_pair = self.get_link2port(path[0], path[1])
                dst_port = port_pair[0]

                src_port_info = self.dpset.get_port(path[0], dst_port)
                src_mac = src_port_info.hw_addr
                dst_port_info = self.dpset.get_port(path[1], port_pair[1])
                dst_mac = dst_port_info.hw_addr

                set_mac1 = parser.OFPActionSetField(eth_src=EUI(src_mac))
                set_mac2 = parser.OFPActionSetField(eth_dst=EUI(dst_mac))
                action = [set_mac1, set_mac2, parser.OFPActionOutput(dst_port)]
                #
                flow_info['in_port'] = in_port
                match = parser.OFPMatch(**flow_info)

                priority_=8+path_version
                self.add_flow(datapath_first,
                              priority_, match, action, routing_mode, idle_timeout=10, hard_timeout=0)

                #########################################################
                # the last hop: tor -> host
                datapath = self.datapaths[path[-1]]
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser
                actions = []
                src_port = self.get_link2port(path[-2], path[-1])[1]
                dst_port = None

                for key in self.access_table.keys():
                    if flow_info['ipv4_dst'] == self.access_table[key]:
                        dst_port = key[1]
                        break
                # actions.append(parser.OFPActionOutput(dst_port))
                host_mac = self.access_table_mac[flow_info['ipv4_dst']]
                set_mac1 = parser.OFPActionSetField(eth_dst=EUI(host_mac))
                actions = [set_mac1, parser.OFPActionOutput(dst_port)]

                flow_info['in_port'] = src_port
                match = parser.OFPMatch(**flow_info)

                ##self.logger.info("1=================---IP mac:%s ", self.access_table_mac[flow_info['ipv4_dst']])

                priority_ =  path_version+ 7
                self.logger.info("1================= priority &&&&&&&&&&&&&&&& :%s --- %s ", priority_,path_version)

                self.add_flow(datapath, priority_, match, actions, routing_mode, idle_timeout=10, hard_timeout=0)




            else:  # src and dst on the same

                self.logger.info("ON SAME SW____FLOW INSTALL A-4 ----->  PATH:%s ", path)

                out_port = None
                actions = []
                for key in self.access_table.keys():
                    # if flow_info[2] == self.access_table[key]:
                    if flow_info['ipv4_dst'] == self.access_table[key]:
                        out_port = key[1]
                        break

                actions.append(parser.OFPActionOutput(out_port))

                flow_info['in_port'] = in_port
                match = parser.OFPMatch(**flow_info)

                priority_= 8+path_version
                self.add_flow(
                    datapath_first, priority_, match, actions,routing_mode,
                    idle_timeout=10, hard_timeout=0)

            self.logger.info("====UDP FLOW ADDITION DONE!============ %s",myflow)
            self.logger.info("=========================================================")


        except:
            self.logger.info("==================>DATAPATH EXCEPTION - FLOW CANNOT BE INSTALLED YET!")

    def install_flow_bidirect_version2(self, dp_first, dp_last, flow_info, path, path_version, routing_mode=None, policy=None):

        in_port = flow_info['in_port']
        try:

            datapath_first = self.datapaths[dp_first]
            datapath_last = self.datapaths[dp_last]

            parser = datapath_first.ofproto_parser
            ofproto = datapath_first.ofproto

            if dp_first == dp_last:
                path=[dp_first]

            myflow=self.dict_to_tuple(flow_info)
            self.logger.info("=========================================================")
            self.logger.info("====TCP/ICMP FLOW DETECTED!!!=====(install flow bidirect)======= %s",myflow)
            self.logger.info("====TCP/ICMP TRAFFIC = ROUTING MODE: %s === version: %s", routing_mode,path_version)


            src,dst=flow_info['ipv4_src'],flow_info['ipv4_dst']


            ##########################
            ##TECHICAL JOBS
            ##FLOW ADDITION TO SWITCHES

            # inter_link
            if len(path) > 2:

                for i in xrange(1, len(path) - 1):
                    port = self.get_link2port(path[i - 1], path[i])
                    port_next = self.get_link2port(path[i], path[i + 1])

                    if port:
                        src_port, dst_port = port[1], port_next[0]
                        datapath = self.datapaths[path[i]]
                        ofproto = datapath.ofproto
                        parser = datapath.ofproto_parser

                        ##################################################################
                        # mac-assignment!!
                        src_port_info = self.dpset.get_port(path[i], port_next[0])
                        src_mac = src_port_info.hw_addr

                        dst_port_info = self.dpset.get_port(path[i + 1], port_next[1])
                        dst_mac = dst_port_info.hw_addr

                        set_mac1 = parser.OFPActionSetField(eth_src=EUI(src_mac))
                        set_mac2 = parser.OFPActionSetField(eth_dst=EUI(dst_mac))

                        actions = [set_mac1, set_mac2, parser.OFPActionOutput(dst_port)]

                        # actions.append(parser.OFPActionOutput(dst_port))

                        flow_info['in_port'] = src_port
                        match = parser.OFPMatch(**flow_info)

                        self.add_flow(
                            datapath, 67+path_version, match, actions, routing_mode,
                            idle_timeout=10, hard_timeout=0)


                        ##################################################################
                        # REVERSE FLOW RULE FOR TCP-LIKE TRAFFIC !!
                        actions = []

                        src_port, dst_port = port_next[0], port[1]

                        src_port_info = self.dpset.get_port(path[i], port[1])
                        src_mac = src_port_info.hw_addr

                        dst_port_info = self.dpset.get_port(path[i - 1], port[0])
                        dst_mac = dst_port_info.hw_addr

                        set_mac1 = parser.OFPActionSetField(eth_src=EUI(src_mac))
                        set_mac2 = parser.OFPActionSetField(eth_dst=EUI(dst_mac))

                        actions = [set_mac1, set_mac2, parser.OFPActionOutput(dst_port)]
                        #######BURAYA DON REVERSE YAZDIKTAN SONRA
                        # reversed_flow_info=flow_info
                        reversed_flow_info = self.reverse_flow_info(flow_info)
                        self.logger.info("datatapath_id:%s ---- reversed flow: %s ---flow info:%s", datapath.id,
                                         reversed_flow_info, flow_info)

                        reversed_flow_info['in_port'] = src_port
                        match = parser.OFPMatch(**reversed_flow_info)

                        self.add_flow(
                            datapath, 66+path_version, match, actions,routing_mode,
                            idle_timeout=10, hard_timeout=0)



                        ##################################################################

            if len(path) > 1:

                # the  first flow entry
                datapath = self.datapaths[path[0]]
                parser = datapath.ofproto_parser

                port_pair = self.get_link2port(path[0], path[1])
                dst_port = port_pair[0]

                src_port_info = self.dpset.get_port(path[0], dst_port)
                src_mac = src_port_info.hw_addr
                dst_port_info = self.dpset.get_port(path[1], port_pair[1])
                dst_mac = dst_port_info.hw_addr

                set_mac1 = parser.OFPActionSetField(eth_src=EUI(src_mac))
                set_mac2 = parser.OFPActionSetField(eth_dst=EUI(dst_mac))
                action = [set_mac1, set_mac2, parser.OFPActionOutput(dst_port)]
                #
                flow_info['in_port'] = in_port
                self.logger.info("1---datatapath_id:%s -- flow info:%s", datapath.id, flow_info)

                match = parser.OFPMatch(**flow_info)
                self.add_flow(datapath_first,
                              65+path_version, match, action, routing_mode, idle_timeout=10, hard_timeout=0)

                #######buradan sonra reverse icin#########################
                actions = []
                src_port = self.get_link2port(path[0], path[1])[0]
                dst_port = None

                for key in self.access_table.keys():
                    if flow_info['ipv4_src'] == self.access_table[key]:
                        dst_port = key[1]
                        break
                # actions.append(parser.OFPActionOutput(dst_port))
                host_mac = self.access_table_mac[flow_info['ipv4_src']]
                set_mac1 = parser.OFPActionSetField(eth_dst=EUI(host_mac))
                actions = [set_mac1, parser.OFPActionOutput(dst_port)]

                reversed_flow_info = self.reverse_flow_info(flow_info)

                reversed_flow_info['in_port'] = src_port
                match = parser.OFPMatch(**reversed_flow_info)
                self.logger.info("2 ---datatapath_id:%s -- rev flow info:%s", datapath.id, reversed_flow_info)
                self.add_flow(datapath, 64+path_version, match, actions, routing_mode, idle_timeout=10, hard_timeout=0)
                #########################################################
                # the last hop: tor -> host
                datapath = self.datapaths[path[-1]]
                ofproto = datapath.ofproto
                parser = datapath.ofproto_parser

                actions = []
                src_port = self.get_link2port(path[-2], path[-1])[1]
                dst_port = None

                for key in self.access_table.keys():
                    if flow_info['ipv4_dst'] == self.access_table[key]:
                        dst_port = key[1]
                        break
                # actions.append(parser.OFPActionOutput(dst_port))
                set_mac_host = parser.OFPActionSetField(eth_dst=EUI(self.access_table_mac[flow_info['ipv4_dst']]))
                actions = [set_mac_host, parser.OFPActionOutput(dst_port)]

                flow_info['in_port'] = src_port

                match = parser.OFPMatch(**flow_info)

                self.add_flow(datapath, 69+path_version, match, actions,routing_mode, idle_timeout=10, hard_timeout=0)
                # first pkt_out !!! but Codes! Deleted
                # datapath_first.send_msg(out)

                # last pkt_out
                actions = []
                actions.append(parser.OFPActionOutput(dst_port))

                #######buradan sonra reverse icin########################
                # Normalde son hop sw uzerindeuiz. reverse flow yaziyoruz
                action = []
                port_pair = self.get_link2port(path[-2], path[-1])
                out_port = port_pair[1]

                src_port_info = self.dpset.get_port(path[-1], out_port)
                src_mac = src_port_info.hw_addr
                dst_port_info = self.dpset.get_port(path[-2], port_pair[0])
                dst_mac = dst_port_info.hw_addr

                set_mac1 = parser.OFPActionSetField(eth_src=EUI(src_mac))
                set_mac2 = parser.OFPActionSetField(eth_dst=EUI(dst_mac))
                action = [set_mac1, set_mac2, parser.OFPActionOutput(out_port)]
                #
                reversed_flow_info = self.reverse_flow_info(flow_info)

                reversed_flow_info['in_port'] = dst_port
                match = parser.OFPMatch(**reversed_flow_info)

                self.add_flow(datapath, 68+path_version, match, action,routing_mode, idle_timeout=10, hard_timeout=0)
                #########################################################


            else:  # src and dst on the same

                self.logger.info("TCP SAME HOST === FLOW INSTALL A-4 -----> I am IN ELSE, PATH:%s ", path)

                out_port = None
                actions = []
                for key in self.access_table.keys():
                    if flow_info['ipv4_dst'] == self.access_table[key]:
                        out_port = key[1]
                        break

                actions.append(parser.OFPActionOutput(out_port))

                flow_info['in_port'] = in_port
                match = parser.OFPMatch(**flow_info)

                self.add_flow(
                    datapath_first, 8+path_version, match, actions,routing_mode,
                    idle_timeout=10, hard_timeout=0)

                ## REVERSE FLOW ADD
                reverse_actions = []
                reversed_flow_info = self.reverse_flow_info(flow_info)
                reverse_out_port = in_port
                reverse_in_port=out_port

                reverse_actions.append(parser.OFPActionOutput(reverse_out_port))

                reversed_flow_info['in_port'] = reverse_in_port
                reverse_match = parser.OFPMatch(**reversed_flow_info)

                self.add_flow(
                    datapath_first, 8+path_version, reverse_match, reverse_actions,routing_mode,
                    idle_timeout=10, hard_timeout=0)


                self.logger.info("TCP SAME HOST === FLOW:%s =====REVERSE FLOW:%s ", match,reverse_match)

                # pkt_out deleted!

            self.logger.info("====TCP/ICMP FLOW ADDITION DONE!============ %s",myflow)
            self.logger.info("=========================================================")
        except:
            self.logger.info("==================>DATAPATH EXCEPTION - FLOW CANNOT BE INSTALLED YET!")

            # Geri don buraya!!!!

    def reverse_flow_info(self, flow_info):
        flow_info = flow_info.copy()
        if flow_info['ipv4_dst']:
            temp = flow_info['ipv4_dst']
            flow_info['ipv4_dst'] = flow_info['ipv4_src']
            flow_info['ipv4_src'] = temp

        if flow_info['ip_proto'] == inet.IPPROTO_TCP:
            temp = flow_info['tcp_dst']
            flow_info['tcp_dst'] = flow_info['tcp_src']
            flow_info['tcp_src'] = temp
        if flow_info['ip_proto'] == inet.IPPROTO_UDP:
            temp = flow_info['udp_dst']
            flow_info['udp_dst'] = flow_info['udp_src']
            flow_info['udp_src'] = temp

        return flow_info


    # In packet_in handler,  need to learn access_table by ARP.
    # Therefore, the first packet from UNKOWN host MUST be ARP.
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):

        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)

        eth_type = pkt.get_protocols(ethernet.ethernet)[0].ethertype


        arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        pkt_udp = pkt.get_protocol(udp.udp)
        pkt_tcp = pkt.get_protocol(tcp.tcp)
        pkt_icmp = pkt.get_protocol(icmp.icmp)

        if pkt_tcp:
            dst_port_l4 = pkt_tcp.dst_port
            src_port_l4 = pkt_tcp.src_port

        if pkt_udp:

            dst_port_l4 = pkt_udp.dst_port
            src_port_l4 = pkt_udp.src_port



        if isinstance(arp_pkt, arp.arp):
            arp_src_ip = arp_pkt.src_ip
            arp_dst_ip = arp_pkt.dst_ip

            result = self.get_host_location(arp_dst_ip)
            if result:  # host record in access table.
                datapath_dst, out_port = result[0], result[1]
                actions = [parser.OFPActionOutput(out_port)]
                datapath = self.datapaths[datapath_dst]

                out = parser.OFPPacketOut(
                    datapath=datapath,
                    buffer_id=ofproto.OFP_NO_BUFFER,
                    in_port=ofproto.OFPP_CONTROLLER,
                    actions=actions, data=msg.data)
                datapath.send_msg(out)
            else:  # access info is not existed. send to all host.
                for dpid in self.access_ports:
                    for port in self.access_ports[dpid]:
                        if (dpid, port) not in self.access_table.keys():
                            actions = [parser.OFPActionOutput(port)]
                            datapath = self.datapaths[dpid]
                            out = parser.OFPPacketOut(
                                datapath=datapath,
                                buffer_id=ofproto.OFP_NO_BUFFER,
                                in_port=ofproto.OFPP_CONTROLLER,
                                actions=actions, data=msg.data)
                            datapath.send_msg(out)

        if isinstance(ip_pkt, ipv4.ipv4):
            ip_src = ip_pkt.src
            ip_dst = ip_pkt.dst
            protocol = ip_pkt.proto

            result = None
            src_sw = None
            dst_sw = None

            src_location = self.get_host_location(ip_src)
            dst_location = self.get_host_location(ip_dst)



            ##Find Hosts
            if src_location:
                src_sw = src_location[0]
            else:
                self.find_arp(ip_src)

            if dst_location:
                dst_sw = dst_location[0]
            else:
                self.find_arp(ip_dst)

            if SHOW_ACCESS_TABLE:
                self.logger.info("XXXXXXXXXXXXX-SRC:%s DST:%s ||||||||| ACCESS_TABLE:%s", src_location, dst_location,
                                 self.access_table)

            # Create == Flow_info ===
            if True:

                if pkt_tcp:
                    tcp_dst = pkt_tcp.dst_port
                    tcp_src = pkt_tcp.src_port

                    flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                                     ipv4_src=ip_src, ipv4_dst=ip_dst,
                                     ip_proto=inet.IPPROTO_TCP, tcp_src=tcp_src, tcp_dst=tcp_dst)

                    #qos_req=(src_sw, dst_sw,flow_info,routing_mode,policy)
                    #self.send_qos_req(src_sw, dst_sw,flow_info,routing_mode,policy)

                elif pkt_udp:
                    udp_dst = pkt_udp.dst_port
                    udp_src = pkt_udp.src_port
                    flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                                     ipv4_src=ip_src, ipv4_dst=ip_dst,
                                     ip_proto=protocol, udp_src=pkt_udp.src_port, udp_dst=pkt_udp.dst_port)

                    #qos_req=(src_sw, dst_sw,flow_info,routing_mode,policy)
                    #self.send_qos_req(src_sw, dst_sw,flow_info,routing_mode,policy)



                elif pkt_icmp:

                    flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                                     ipv4_src=ip_src, ipv4_dst=ip_dst,
                                     ip_proto=inet.IPPROTO_ICMP)



                else:
                    self.logger.info("XXXXXXXXXXX ICMP,UDP,TCP DISINDA BIR PAKET XXXXXXXXXXXXXX%s",
                                     pkt.get_protocol(ipv4.ipv4))
                    return

                myflow=self.dict_to_tuple(flow_info)

                if not myflow in self.flowPathMap.keys():

                    #QoS Check
                    policy = self.qos_check(msg)
                    routing_mode=None
                    if policy:
                        policy=policy[0]
                        routing_mode=self.qos_policy_check(policy)
                        #If policy exists, get the first of it as policy

                    ##End of QoS Check

                    self.send_qos_req(src_sw, dst_sw, flow_info, routing_mode, policy)

                else:
                    #DUPLICATE FLOW REQUEST
                    ##self.logger.info("DUPLICATE FLOW REQUEST FOR FLOW : %s",myflow)

                    return

            else:
                # Reflesh the topology database.
                self.network_aware.get_topology(None)


    #suitable path found=resevertaion is done for futher process
    def add_bw_res(self,path,bw):
        self.logger.info("====================IN ADD BW RESERVATION=============%s====%s====================",path,bw)

        for i in xrange(len(path) - 1):

            #current_ = self.netx[path[i]][path[i + 1]]['reserved_bw']
            #self.netx[path[i]][path[i + 1]]['reserved_bw']=float(current_)+float(bw)

            current_ = NETQX[path[i]][path[i + 1]]['reserved_bw']
            NETQX[path[i]][path[i + 1]]['reserved_bw']=float(current_)+float(bw)

    #resevertation is not valid
    def del_bw_res(self,path,bw):
        self.logger.info("====================IN DEL BW RESERVATION=============%s====%s====================",path,bw)

        #min_bw = LINK_SPEED
        for i in xrange(len(path) - 1):

            #current_ = self.netx[path[i]][path[i + 1]]['reserved_bw']
            #self.netx[path[i]][path[i + 1]]['reserved_bw']=float(current_)-float(bw)

            current_ = NETQX[path[i]][path[i + 1]]['reserved_bw']
            NETQX[path[i]][path[i + 1]]['reserved_bw']=float(current_)-float(bw)

    #########################################################
    #########################################################
    # QoS ISSUES     ########################################
    def send_qos_req(self,dp_first, dp_last, flow_info, routing_mode, policy):
        in_port = flow_info['in_port']
        try:
            version_=0
            lock_flag_=False
            path_=0
            same_sw=False

            datapath_first = self.datapaths[dp_first]
            datapath_last = self.datapaths[dp_last]

            parser = datapath_first.ofproto_parser
            ofproto = datapath_first.ofproto
            src,dst=flow_info['ipv4_src'],flow_info['ipv4_dst']
            myflow=self.dict_to_tuple(flow_info)

            self.logger.info("=========================================================")
            self.logger.info("====SEND QOS REQUEST !!!============")

            if flow_info['ip_proto']==inet.IPPROTO_UDP:
                self.logger.info("###### ONE-WAY TRAFIC #############")

            else:
                self.logger.info("###### TWO-WAY TRAFIC #############")

            self.logger.info("====FLOW DETECTED!!!============ %s",myflow)
            self.logger.info("====ROUTING MODE: %s", routing_mode)


            #higher version flow has come!!!! increase version, make lock_flag=True
            if myflow in self.flowPathMap.keys() :
                self.logger.info("FLOW ENTRY RECORD FOUND FOR -------%s",myflow)
                self.logger.info("FLOW ENTRY ==>(unversioned flowpathmap= %s",self.flowPathMap[myflow])
                lock_flag_=True #Cannot be deleted
                version_=self.flowPathMap[myflow][1]
                version_=version_+1


                #self.logger.info("FLOW ENTRY ==>(higherversioned) flowpathmap= %s",self.flowPathMap[myflow])

            #Simdiye kadar ya hic gormedim bu flowu ya da artik cok cok eski bir flow
            #Yeni kayit aciyorum 0 version numarali
            else:
                self.logger.info("NO == FLOW ENTRY RECORD FOUND FOR-------%s",myflow)

                version_=0
                lock_flag_=False
                self.flowPathMap[myflow]=(0,version_,lock_flag_,None)



            if datapath_first.id == datapath_last.id:
                path_of_bw=LINK_SPEED
                path_=[datapath_first.id,datapath_last.id]
                self.logger.info("HOST ARE ON SAME SWITCH!! POLICY NONE!!!! ESTABLISHED Path is: %s -- POLICY:%s", path_,policy)
                same_sw=True
            else:
                if lock_flag_:
                    prev_path=self.flowPathMap[myflow][0]


                path_=[]


                if MIN_HOP_ROUTING:
                    #possible_paths =self.sort_paths_by_min_hop(datapath_first.id, datapath_last.id)
                    #possible_paths = list(possible_paths)
                    #path_ = possible_paths[0][0]

                    path_ = nx.shortest_path(NETQX, source=datapath_first.id, target=datapath_last.id)
                    self.logger.info("huso (MIN-HOP) %s", path_)


                else:
                    if (  int(myflow[3])<2000 and int(myflow[3])>1900 ) or ( int(myflow[3])<11000 and int(myflow[3])>10900 )  \
                            or (  int(myflow[3])<9000 and int(myflow[3])>8900 ) or ( int(myflow[3])<18000 and int(myflow[3])>17900 ) \
                            or (  int(myflow[3])<5000 and int(myflow[3])>4900 ) or ( int(myflow[3])<14000 and int(myflow[3])>13900 ):
                        #self.logger.info("husooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooooo (MIN-HOP) %s", myflow[3]+1)

                        path_ = nx.shortest_path(NETQX, source=datapath_first.id, target=datapath_last.id)
                        self.logger.info("huso (MIN-HOP) %s", path_)

                    elif routing_mode == None:
                        self.logger.info("POLICY NONE!!!")

                        (path_,path_of_bw) = self.find_path(datapath_first.id, datapath_last.id,routing_mode)
                        self.logger.info("POLICY # %s #!!!! YASEMIN NONE##### Path is: %s -Path of bw:%s - POLICY:%s ", routing_mode, path_,path_of_bw,policy)

                    elif routing_mode == 'bw':

                        (path_,path_of_bw) = self.find_path(datapath_first.id, datapath_last.id,routing_mode)
                        self.logger.info("POLICY # %s #!!!! YASEMINBW##### Path is: %s -Path of bw:%s - POLICY:%s ", routing_mode, path_,path_of_bw,policy)

                    elif routing_mode == 'delay':

                        (path_, path_of_bw) = self.find_path(datapath_first.id, datapath_last.id, routing_mode)
                        self.logger.info("POLICY # %s #!!!! YASEMIN DELAY##### Path is: %s -Path of bw:%s - POLICY:%s ",
                                         routing_mode, path_, path_of_bw, policy)






                        # self.logger.info("BW AND DELAY REQUIREMENT(%s kbps) MET!!! The system offers (%s) ",policy['bw'],path_of_bw,self.path_delay_calculate(path))
                        ##################################################################################################
                        ###burasi except icinde degil
                        #self.logger.info("################### CHOSEN PATH : %s \n",path_ )
        except:
            self.logger.info("== send_qos_req exception 1 ==========")



        try:
            if path_:



                self.logger.info("################### FLOW_TABLE (send_qos)==> hosts:%s myflow:%s PATH: %s", (src, dst),
                                 self.flowPathMap[myflow], path_)

                #
                if flow_info['ip_proto'] == inet.IPPROTO_UDP:
                    self.install_flow_unidirect_version2(dp_first, dp_last, flow_info, path_, version_, routing_mode,
                                                         policy)
                    self.logger.info("################### FLOW_TABLE (send_qos ONE-WAY)==> flow: %s === path: %s INSTALLED",
                                     self.flowPathMap[myflow], path_)

                else:
                    self.install_flow_bidirect_version2(dp_first, dp_last, flow_info, path_, version_, routing_mode,
                                                        policy)
                    self.logger.info("################### FLOW_TABLE (send_qos TWO-WAY)==> flow: %s === path: %s INSTALLED",
                                     self.flowPathMap[myflow], path_)

                # SAVE THE CHOSEN PATH FOR GIVEN FLOW
                self.flowPathMap[myflow] = (path_, version_, lock_flag_, policy)

                self.add_flow_to_db(myflow)


                if policy:
                    self.logger.info(
                        "################### flow_path_map => THEREIS PATH AND I LOOK POLICY AND BW :%s ====%s",
                        policy[-1], policy)
                    self.add_bw_res(path_, policy[-1])


            else:
                self.logger.info("###################(in del flow) flow_path_map => no possible path for flow:%s ",myflow)

                del self.flowPathMap[myflow]
                if policy:
                    self.del_bw_res(path_, policy[-1])




        except:
            self.logger.info("== send_qos_req exception 2 ==========")

    #CURRENTLY UNUSED but IMPORTANT -- it periodically checks whether qos violation occurs
    def periodic_qos_fail_detect(self):


        if not self.flowPathMap.keys():
            self.logger.info("CCCCCCCCCC periodic_qos_fail_check : FLOW LIST IS EMPTY")
            pass
        self.logger.info("\nXXXXXXXXXXXXXXXXXXXXXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

        self.logger.info("XXXXXXXXXXXXXXXXXXXXX= New Period for Violation Check =XXXXXXXXXXXXXXXXXXXXXXXXXXXX")

        self.logger.info("CCCCCCCCCC periodic_qos_fail_check : ALL FLOWS : %s\n",self.flowPathMap.keys())
        for flow in self.flowPathMap.keys():
            path,version,flag,policy=self.flowPathMap[flow]
            self.logger.info("CCCCCCCCCC periodic_qos_fail_check : FLOW %s === PATH:%s :",flow,path)

            if path and path[0]==path[1]:
                self.logger.info("CCCCCCCCCC periodic_qos_fail_check POLICY:%s!===SAME SW====!:",path)
                continue

            policy__ = (policy,)
            self.logger.info("CCCCCCCCCC periodic_qos_fail_check POLICY:%s!!!:",policy__)

            routing_mode=self.qos_policy_check(policy)
            dict_flow_info=self.tuple_to_dict(flow)
            self.logger.info("CCCCCCCCCC periodic_qos_fail_check flow_info: %s ---routing mode: %s!!!:",dict_flow_info,routing_mode)



            if path:
                dp_first,dp_last=path[0],path[-1]
                datapath_first = self.datapaths[dp_first]

                #check flow is still living
                self.logger.info("\nCCCCCCCCCC CHECK FLOW IS LIVING OR NOT : %s",path)
                if (dp_first,flow) in self.flowStats.keys():
                    self.logger.info("\nCCCCCCCCCC CHECK FLOW IS LIVING OR NOT : %s",self.flowStats[(dp_first,flow)])

                #match = parser.OFPMatch(**dict_flow_info)
                #datapath_last = self.datapaths[dp_last]

                parser = datapath_first.ofproto_parser
                ofproto = datapath_first.ofproto
                match=parser.OFPMatch(**dict_flow_info)
                self.send_flow_stats_request(datapath_first,match)

            else:
                self.logger.info("CCCCCCCCCC periodic_qos_fail_check ##PATH IS NOT INSTALLED YET !!!:")
                continue



            if routing_mode=='bw':
                policy_bw=float(policy[-1])*1024

                if (dp_first,flow) in self.flowStats.keys():
                    self.logger.info("CCCCCCCCCC periodic_qos_fail_c flow: :%s", flow)
                    (rate, uptime)=self.flowStats[(dp_first, flow)]
                    self.logger.info("CCCCCCCCCC periodic_qos_fail_c rate  :%s", rate)


                    if  rate and rate > policy[-1]*1024:

                        self.logger.info("CCCCCCCCCC periodic_qos_fail_check---BW AZ GELDI:%s==== %s--%s", policy_bw,rate,policy)
                        self.send_qos_req(dp_first,dp_last,dict_flow_info,routing_mode,policy)

                    else:
                        self.logger.info("CCCCCCCCCC periodic_qos_fail_dcheck --- NO-PROBLEM!!!!: %s--%s", rate,policy[-1])
            elif routing_mode=='delay':
                policy_delay=float(policy[-2])
                calced_delay=float(self.path_delay_calculate(path))
                if calced_delay > policy_delay:
                    self.logger.info("CCCCCCCCCC periodic_qos_fail_check---DELAY SLA VIOLATION: %s > %s", calced_delay,policy[-2])
                    self.send_qos_req(dp_first,dp_last,dict_flow_info,routing_mode,policy)
                else:
                    self.logger.info("CCCCCCCCCC periodic_qos_fail_check --- NO-PROBLEM!!!!: %s bps > %s Kbps", calced_delay,policy[-2])

            elif routing_mode=='combined':
                policy_bw=float(policy[-1])*1024
                policy_delay=float(policy[-2])

                calced_delay=float(self.path_delay_calculate(path))
                calced_bw=float(self.path_bw_calculate_usage(path,routing_mode))

                if  calced_delay>policy_delay or calced_bw<policy_bw:
                    self.logger.info("CCCCCCCCCC periodic_qos_fail_check---DELAY&BW PROBLEM:delay: %s  bw:%s", calced_delay,calced_bw)
                    self.send_qos_req(dp_first,dp_last,dict_flow_info,routing_mode,policy)
                else:
                    self.logger.info("CCCCCCCCCC periodic_qos_fail_check --- (COMBINED) NO-PROBLEM!!!! ")



            else:
                self.logger.info("CCCCCCCCCC NO_SLA&POLICY  !!! \n")
            self.logger.info("CCCCCCCCCCCCCCCCCCCCCCCC")
            self.logger.info("CCCCCCCCCCCCCCCCCCCCCCCC")

        self.logger.info("XXXXXXXXXXXXXXXXXXXXXxxxxxxxxxxxxxx END xxxxxxxxxxxxxXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
        self.logger.info("XXXXXXXXXXXXXXXXXXXXXxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxXXXXXXXXXXXXXXXXXXXXXXXXXXXX\n")

    # POLICY to Routing_mode conversion .. It returns mode'delay' or 'bw' etc.
    def qos_policy_check(self,policy):

        if policy:

            routing_mode = 'bw'
            self.logger.info("CCCCCCCCCC QoS POLICY: %s--%s", policy,policy[-1])

            if not policy[-1] == '' and not policy[-2] == '':
                #self.logger.info("both delay and  bw oriented!!!!!!!!!!!!!!!!!")
                routing_mode = 'combined'
                self.logger.info("CCCCCCCCCC QoS POLICY: MODE_COMBINED!!! %s msec --%s bps", policy[-2],policy[-1])

            if not policy[-1] == '' and policy[-2] == '':
                #self.logger.info("only bw oriented!!!!!!!!!!!!!!!!!")
                routing_mode = 'bw'
                self.logger.info("CCCCCCCCCC QoS POLICY: MODE_BANDDDWIDTH!!! %s KBPS--", policy[-1])


            if policy[-1] == '' and not policy[-2] == '':
                #self.logger.info("only delay oriented!!!!!!!!!!!!!!!!!")
                self.logger.info("CCCCCCCCCC QoS POLICY: MODE_DELAY!!! %s msec --", policy[-2])

                routing_mode = 'delay'
        else:
            routing_mode = None
            #self.logger.info("only NONE oriented!!!!!!!!!!!!!!!!!")

        return routing_mode

    # When a new packet arrives, check it from SLA DB whether it has SLA or not.
    def qos_check(self, msg):
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        pkt = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)


        #arp_pkt = pkt.get_protocol(arp.arp)
        ip_pkt = pkt.get_protocol(ipv4.ipv4)
        pkt_udp = pkt.get_protocol(udp.udp)
        pkt_tcp = pkt.get_protocol(tcp.tcp)
        pkt_icmp = pkt.get_protocol(icmp.icmp)


        if isinstance(pkt_icmp, icmp.icmp):
            return None


        if eth_pkt:
            src_mac=eth_pkt.src
            dst_mac=eth_pkt.dst


        if isinstance(ip_pkt, ipv4.ipv4):

            if pkt_tcp:
                dst_port = pkt_tcp.dst_port
                src_port = pkt_tcp.src_port

            if pkt_udp:

                dst_port = pkt_udp.dst_port
                src_port = pkt_udp.src_port

            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst
            protocol = ip_pkt.proto

            #select *,case src_ip when '10.0.7.2' then 1 else 0 end + case dst_port when 443 then 1 else 0 end as matches from policies order by matches desc;
            #sql_request = "SELECT * FROM policies WHERE (src_ip='%s' AND dst_ip='%s') OR (src_ip='%s' AND dst_ip='x') OR (src_ip='x' AND dst_ip='%s')" % (
            #src, dst, src, dst)

            ####esas oglan bu!!!
            ##sql_request="select *,case src_ip when '%s' then 1 else 0 end + case src_mac when '%s' then 1 else 0 end + case ip_dst when '%s' then 1 else 0 end + case dst_mac when '%s' then 1 else 0 end + case ip_proto when '%s' then 1 else 0 end + case src_port when '%s' then 1 else 0 end + case dst_port when '%s' then 1 else 0 end + case vlan when '%s' then 1 else 0 end + case tos when '%s' then 1 else 0 end as matches from policies order by matches desc"  % (
            ##ip_src, src_mac, ip_dst, dst_mac, ip_proto, src_port, dst_port, vlan, tos)

            #binary ip yapmadan once exact match
            #sql_request="select *,case src_ip when '%s' then 1 else 0 end + case src_mac when '%s' then 1 else 0 end + case dst_ip when '%s' then 1 else 0 end + case dst_mac when '%s' then 1 else 0 end + case ip_proto when '%s' then 1 else 0 end + case src_port when '%s' then 1 else 0 end + case dst_port when '%s' then 1 else 0 end as matches from policies order by matches desc"  % (
            #src_ip, src_mac, dst_ip, dst_mac, protocol, src_port, dst_port)

            src_ip=self.ip2bin(src_ip)
            dst_ip=self.ip2bin(dst_ip)

            sql_request="select *,case WHEN '%s' LIKE CONCAT(src_ip,'%%') then 1 else 0 end + case src_mac when '%s' then 1 else 0 end + case WHEN '%s' LIKE CONCAT(dst_ip,'%%') then 1 else 0 end + case dst_mac when '%s' then 1 else 0 end + case ip_proto when '%s' then 1 else 0 end + case src_port when '%s' then 1 else 0 end + case dst_port when '%s' then 1 else 0 end as matches from policies order by matches desc"  % (
                src_ip, src_mac, dst_ip, dst_mac, protocol, src_port, dst_port)


            self.logger.info("--------------------> SQL_REQUEST: %s", sql_request)

            cur = self.db.cursor()
            cur.execute(sql_request)
            # print all the first cell of all the rows
            self.logger.info("(POLICY DB QUERY)----- QoS POLICY COUNT (MATCHED) %s#", cur.rowcount)

            if cur.rowcount > 0:
                ihave=cur.fetchmany(size=1)
                self.logger.info("DB_SCRIPT------ POLICY : %s", ihave[0])
                ihave_=ihave[0]
                #self.logger.info("DB_SCRIPT------ POLICYu : matches yasemin: %s", ihave_[-1])
                match_field_number=ihave_[-1]
                policy_id=ihave_[0]


                sql_request_empty_check="select *,case src_ip when '' then 1 else 0 end + case src_mac when '' then 1 else 0 end + case dst_ip when '' then 1 else 0 end + case dst_mac when '' then 1 else 0 end + case ip_proto when '' then 1 else 0 end + case src_port when '' then 1 else 0 end + case dst_port when '' then 1 else 0 end as matches from policies where id='%s' order by matches desc" % (policy_id)
                cur.execute(sql_request_empty_check)
                ihave22=cur.fetchmany(size=1)
                number_empty_field=ihave22[0][-1]
                #self.logger.info("DB_SCRIPT------ NUMBER OF EMPTY FIELD : %s", number_empty_field)

                if int(number_empty_field)+int(match_field_number)<7:
                    self.logger.info("DB_SCRIPT------ not not not EXACT MATCH !!!")
                    return None

                self.logger.info("DB_SCRIPT------ EXACT MATCH !!!")

                return (ihave_[0:-1],)
            else:
                return None


    #########################################################
    #########################################################
    # FLOW ISSUES    ########################################

    #UNUSED- UPDATE THE PATH OF FLOW FROM DB
    def update_flow_path_db(self,flow):

        path=self.flowPathMap[flow][0]

        self.logger.info("################### DATABASE ACTIVE FLOW ENTRY UPDATED: %s-%s--%s",flow,len(flow),path)

        if len(flow)==4:
            src_ip = flow[0]
            dst_ip = flow[1]
            ip_proto = flow[2]
            vlan = 0
            src_mac = self.access_table_mac[src_ip]
            dst_mac = self.access_table_mac[dst_ip]
            cur = self.db.cursor()
            sql_request = "UPDATE activeflows SET path='%s' WHERE ( src_ip='%s', src_mac='%s', dst_ip='%s' ,dst_mac='%s', ip_proto='%s',vlan='%s')" % (
                path,src_ip, src_mac, dst_ip ,dst_mac, ip_proto,vlan)
            self.logger.info("################### DATABASE ACTIVE FLOW ENTRY UPDATED ICMP:(sql_request) %s",sql_request)
            cur.execute(sql_request)
            self.db.commit()
        else:

            vlan = 0
            src_ip = flow[0]
            src_mac = self.access_table_mac[src_ip]
            dst_ip = flow[1]
            dst_mac = self.access_table_mac[dst_ip]
            ip_proto = flow[4]
            src_port = flow[2]
            dst_port = flow[3]


            cur = self.db.cursor()
            sql_request = "UPDATE activeflows SET path='%s' WHERE ( src_ip='%s', src_mac='%s', dst_ip='%s' ,dst_mac='%s', ip_proto='%s',src_port='%s',dst_port='%s',vlan='%s')" % (
                path,src_ip, src_mac, dst_ip ,dst_mac, ip_proto,src_port,dst_port,vlan)
            self.logger.info("################### DATABASE ACTIVE FLOW ENTRY UPDATED:(sql_request) %s",sql_request)
            cur.execute(sql_request)
            self.db.commit()

    #Add flow to DB
    def add_flow_to_db(self,flow):
        path=self.flowPathMap[flow][0]
        version=self.flowPathMap[flow][1]

        self.logger.info("################### DATABASE ACTIVE FLOW ENTRY INSERTED: %s-%s--%s",flow,len(flow),path)

        if len(flow)==4:
            src_ip = flow[0]
            dst_ip = flow[1]
            ip_proto = flow[2]
            vlan = 0
            src_mac = self.access_table_mac[src_ip]
            dst_mac = self.access_table_mac[dst_ip]
            cur = self.db.cursor()
            if version:
                sql_request = "UPDATE activeflows SET path=%s WHERE ( src_ip and  src_mac and  dst_ip  and dst_mac and  ip_proto and vlan) VALUES (  '%s' and  '%s' and  '%s' and  '%s' and  '%s' and  '%s' ) " % (
                    path, src_ip, src_mac, dst_ip ,dst_mac, ip_proto,vlan)
            else:
                sql_request = "INSERT INTO activeflows ( src_ip, src_mac, dst_ip ,dst_mac, ip_proto,vlan,path) VALUES (  '%s', '%s', '%s', '%s', '%s', '%s', '%s' ) " % (
                    src_ip, src_mac, dst_ip ,dst_mac, ip_proto,vlan, path)
            self.logger.info("################### DATABASE ACTIVE FLOW ENTRY INSERTED ICMP:(sql_request) %s",sql_request)
            cur.execute(sql_request)
            self.db.commit()
        else:

            vlan = 0
            src_ip = flow[0]
            src_mac = self.access_table_mac[src_ip]
            dst_ip = flow[1]
            dst_mac = self.access_table_mac[dst_ip]
            ip_proto = flow[4]
            src_port = flow[2]
            dst_port = flow[3]


            cur = self.db.cursor()
            if version:
                #sql_request = "UPDATE activeflows SET path=%s WHERE ( src_ip, src_mac, dst_ip ,dst_mac, ip_proto, src_port,dst_port,vlan ) VALUES (  '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s') " % (
                #       path, src_ip, src_mac, dst_ip ,dst_mac, ip_proto, src_port,dst_port,vlan)
                sql_request = "UPDATE activeflows SET path='%s' WHERE src_ip = '%s' and  src_mac = '%s' and  dst_ip = '%s'  and dst_mac = '%s' and  ip_proto = '%s' and  src_port = '%s' and dst_port = '%s' and vlan = '%s' " % (
                    path, src_ip, src_mac, dst_ip, dst_mac, ip_proto, src_port, dst_port, vlan)

            else:
                sql_request = "INSERT INTO activeflows ( src_ip, src_mac, dst_ip ,dst_mac, ip_proto, src_port,dst_port,vlan,path) VALUES ( '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s' ) " % (
                    src_ip, src_mac, dst_ip ,dst_mac, ip_proto, src_port,dst_port,vlan,path)
            self.logger.info("################### DATABASE ACTIVE FLOW ENTRY INSERTED:(sql_request) %s",sql_request)
            cur.execute(sql_request)
            self.db.commit()

    #Delete flow from DB
    def del_flow_from_db(self,flow):

        self.logger.info("################### DATABASE PASSIVE FLOW DELETED: %s",flow)

        vlan = 0
        src_ip = flow[0]
        src_mac = self.access_table_mac[src_ip]
        dst_ip = flow[1]
        dst_mac = self.access_table_mac[dst_ip]

        #ICMP
        if len(flow)==4:
            ip_proto=flow[2]
            cur = self.db.cursor()
            sql_request = "DELETE FROM activeflows WHERE src_ip='%s' and src_mac='%s' and dst_ip='%s' and dst_mac='%s' and ip_proto='%s'and vlan='%s' " % (
                src_ip, src_mac, dst_ip ,dst_mac, ip_proto,vlan)
            cur.execute(sql_request)
            self.db.commit()
        else:
            ip_proto = flow[4]
            src_port = flow[2]
            dst_port = flow[3]

            cur = self.db.cursor()
            sql_request = "DELETE FROM activeflows WHERE src_ip='%s' and src_mac='%s' and dst_ip='%s' and dst_mac='%s' and ip_proto='%s' and src_port='%s' and dst_port='%s' and vlan='%s' " % (
                src_ip, src_mac, dst_ip ,dst_mac, ip_proto, src_port,dst_port,vlan)
            self.logger.info("################### DATABASE PASSIVE FLOW DELETED: SQL Request: %s",sql_request)

            cur.execute(sql_request)
            self.db.commit()

    #path bw calculation with PORT  QUEUE
    def path_bw_calculate_usage(self, path, mode=None):

        if mode==None:
            queue_number=47
            bufsize=Q47_BUF
        elif mode=='bw':
            queue_number=31
            bufsize=Q31_BUF
        elif mode=='delay' or mode=='combined':
            queue_number=15
            bufsize=Q15_BUF
        else:
            self.logger.info("############# warning: shortest route.py unknown routing mode: %s ",mode)

        queue_id = 'queue_id_' + str(queue_number)

        max_bw = 0
        for i in xrange(len(path) - 1):

            current_bw = NETQX[path[i]][path[i + 1]][queue_id][0] #bandwidth
            self.logger.info("############# PATH BW CALCULATE FOR %s -- %s for queue_id:%s -",path,current_bw,queue_id)

            if current_bw > 0 and current_bw > max_bw:
                max_bw = current_bw


        #return bufsize-max_bw
        return max_bw
        #return LINK_SPEED-max_bw

    #Remaining bw'e gore sort eder. NETQX in queue_1 de arar..
    def sort_paths_by_bw_used(self, src_sw, dst_sw, mode=None):

        poso=nx.all_simple_paths(NETQX,src_sw,dst_sw)

        #possible_paths = list(possible_paths)
        possible_paths = list(poso)


        route_dict = []
        for pathik in possible_paths:
            used_bw = self.path_bw_calculate_usage(pathik,mode)
            # used_bw = self.path_bw_calculate(pathik, mode)
            route_dict.append([pathik, used_bw,len(pathik)])

        route_dict.sort(key=lambda tup: (tup[1], tup[2]), reverse=False)



        self.logger.info("SORTED PATHS REGARDING -(used_bw) %s", route_dict)


        return route_dict

    #burayi min max load yapacagim.
    def path_delay_calculate(self, path, mode='delay'):
        self.logger.info("#####in path delay path calc######## PATH max load of path:%s--mode: %s -",path,mode)
        if mode == None:
            queue_number=2
            bufsize=Q47_BUF
        elif mode  =='bw':
            queue_number=1
            bufsize=Q31_BUF
        elif mode =='delay' or mode =='combined':
            queue_number=0
            bufsize=Q15_BUF
        else:
            self.logger.info("############# warning: shortest route.py unknown routing mode: %s ",mode)


        max_load=1.0
        #total_delay = 0.0
        for i in xrange(len(path) - 1):

            queue_id = 'queue_id_' + str(queue_number)
            current_load = NETQX[path[i]][path[i + 1]][queue_id][2]  # bandwidth


            # self.logger.info("############# PATH BW CALCULATE FOR %s -- %s for queue_id:%s -",path,current_bw,queue_id)

            if current_load > 0 and current_load > max_load:
                max_load = "{:10.4f}".format(current_load)


        self.logger.info("############# MAX_LOAD CALCULATE FOR %s ++++++++++++ %s -",path, max_load)


        return max_load

    def sort_paths_by_delay(self, src_sw, dst_sw,mode='delay'):


        poso = nx.all_simple_paths(NETQX, src_sw, dst_sw, 7)

        # possible_paths = list(possible_paths)
        simple_paths = list(poso)


        self.logger.info("########### SORT PATH::::::::::::::::::::::::::::: %s -- ", simple_paths)

        route_dict = []
        for pathik in simple_paths:
            total_delay = self.path_delay_calculate(pathik,mode)
            route_dict.append([pathik, total_delay,len(pathik)])

        route_dict.sort(key=lambda tup: (tup[1],tup[2]), reverse=False)

        self.logger.info(" ROUTE___DICTIONARY==--(DELAY) %s \n", route_dict)

        return route_dict

    #FIND MIN-HOP PATH within all possible paths between src and dst
    def sort_paths_by_min_hop(self, src_sw, dst_sw, mode=None):

        poso=nx.all_simple_paths(NETQX,src_sw,dst_sw)

        #possible_paths = list(possible_paths)
        possible_paths = list(poso)


        route_dict = []
        for pathik in possible_paths:
            reserved_bw = 0 # garbage variable
            route_dict.append([pathik, reserved_bw,len(pathik)])

        #route_dict.sort(key=lambda tup: tup[1], reverse=True)
        route_dict.sort(key=lambda tup: tup[2])

        self.logger.info("SORTED PATHS REGARDING -(MIN-HOP) %s", route_dict)

        return route_dict


    #########################################################
    def find_path(self, src_sw, dst_sw, mode=None):
        #self.logger.info("Allah$$$$$$$$$$$$$$$$ -(MIN-HOP) %s", self.pX['1][6])

        fuzzy_tuple = self.shortest_fuzzy_path(NETQX, src_sw, dst_sw)
        self.logger.info('fuzzy shortest path: %s', fuzzy_tuple)
        cost_of_path = fuzzy_tuple[0][3]  # atmaca
        path_ = fuzzy_tuple[1]

        return (path_, cost_of_path)
    #########################################################
    #  FUZZY ISSUES    ########################################
    #########################################################
    def dijkstra(self, graph, initial,mode=None):
        # self.logger.info('dijkstraaaaaaaaaaaaaaaaaa ')

        # visited = {initial: 0}



        visited = {initial: [LINK_SPEED, 1, 0, 10,LINK_SPEED,0]}



        path = {}
        beta = 0.8

        nodes = set(graph.nodes)
        edges = set(graph.edges)
        pathList = nx.single_source_shortest_path(NETQX, initial)
        HMAX = len(nodes)-1
        self.logger.info('dijkstraaaaaaaaaaaaaaaaaa HMAXX: %s - %s', pathList,HMAX)


        if mode == None:
            queue_number=47
        elif mode  =='bw':
            queue_number=31
        elif mode =='delay' or mode =='combined':
            queue_number=15
        else:
            queue_number=0
            self.logger.info("############# warning: shortest route.py unknown routing mode: %s ",mode)


        queue_id = 'queue_id_' + str(queue_number)


        while nodes:
            min_node = None
            for node in nodes:
                if node in visited:
                    #self.logger.info('dijkstraaaaaaaaaaaaaaaaaa visited[node]: %s visited[node]:%s ', visited[node], visited[min_node])

                    if min_node is None:
                        min_node = node


                    elif visited[node][3] < visited[min_node][3]:

                        min_node = node

            if min_node is None:
                break

            nodes.remove(min_node)

            current_weight = visited[min_node]

            error_rate=0

            # for edge in graph.edges[min_node]:
            for edge in graph[min_node]:
                #1#self.logger.info('dijkstraaaaaaaaaaaaaaaaaa loopP edge: %s --- min_node_removed_: %s ', edge,min_node)

                try:
                    # hopCount = current_weight[2] + 1
                    weight = []

                    # self.logger.info('dijkstraaaaaaaaaaaaaaaaaa loopP graph edge: %s ', graph[min_node][edge]['queue_id_0'])
                    # graph edge: {'reserved_bw': 200, 'residual_bw': 300000000, 'delay': inf, 'bandwidth': 100, 'queue_id_15': (0, 0, 0, 1000), 'queue_id_0': (0, 0, 0, 1000), 'queue_id_47': (0, 0, 0, 1000),

                    if mode == 'delay':
                        #queue_load = graph[min_node][edge]['queue_id_47'][0]+graph[min_node][edge]['queue_id_31'][0]*1.618+ graph[min_node][edge]['queue_id_15'][0]*2.617

                        #queue_load=graph[min_node][edge]['queue_id_47'][0]*0.618+graph[min_node][edge]['queue_id_31'][0]*0.618+ graph[min_node][edge]['queue_id_15'][0]*1
                        queue_load = graph[min_node][edge]['queue_id_0'][0]
                        #queue_load_prio = graph[min_node][edge]['queue_id_15'][0]
                        queue_load_prio = 0

                        error_rate=graph[min_node][edge]['queue_id_15'][1]


                    elif mode == 'bw':
                        #queue_load=graph[min_node][edge]['queue_id_47'][0]*0.618+graph[min_node][edge]['queue_id_31'][0]*1+ graph[min_node][edge]['queue_id_15'][0]*1.618
                        # queue_load = graph[min_node][edge]['queue_id_47'][0]+graph[min_node][edge]['queue_id_31'][0]*1.618+ graph[min_node][edge]['queue_id_15'][0]*2.617

                        queue_load = graph[min_node][edge]['queue_id_0'][0]
                        queue_load_prio =  graph[min_node][edge]['queue_id_15'][0]

                        error_rate = graph[min_node][edge]['queue_id_31'][1]

                    elif mode == None:
                        # queue_load = graph[min_node][edge]['queue_id_47'][0]+graph[min_node][edge]['queue_id_31'][0]*1.618+ graph[min_node][edge]['queue_id_15'][0]*2.617
                        queue_load = graph[min_node][edge]['queue_id_0'][0]
                        queue_load_prio=graph[min_node][edge]['queue_id_31'][0]+ graph[min_node][edge]['queue_id_15'][0]
                        error_rate = graph[min_node][edge]['queue_id_47'][1]

                    unreserved_bw = LINK_SPEED-queue_load
                    if unreserved_bw<0:
                        self.logger.info('dijkstraaaaaaaaaaaaaaaaaa NO PATH - NEGATIVE BW')
                        unreserved_bw=0

                    BW_MIN = 100
                    BW_MAX = LINK_SPEED

                    # if unreserved_bw>BW_MAX:

                    unreserved_prio_bw=LINK_SPEED-queue_load_prio

                    pathBw = min(current_weight[0], unreserved_bw)
                    pathPrioBw = min(current_weight[0], unreserved_prio_bw)
                    #1#self.logger.info('dijkstraaaaaaaaaaaaaaaaaa 111 Path PRIO BW: %s == current_weight(4):%s === unreserved_prio_bw: %s ',pathPrioBw, current_weight[4],unreserved_prio_bw)

                    ##pathDelay = current_weight[1] + graph[min_node][edge][queue_id][1]
                    hopCount = current_weight[2] + 1
                    #self.logger.info('dijkstraaaaaaaaaaaaaaaaaa1111 = pathBw:%s = current_weight[0]:%s ==== loopP graph edge: %s ',pathBw,current_weight[0],graph[min_node][edge])

                    fuzzBw = self.calc_pxy(pathBw, 100, LINK_SPEED)
                    fuzzPrioBw = self.calc_pxy(pathPrioBw, 100, LINK_SPEED)

                    #fuzzPrioBw = self.calc_prio_pxy(pathPrioBw, 100, LINK_SPEED)
                    fuzzHop = self.calc_hxy(hopCount, 1, 6)

                    fuzzError= self.calc_err(error_rate,5,120)
                    #1#self.logger.info('dijkstraaaaaaaaaaaaaaaaaa111 -- current_weight:%s - unreserved_bw: %s ', current_weight, unreserved_bw)

                    #1#self.logger.info('dijkstraaaaaaaaaaaaaaaaaa222 -- Graph Bw:%s - ', graph[min_node][edge][queue_id][0])

                    self.logger.info('dijkstraaaaaaaaaaaaaaaaaa222 -- loopP graph edge: Bw:%s - FuzBw: %s -# fuzBW PRIO: %s #-  Hop:%s -- fuzHop:%s # fuzzErr:%s', pathBw,fuzzBw,fuzzPrioBw,hopCount,fuzzHop,fuzzError)

                    #
                    S_u=1/(1.0+len(pathList[edge]))
                    #

                    unresv_load = (unreserved_bw-BW_MIN)/(BW_MAX-BW_MIN-0.0)
                    S_j=S_u*(1.0-unresv_load)
                    lxy = current_weight[1] - S_j
                    #1#self.logger.info("dijkstraaaaaaaaaaaaaaaaaa <S_u: %s> lxy: %s --- unresv_load:%s -----Sj:%s ", S_u,lxy,unresv_load,S_j)

                    # fuzzBw = calc_pxy(pathDelay, 100, 1000)
                    if mode == 'delay':
                        #fuzzTotal = beta * min(fuzzBw, fuzzHop,lxy) + (1 - beta) * 1 / 3 * (fuzzBw + fuzzHop+lxy)
                        fuzzTotal = beta * min(fuzzBw, fuzzHop ,fuzzError) + (1 - beta) * 1 / 3 * (fuzzBw + fuzzHop +fuzzError)

                    else:
                        #fuzzTotal = beta * min(fuzzBw, fuzzPrioBw, fuzzHop, lxy) + (1 - beta) * 1 / 4 * (
                        #fuzzBw + fuzzPrioBw + fuzzHop + lxy)
                        fuzzTotal = beta * min(fuzzBw, fuzzPrioBw, fuzzHop, fuzzError) + (1 - beta) * 1 / 4 * (fuzzBw + fuzzPrioBw + fuzzHop +fuzzError)
                        self.logger.info("dijkstra Fuzz HOP(%s): %s> fuzzError: %s   ", hopCount,fuzzHop,fuzzError)



                    weight = [pathBw, lxy, hopCount, fuzzTotal,fuzzPrioBw,error_rate]

                except:
                    err_msg = sys.exc_info()[0]
                    self.logger.info("<except Djkstra: %s>   ", err_msg)
                    continue

                if edge not in visited or weight[3] > visited[edge][3]:


                    visited[edge] = weight
                    path[edge] = min_node

                    self.logger.info('dijkstraaaaaaaaaaaaaaaaaa44444 UPDATE: Total: %s -- min_node:%s --CurrentPath:%s', weight, min_node,path)


        return visited, path

    def shortest_fuzzy_path(self, graph, origin, destination,mode=None):

        # Run:     print(shortest_fuzzy_path(graph, 'A', 'B')) # output: (25, ['A', 'B', 'D'])
        # self.logger.info(' shortest_fuzzy_pa dijkstraaaaaaaaaaaaaaaaaa ')

        visited, paths = self.dijkstra(graph, origin,mode)
        # self.logger.info(' shortest_fuzzy_pa dijkstraaaaaaaaaaaaaaaaaa 22222222222222')

        full_path = deque()
        _destination = paths[destination]

        while _destination != origin:
            full_path.appendleft(_destination)
            _destination = paths[_destination]

        full_path.appendleft(origin)
        full_path.append(destination)
        #1#self.logger.info(' shortest_fuzzy_pa dijkstraaaaaaaaaaaaaaaaaa 3333 %s - %s',visited[destination],list(full_path))

        return visited[destination], list(full_path)

    def calc_pxy(self, x, minBw=100, maxBw=100):

        if x <= minBw:
            return 0.25

        if minBw < x < maxBw:
            return 0.75 * (x - minBw) / (maxBw - minBw + 0.0) + 0.25

        if maxBw <= x:
            return 1

    def calc_err(self, x, minErr, maxErr):
        m = 0.4
        if x <= minErr:
            return 1
        if minErr < x <= maxErr:
            return ((maxErr - x) * (1 - m) / (maxErr - minErr)) + m
            # return (x-minH)/(3/4*(maxH-minH))
        if maxErr < x:
            return 0

    def calc(self, input1, input2, input3):

        x_hop = np.arange(0, 1000, 1)
        x_delay = np.arange(0, 600, 1)
        x_loss = np.arange(1, 11, 1)

        bandwidth = ctrl.Antecedent(x_hop, 'bandwidth')
        delay = ctrl.Antecedent(x_delay, 'delay')
        lossCount = ctrl.Antecedent(x_loss, 'lossCount')

        tip = ctrl.Consequent(np.arange(0, 11, 1), 'tip')

        names = ['lo', 'md', 'hi']

        # bandwidth.automf(names=names)
        # delay.automf(names=names)
        # tip.automf(names=names)
        # Generate fuzzy membership functions
        bandwidth['lo'] = fuzz.trimf(x_hop, [0, 0, 400])  # (start,top,stop)
        bandwidth['md'] = fuzz.trimf(x_hop, [100, 500, 900])
        bandwidth['hi'] = fuzz.trimf(x_hop, [600, 1000, 1000])

        delay['lo'] = fuzz.trimf(x_delay, [0, 0, 240])  # (start,top,stop)
        delay['md'] = fuzz.trimf(x_delay, [60, 300, 540])
        delay['hi'] = fuzz.trimf(x_delay, [360, 600, 600])

        lossCount['lo'] = fuzz.trimf(x_loss, [0, 0, 4])  # (start,top,stop)
        lossCount['md'] = fuzz.trimf(x_loss, [1, 5, 9])
        lossCount['hi'] = fuzz.trimf(x_loss, [6, 10, 10])

        tip['lo'] = fuzz.trimf(tip.universe, [0, 0, 5])
        tip['md'] = fuzz.trimf(tip.universe, [0, 5, 11])
        tip['hi'] = fuzz.trimf(tip.universe, [5, 11, 11])

        rule1 = ctrl.Rule(antecedent=(
            (bandwidth['lo'] & delay['lo'] & lossCount['lo']) |
            (bandwidth['lo'] & delay['lo'] & lossCount['md']) |
            (bandwidth['lo'] & delay['lo'] & lossCount['hi']) |
            (bandwidth['lo'] & delay['md'] & lossCount['lo']) |
            (bandwidth['lo'] & delay['md'] & lossCount['md']) |
            (bandwidth['lo'] & delay['md'] & lossCount['hi']) |
            (bandwidth['lo'] & delay['hi'] & lossCount['lo']) |
            (bandwidth['lo'] & delay['hi'] & lossCount['md']) |
            (bandwidth['lo'] & delay['hi'] & lossCount['hi']) |
            (bandwidth['md'] & delay['md'] & lossCount['md']) |
            (bandwidth['md'] & delay['md'] & lossCount['hi']) |
            (bandwidth['md'] & delay['hi'] & lossCount['lo']) |
            (bandwidth['md'] & delay['hi'] & lossCount['md']) |
            (bandwidth['md'] & delay['hi'] & lossCount['hi']) |
            (bandwidth['hi'] & delay['hi'] & lossCount['hi'])
        ),
            consequent=tip['lo'], label='rule ns')

        rule2 = ctrl.Rule(antecedent=(

            (bandwidth['md'] & delay['lo'] & lossCount['lo']) |
            (bandwidth['md'] & delay['lo'] & lossCount['md']) |
            (bandwidth['md'] & delay['lo'] & lossCount['hi']) |
            (bandwidth['md'] & delay['md'] & lossCount['lo']) |

            (bandwidth['hi'] & delay['lo'] & lossCount['hi']) |
            (bandwidth['hi'] & delay['md'] & lossCount['md']) |
            (bandwidth['hi'] & delay['md'] & lossCount['hi']) |
            (bandwidth['hi'] & delay['hi'] & lossCount['lo']) |
            (bandwidth['hi'] & delay['hi'] & lossCount['md'])
        ),
            consequent=tip['md'], label='rule ze')

        rule3 = ctrl.Rule(antecedent=(
            (bandwidth['hi'] & delay['lo'] & lossCount['lo']) |
            (bandwidth['hi'] & delay['lo'] & lossCount['md']) |
            (bandwidth['hi'] & delay['md'] & lossCount['lo'])

        ),
            consequent=tip['hi'], label='rule ps')

        # system = ctrl.ControlSystem(rules=[rule1, rule2, rule3])

        # bandwidth.view()
        # delay.view()




        tipping_ctrl = ctrl.ControlSystem([rule1, rule2, rule3])
        tipping = ctrl.ControlSystemSimulation(tipping_ctrl)

        tipping.input['bandwidth'] = input1
        tipping.input['delay'] = input2
        tipping.input['lossCount'] = input3

        # Crunch the numbers
        tipping.compute()
        ############
        # print '###########',tipping.output['tip']
        return tipping.output['tip']

        #########################################################

    def calc_hxy(self, x, minH, maxH):

        m = 0.4
        if x <= minH:
            return 1
        if minH < x <= maxH:
            return ((maxH - x) * (1 - m) / (maxH - minH)) + m
            # return (x-minH)/(3/4*(maxH-minH))
        if maxH < x:
            return 0

    #########################################################
    #########################################################
    # ARP and HOST ISSUE      ###############################
    def _handle_arp1(self, datapath, dst_ip_addr):

        temp = dst_ip_addr.split('.', 3)

        gateway_ip = temp[0] + '.' + temp[1] + '.' + temp[2] + '.1'

        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=ether.ETH_TYPE_ARP,
                                           dst='ff:ff:ff:ff:ff:ff',
                                           src='00:00:00:00:00:22'))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REQUEST,
                                 src_mac='00:00:00:00:00:22',
                                 src_ip=gateway_ip,
                                 dst_mac='00:00:00:00:00:00',
                                 dst_ip=dst_ip_addr))
        pkt.serialize()
        ofproto = datapath.ofproto

        parser = datapath.ofproto_parser
        data = pkt.data
        actions = [parser.OFPActionOutput(port=ofproto.OFPP_ALL)]

        out = parser.OFPPacketOut(datapath=datapath,
                                  buffer_id=ofproto.OFP_NO_BUFFER,
                                  in_port=ofproto.OFPP_CONTROLLER,
                                  actions=actions,
                                  data=data)
        datapath.send_msg(out)

    def find_arp(self, ip_addr):
        ###self._send_packet(datapath, port, pkt)

        for key in self.datapaths.keys():
            dp = self.datapaths[key]
            self._handle_arp1(dp, ip_addr)

            # this function checks a packet whether qos rule is defined for it or not.
            # But, works very primitively. Needs to be developed and upgraded!
            # But, works very primitively. Needs to be developed and upgraded!

    # Returns the datapath(sw) that host is connected. ip veriyoruz
    def get_host_location(self, host_ip):
        for key in self.access_table:
            if self.access_table[key] == host_ip:
                return key
        self.logger.debug("%s location is not found." % host_ip)
        return None

    # Get which ports are used to connect to neighbor switch
    def get_link2port(self, src_dpid, dst_dpid):
        if (src_dpid, dst_dpid) in self.link_to_port:
            return self.link_to_port[(src_dpid, dst_dpid)]
        else:
            self.logger.debug("Link to port is not found.")
            return None


    #########################################################
    #########################################################
    # CONVERTERS     ########################################

    def ipv4_to_int(self, string):
        ip = string.split('.')
        assert len(ip) == 4
        i = 0
        for b in ip:
            b = int(b)
            i = (i << 8) | b
        return i

    def ip2bin(self,ip):
        ipBinary = ''.join([bin(int(x)+256)[3:] for x in ip.split('.')])
        return ipBinary

    def dict_to_tuple(self,flow_info):

        if flow_info is None:
            return None

        myflow=''

        if flow_info['ip_proto'] == inet.IPPROTO_TCP:
            myflow=(flow_info['ipv4_src'],flow_info['ipv4_dst'],flow_info['tcp_src'],flow_info['tcp_dst'],flow_info['ip_proto'],flow_info['in_port'])

        if flow_info['ip_proto'] == inet.IPPROTO_UDP:
            myflow=(flow_info['ipv4_src'],flow_info['ipv4_dst'],flow_info['udp_src'],flow_info['udp_dst'],flow_info['ip_proto'],flow_info['in_port'])

        if flow_info['ip_proto'] == inet.IPPROTO_ICMP:
            myflow=(flow_info['ipv4_src'],flow_info['ipv4_dst'],flow_info['ip_proto'],flow_info['in_port'])

        return myflow

    def tuple_to_dict(self,flow):

        ip_src,ip_dst=flow[0],flow[1]
        src_port,dst_port=flow[2],flow[3]
        in_port=flow[-1]


        if flow[-2] == inet.IPPROTO_TCP:
            #myflow=(flow_info['ipv4_src'],flow_info['ipv4_dst'],flow_info['tcp_src'],flow_info['tcp_dst'],flow_info['ip_proto'],flow_info['in_port'])
            flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                             ipv4_src=ip_src, ipv4_dst=ip_dst,
                             ip_proto=inet.IPPROTO_TCP, tcp_src=src_port, tcp_dst=dst_port)
        if flow[-2] == inet.IPPROTO_UDP:
            #myflow=(flow_info['ipv4_src'],flow_info['ipv4_dst'],flow_info['udp_src'],flow_info['udp_dst'],flow_info['ip_proto'],flow_info['in_port'])
            flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                             ipv4_src=ip_src, ipv4_dst=ip_dst,
                             ip_proto=inet.IPPROTO_UDP, udp_src=src_port, udp_dst=dst_port)
        if flow[-2] == inet.IPPROTO_ICMP:
            #flow_info=(flow_info['ipv4_src'],flow_info['ipv4_dst'],flow_info['ip_proto'],flow_info['in_port'])
            flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                             ipv4_src=ip_src, ipv4_dst=ip_dst,
                             ip_proto=inet.IPPROTO_ICMP)

        return flow_info

    # OFMatch to Dict Conversion
    def ofmatch_to_dict(self,match):
        #self.logger.info('ofmatch_to_dict HUSSOO %s', match)

        #LLDP
        if match['eth_type'] == 35020:
            #self.logger.info('ofmatch_to_dict eth_type=88CC (LLDP beacons) %s', match)
            return None
        if match['eth_type'] == 2688:
            #self.logger.info('ofmatch_to_dict eth_type=2688 (delay beacons) %s', match)
            return None

        if match['eth_type'] == 2048:
            #self.logger.info('ofmatch_to_dict eth_type=2048 (IP PACKTS) %s', match)

            ip_protocol= match['ip_proto']

            in_port = match['in_port']
            ip_src = match['ipv4_src']
            ip_dst = match['ipv4_dst']


            if ip_protocol==inet.IPPROTO_TCP:
                tcp_dst = match['tcp_dst']
                tcp_src = match['tcp_src']

                flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                                 ipv4_src=ip_src, ipv4_dst=ip_dst,
                                 ip_proto=inet.IPPROTO_TCP, tcp_src=tcp_src, tcp_dst=tcp_dst)

            #OFPFlowRemoved received: match=OFPMatch(oxm_fields={'ipv4_dst': '10.0.5.2', 'ipv4_src': '10.0.2.2',
            #  'udp_src': 51351, 'eth_type': 2048, 'ip_proto': 17, 'udp_dst': 5001, 'in_port': 2})
            elif ip_protocol==inet.IPPROTO_UDP:
                udp_dst = match['udp_dst']
                udp_src = match['udp_src']

                flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                                 ipv4_src=ip_src, ipv4_dst=ip_dst,
                                 ip_proto=inet.IPPROTO_UDP, udp_src=udp_src, udp_dst=udp_dst)



            elif ip_protocol==inet.IPPROTO_ICMP:

                flow_info = dict(in_port=in_port, eth_type=ether_types.ETH_TYPE_IP,
                                 ipv4_src=ip_src, ipv4_dst=ip_dst,
                                 ip_proto=inet.IPPROTO_ICMP)

            return flow_info

    def gethex(self, decimal):
        return hex(decimal)[2:]

    def gethex_dpid(self, dpid):

        dpid_hex = self.gethex(int(dpid))

        return dpid_hex.rjust(16, "0")

    def seq_in_seq(self,subseq, seq):
        while subseq[0] in seq:
            index = seq.index(subseq[0])
            if subseq == seq[index:index + len(subseq)]:
                return index
            else:
                seq = seq[index + 1:]
        else:
            return -1


    ##########################################################
    # flow removed handler - this function controls what happens when flow removed
    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):

        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        if msg.reason == ofp.OFPRR_IDLE_TIMEOUT:
            reason = 'IDLE TIMEOUT'
        elif msg.reason == ofp.OFPRR_HARD_TIMEOUT:
            reason = 'HARD TIMEOUT'
        elif msg.reason == ofp.OFPRR_DELETE:
            reason = 'DELETE'
        elif msg.reason == ofp.OFPRR_GROUP_DELETE:
            reason = 'GROUP DELETE'
        else:
            reason = 'unknown'


        # self.logger.info('OFPFlowRemoved received: '
        #                  'match=%s cookie=%d priority=%d reason=%s'
        #                  'duration_sec=%d duration_nsec=%d'
        #                  'idle_timeout=%d packet_count=%d byte_count=%d',
        #                  msg.match, msg.cookie, msg.priority, reason,
        #                  msg.duration_sec, msg.duration_nsec,
        #                  msg.idle_timeout, msg.packet_count,
        #                  msg.byte_count)
        #
        # self.logger.info("Flow_Removed => MATCH: %s ",msg.match)


        temp_=self.ofmatch_to_dict(msg.match)
        flow_tuple=self.dict_to_tuple(temp_)

        try:
            #Unlocked path
            if not self.flowPathMap[flow_tuple][2]:
                self.logger.info("FLOW DELETED => flow: %s ",self.flowPathMap[flow_tuple])
                del self.flowPathMap[flow_tuple]
                self.del_flow_from_db(flow_tuple)
            else:
                self.logger.info("FLOW LOCKED 'cannot deleted' => flow: %s ",self.flowPathMap[flow_tuple])


        except:
            self.logger.info("Flow_Removed => THIS FLOW HAS ALREADY BEEN DELETED! %s ",flow_tuple)

    ########################################################
    def send_meter_entry2(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        band = parser.OFPMeterBandDscpRemark(rate=500, burst_size=5, prec_level=2)
        req = parser.OFPMeterMod(datapath, ofproto.OFPMC_ADD,
                                 ofproto.OFPMF_KBPS, 1, [band])
        datapath.send_msg(req)
        eth_IP = ether.ETH_TYPE_IP
        match = parser.OFPMatch(eth_type=eth_IP, ip_dscp=24)
        instructions = [parser.OFPInstructionMeter(1),
                        parser.OFPInstructionGotoTable(2)]
        flow_mod = self.create_flow_mod(datapath, 0, 1,
                                        match, instructions)
        datapath.send_msg(flow_mod)
        # Policing for Scavenger class
        band = parser.OFPMeterBandDrop(rate=100,
                                       burst_size=5)
        req = parser.OFPMeterMod(datapath, ofproto.OFPMC_ADD,
                                 ofproto.OFPMF_KBPS, 2, [band])
        datapath.send_msg(req)

    def send_meter_entry(self, datapath):
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        self.logger.info("(SEND METER ENTRY 2 --- START)")

        # Policing for Scavenger class
        band = parser.OFPMeterBandDrop(rate=100,
                                       burst_size=5)
        req = parser.OFPMeterMod(datapath, ofproto.OFPMC_ADD,
                                 ofproto.OFPMF_KBPS, 1, [band])
        self.logger.info("(SEND METER ENTRY 2 --- REQ:%s",req)


        datapath.send_msg(req)
    ########################################################



    #Send flow statistic for a specific MATCH to SWITCH
    def send_flow_stats_request(self, datapath,match):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        cookie = cookie_mask = 0

        self.logger.info('FlowStats_Req_Sent: %s', match)

        req = ofp_parser.OFPFlowStatsRequest(datapath, 0,
                                             ofp.OFPTT_ALL,
                                             ofp.OFPP_ANY, ofp.OFPG_ANY,
                                             cookie, cookie_mask,
                                             match)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, ev):

        dp = ev.msg.datapath
        parser=dp.ofproto_parser


        flows = []

        for stat in ev.msg.body:
            flows.append('table_id=%s '
                         'duration_sec=%d duration_nsec=%d '
                         'priority=%d '
                         'idle_timeout=%d hard_timeout=%d flags=0x%04x '
                         'cookie=%d packet_count=%d byte_count=%d '
                         'match=%s instructions=%s' %
                         (stat.table_id,
                          stat.duration_sec, stat.duration_nsec,
                          stat.priority,
                          stat.idle_timeout, stat.hard_timeout, stat.flags,
                          stat.cookie, stat.packet_count, stat.byte_count,
                          stat.match, stat.instructions))

            current_time=stat.duration_sec+float(stat.duration_nsec/1000000000.0)
            current_flow= ( current_time, stat.packet_count, stat.byte_count)
            flow_match = stat.match

            #any match
            if not flow_match.fields:
                ###self.logger.info('FlowStats: MATCH ANY %s', flow_match)
                return

            else:

                my_dict = self.ofmatch_to_dict(flow_match)

                flow_tuple = self.dict_to_tuple(my_dict)
                if flow_tuple:


                    if (dp.id,flow_tuple) in self.pre_flowStats: # there is prev flow entry
                        (prev_time, prev_n_packet,prev_n_bytes)=self.pre_flowStats[(dp.id,flow_tuple)]

                        period = (current_time - prev_time)
                        if not period:
                            self.logger.info('FlowStats:DEVISION ZEROO %s %s %s ', current_time,prev_time, flow_tuple)

                        else:
                            rate = 8 * (stat.byte_count - prev_n_bytes) / period
                            uptime = current_time

                            self.flowStats[(dp.id, flow_tuple)] = (rate, uptime)

                            #self.logger.info('********FlowStats: FLOW: %s, rate:%s bps, uptime:%s sec in SW:%s========%s', flow_tuple,rate,uptime,dp.id,self.flowPathMap)
                            '''
                            if flow_tuple in self.flowPathMap.keys():
                                self.logger.info('********FlowStats: FLOW_2: %s', self.flowPathMap[flow_tuple])
                                path_=self.flowPathMap[flow_tuple][0]
                                i=0

                                for i in xrange(0, len(path_) - 1):
                                    link = (path_[i], path_[i + 1])
                                    print link



                                    if not flow_tuple in self.flows_on_link[link]:

                                        self.flows_on_link[link].append(flow_tuple)
                                        self.logger.info('********FlowStats: FLOW_3: %s', self.flows_on_link[link])

                                    #self.flowPathMap[flow_tuple] = (path_, version_, lock_flag_, policy)
                            '''
                    self.pre_flowStats[(dp.id, flow_tuple)] = (current_time, stat.packet_count, stat.byte_count)

                else:
                    #self.logger.info('FlowStats: SPECIAL FLOW- NO FLOW TUPLE :: %s ', flow_match)
                    pass




    #########################################################################
    #########################################################################
    # LINK AND PORT UP/DOWN ISSUES

    @handler.set_ev_cls(network_monitor.EventLinkDown,MAIN_DISPATCHER)
    #@set_ev_cls(network_monitor.EventLinkDown)
    def link_down_action_handler(self,ev):



        src_dp=ev.src_dp
        dst_dp=ev.dst_dp
        status=ev.status
        if status=='congested':
            subpath = [src_dp, dst_dp]
            self.logger.info('event: LINK (%s-%s) IS %s !!!! ', src_dp,dst_dp,status)
            self.check_down_link_usage(subpath)

        #UPDATE LINKS IN NETX AND NETQX
        elif status=='down':

            subpath=[src_dp,dst_dp]
            subpath_rev=[dst_dp,src_dp]

            #if src_dp in self.netx.neighbors(dst_dp):
            if src_dp in NETQX.neighbors(dst_dp):
                #self.netx.remove_edge(src_dp,dst_dp)
                NETQX.remove_edge(src_dp,dst_dp)

            self.logger.info('event: LINK %s IS %s !!!! ', subpath,status)
            self.check_down_link_usage(subpath)
        else:
            self.logger.info('event: LINK IS %s !!!! ',status)
            src_port, dst_port=self.link_to_port[(src_dp,dst_dp)]
            link_to_neighbor[src_dp, src_port]=dst_dp
            link_to_neighbor[dst_dp, dst_port] =src_dp


            #self.netx.add_edge(src_dp, dst_dp, bandwidth=1, reserved_bw=1, residual_bw=300000000, delay=float('inf'))
            NETQX.add_edge(src_dp, dst_dp, bandwidth=100, reserved_bw=200, residual_bw=300000000, delay=float('inf'),
                           queue_id_0=(0, 0, 0, 1000), queue_id_15=(0, 0, 0, 1000), queue_id_31=(0, 0, 0, 1000), queue_id_47=(0, 0, 0, 1000))

    def check_down_link_usage(self,fail_path):


        for flow in self.flowPathMap.keys():
            current_path=self.flowPathMap[flow][0]
            result=self.seq_in_seq(fail_path,current_path)
            self.logger.info('event: LINK IS %s ==== PATH:%s !!!! RESULT:%s ',fail_path,current_path,result)
            if result== -1:
                self.logger.info('Problem! - current path--- %s', current_path)


                (path_, version_, lock_flag_, policy)= self.flowPathMap[flow]
                dict_flow_info=self.tuple_to_dict(flow)
                routing_mode = self.qos_policy_check(policy)
                dp_first,dp_last = path_[0],path_[-1]
                self.send_qos_req(dp_first, dp_last, dict_flow_info, routing_mode, policy)


    #########################################################################
    #########################################################################
    #########################################################################
    #   UNUSED FUNCTIONS ####################################################


    #UNUSED FUNCTION
    def decide_path_bw(self,prev_path,new_path):
        prev=self.path_bw_calculate(prev_path)
        new=self.path_bw_calculate(new_path)

        ratio=prev/new

        if ratio < 0.9:
            return new_path
        if len(new_path)-len(prev_path)<0:
            return new_path
        else:
            # self.logger.info("############# PATH Does not CHANGE DUE TO  ")
            return  prev_path


    #UNUSED FUNC CURRENTLY!
    def find_pathXX(self,src_dpid,dst_dpid,routing_mode,policy,mode):

        if mode == None:
            self.logger.info("POLICY NONE!!!")

            # Find possible paths

            possible_paths = self.sort_paths_by_bw_used(src_dpid, dst_dpid)
            possible_paths = list(possible_paths)
            path_ = possible_paths[0][0]
            path_of_bw = possible_paths[0][1]

    #UNUSED
    def path_qos_validity(self, path, routing_mode=None, policy=None):

        if routing_mode == 'bw':
            if self.path_bw_calculate(path) >= (policy['bw'] * 1024):
                return True
        elif routing_mode is None:
            return True
            # policy siz ise sonsuza kadar ayni path den gidebilir !!!!!

        elif routing_mode == 'delay':
            if self.path_delay_calculate(path) <= policy['delay']:
                return True

        elif routing_mode == 'combined':
            if self.path_bw_calculate_usage(path) >= (policy['bw'] * 1024) and self.path_delay_calculate(path) <= policy[
                'delay']:
                return True
        else:
            return False

    #Old type path bw calculation(before queuing)
    def path_bw_calculate(self, path):

        min_bw = LINK_SPEED
        for i in xrange(len(path) - 1):
            current_bw = self.netx[path[i]][path[i + 1]]['residual_bw']
            # self.logger.info("############# PATH BW CALCULATE FOR %s -- %s -",path,current_bw)

            if current_bw > 0 and current_bw < min_bw:
                min_bw = current_bw

        # self.logger.info("############# PATH BW CALCULATE FOR %s ++++++++++++ %s -",path,min_bw)

        return min_bw

    #UNUSED - HOST_IP TO (SW,PORT)..BUT IT JUST RETURNS PORT.
    def get_host_connected_port(self, host_ip):

        for key in self.access_table.keys():
            if host_ip == self.access_table[key]:
                dst_port = key[1]
                return dst_port
        return None

    #UNUSED - delete flow rule from a switch
    def del_flow(self, datapath, table_id, priority, match, inst):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        mod = parser.OFPFlowMod(datapath=datapath, command=ofproto.OFPFC_DELETE, table_id=table_id, priority=priority,
                                out_port=ofproto.OFPP_ANY, out_group=ofproto.OFPG_ANY, match=match, instructions=inst)

        datapath.send_msg(mod)
    #######################from ex routing################################
    #path bw calculation with PORT  QUEUE
    def path_bw_calculate_usage_mult(self, path, mode):

        if mode==None:
            queue_number=47
            bufsize=Q47_BUF
        elif mode=='bw':
            queue_number=31
            bufsize=Q31_BUF
        elif mode=='delay' or mode=='combined':
            queue_number=15
            bufsize=Q15_BUF
        elif mode == 'link':
            queue_number=0

        else:
            self.logger.info("############# warning: shortest route.py unknown routing mode: %s ",mode)


        max_bw_0 = 0
        max_bw_15 = 0
        max_bw_31 = 0
        max_bw_47 = 0
        for i in xrange(len(path) - 1):

            queue_id = 'queue_id_0'
            current_bw = NETQX[path[i]][path[i + 1]][queue_id][0] #bandwidth
            #self.logger.info("############# PATH BW CALCULATE FOR %s -- %s for queue_id:%s -",path,current_bw,queue_id)

            if current_bw > 0 and current_bw > max_bw_0:
                max_bw_0 = current_bw

            queue_id = 'queue_id_15'
            current_bw = NETQX[path[i]][path[i + 1]][queue_id][0] #bandwidth
            #self.logger.info("############# PATH BW CALCULATE FOR %s -- %s for queue_id:%s -",path,current_bw,queue_id)

            if current_bw > 0 and current_bw > max_bw_15:
                max_bw_15 = current_bw


            queue_id = 'queue_id_31'
            current_bw = NETQX[path[i]][path[i + 1]][queue_id][0] #bandwidth
            #self.logger.info("############# PATH BW CALCULATE FOR %s -- %s for queue_id:%s -",path,current_bw,queue_id)

            if current_bw > 0 and current_bw > max_bw_31:
                max_bw_31 = current_bw


            queue_id = 'queue_id_47'
            current_bw = NETQX[path[i]][path[i + 1]][queue_id][0] #bandwidth
            #self.logger.info("############# PATH BW CALCULATE FOR %s -- %s for queue_id:%s -",path,current_bw,queue_id)

            if current_bw > 0 and current_bw > max_bw_47:
                max_bw_47 = current_bw



        #return bufsize-max_bw
        return (max_bw_0,max_bw_15,max_bw_31,max_bw_47)
        #return 100000000-max_bw


    #UNUSED FUNC CURRENTLY!
    def find_path2(self,src_sw,dst_sw,mode=None):

        if mode == None:
            self.logger.info("POLICY NONE!!!")

            poso = nx.all_simple_paths(NETQX, src_sw, dst_sw)

            # possible_paths = list(possible_paths)
            possible_paths = list(poso)

            route_dict = []
            for pathik in possible_paths:

                used_bw = self.path_bw_calculate_usage_mult(pathik, mode)
                #used_bw  <===(max_bw_0,max_bw_15,max_bw_31,max_bw_47)
                weighted_used_bw=( 3*used_bw[1] + 1.5*used_bw[2] + used_bw[3])
                total=used_bw[0]
                route_dict.append([pathik, total, len(pathik),weighted_used_bw])

            ##route_dict.sort(key=lambda tup: (tup[1], tup[2]), reverse=False)
            #route_dict.sort(key=lambda tup: tup[1], reverse=False)
            route_dict.sort(key=lambda tup: tup[3], reverse=False)
            self.logger.info("FIND PATH phase: 1 (BW sort)-(used_bw NONE) %s", route_dict)


            """
            #Second Phase %10
            best=route_dict[0]
            route_dict2 = []

            for route_tuple in route_dict:

                ratio = (best[1]+1) / (route_tuple[1]+1)

                if ratio > 0.9:
                    route_dict2.append(route_tuple)

            route_dict2.sort(key=lambda tup: tup[2], reverse=False)
            """

            possible_paths = list(route_dict)
            path_ = possible_paths[0][0]
            path_of_bw = possible_paths[0][1]
            self.logger.info("FIND PATH phase: 2 (0.1 rate check)-(used_bw NONE %s", route_dict)

        if mode == 'bw':
            self.logger.info("POLICY bw!!!")

            poso = nx.all_simple_paths(NETQX, src_sw, dst_sw)

            # possible_paths = list(possible_paths)
            possible_paths = list(poso)

            route_dict = []
            for pathik in possible_paths:
                used_bw = self.path_bw_calculate_usage_mult(pathik, mode)
                #route_dict.append([pathik, link_total, len(pathik)])
                route_dict.append([pathik, used_bw, len(pathik)])

            ##route_dict.sort(key=lambda tup: (tup[1], tup[2]), reverse=False)
            route_dict.sort(key=lambda tup: tup[1][0], reverse=False)
            self.logger.info("FIND PATH phase: 1 (BW sort)-(used_bw BW) %s", route_dict)

            # Second Phase %10
            best = route_dict[0]
            route_dict2 = []

            for route_tuple in route_dict:

                ratio = (best[1][0]+1) / (route_tuple[1][0]+1)

                if ratio > 0.9:
                    route_dict2.append(route_tuple)

            route_dict2.sort(key=lambda tup: tup[2], reverse=False)


            self.logger.info("FIND PATH phase: 2 (0.1 rate check)-(used_bw BW) %s", route_dict2)

            # Third Phase load type

            route_dict3 = []

            for route_tuple in route_dict2:

                prio_ratio = (route_tuple[1][1]+route_tuple[1][2]+1)/(route_tuple[1][0]+1)
                route_dict3.append([route_tuple,prio_ratio])

            route_dict3.sort(key=lambda tup: tup[1] , reverse=False)

            possible_paths = list(route_dict3)
            path_ = possible_paths[0][0][0]
            path_of_bw = possible_paths[0][0][1]
            self.logger.info("FIND PATH 3-(used_bw BW)  path_:%s path-of-bw:%s --------->", path_,path_of_bw)

        if mode == 'delay':
            self.logger.info("POLICY delay!!!")

            poso = nx.all_simple_paths(NETQX, src_sw, dst_sw)

            # possible_paths = list(possible_paths)
            possible_paths = list(poso)

            route_dict = []
            for pathik in possible_paths:
                used_bw = self.path_bw_calculate_usage_mult(pathik, mode)

                #route_dict.append([pathik, link_total, len(pathik)])
                route_dict.append([pathik, used_bw, len(pathik)])

            ##route_dict.sort(key=lambda tup: (tup[1], tup[2]), reverse=False)
            route_dict.sort(key=lambda tup: tup[1][0], reverse=False)
            self.logger.info("FIND PATH phase: 1 (BW sort)-(used_bw delay) %s", route_dict)

            # Second Phase %10
            best = route_dict[0]
            route_dict2 = []

            for route_tuple in route_dict:

                ratio = (best[1][0]+1) / (route_tuple[1][0]+1)

                if ratio > 0.9:
                    route_dict2.append(route_tuple)

            route_dict2.sort(key=lambda tup: tup[2], reverse=False)


            self.logger.info("FIND PATH phase: 2 (0.1 rate check) -(used_bw delay) %s", route_dict2)

            # Third Phase load type

            route_dict3 = []

            for route_tuple in route_dict2:

                prio_ratio = (route_tuple[1][1]+1)/(route_tuple[1][0]+1)
                route_dict3.append([route_tuple,prio_ratio])

            route_dict3.sort(key=lambda tup: tup[1] , reverse=False)

            possible_paths = list(route_dict3)
            path_ = possible_paths[0][0][0]
            path_of_bw = possible_paths[0][0][1]
            self.logger.info("FIND PATH 3-(used_bw delay)  path_:%s path-of-bw:%s --------->", path_,path_of_bw)



        if mode == 'combined':
            pass


        return (path_,path_of_bw)
