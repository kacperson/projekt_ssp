from pox.core import core
from pox.lib.packet import ethernet, ipv4, tcp, arp
from pox.lib.addresses import EthAddr, IPAddr
import pox.openflow.libopenflow_01 as of
from collections import defaultdict
from pox.lib.util import str_to_dpid, dpid_to_str
from pox.lib.revent import Event, EventMixin

log = core.getLogger()

ZERO_DPID = "00-00-00-00-00-0"

class RequestPathEvent(Event):
        def __init__(self, dpid1, dpid2):
            Event.__init__(self)
            self.path_endpoints = (dpid1, dpid2)


# class LBEvents(EventMixin):

#     _eventMixin_events = set([RequestPathEvent])

#     def __init__(self):
#         EventMixin.__init__(self)

#     def _request_Path(self, dpid1, dpid2):
#             log.debug("Raising requestPathEvent")
#             self.raiseEvent(RequestPathEvent(dpid1, dpid2))


class LeastConnectionLB(EventMixin):
    _eventMixin_events = set([RequestPathEvent])  # Register events
    
    def __init__(self):
        # Initialize EventMixin first
        EventMixin.__init__(self)
        log.info("Starting Least Connection Load Balancer")
        self._core_name = 'misc_lclb'
        # Server pool configuration
        self.server_pool = [
            {'ip': IPAddr('10.0.0.1'), 'mac': EthAddr('00:00:00:00:00:01')},  # H5
            {'ip': IPAddr('10.0.0.2'), 'mac': EthAddr('00:00:00:00:00:02')},  # H6
            {'ip': IPAddr('10.0.0.3'), 'mac': EthAddr('00:00:00:00:00:03')},  # H7
            {'ip': IPAddr('10.0.0.4'), 'mac': EthAddr('00:00:00:00:00:04')}   # H8
        ]
        
        # Virtual service configuration
        self.virtual_ip = IPAddr('10.0.0.100')
        self.virtual_mac = EthAddr('0a:00:00:64:00:00')
        
        # Connection tracking
        self.connection_counts = defaultdict(int)  # Active connections per server
        self.paths = {}  # Store computed paths
        
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
        
    def _handle_ConnectionUp(self, event):
        """Store switch connection when it connects"""
        dpid = event.dpid
        self.connections[dpid] = event.connection
        print(f"Switch {dpid_to_str(dpid)} connected")
        
    def _handle_ConnectionDown(self, event):
        """Remove switch connection when it disconnects"""
        dpid = event.dpid
        if dpid in self.connections:
            del self.connections[dpid]
            print(f"Switch {dpid_to_str(dpid)} disconnected")
            
    def get_switch_connection(self, dpid):
        """Get connection to specific switch by DPID"""
        return self.connections.get(dpid)
        
    def send_message_to_switch(self, dpid, message):
        """Send OpenFlow message to specific switch"""
        connection = self.get_switch_connection(dpid)
        if connection:
            connection.send(message)
            return True
        return False
    
    def _handle_ResponsePathEvent(self, event):
        log.info("ResponsePATH")
        self.tmpPath = event.path

    def _request_Path(self, dpid1, dpid2):
        log.debug("Raising requestPathEvent")
        self.raiseEvent(RequestPathEvent(dpid1, dpid2))

    def _handle_SendLink(self, event):

        if event.link.dpid1 not in self.paths:
            self.paths[event.link.dpid1] = {event.link.dpid2: event.link.port1}
        else:
            self.paths[event.link.dpid1][event.link.dpid2] = event.link.port1
        
        if event.link.dpid2 not in self.paths:
            self.paths[event.link.dpid2] = {event.link.dpid1: event.link.port2}
        else:
            self.paths[event.link.dpid2][event.link.dpid1] = event.link.port2

        #log.info(f"dpid1: {event.link.dpid1}, port1: {event.link.port1}, dpid2: {event.link.dpid2}, port2: {event.link.port2}")

    def _handle_PacketIn(self, event):
        packet = event.parsed
        if not packet:
            return

        in_port = event.port
        connection = event.connection
        if packet.type == ethernet.ARP_TYPE:
            arp_packet = packet.payload
            
            if arp_packet.opcode == arp.REQUEST:
                if arp_packet.protodst == self.virtual_ip:
                    log.debug("Received ARP request for virtual IP")
                    
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
                    
                    # log.info("Sent ARP reply: %s is at %s", self.virtual_ip, self.virtual_mac)

        # Process only IPv4 traffic
        if packet.type == ethernet.IP_TYPE:
            ip_packet = packet.find('ipv4')
            #tcp_packet = packet.find('udp')
            print("dupa1")
            print(type(packet))
            if ip_packet:
                # Handle traffic directed to the virtual IP
                print("dupa2")
                if ip_packet.dstip == IPAddr('10.0.0.100'):
                    selected_server = self._select_server()
                    print("dupa3")
                    print(selected_server)
                    if selected_server:
                        print("dupa4")
                        self.connection_counts[selected_server['ip']] += 1
                        self._redirect_to_server(
                            event, ip_packet, selected_server, in_port
                        )
                    return

                # Handle traffic from backend servers to clients
                for server in self.server_pool:
                    if ip_packet.srcip == server['ip']:
                        print("duap5")
                        self._redirect_to_client(event, ip_packet, server, in_port)
                        return

        # Flood other packets
        self._flood(event)


    def _select_server(self):
        """
        Select the backend server with the least active connections.
        """
        return min(self.server_pool, key=lambda s: self.connection_counts[s['ip']])

    def _redirect_to_server(self, event, ip_packet, server, client_port):
        """
        Modify packet headers and redirect to the selected backend server.
        """
        DPID = "00-00-00-00-00-0"

        packet = event.parsed
        connection = event.connection

        print("Original packet: ")
        print(ip_packet)
        print("redirected: ")
        print(server["ip"])

        # Rewrite destination IP/MAC to server's IP/MAC
        ip_packet.dstip = server['ip']
        packet.dst = server['mac']

        dpid_client = self.host_port_map[ip_packet.srcip][0]
        dpid_server = self.host_port_map[server["ip"]][0]

        self._request_Path(dpid1=dpid_client, dpid2=dpid_server)
        log.info("request path sent")

        while self.tmpPath is None:
            pass
        
        path_reversed = list(reversed(self.tmpPath))
        print(path_reversed)
        for dpid in path_reversed:
            connection = self.get_switch_connection(str_to_dpid(DPID + f"{dpid}"))
            if dpid == path_reversed[0]:
                port_server = self.host_port_map[server["ip"]][1]
                self._install_flow(connection, port_server, server['mac'], server['ip'], packet.src, ip_packet.srcip)
                port_client = self.paths[dpid][path_reversed[path_reversed.index(dpid)+1]]
                self._install_flow(connection, port_server, packet.src, ip_packet.srcip, server['mac'], server['ip'])
                log.info(f"Install flow in {dpid}")
            elif dpid == path_reversed[-1]:
                port_server = self.paths[dpid][path_reversed[path_reversed.index(dpid)-1]]
                self._install_flow_with_change(connection, port_server, server['mac'], server['ip'], packet.src, ip_packet.srcip)
                port_client = self.host_port_map[ip_packet.srcip][1]
                self._install_flow(connection, port_client, packet.src, ip_packet.srcip, server['mac'], server['ip'])
                log.info(f"Install flow in {dpid}")
            else:
                port_server = self.paths[dpid][path_reversed[path_reversed.index(dpid)-1]]
                self._install_flow(connection, port_server, server['mac'], server['ip'], packet.src, ip_packet.srcip)
                port_client = self.paths[dpid][path_reversed[path_reversed.index(dpid)+1]]
                self._install_flow(connection, port_client, packet.src, ip_packet.srcip, server['mac'], server['ip'])
                log.info(f"Install flow in {dpid}")
                
        self.tmpPath = None

        # Install a flow rule for client -> server
        
        # Send the packet to the server
        # msg = of.ofp_packet_out(data=event.ofp)
        # msg.actions.append(of.ofp_action_output(port=of.OFPP_TABLE))
        # connection.send(msg)

    def _redirect_to_client(self, event, ip_packet, server, server_port):
        """
        Redirect traffic from backend servers to the client.
        """
        packet = event.parsed
        connection = event.connection

        # Rewrite source IP/MAC to the virtual IP/MAC
        ip_packet.srcip = self.virtual_ip
        packet.src = self.virtual_mac

        # Install a flow rule for server -> client
        self._install_flow(connection, server_port, server['mac'], server['ip'], packet.dst, ip_packet.dstip)
        
        # Send the packet to the client
        msg = of.ofp_packet_out(data=event.ofp)
        msg.actions.append(of.ofp_action_output(port=of.OFPP_TABLE))
        connection.send(msg)

    def _install_flow(self, connection, out_port, src_mac, src_ip, dst_mac, dst_ip):
        """
        Install a single flow entry that modifies addresses and forwards
        """
        msg = of.ofp_flow_mod()
        msg.match.dl_src = src_mac
        msg.match.dl_dst = dst_mac
        msg.match.dl_type = 0x0800
        msg.match.nw_src = src_ip
        msg.match.nw_dst = dst_ip
        msg.idle_timeout = 30
        
        # First modify addresses, then forward
        msg.actions.append(of.ofp_action_output(port=out_port))
        
        connection.send(msg)
    
    def _install_flow_with_change(self, connection, out_port, src_mac, src_ip, dst_mac, dst_ip):
        """
        Install a single flow entry that modifies addresses and forwards
        """
        msg = of.ofp_flow_mod()
        msg.match.dl_src = src_mac
        msg.match.dl_type = 0x0800
        msg.match.nw_src = src_ip
        msg.match.nw_dst = IPAddr("10.0.0.100")
        msg.idle_timeout = 30
        
        # First modify addresses, then forward
        msg.actions.append(of.ofp_action_dl_addr.set_dst(dst_mac))
        msg.actions.append(of.ofp_action_nw_addr.set_dst(dst_ip))
        msg.actions.append(of.ofp_action_output(port=out_port))
        
        connection.send(msg)

    def _flood(self, event):
        """
        Flood packets as a fallback.
        """
        msg = of.ofp_packet_out(data=event.ofp)
        msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
        event.connection.send(msg)


def launch():
    """
    Launch the Least Connection Load Balancer.
    """
    core.registerNew(LeastConnectionLB)
    #core.registerNew(LBEvents, "LBEvents")
