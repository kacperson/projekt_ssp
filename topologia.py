from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import CPULimitedHost, Controller, RemoteController, OVSSwitch, Ryu, OVSKernelSwitch
from mininet.link import TCLink
from mininet.util import dumpNodeConnections
from mininet.log import setLogLevel
from mininet.cli import CLI
from functools import partial
from time import sleep

class CustomMininetTopo(Topo):
    "Single switch connected to n hosts."
    def build( self ):
        "Create custom topo."
        NUMBER_OF_SWITCHES = 6
        NUMBER_OF_HOSTS = 8

        switchesNames = [f"s{num+1}" for num in range(NUMBER_OF_SWITCHES)]
        hostNames = [f"h{num+1}" for num in range(NUMBER_OF_HOSTS)]

        hosts = [self.addHost(hName, mac=f'00:00:00:0{hName[1]}:0{hName[1]}:0{hName[1]}')\
                for hName in hostNames]
        switches = [self.addSwitch(name) for name in switchesNames]
        switch = lambda name: switches[switchesNames.index(name)]
        host = lambda name: hosts[hostNames.index(name)]

        
        self.addLink(switch("s1"), switch("s2"), port1=1, port2=1, bw=50)
        self.addLink(switch("s2"), switch("s3"), port1=2, port2=2, bw=50)
        self.addLink(switch("s3"), switch("s4"), port1=1, port2=1, bw=50)
        self.addLink(switch("s4"), switch("s1"), port1=2, port2=2, bw=50)
        self.addLink(switch("s5"), switch("s2"), port1=1 ,port2=3, bw=50)
        self.addLink(switch("s6"), switch("s4"), port1=1 ,port2=3, bw=50)
  
        self.addLink(switch("s1"), host("h1"), port1=3 ,port2=1, bw=50)
        self.addLink(switch("s1"), host("h2"), port1=4 ,port2=1, bw=50)
        self.addLink(switch("s3"), host("h3"), port1=3 ,port2=1, bw=50)
        self.addLink(switch("s3"), host("h4"), port1=4 ,port2=1, bw=50)
        self.addLink(switch("s5"), host("h5"), port1=2 ,port2=1, bw=50)
        self.addLink(switch("s5"), host("h6"), port1=3 ,port2=1, bw=50)
        self.addLink(switch("s6"), host("h7"), port1=2 ,port2=1, bw=50)
        self.addLink(switch("s6"), host("h8"), port1=3 ,port2=1, bw=50)
        


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
    # print("Start iperf server")
    # net.hosts[3].cmd("iperf3 -s -p 3001 & \n")
    # net.hosts[3].cmd("iperf3 -s -p 3002 & \n")
    # net.hosts[3].cmd("iperf3 -s -p 3003 & \n")
    # sleep(3)
    # print("Start clients")
    # net.hosts[0].cmd("iperf3 -c 10.0.0.4 -p 3001 -t 1260 -i 1 --logfile ./flows_Scenario1/h1s1new.txt & \n")
    # net.hosts[1].cmd("iperf3 -c 10.0.0.4 -p 3002 -t 1260 -i 1 --logfile ./flows_Scenario1/h2s1new.txt & \n")
    # net.hosts[2].cmd("iperf3 -c 10.0.0.4 -p 3003 -t 1260 -i 1 --logfile ./flows_Scenario1/h3s1new.txt & \n")
    #sleep()
    #input()
    #networkTest2(net)

    CLI(net)
    net.stop()


if __name__ == '__main__':
    setLogLevel('info')
    networkSetup()
