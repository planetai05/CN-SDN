# Simple QoS Priority Controller
**Course:** UE24CS252B – Computer Networks  
**Student:** ANISH A KUNDER | SRN : PES1UG24AM343  
**Project:** SDN Mininet-based Simulation – Simple QoS Priority Controller

---

## Problem Statement

In a real network, not all traffic is equally important. A video call should not be disrupted by a background file download. **Quality of Service (QoS)** solves this by assigning priority levels to different traffic types.

This project implements a **Simple QoS Priority Controller** using:
- **Mininet** – to simulate the network topology
- **Ryu** – as the SDN (OpenFlow 1.3) controller
- **OpenFlow flow rules** – to classify and prioritize traffic

### Traffic Priority Levels

| Traffic Type | Protocol | Priority Level | Use Case |
|---|---|---|---|
| ICMP (ping) | IP Proto 1 | **HIGH – 300** | Network control, diagnostics |
| TCP | IP Proto 6 | **MEDIUM – 200** | HTTP, file transfer, iperf |
| UDP | IP Proto 17 | **LOW – 100** | Video streaming, DNS |
| Other | — | **DEFAULT – 1** | Everything else (flood) |

---

## Network Topology

```
              [ Ryu Controller ]
                     |
                  (port 6653)
                     |
  h1 (10.0.0.1) ──┐
                   s1 ──── s2 ──── s3
  h2 (10.0.0.2) ──┘               |── h3 (10.0.0.3)
                                   └── h4 (10.0.0.4)

Switches : s1, s2, s3  (OVSSwitch, OpenFlow 1.3)
Links    : host-switch = 10 Mbps | switch-switch = 5 Mbps (bottleneck)
```

The switch-to-switch link is intentionally limited to **5 Mbps** to make the QoS priority effect observable.

---

## Project Files

```
qos_controller/
├── qos_controller.py   ← Ryu SDN controller (QoS logic)
├── topology.py         ← Mininet custom topology + interactive CLI
├── test_qos.py         ← Automated test runner (both test scenarios)
└── README.md           ← This file
```

---

## Setup & Execution Steps

### Prerequisites

Make sure you have the following installed on your Ubuntu VM:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Mininet
sudo apt install mininet -y

# Install Ryu SDN controller
pip install ryu

# Verify installations
sudo mn --version
ryu-manager --version
```

### Running the Project

You need **two terminal windows** open simultaneously.

#### Terminal 1 – Start the Ryu Controller

```bash
cd qos_controller/
ryu-manager qos_controller.py
```

You should see:
```
=======================================================
  Simple QoS Priority Controller started
  ICMP=HIGH(300)  TCP=MEDIUM(200)  UDP=LOW(100)
=======================================================
```

The controller is now listening for switches to connect.

#### Terminal 2 – Option A: Interactive Mode

```bash
cd qos_controller/
sudo python3 topology.py
```

This drops you into the **Mininet CLI** (`mininet>`) where you can run tests manually.

#### Terminal 2 – Option B: Automated Tests

```bash
cd qos_controller/
sudo python3 test_qos.py
```

This automatically runs all 5 test scenarios and prints results.

---

## Test Scenarios & Expected Output

### Scenario 1 – Basic Connectivity (`pingall`)

**Command (in Mininet CLI):**
```
mininet> pingall
```

**Expected Output:**
```
*** Ping: testing ping reachability
h1 -> h2 h3 h4
h2 -> h1 h3 h4
h3 -> h1 h2 h4
h4 -> h1 h2 h3
*** Results: 0% dropped (12/12 received)
```

All 4 hosts can reach each other. ✅

---

### Scenario 2 – ICMP Latency (HIGH Priority)

**Command (in Mininet CLI):**
```
mininet> h1 ping -c 10 h4
```

**Expected Output:**
```
10 packets transmitted, 10 received, 0% packet loss
rtt min/avg/max/mdev = 0.X/0.X/0.X/0.X ms
```

Controller log shows:
```
[QoS] HIGH   priority=300 | ICMP | 10.0.0.1 → 10.0.0.4 | port 2
```

---

### Scenario 3 – TCP Throughput (MEDIUM Priority)

**Commands (in Mininet CLI):**
```
mininet> h4 iperf -s &
mininet> h1 iperf -c 10.0.0.4 -t 10
```

**Expected Output:**
```
[  3]  0.0-10.0 sec   X.XX MBytes   X.XX Mbits/sec
```

Controller log shows:
```
[QoS] MEDIUM priority=200 | TCP  | 10.0.0.1 → 10.0.0.4 | port 2
```

---

### Scenario 4 – UDP Throughput (LOW Priority)

**Commands (in Mininet CLI):**
```
mininet> h4 iperf -s -u &
mininet> h1 iperf -c 10.0.0.4 -u -b 5M -t 10
```

**Expected Output:**
```
[  3]  0.0-10.0 sec   X.XX MBytes   X.XX Mbits/sec  X% packet loss
```

Controller log shows:
```
[QoS] LOW    priority=100 | UDP  | 10.0.0.1 → 10.0.0.4 | port 2
```

---

### Scenario 5 – Flow Table Verification

**Command (in Mininet CLI):**
```
mininet> sh ovs-ofctl -O OpenFlow13 dump-flows s1
```

**Expected Output (after running both ICMP and TCP tests):**
```
 priority=300,icmp,in_port="s1-eth1",nw_src=10.0.0.1,nw_dst=10.0.0.4 actions=output:"s1-eth3"
 priority=200,tcp,in_port="s1-eth1",nw_src=10.0.0.1,nw_dst=10.0.0.4  actions=output:"s1-eth3"
 priority=100,udp,in_port="s1-eth1",nw_src=10.0.0.1,nw_dst=10.0.0.4  actions=output:"s1-eth3"
 priority=0 actions=CONTROLLER:65535
```

This confirms flow rules are installed with correct QoS priority values. ✅

---

## How It Works – SDN Logic Explained

### 1. Controller–Switch Handshake

When a switch connects, the controller installs a **table-miss rule** (priority=0):
- Match: all packets
- Action: send to controller

This ensures unknown packets reach the controller.

### 2. Packet-In Event (packet_in_handler)

For each new packet:
1. **MAC Learning** – the controller notes which port a MAC address arrived from
2. **Forwarding Decision** – if destination MAC is known, forward to that port; else flood
3. **Traffic Classification** – inspect IP protocol field:
   - `ip_proto = 1`  → ICMP → priority 300
   - `ip_proto = 6`  → TCP  → priority 200
   - `ip_proto = 17` → UDP  → priority 100
4. **Flow Rule Installation** – push OpenFlow FLOW_MOD to the switch so future matching packets bypass the controller
5. **Packet Out** – forward the current packet immediately

### 3. Match–Action Design

```
Match: [in_port, eth_type=IP, ip_proto, src_ip, dst_ip]
Action: [output → specific port]
Priority: based on traffic type
```

Higher priority rules are evaluated first by the switch, giving ICMP traffic preferential treatment over TCP and UDP.

---

## Cleanup

After running experiments, always clean up:

```bash
# In Mininet CLI
mininet> exit

# Clean up OVS and Mininet state
sudo mn -c
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ryu-manager: command not found` | `pip install ryu` or `pip3 install ryu` |
| Controller not connecting | Check port 6653 is not blocked: `sudo ufw allow 6653` |
| `sudo mn` hangs | Run `sudo mn -c` first to clean up old state |
| `iperf: command not found` | `sudo apt install iperf -y` |
| Flow rules not showing | Wait 2–3 seconds after `pingall`, then run `dump-flows` |

---

## References

1. Ryu SDN Framework Documentation – https://ryu.readthedocs.io/en/latest/
2. OpenFlow 1.3 Specification – https://opennetworking.org/wp-content/uploads/2014/10/openflow-spec-v1.3.0.pdf
3. Mininet Walkthrough – https://mininet.org/walkthrough/
4. Mininet GitHub – https://github.com/mininet/mininet
5. Open vSwitch Documentation – https://docs.openvswitch.org/
6. Course Material: UE24CS252B – Computer Networks, PES University

---

*This project was submitted as part of the SDN Mininet-based Simulation assignment for UE24CS252B – Computer Networks.*
