from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost, Controller, RemoteController, OVSSwitch, Ryu, OVSKernelSwitch
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from functools import partial
from time import sleep, time_ns
import random
import threading

NUMBER_OF_SWITCHES = 6
NUMBER_OF_HOSTS = 8

MIN_DURATION = 3
MAX_DURATION = 10

MIN_BURST = 10
MAX_BURST = 1000

MIN_INTERVAL = 0.1
MAX_INTERVAL = 1.0

NUMBER_OF_SERVERS = 9

class CustomMininetTopo(Topo):
    "Single switch connected to n hosts."
    def build( self ):
        "Create custom topo."

        switchesNames = [f"s{num+1}" for num in range(NUMBER_OF_SWITCHES)]
        hostNames = [f"h{num+1}" for num in range(NUMBER_OF_HOSTS)]

        hosts = [self.addHost(hName, mac=f'00:00:00:0{hName[1]}:0{hName[1]}:0{hName[1]}')\
                for hName in hostNames]
        switches = [self.addSwitch(name) for name in switchesNames]
        switch = lambda name: switches[switchesNames.index(name)]
        host = lambda name: hosts[hostNames.index(name)]

        
        self.addLink(switch("s1"), switch("s2"), port1=1, port2=1, bw=2)
        self.addLink(switch("s2"), switch("s3"), port1=2, port2=2, bw=2)
        self.addLink(switch("s3"), switch("s4"), port1=1, port2=1, bw=2)
        self.addLink(switch("s4"), switch("s1"), port1=2, port2=2, bw=2)
        self.addLink(switch("s5"), switch("s2"), port1=1 ,port2=3, bw=2)
        self.addLink(switch("s6"), switch("s4"), port1=1 ,port2=3, bw=2)
  
        self.addLink(switch("s1"), host("h1"), port1=3 ,port2=1, bw=2)
        self.addLink(switch("s1"), host("h2"), port1=4 ,port2=1, bw=2)
        self.addLink(switch("s3"), host("h3"), port1=3 ,port2=1, bw=2)
        self.addLink(switch("s3"), host("h4"), port1=4 ,port2=1, bw=2)
        self.addLink(switch("s5"), host("h5"), port1=2 ,port2=1, bw=2)
        self.addLink(switch("s5"), host("h6"), port1=3 ,port2=1, bw=2)
        self.addLink(switch("s6"), host("h7"), port1=2 ,port2=1, bw=2)
        self.addLink(switch("s6"), host("h8"), port1=3 ,port2=1, bw=2)
        


def networkSetup():
    "Create network and run simple performance test"
    topo = CustomMininetTopo()
    net = Mininet(topo=topo,
                    switch=OVSKernelSwitch,
                    controller=RemoteController(name='c0', ip='192.168.110.137', port=6633),
                    autoSetMacs = False,
                    autoStaticArp = False,
                    xterms=False,
                    host=CPULimitedHost, link=TCLink)
    
    for sw in net.switches:
        sw.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        sw.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        sw.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
        
    
    for switch in net.switches:
        switch_nr = int(switch.name.replace('s', ''))  # Extract switch number from name
        for port in switch.intfList():
            if 'eth' in port.name:
                port_nr = int(port.name.replace(switch.name + '-eth', ''))  # Extract port number from interface name
                mac_address = '88:0{switch_nr:1d}:00:00:00:{port_nr:02d}'.format(switch_nr=switch_nr, port_nr=port_nr)
                port.setMAC(mac_address)
    
    
    net.start()
    dumpNodeConnections(net.hosts)
    net.pingAll()
    generate_random_traffic(net)
    CLI()

    net.stop()

def run_iperf_servers(net):
    """Run Iperf servers on hosts 1 to 4"""
    for i in range(1, 5):
        for j in range (1, 10):
            host = net.get(f'h{i}')
            host.cmd(f'iperf3 -s -i 1 -p {i}00{j} &')
        print(f'Iperf server started on h{i}')

def run_iperf_client(client, server):
    """Run Iperf clients on hosts 5 to 8"""
    duration = random.randint(MIN_DURATION, MAX_DURATION)
    burst_size = random.randint(MIN_BURST, MAX_BURST)
    interval = random.uniform(MIN_INTERVAL, MAX_INTERVAL)
    port_nr = random.randint(1, NUMBER_OF_SERVERS)
    timestamp = time_ns()
    print(f'iperf3 -c {server.IP()} -t {duration} -b {burst_size}K -i {interval} -p {server.name[1]}00{port_nr} -u --logfile iperf_{client.name}_to_{server.name}_{timestamp}.log &')
    client.cmd(f'iperf3 -c {server.IP()} -t {duration} -b {burst_size}K -i {interval} -p {server.name[1]}00{port_nr} -u --logfile iperf_{client.name}_to_{server.name}_{timestamp}.log &')

def generate_random_traffic(net):

    src_hosts = net.hosts[4:]
    dst_hosts = net.hosts[:4]
    run_iperf_servers(net)
    while True:
        client = random.choice(src_hosts)
        server = random.choice(dst_hosts)
        run_iperf_client(client, server)
        sleep(2)




if __name__ == '__main__':
    setLogLevel('info')
    networkSetup()
