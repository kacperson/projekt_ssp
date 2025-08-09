# 🇵🇱
# Projekt SDN - Least Connection Load Balancer#

Projekt polega na zbudowaniu load balancera opartego na algorytmie least connections, czyli ruch kierowany jest do serwerów docelowych które mają najmniej połączeń.  
W zakres projektu wchodzi:  
- odpytywanie przełączników **s1** i **s3** o aktywne połączenia
- generowanie ruchu z klientów **h5/h6/h7/h8** na adres wirtualny **10.0.0.100** i kierowanie połączenia do wyznaczonego przez algorytm serwera **h1/h2/h3/h4**
- podmienianie adresu docelowego wirtualnego **10.0.0.100** na adres docelowego serwera przez przełączniki **s5** i **s6**

Projekt korzysta z gotowych modułów sterownika POX *discovery*, *spanning tree*, *host_tracker*. Moduł *discovery* jest wzbogacony o wysyłanie informacji o połączeniach między węzłami i portach na jakich są połączone oraz o wysyłanie ścieżki między węzłami jeżeli zostanie o to zapytany.
Moduł *LeastConnectionLB* jest odpowiedzialny za obsługę sterownika sieci razem z algorytmem least connections.

Narzędzia z jakich skorzystano to:
- sterwonik POX
- środowisko mininet
- generator ruchu iperf3
  
## Topologia ##

![image](https://github.com/user-attachments/assets/7ed83267-4321-4976-9ba1-9c31f57abedd)



## Algorytm sterownika ##
![image](https://github.com/user-attachments/assets/08491389-cd2b-4586-8a9b-ea01e602bda7)

## Instrukcja uruchomienia sterownika ##
### 1. Przygotowanie środowiska ###
Zalecaną wersją linuxa do uruchomienia tego sterownika jest Ubuntu 20.04.14. 

### 2. Sterownik POX ###
Aby sterownik POX zadziałał należy pobrać poniższe repozytorium do katalogu domowego:  
```
~$ git clone http://github.com/noxrepo/pox
``` 
Następnie pobieramy 2 pliki z tego repozytorium: `leastConnectionLB.py` i `discovery.py`.  
Plik `leastConnectionLB.py` kopiujemy do folderu `~/pox/pox/misc/`.  
Plik `discovery.py` podmieniamy z plikiem `discovery.py` znajdującym się w `~/pox/pox/openflow/`  
Doinstalowujemy potrzebne biblioteki, domyślnie powinno to być tylko: `pip install networkx`  

### 3. Mininet ###
Pobieramy środowisko mininet oraz instalujemy je:  
```
~$ git clone https://github.com/mininet/mininet
~$ mininet/util/install.sh -a
```
Jeżeli nie mamy zainstalowego programu iperf3 też należy go zainstalować:  
```
~$ sudo apt install iperf3`
```
Pobieramy plik `topologia.py` z tego repozytorium i umieszczamy w katalogu `~/mininet/custom/`.  
W pliku `topologia.py` wpisujemy prawdziwy adres ip sterownika.
```
    net = Mininet(topo=topo,
                    switch=OVSKernelSwitch,
                    controller=RemoteController(name='c0', ip='<controller_ip>', port=6633),
                    autoSetMacs = False,
                    autoStaticArp = False,
                    xterms=False,
                    host=CPULimitedHost, link=TCLink)
```

### 4. Testowanie sterownika ###
Aby sprawdzić działanie sterwonika zalecane jest włączenie go przed uruchomieniem środowiska mininet:  
```
~/pox$ ./pox.py openflow.discovery host_tracker.host_tracker misc.leastConnectionLB openflow.spanning_tree
```
Następnie w innym terminalu włączamy skrypt z topologią:  
```
~/mininet$ sudo python3 custom/topologia.py
```
W folderze `mininet` powinny zacząć pojawiać się logi generowane przez program iperf3 generujący ruch sieciowy.
W terminalu ze sterownikiem powinny pojawiać się logi, w których jest pokazane ile jest aktywnych połączeń do każdego z serwerów.  

### 5. Opcje testowania ###
W pliku `topologia.py` możemy zmieniać opcje generowania ruchu.  
```
#duration of packet stream
MIN_DURATION = 2
MAX_DURATION = 10

#size of packet burst
MIN_BURST = 10
MAX_BURST = 1000

#interval between packet bursts
MIN_INTERVAL = 0.1
MAX_INTERVAL = 1.0

#interval between creating new packet stream
GENERATION_INTERVAL = 2
```

W pliku `leasConnectionLB.py` znajdują się opcje które można zmieniać działanie sterownika:  
```
#flow entry timeouts
IDLE_TIMEOUT = 2
HARD_TIMEOUT = 5

#interval between requesting from OVS'es connections stats 
REQUEST_FOR_STATS_INTERVAL = 1
```

# 🇬🇧
# SDN Project - Least Connection Load Balancer #

The project involves building a load balancer based on the least connections algorithm, where traffic is directed to destination servers that have the fewest connections.

The project scope includes:
- querying switches **s1** and **s3** for active connections
- generating traffic from clients **h5/h6/h7/h8** to virtual address **10.0.0.100** and directing connections to the server designated by the algorithm **h1/h2/h3/h4**
- replacing the virtual destination address **10.0.0.100** with the destination server address through switches **s5** and **s6**

The project uses ready-made POX controller modules *discovery*, *spanning tree*, *host_tracker*. The *discovery* module is enhanced to send information about connections between nodes and the ports they are connected to, as well as to send paths between nodes when requested.

The *LeastConnectionLB* module is responsible for handling the network controller together with the least connections algorithm.

Tools used:
- POX controller
- mininet environment
- iperf3 traffic generator

## Topology ##
![image](https://github.com/user-attachments/assets/7ed83267-4321-4976-9ba1-9c31f57abedd)

## Controller Algorithm ##
![image](https://github.com/user-attachments/assets/08491389-cd2b-4586-8a9b-ea01e602bda7)

## Controller Setup Instructions ##

### 1. Environment Preparation ###
The recommended Linux version for running this controller is Ubuntu 20.04.14.

### 2. POX Controller ###
For the POX controller to work, you need to download the following repository to your home directory:
```
~$ git clone http://github.com/noxrepo/pox
```
Next, download 2 files from this repository: `leastConnectionLB.py` and `discovery.py`.
Copy the `leastConnectionLB.py` file to the `~/pox/pox/misc/` folder.
Replace the `discovery.py` file with the `discovery.py` file located in `~/pox/pox/openflow/`
Install the required libraries, by default this should only be: `pip install networkx`

### 3. Mininet ###
Download the mininet environment and install it:
```
~$ git clone https://github.com/mininet/mininet
~$ mininet/util/install.sh -a
```
If you don't have iperf3 installed, you also need to install it:
```
~$ sudo apt install iperf3
```
Download the `topologia.py` file from this repository and place it in the `~/mininet/custom/` directory.
In the `topologia.py` file, enter the actual IP address of the controller.
```
    net = Mininet(topo=topo,
                    switch=OVSKernelSwitch,
                    controller=RemoteController(name='c0', ip='<controller_ip>', port=6633),
                    autoSetMacs = False,
                    autoStaticArp = False,
                    xterms=False,
                    host=CPULimitedHost, link=TCLink)
```

### 4. Controller Testing ###
To check the controller's operation, it is recommended to start it before launching the mininet environment:
```
~/pox$ ./pox.py openflow.discovery host_tracker.host_tracker misc.leastConnectionLB openflow.spanning_tree
```
Then in another terminal, run the topology script:
```
~/mininet$ sudo python3 custom/topologia.py
```
In the `mininet` folder, logs generated by the iperf3 program generating network traffic should start appearing.
In the controller terminal, logs should appear showing how many active connections there are to each server.

### 5. Testing Options ###
In the `topologia.py` file, we can change the traffic generation options.
```
#duration of packet stream
MIN_DURATION = 2
MAX_DURATION = 10
#size of packet burst
MIN_BURST = 10
MAX_BURST = 1000
#interval between packet bursts
MIN_INTERVAL = 0.1
MAX_INTERVAL = 1.0
#interval between creating new packet stream
GENERATION_INTERVAL = 2
```
In the `leastConnectionLB.py` file, there are options that can change the controller's behavior:
```
#flow entry timeouts
IDLE_TIMEOUT = 2
HARD_TIMEOUT = 5
#interval between requesting from OVS'es connections stats 
REQUEST_FOR_STATS_INTERVAL = 1
```
