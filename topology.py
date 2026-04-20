"""
QoS Topology – Simple Linear Network
======================================
Student: ANISH A KUNDER | Roll No: 16

Topology:
                     [ Ryu Controller ]
                            |
    h1 ── s1 ── s2 ── s3 ── h4
           |         |
           h2        h3

    Hosts : h1 (10.0.0.1), h2 (10.0.0.2), h3 (10.0.0.3), h4 (10.0.0.4)
    Switches: s1, s2, s3 (OpenFlow 1.3)

Usage:
    # Terminal 1 – start controller
    ryu-manager qos_controller.py

    # Terminal 2 – start topology
    sudo python3 topology.py
"""

from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink


def build_qos_topology():
    """
    Build and run the custom QoS topology.
    Uses TCLink so we can add bandwidth/delay constraints for testing.
    """
    setLogLevel('info')

    # ── Create network with Remote Ryu controller ─────────────────────────
    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,           # Allows bw/delay parameters per link
        autoSetMacs=True       # Assigns sequential MACs automatically
    )

    info('\n*** Adding Ryu Controller\n')
    c0 = net.addController(
        'c0',
        controller=RemoteController,
        ip='127.0.0.1',
        port=6653              # Default Ryu OpenFlow port
    )

    # ── Add Switches ──────────────────────────────────────────────────────
    info('*** Adding Switches\n')
    s1 = net.addSwitch('s1', cls=OVSSwitch, protocols='OpenFlow13')
    s2 = net.addSwitch('s2', cls=OVSSwitch, protocols='OpenFlow13')
    s3 = net.addSwitch('s3', cls=OVSSwitch, protocols='OpenFlow13')

    # ── Add Hosts ─────────────────────────────────────────────────────────
    info('*** Adding Hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1/24')   # Source host 1
    h2 = net.addHost('h2', ip='10.0.0.2/24')   # Source host 2
    h3 = net.addHost('h3', ip='10.0.0.3/24')   # Destination host 1
    h4 = net.addHost('h4', ip='10.0.0.4/24')   # Destination host 2

    # ── Add Links (with bandwidth limits to see QoS effect) ───────────────
    info('*** Adding Links\n')
    # Host-to-switch links (10 Mbps)
    net.addLink(h1, s1, bw=10)
    net.addLink(h2, s1, bw=10)
    net.addLink(h3, s3, bw=10)
    net.addLink(h4, s3, bw=10)

    # Switch-to-switch backbone links (5 Mbps – bottleneck to show QoS)
    net.addLink(s1, s2, bw=5)
    net.addLink(s2, s3, bw=5)

    # ── Start Network ─────────────────────────────────────────────────────
    info('*** Starting Network\n')
    net.build()
    c0.start()
    s1.start([c0])
    s2.start([c0])
    s3.start([c0])

    # Give OVS a moment to connect to Ryu
    import time
    time.sleep(2)

    # ── Print topology summary ────────────────────────────────────────────
    info('\n' + '='*55 + '\n')
    info('  QoS Topology Ready!\n')
    info('  Hosts: h1=10.0.0.1  h2=10.0.0.2\n')
    info('         h3=10.0.0.3  h4=10.0.0.4\n')
    info('='*55 + '\n')
    info('  Quick test commands:\n')
    info('  pingall                    → test all connectivity\n')
    info('  h1 ping -c 5 h4            → ICMP (HIGH priority)\n')
    info('  h1 iperf -s &; h2 iperf -c 10.0.0.1   → TCP throughput\n')
    info('  h1 iperf -s -u &; h2 iperf -c 10.0.0.1 -u  → UDP\n')
    info('='*55 + '\n')

    # ── Drop into Mininet CLI ─────────────────────────────────────────────
    CLI(net)

    # ── Cleanup ───────────────────────────────────────────────────────────
    info('*** Stopping Network\n')
    net.stop()


if __name__ == '__main__':
    build_qos_topology()
