# Projekt SDN - Least Connection Load Balancer #

Projekt polega na zbudowaniu load balancera opartego na algorytmie least conections czyli ruch kierowany jest do serwerów docelowych które mają najmniej połączeń.

## Topologia ##

![image](https://github.com/user-attachments/assets/7ed83267-4321-4976-9ba1-9c31f57abedd)



## Algorytm sterownika ##
![image](https://github.com/user-attachments/assets/08491389-cd2b-4586-8a9b-ea01e602bda7)

## Instrukcja uruchomienia sterownika ##
### 1. Przygotowanie środowiska ###
Zalecaną wersją linuxa do uruchomienia tego sterownika jest Ubuntu 20.04.14. 

### 2. Sterownik POX ###
Aby sterownik POX zadziałał należy pobrać poniższe repozytorium do katalogu domowego:  
`git clone http://github.com/noxrepo/pox`  
Następnie pobieramy 2 pliki z tego repozytorium: `leastConnectionLB.py` i `discovery.py`.  
Plik `leastConnectionLB.py` kopiujemy do folderu `~/pox/pox/misc/`.  
Plik `discovery.py` podmieniamy z plikiem `discovery.py` znajdującym się w `~/pox/pox/openflow/`  
Doinstalowujemy potrzebne biblioteki, domyślnie powinno to być tylko: `pip install networkx`  

### 3. Mininet ###
Pobieramy środowisko mininet oraz instalujemy je:  
```
git clone https://github.com/mininet/mininet
mininet/util/install.sh -a
```
Jeżeli nie mamy zainstalowego programu iperf3 też należy go zainstalować:  
`sudo apt install iperf3`  
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
`~/pox$ ./pox.py openflow.discovery host_tracker.host_tracker misc.leastConnectionLB openflow.spanning_tree`  
Następnie włączamy skrypt z topologią:  
`~/mininet$ sudo python3 custom/topologia.py`  
W folderze `mininet` powinny zacząć pojawiać się logi generowane przez program iperf3 generujący ruch sieciowy.
