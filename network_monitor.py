from __future__ import division
from operator import attrgetter
from ryu.base import app_manager
#ryu.controller.event.EventBase
from ryu.controller import event
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub

import MySQLdb



from network_aware import NETQX
from network_aware import link_to_neighbor



SLEEP_PERIOD = 3
STAT_TO_DB = True # Enabling to save port statistics to DB
#(src_dpid,src_port)
DOWN_PORTS=[]

LINK=100000000
BUFSIZE={'queue_id_15':30000000,'queue_id_31':30000000,'queue_id_47':60000000}
del_link_to_neighbor={}

class EventLinkDown(event.EventBase):
    def __init__(self, status ,src_dp,dst_dp):

        super(EventLinkDown,self).__init__()


        self.status=status
        self.src_dp=src_dp
        self.dst_dp=dst_dp


class Network_Monitor(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _NAME = 'Network_Monitor'
    _EVENTS = [EventLinkDown]


    def __init__(self, *args, **kwargs):
        super(Network_Monitor, self).__init__(*args, **kwargs)

        self.name = 'Network_monitor'

        self.datapaths = {}
        self.port_stats = {}
        self.port_speed = {}
        self.flow_stats = {} #UNUSED

        self.queue_stats = {}
        self.queue_stats_current = {}



        self.flow_speed = {}
        # {"port":{dpid:{port:body,..},..},"flow":{dpid:body,..}
        self.stats = {}
        self.port_link = {}  # {dpid:{port_no:(config,state,cur),..},..}
        self.db = MySQLdb.connect(host="localhost",  # your host, usually localhost
                                  user="root",  # your username
                                  passwd="1234",  # your password
                                  db="POLICYDB")  # name of the data base

        self.monitor_thread = hub.spawn(self._monitor)

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

    def _monitor(self):
        hub.sleep(5)
        while True:
            self.stats['flow'] = {}
            self.stats['port'] = {}
            for dp in self.datapaths.values():
                self.port_link.setdefault(dp.id, {})
                self._request_stats(dp)

            self.send_flow_stats_request_all()

            hub.sleep(SLEEP_PERIOD)
            if STAT_TO_DB and (self.stats['flow'] or self.stats['port']):
                self.show_stat('flow', self.stats['flow'])
                self.show_stat('port', self.stats['port'])
                hub.sleep(1)

    def _request_stats(self, datapath):

        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser


        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

        req = parser.OFPPortDescStatsRequest(datapath, 0)
        datapath.send_msg(req)

        req = parser.OFPQueueStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)


    def _save_stats(self, dist, key, value, length):
        if key not in dist:
            dist[key] = []
        dist[key].append(value)

        if len(dist[key]) > length:
            dist[key].pop(0)

    def _get_speed(self, now, pre, period):
        if period:
            return (now - pre) / (period)
        else:
            return 0

    def _get_time(self, sec, nsec):
        return sec + nsec / (10 ** 9)

    def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
        return self._get_time(n_sec, n_nsec) - self._get_time(p_sec, p_nsec)

    #PORT STATISTIKLERINI DATABASE'E ATIYOR
    def show_stat(self, type, bodys):
        '''
            type: 'port' 'flow'
            bodys: port or flow `s information :{dpid:body}

        if (type == 'flow' and False):

            print('datapath         ''   in-port        ip-dst      '
                  'out-port packets  bytes  flow-speed(B/s)')
            print('---------------- ''  -------- ----------------- '
                  '-------- -------- -------- -----------')
            for dpid in bodys.keys():
                for stat in sorted(
                        [flow for flow in bodys[dpid] if flow.priority == 1],
                        key=lambda flow: (flow.match.get('in_port'),
                                          flow.match.get('ipv4_dst'))):
                    print('%016x %8x %17s %8x %8d %8d %8.1f' % (
                        dpid,
                        stat.match['in_port'], stat.match['ipv4_dst'],
                        stat.instructions[0].actions[0].port,
                        stat.packet_count, stat.byte_count,
                        abs(self.flow_speed[dpid][
                                (stat.match.get('in_port'),
                                 stat.match.get('ipv4_dst'),
                                 stat.instructions[0].actions[0].port)][-1])))
            print '\n'
        '''
        if (type == 'port'):
            '''
            print('datapath             port   ''rx-pkts  rx-bytes rx-error '
                  'tx-pkts  tx-bytes tx-error  port-speed(b/s)'
                  ' current-capacity(Kbps)  '
                  'port-stat   link-stat')
            print('----------------   -------- ''-------- -------- -------- '
                  '-------- -------- -------- '
                  '----------------  ----------------   '
                  '   -----------    -----------')
            format = '%016x %8x %8d %8d %8d %8d %8d %8d %8.1f %16d %16s %16s'
            '''


            for dpid in bodys.keys():
                for stat in sorted(bodys[dpid], key=attrgetter('port_no')):
                    if stat.port_no != ofproto_v1_3.OFPP_LOCAL:
                        self.update_port_stat(dpid, stat.port_no, stat.rx_packets, stat.rx_bytes, stat.rx_errors,
                                              stat.tx_packets, stat.tx_bytes, stat.tx_errors,
                                              abs(8 * self.port_speed[(dpid, stat.port_no)][-1]),
                                              self.port_link[dpid][stat.port_no][2],
                                              self.port_link[dpid][stat.port_no][0],
                                              self.port_link[dpid][stat.port_no][1])


    #UNUSED
    #@set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        self.stats['flow'][dpid] = body
        self.flow_stats.setdefault(dpid, {})
        self.flow_speed.setdefault(dpid, {})
        for stat in sorted([flow for flow in body if flow.priority == 1],
                           key=lambda flow: (flow.match.get('in_port'),
                                             flow.match.get('ipv4_dst'))):
            key = (stat.match['in_port'], stat.match.get('ipv4_dst'),
                   stat.instructions[0].actions[0].port)
            value = (stat.packet_count, stat.byte_count,
                     stat.duration_sec, stat.duration_nsec)
            self._save_stats(self.flow_stats[dpid], key, value, 5)

            # Get flow's speed.
            pre = 0
            period = SLEEP_PERIOD
            tmp = self.flow_stats[dpid][key]
            if len(tmp) > 1:
                pre = tmp[-2][1]
                period = self._get_period(tmp[-1][2], tmp[-1][3],
                                          tmp[-2][2], tmp[-2][3])

            speed = self._get_speed(self.flow_stats[dpid][key][-1][1],
                                    pre, period)

            self._save_stats(self.flow_speed[dpid], key, speed, 5)

    def update_port_stat(self, dpid, port, rxpkts, rxbytes, rxerror, txpkts, txbytes, txerror, portspeed,
                         currentcapacity, portstat, linkstat):
        dpid16 = format(dpid, '016')
        cur = self.db.cursor()
        sql_request = "UPDATE portstat SET rxpkts='%s', rxbytes='%s', rxerror='%s' , txpkts='%s', txbytes='%s', txerror='%s', portspeed='%s',currentcapacity='%s', portstat='%s',linkstat='%s'  WHERE datapath='%s' and port='%s' " % (
        rxpkts, rxbytes, rxerror, txpkts, txbytes, txerror, portspeed, currentcapacity, portstat, linkstat, dpid16,
        port)
        # self.logger.info("################### MONITOR - PORT DATAABASE UPDATE!!!! %s",sql_request)
        cur.execute(sql_request)

        sql_request2 = "UPDATE links SET speed='%s', capacity='%s' WHERE srcid='%s' and srcport='%s' " % (
            portspeed, currentcapacity, dpid, port)
        # self.logger.info("################### MONITOR - PORT DATAABASE UPDATE!!!! %s", sql_request2)
        cur.execute(sql_request2)

        self.db.commit()

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        body = ev.msg.body
        self.stats['port'][ev.msg.datapath.id] = body
        for stat in sorted(body, key=attrgetter('port_no')):
            if stat.port_no != ofproto_v1_3.OFPP_LOCAL:
                key = (ev.msg.datapath.id, stat.port_no)
                value = (stat.tx_bytes, stat.rx_bytes, stat.rx_errors,
                         stat.duration_sec, stat.duration_nsec)

                self._save_stats(self.port_stats, key, value, 5)

                # Get port speed.
                pre = 0
                period = SLEEP_PERIOD
                tmp = self.port_stats[key]
                if len(tmp) > 1:
                    pre = tmp[-2][0] + tmp[-2][1]
                    period = self._get_period(tmp[-1][3], tmp[-1][4],
                                              tmp[-2][3], tmp[-2][4])

                speed = self._get_speed(
                    self.port_stats[key][-1][0] + self.port_stats[key][-1][1],
                    pre, period)

                self._save_stats(self.port_speed, key, speed, 5)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        msg = ev.msg
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        config_dist = {ofproto.OFPPC_PORT_DOWN: "Down",
                       ofproto.OFPPC_NO_RECV: "No Recv",
                       ofproto.OFPPC_NO_FWD: "No Forward",
                       ofproto.OFPPC_NO_PACKET_IN: "No Packet-in"}

        state_dist = {ofproto.OFPPS_LINK_DOWN: "Down",
                      ofproto.OFPPS_BLOCKED: "Blocked",
                      ofproto.OFPPS_LIVE: "Live"}

        ports = []
        for p in ev.msg.body:
            ports.append('port_no=%d hw_addr=%s name=%s config=0x%08x '
                         'state=0x%08x curr=0x%08x advertised=0x%08x '
                         'supported=0x%08x peer=0x%08x curr_speed=%d '
                         'max_speed=%d' %
                         (p.port_no, p.hw_addr,
                          p.name, p.config,
                          p.state, p.curr, p.advertised,
                          p.supported, p.peer, p.curr_speed,
                          p.max_speed))

            if p.config in config_dist:
                config = config_dist[p.config]
            else:
                config = "up"

            if p.state in state_dist:
                state = state_dist[p.state]
            else:
                state = "up"

            port_feature = (config, state, 100000)
            # p.curr_speed i 100Mbps yaptik!!! statik olarak
            # port_feature = (config, state, p.curr_speed)
            self.port_link[dpid][p.port_no] = port_feature

        self.logger.debug('OFPPortDescStatsReply received: %s', ports)

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        reason_dict = {ofproto.OFPPR_ADD: "added",
                       ofproto.OFPPR_DELETE: "deleted",
                       ofproto.OFPPR_MODIFY: "modified", }

        if reason in reason_dict:

            print "switch%d: port %s %s" % (dpid, reason_dict[reason], port_no)
        else:
            print "switch%d: Illeagal port state %s %s" % (port_no, reason)

    def send_queue_stats_request(self, datapath):
        ofp = datapath.ofproto
        ofp_parser = datapath.ofproto_parser

        req = ofp_parser.OFPQueueStatsRequest(datapath, 0, ofp.OFPP_ANY,
                                              ofp.OFPQ_ALL)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPQueueStatsReply)
    def queue_stats_reply_handler(self, ev):

        queues = []


        for stat in ev.msg.body:
            queues.append('port_no=%d queue_id=%d '
                          'tx_bytes=%d tx_packets=%d tx_errors=%d '
                          'duration_sec=%d duration_nsec=%d' %
                          (stat.port_no, stat.queue_id,
                           stat.tx_bytes, stat.tx_packets, stat.tx_errors,
                           stat.duration_sec, stat.duration_nsec))
            #self.queue_stats[(ev.msg.datapath.id, stat.port_no,stat.queue_id)]=(stat.tx_bytes,stat.duration_sec)
            #self.logger.info('Q MAHMUT, sw:%s----queue_id:%s',ev.msg.datapath.id,stat.queue_id )

            if (ev.msg.datapath.id, stat.port_no,stat.queue_id) in self.queue_stats:

                (prev_tx, prev_time, prev_txerror)=self.queue_stats[(ev.msg.datapath.id, stat.port_no, stat.queue_id)]

                period=(stat.duration_sec + float(stat.duration_nsec/1000000000.0) - prev_time)

                rate=8*(stat.tx_bytes-prev_tx)/period
                #rate=rate*2 # enterasan bir sekilde rate'in yarisini goruyorum istatistiklerde

                #Error tx count in stat period
                error_count=stat.tx_errors-prev_txerror
                #Un Used!
                #self.queue_stats_current[(ev.msg.datapath.id, stat.port_no,stat.queue_id)]=(rate,error_count)

                self.queue_stats[(ev.msg.datapath.id, stat.port_no,stat.queue_id)]=(stat.tx_bytes,  stat.duration_sec,  stat.tx_errors)

                src, src_port = ev.msg.datapath.id, stat.port_no


                if rate>10.0 and (src, src_port) in link_to_neighbor.keys():

                    dst = link_to_neighbor[src, src_port]

                    queue_id='queue_id_' + str(stat.queue_id)
                    #self.logger.info('Quueue ID: %s #%s# %s',queue_id,NETQX[src][dst],self.queue_stats)

                    ##self.logger.info('Quueue ID: %s #%s# ', queue_id, NETQX[src][dst])
                    tuple=NETQX[src][dst][queue_id]



                    W=1

                    if stat.queue_id==15:
                        ro=rate/LINK
                        #W=1/(1-ro)
                        W=0


                    elif stat.queue_id==31:
                        rate_0=NETQX[src][dst]['queue_id_15'][0]
                        ro_0=rate_0/LINK

                        rate_1 = NETQX[src][dst]['queue_id_31'][0]
                        ro_1 = rate_1 / LINK

                        #W= 1 / ((1-ro_0)*(1-ro_0-ro_1))
                        W = rate_0


                    elif stat.queue_id== 47:
                        rate_0 = NETQX[src][dst]['queue_id_15'][0]
                        ro_0 = rate_0 / LINK

                        rate_1 = NETQX[src][dst]['queue_id_31'][0]
                        ro_1 = rate_1 / LINK

                        rate_2 = NETQX[src][dst]['queue_id_47'][0]
                        ro_2 = rate_2 / LINK

                        #W = 1 / ((1 - ro_0-ro_1) * (1 - ro_0 - ro_1-ro_2))
                        W=rate_0 + rate_1

                    NETQX[src][dst][queue_id]=(rate,error_count+6,W,tuple[3])
                    #self.logger.info('Quueue ID: %s #%s# ', queue_id, NETQX[src][dst])



            else:

                self.queue_stats[(ev.msg.datapath.id, stat.port_no,stat.queue_id)]=(stat.tx_bytes,stat.duration_sec + stat.duration_nsec/1000000000,stat.tx_errors)

    def send_flow_stats_request_all(self):

        for dp in self.datapaths:
            datapath=self.datapaths[dp]
            ofp = datapath.ofproto
            ofp_parser = datapath.ofproto_parser
            cookie = cookie_mask = 0
            match = ofp_parser.OFPMatch()

            req = ofp_parser.OFPFlowStatsRequest(datapath, 0,
                                         ofp.OFPTT_ALL,
                                         ofp.OFPP_ANY, ofp.OFPG_ANY,
                                         cookie, cookie_mask)
            datapath.send_msg(req)


    @set_ev_cls(ofp_event.EventOFPPortStatus,MAIN_DISPATCHER)
    def port_state_handler(self, ev):

        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto
        src_dp=msg.datapath.id


        self.logger.info('PORT STATUS CHANGED---->>>>>> SW:%s, Port_no: %s, Status: %s (0:UP 1:Down)', msg.datapath, msg.desc[0],msg.desc[4])
        # 0 means UP
        if msg.desc[4]==0:
            if(src_dp,msg.desc[0]) in DOWN_PORTS:
                DOWN_PORTS.remove((src_dp,msg.desc[0]))

                if (src_dp,msg.desc[0]) in del_link_to_neighbor.keys():
                    dst_dp=del_link_to_neighbor[src_dp, msg.desc[0]]
                    self.send_event_to_observers(EventLinkDown('up', src_dp, dst_dp))
                    del del_link_to_neighbor[src_dp, msg.desc[0]]
                    self.logger.info('-------------->>>>>> UP PORTS LIST: del_link_to_neighbor %s',del_link_to_neighbor)


        else:
            if not (src_dp,msg.desc[0]) in  DOWN_PORTS:
                DOWN_PORTS.append((msg.datapath.id, msg.desc[0]))

                if (src_dp,msg.desc[0]) in link_to_neighbor.keys():
                    dst_dp=link_to_neighbor[src_dp,msg.desc[0]]
                    dst_dp_port_list = [i for i in link_to_neighbor if i[0] == dst_dp]
                    dst_dp_port = [i for i in dst_dp_port_list if link_to_neighbor[i] == src_dp]

                    del_link_to_neighbor[src_dp, msg.desc[0]]=dst_dp
                    del link_to_neighbor[src_dp, msg.desc[0]]


                    self.send_event_to_observers(EventLinkDown('down', src_dp, dst_dp))

        self.logger.info('-------------->>>>>> DOWN PORTS LIST: %s',DOWN_PORTS)


    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def switch_state_handler(self, ev):
        datapath = ev.datapath

        if ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:

                self.logger.info('unregister datapath: %016x', datapath.id)

                dp_port_list = [i for i in link_to_neighbor if i[0] == datapath]
                self.logger.info('unregister datapath__down port list: %s',dp_port_list)

                del self.datapaths[datapath.id]

    #@set_ev_cls(event2.EventLinkDelete)
    def get_topss(self, ev):
        self.logger.info('PORT STATUS CHANGED---->>>>>> DOWN PORTS  allah allah allah %s',ev.link)


