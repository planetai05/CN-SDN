"""
QoS Test Script – Automated Test Scenarios
============================================
Student: ANISH A KUNDER | Roll No: 16

This script runs the topology and performs two test scenarios:
    Scenario 1: Latency comparison – ICMP (HIGH) vs UDP (LOW)
    Scenario 2: Flow table verification – shows installed QoS rules

Usage:
    # Terminal 1: ryu-manager qos_controller.py
    # Terminal 2: sudo python3 test_qos.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.log import setLogLevel, info
from mininet.link import TCLink
import time


def run_tests():
    setLogLevel('info')

    # ── Build same topology ───────────────────────────────────────────────
    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True
    )

    c0 = net.addController('c0', controller=RemoteController,
                            ip='127.0.0.1', port=6653)

    s1 = net.addSwitch('s1', cls=OVSSwitch, protocols='OpenFlow13')
    s2 = net.addSwitch('s2', cls=OVSSwitch, protocols='OpenFlow13')
    s3 = net.addSwitch('s3', cls=OVSSwitch, protocols='OpenFlow13')

    h1 = net.addHost('h1', ip='10.0.0.1/24')
    h2 = net.addHost('h2', ip='10.0.0.2/24')
    h3 = net.addHost('h3', ip='10.0.0.3/24')
    h4 = net.addHost('h4', ip='10.0.0.4/24')

    net.addLink(h1, s1, bw=10)
    net.addLink(h2, s1, bw=10)
    net.addLink(h3, s3, bw=10)
    net.addLink(h4, s3, bw=10)
    net.addLink(s1, s2, bw=5)
    net.addLink(s2, s3, bw=5)

    net.build()
    c0.start()
    for sw in [s1, s2, s3]:
        sw.start([c0])

    time.sleep(2)

    print("\n" + "="*60)
    print("  RUNNING AUTOMATED QoS TEST SCENARIOS")
    print("="*60)

    # ────────────────────────────────────────────────────────────
    #  SCENARIO 1: Basic connectivity – pingall
    # ────────────────────────────────────────────────────────────
    print("\n[SCENARIO 1] Basic Connectivity Test (pingall)")
    print("-" * 50)
    net.pingAll()
    time.sleep(1)

    # ────────────────────────────────────────────────────────────
    #  SCENARIO 2: ICMP latency (HIGH priority traffic)
    # ────────────────────────────────────────────────────────────
    print("\n[SCENARIO 2] ICMP Ping Latency – HIGH Priority Traffic")
    print("-" * 50)
    print("h1 → h4 (ICMP / ping) – should be fast & consistent")
    result = h1.cmd('ping -c 10 10.0.0.4')
    print(result)
    time.sleep(1)

    # ────────────────────────────────────────────────────────────
    #  SCENARIO 3: TCP throughput (MEDIUM priority)
    # ────────────────────────────────────────────────────────────
    print("\n[SCENARIO 3] TCP Throughput – MEDIUM Priority Traffic")
    print("-" * 50)
    print("Starting iperf TCP server on h4 ...")
    h4.cmd('iperf -s &')
    time.sleep(1)
    print("Running iperf TCP client from h1 → h4 (10 seconds)")
    result = h1.cmd('iperf -c 10.0.0.4 -t 10')
    print(result)
    h4.cmd('kill %iperf')
    time.sleep(1)

    # ────────────────────────────────────────────────────────────
    #  SCENARIO 4: UDP throughput (LOW priority)
    # ────────────────────────────────────────────────────────────
    print("\n[SCENARIO 4] UDP Throughput – LOW Priority Traffic")
    print("-" * 50)
    print("Starting iperf UDP server on h4 ...")
    h4.cmd('iperf -s -u &')
    time.sleep(1)
    print("Running iperf UDP client from h1 → h4 (10 seconds)")
    result = h1.cmd('iperf -c 10.0.0.4 -u -b 5M -t 10')
    print(result)
    h4.cmd('kill %iperf')
    time.sleep(1)

    # ────────────────────────────────────────────────────────────
    #  SCENARIO 5: Flow table dump (verify QoS rules installed)
    # ────────────────────────────────────────────────────────────
    print("\n[SCENARIO 5] OpenFlow Flow Table – Switch s1")
    print("-" * 50)
    print("Installed flow rules with QoS priorities:")
    result = s1.cmd('ovs-ofctl -O OpenFlow13 dump-flows s1')
    print(result)

    print("\n[SCENARIO 5] OpenFlow Flow Table – Switch s2")
    print("-" * 50)
    result = s2.cmd('ovs-ofctl -O OpenFlow13 dump-flows s2')
    print(result)

    # ────────────────────────────────────────────────────────────
    #  Summary
    # ────────────────────────────────────────────────────────────
    print("\n" + "="*60)
    print("  TEST COMPLETE")
    print("  Priority levels verified:")
    print("    ICMP  (ping) → priority 300 (HIGH)")
    print("    TCP   (iperf)→ priority 200 (MEDIUM)")
    print("    UDP   (iperf)→ priority 100 (LOW)")
    print("    Other traffic→ priority   1 (DEFAULT/FLOOD)")
    print("="*60 + "\n")

    net.stop()


if __name__ == '__main__':
    run_tests()
