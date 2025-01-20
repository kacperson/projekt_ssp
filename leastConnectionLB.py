from pox.core import core
from pox.lib.packet import ethernet, ipv4, tcp, arp
from pox.lib.addresses import EthAddr, IPAddr
import pox.openflow.libopenflow_01 as of
from collections import defaultdict
from pox.lib.util import str_to_dpid, dpid_to_str
from pox.lib.revent import Event, EventMixin
from time import sleep
import threading
import warnings
import inspect

log = core.getLogger()

ZERO_DPID = "00-00-00-00-00-0"
MAC_ZERO = "00:00:00:00:00:0"

IDLE_TIMEOUT = 2
HARD_TIMEOUT = 5

REQUEST_FOR_STATS_INTERVAL = 1

class RequestPathEvent(Event):
        def __init__(self, dpid1, dpid2):
            Event.__init__(self)
            self.path_endpoints = (dpid1, dpid2)

class LeastConnectionLB(EventMixin):
    _eventMixin_events = set([RequestPathEvent])  # Register events
    warnings.filterwarnings('ignore')

    def __init__(self):
        # Initialize EventMixin first
        EventMixin.__init__(self)

        self._core_name = 'misc_lclb'

        # Server pool configuration
        self.server_pool = {IPAddr(f'10.0.0.{i}'):0 for i in range(1,5)} # server ip: connections count
        self.server_pool_tmp = {IPAddr(f'10.0.0.{i}'):0 for i in range(1,5)}
        
        # Virtual service configuration
        self.virtual_ip = IPAddr('10.0.0.100')
        self.virtual_mac = EthAddr('0a:00:00:64:00:00')
        # Connection tracking
        self.connection_counts = defaultdict(int)  # Active connections per server
        self.paths = dict()  # Store computed paths
        # Network topology mapping
        self.host_port_map = {
            IPAddr("10.0.0.1"): (str_to_dpid(ZERO_DPID+"1"), 3),
            IPAddr("10.0.0.2"): (str_to_dpid(ZERO_DPID+"1"), 4),
            IPAddr("10.0.0.3"): (str_to_dpid(ZERO_DPID+"3"), 3),
            IPAddr("10.0.0.4"): (str_to_dpid(ZERO_DPID+"3"), 4),
            IPAddr("10.0.0.5"): (str_to_dpid(ZERO_DPID+"5"), 2),
            IPAddr("10.0.0.6"): (str_to_dpid(ZERO_DPID+"5"), 3),
            IPAddr("10.0.0.7"): (str_to_dpid(ZERO_DPID+"6"), 2),
            IPAddr("10.0.0.8"): (str_to_dpid(ZERO_DPID+"6"), 3)
        }
        
        # Set up event listeners
        core.openflow.addListeners(self)  # Listen to OpenFlow events
        core.listen_to_dependencies(self)  # Listen to dependency events
        
        # Listen to discovery events directly
        if core.hasComponent("openflow_discovery"):
            self.listenTo(core.openflow_discovery)
        else:
            # If discovery component isn't ready yet, wait for it
            core.call_when_ready(self._handle_discovery_ready, 
                               ["openflow_discovery"])
        
        if core.hasComponent("openflow_discGraph"):
            self.listenTo(core.openflow_discGraph)
        else:
            # If discovery component isn't ready yet, wait for it
            core.call_when_ready(self._handle_discGraph_ready, 
                               ["openflow_discGraph"])

        self.tmpPath = None
    
        self.connections = {}  # Dictionary to store switch connections
        core.openflow.addListeners(self)
        self.flows = {IPAddr(f'10.0.0.{i}'):list() for i in range(1,5)}
        # Hardcoded DPIDs (example values - replace with your actual DPIDs)
        self.dpids = [1, 3]  # DPIDs as integers
        # Start the stats collection thread
        self.running = True
        self.stats_thread = threading.Thread(target=self._stats_loop)
        self.stats_thread.daemon = True
        self.stats_thread.start()
        
    def _handle_ConnectionUp(self, event):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """Store switch connection when it connects"""
        dpid = event.dpid
        self.connections[dpid] = event.connection
        #log.info(f"Switch {dpid_to_str(dpid)} connected")
        
    def _handle_ConnectionDown(self, event):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """Remove switch connection when it disconnects"""
        dpid = event.dpid
        if dpid in self.connections:
            del self.connections[dpid]
            #print(f"Switch {dpid_to_str(dpid)} disconnected")
            
    def get_switch_connection(self, dpid):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """Get connection to specific switch by DPID"""
        return self.connections.get(dpid)
        
    def send_message_to_switch(self, dpid, message):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """Send OpenFlow message to specific switch"""
        connection = self.get_switch_connection(dpid)
        if connection:
            connection.send(message)
            return True
        return False
    
    def _handle_ResponsePathEvent(self, event):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        self.tmpPath = event.path

    def _request_Path(self, dpid1, dpid2):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        self.raiseEvent(RequestPathEvent(dpid1, dpid2))

    def _handle_SendLink(self, event):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        if event.link.dpid1 not in self.paths:
            self.paths[event.link.dpid1] = {event.link.dpid2: event.link.port1}
        else:
            self.paths[event.link.dpid1][event.link.dpid2] = event.link.port1
        
        if event.link.dpid2 not in self.paths:
            self.paths[event.link.dpid2] = {event.link.dpid1: event.link.port2}
        else:
            self.paths[event.link.dpid2][event.link.dpid1] = event.link.port2

        ##log.info(f"dpid1: {event.link.dpid1}, port1: {event.link.port1}, dpid2: {event.link.dpid2}, port2: {event.link.port2}")

    def _handle_PacketIn(self, event):

        packet = event.parsed
        if not packet:
            return

        # handle ARP packets
        if packet.type == ethernet.ARP_TYPE:
            arp_packet = packet.payload
            
            if arp_packet.opcode == arp.REQUEST:
                if arp_packet.protodst == self.virtual_ip:
                    ##log.info("Received ARP request for virtual IP")
                    
                    # Create ARP reply
                    arp_reply = arp()
                    arp_reply.hwsrc = self.virtual_mac
                    arp_reply.hwdst = arp_packet.hwsrc
                    arp_reply.opcode = arp.REPLY
                    arp_reply.protosrc = self.virtual_ip
                    arp_reply.protodst = arp_packet.protosrc
                    
                    # Create ethernet packet
                    ether = ethernet()
                    ether.type = ethernet.ARP_TYPE
                    ether.dst = packet.src
                    ether.src = self.virtual_mac
                    ether.payload = arp_reply
                    
                    # Send packet out
                    msg = of.ofp_packet_out()
                    msg.data = ether.pack()
                    msg.actions.append(of.ofp_action_output(port = event.port))
                    event.connection.send(msg)
                    
                    ##log.info("Sent ARP reply: %s is at %s", self.virtual_ip, self.virtual_mac)
                else:
                    ethDst = EthAddr(MAC_ZERO+arp_packet.protodst.toStr()[-1])
                    arp_reply = arp()
                    arp_reply.hwsrc = ethDst        # MAC of real responder
                    arp_reply.hwdst = arp_packet.hwsrc      # MAC of requester
                    arp_reply.opcode = arp.REPLY
                    arp_reply.protosrc = arp_packet.protodst # IP being requested
                    arp_reply.protodst = arp_packet.protosrc # IP of requester
                    
                    # Create ethernet packet
                    ether = ethernet()
                    ether.type = ethernet.ARP_TYPE
                    ether.dst = packet.src                   # Send to requester
                    ether.src = ethDst                 # From responder
                    ether.payload = arp_reply
                    
                    # Send packet out
                    msg = of.ofp_packet_out()
                    msg.data = ether.pack()
                    msg.actions.append(of.ofp_action_output(port = event.port))
                    event.connection.send(msg)

        # Process only IPv4 traffic
        if packet.type == ethernet.IP_TYPE :
            ip_packet = packet.find('ipv4')
            if ip_packet:
                # Handle traffic directed to the virtual IP
                if ip_packet.dstip == self.virtual_ip:
                    # when packet in comes from the client site
                    selected_server = self._select_server()
                    
                    if selected_server:
                        self._redirect_to_server(event, ip_packet, selected_server)
                else:
                    # when packet in comes from the servers sites
                    self._redirect_to_client(event, ip_packet)
                return

        return

    def _select_server(self):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """
        Select the backend server with the least active connections.
        """
        return min(self.server_pool, key=self.server_pool.get)

    def _redirect_to_server(self, event, ip_packet, server):
        """
        Modify packet headers and redirect to the selected backend server.
        """
        #log.info("redirect to server")

        packet = event.parsed
        connection_og = event.connection

        #print("Original packet: ")
        #print(ip_packet)
        #print("redirected: ")
        #print(server)

        dpid_client = self.host_port_map[ip_packet.srcip][0]
        dpid_server = self.host_port_map[server][0]

        self._request_Path(dpid1=dpid_client, dpid2=dpid_server)

        while self.tmpPath is None:
            pass

        # create flow mod for the path
        self.tmpPath.reverse()
        for i, dpid in enumerate(self.tmpPath):
            connection = self.get_switch_connection(str_to_dpid(ZERO_DPID + f"{dpid}"))
            if dpid == self.tmpPath[0]:
                port_server = self.host_port_map[server][1]
                self._install_flow(connection, port_server, self._ip_to_mac(server), server, packet)
                #log.info(f"Install flow in {dpid}:{port_server}")
                
            elif dpid == self.tmpPath[-1]:
                port_server = self.paths[dpid][self.tmpPath[i-1]]
                self._install_flow_with_change(connection, port_server, self._ip_to_mac(server), server, packet)
                msg = of.ofp_packet_out(data=event.ofp)
                msg.actions.append(of.ofp_action_output(port=port_server))
                connection_og.send(msg)
                #log.info(f"Install flow in {dpid}:{port_server}")
                
            else:
                port_server = self.paths[dpid][self.tmpPath[i-1]]
                self._install_flow(connection, port_server, self._ip_to_mac(server), server, packet)
                #log.info(f"Install flow in {dpid}:{port_server}")
                
                
        self.tmpPath = None


    def _redirect_to_client(self, event, ip_packet):
        """
        Redirect traffic from backend servers to the client.
        """
        packet = event.parsed
        connection_og = event.connection

        dpid_server = self.host_port_map[ip_packet.dstip][0]
        dpid_client = self.host_port_map[ip_packet.srcip][0]

        self._request_Path(dpid1=dpid_client, dpid2=dpid_server)
        #log.info("request path sent")

        while self.tmpPath is None:
            pass
        
        # create flow mod for the path
        self.tmpPath.reverse()
        for i, dpid in enumerate(self.tmpPath):
            connection = self.get_switch_connection(str_to_dpid(ZERO_DPID + f"{dpid}"))
            if dpid == self.tmpPath[-1]:
                port_client = self.paths[dpid][self.tmpPath[i-1]]
                self._install_flow(connection, port_client, packet.dst, ip_packet.dstip, packet)
                msg = of.ofp_packet_out(data=event.ofp)
                msg.actions.append(of.ofp_action_dl_addr.set_dst(packet.dst))
                msg.actions.append(of.ofp_action_nw_addr.set_dst(ip_packet.dstip))
                msg.actions.append(of.ofp_action_output(port=port_client))
                connection_og.send(msg)
                #log.info(f"Install flow in {dpid}:{port_client}")
                
            elif dpid == self.tmpPath[0]:
                port_client = self.host_port_map[ip_packet.dstip][1]
                self._install_flow_with_change(connection, port_client, packet.dst, ip_packet.dstip, packet, True)
                #log.info(f"Install flow in {dpid}:{port_client}")
    
            else:
                port_client = self.paths[dpid][self.tmpPath[i-1]]
                self._install_flow(connection, port_client, packet.dst, ip_packet.dstip, packet)
                #log.info(f"Install flow in {dpid}:{port_client}")
    
        self.tmpPath = None

    def _install_flow(self, connection, out_port, dst_mac, dst_ip, packet, src_ip=None, src_mac=None):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.match.dl_dst = dst_mac
        msg.match.nw_dst = dst_ip
        msg.match.nw_proto = None
        msg.idle_timeout = IDLE_TIMEOUT
        msg.hard_timeout = HARD_TIMEOUT
        #log.info(f"dst: {msg.match.nw_dst} src: {msg.match.nw_src}")
        if not src_ip and src_mac:
            msg.match.dl_src = src_mac
            msg.match.nw_src = src_ip

        msg.actions.append(of.ofp_action_output(port=out_port))
        
        connection.send(msg)

    def _install_flow_with_change(self, connection, out_port, dst_mac, dst_ip, packet, is_to_client=False):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """
        Install a single flow entry that modifies addresses and forwards
        """
        #log.info("install flow change")
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        
        if is_to_client:
            msg.actions.append(of.ofp_action_dl_addr.set_src(self.virtual_mac))
            msg.actions.append(of.ofp_action_nw_addr.set_src(self.virtual_ip))
        else:
            msg.match.nw_dst = self.virtual_ip
            msg.match.dl_dst = self.virtual_mac
            msg.actions.append(of.ofp_action_dl_addr.set_dst(dst_mac))
            msg.actions.append(of.ofp_action_nw_addr.set_dst(dst_ip))
        msg.actions.append(of.ofp_action_output(port=out_port))
        msg.match.nw_proto = None
        msg.idle_timeout = IDLE_TIMEOUT
        msg.hard_timeout = HARD_TIMEOUT
        #log.info(f"dst: {msg.match.nw_dst} src: {msg.match.nw_src}")
        connection.send(msg)

    def _flood(self, event):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """
        Flood packets as a fallback.
        """
        msg = of.ofp_packet_out(data=event.ofp)
        msg.actions.append(of.ofp_action_output(port=of.OFPP_TABLE))
        event.connection.send(msg)
    
    def _request_flow_stats(self, connection):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        # Construct flow stats request
        if connection is not None:
            #log.debug("Sending flow stats request to %s", dpid_to_str(connection.dpid))
            request = of.ofp_stats_request()
            request.type = of.OFPST_FLOW
            request.body = of.ofp_flow_stats_request()
            connection.send(request)

    def _stats_loop(self):
        #log.debug("ENTER: " + inspect.currentframe().f_code.co_name)
        """Thread function that periodically requests stats"""
        while self.running:
            print(self.server_pool)
            self.server_pool= {IPAddr(f'10.0.0.{i}'):0 for i in range(1,5)} # server ip: connections count
            for dpid in self.dpids:
                if dpid in self.connections:
                    self._request_flow_stats(self.connections[dpid])
                else:
                    log.debug("No connection for DPID %s", dpid_to_str(dpid))
            # Wait for 3 seconds before next round
            sleep(REQUEST_FOR_STATS_INTERVAL)

    def _handle_FlowStatsReceived(self, event):
        #log.info("ENTER: " + inspect.currentframe().f_code.co_name)
        # Process flow stats reply
        #log.debug("Received flow stats from %s", dpid_to_str(event.connection.dpid))
        for flow in event.stats:
            # Check if flow has IP addresses
            if flow.match.nw_src and flow.match.nw_dst in self.server_pool.keys():
                # Convert IP addresses to strings
                self.server_pool[flow.match.nw_dst] += 1

            

    def get_flows(self):
        """Return the collected flow tuples"""
        return self.flows

    def stop(self):
        """Stop the stats collection thread"""
        self.running = False
        self.stats_thread.join()

    def _ip_to_mac(self, ip):
        return EthAddr(MAC_ZERO + ip.toStr()[-1])

def launch():
    """
    Launch the Least Connection Load Balancer.
    """
    core.registerNew(LeastConnectionLB)
