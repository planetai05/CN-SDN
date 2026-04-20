"""
Simple QoS Priority Controller
================================
Student: ANISH A KUNDER | Roll No: 16
Course: UE24CS252B - Computer Networks
Project: Simple QoS Priority Controller

Description:
    This Ryu SDN controller implements Quality of Service (QoS) by assigning
    different priority levels to different types of network traffic:

    HIGH PRIORITY   (priority=300) → ICMP (ping) traffic
    MEDIUM PRIORITY (priority=200) → TCP traffic (e.g., HTTP, iperf)
    LOW PRIORITY    (priority=100) → UDP traffic
    DEFAULT         (priority=1)   → All other traffic (flooding)

    The controller intercepts packet_in events, inspects the traffic type,
    and installs appropriate OpenFlow flow rules with different priorities.
"""

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib.packet import packet, ethernet, ipv4, icmp, tcp, udp, ether_types
import logging

# ─────────────────────────────────────────────
#  Priority levels (higher number = higher priority)
# ─────────────────────────────────────────────
PRIORITY_HIGH   = 300   # ICMP  → urgent / control traffic
PRIORITY_MEDIUM = 200   # TCP   → reliable data (HTTP, iperf)
PRIORITY_LOW    = 100   # UDP   → best-effort (video, DNS)
PRIORITY_DEFAULT = 1    # Everything else → flood


class SimpleQoSController(app_manager.RyuApp):
    """
    Ryu application that provides QoS-based flow rule installation.
    Each switch that connects sends its features, and we install a
    table-miss rule. As real packets arrive we classify them and push
    specific high/medium/low priority flow entries.
    """

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(SimpleQoSController, self).__init__(*args, **kwargs)
        # mac_to_port: { datapath_id: { mac_addr: port_number } }
        self.mac_to_port = {}
        self.logger.setLevel(logging.INFO)
        self.logger.info("=" * 55)
        self.logger.info("  Simple QoS Priority Controller started")
        self.logger.info("  ICMP=HIGH(300)  TCP=MEDIUM(200)  UDP=LOW(100)")
        self.logger.info("=" * 55)

    # ──────────────────────────────────────────
    #  STEP 1: Switch handshake – install table-miss rule
    # ──────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        """
        Called when a switch connects.
        Installs a low-priority 'table-miss' flow entry that sends
        all unmatched packets to the controller (packet_in).
        """
        datapath = ev.msg.datapath
        ofproto  = datapath.ofproto
        parser   = datapath.ofproto_parser

        # Match everything (empty match = wildcard all fields)
        match = parser.OFPMatch()

        # Action: send to controller
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]

        # Install as lowest-priority rule (priority=0)
        self._add_flow(datapath, priority=0, match=match, actions=actions)
        self.logger.info("[Switch %s] Connected – table-miss rule installed",
                         datapath.id)

    # ──────────────────────────────────────────
    #  STEP 2: Handle each incoming packet
    # ──────────────────────────────────────────
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
        Called for every packet the switch cannot match.
        We:
          1. Learn the source MAC → port mapping.
          2. Determine the output port (known MAC or flood).
          3. Classify traffic type → assign QoS priority.
          4. Install a flow rule so future packets bypass the controller.
          5. Forward the current packet.
        """
        msg      = ev.msg
        datapath = msg.datapath
        ofproto  = datapath.ofproto
        parser   = datapath.ofproto_parser
        in_port  = msg.match['in_port']

        # Parse the raw packet
        pkt     = packet.Packet(msg.data)
        eth_pkt = pkt.get_protocol(ethernet.ethernet)

        if eth_pkt is None:
            return  # Not an Ethernet frame – ignore

        dst_mac = eth_pkt.dst
        src_mac = eth_pkt.src
        dpid    = datapath.id

        # Initialise MAC table for this switch if needed
        self.mac_to_port.setdefault(dpid, {})

        # ── MAC learning ──────────────────────────────
        self.mac_to_port[dpid][src_mac] = in_port

        # ── Determine output port ─────────────────────
        if dst_mac in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst_mac]
        else:
            out_port = ofproto.OFPP_FLOOD   # Destination unknown → flood

        actions = [parser.OFPActionOutput(out_port)]

        # ── QoS Classification ────────────────────────
        ip_pkt   = pkt.get_protocol(ipv4.ipv4)
        tcp_pkt  = pkt.get_protocol(tcp.tcp)
        udp_pkt  = pkt.get_protocol(udp.udp)
        icmp_pkt = pkt.get_protocol(icmp.icmp)

        if ip_pkt and out_port != ofproto.OFPP_FLOOD:
            src_ip = ip_pkt.src
            dst_ip = ip_pkt.dst

            if icmp_pkt:
                # ── HIGH PRIORITY: ICMP ──────────────
                match = parser.OFPMatch(
                    in_port=in_port,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=1,          # ICMP protocol number
                    ipv4_src=src_ip,
                    ipv4_dst=dst_ip
                )
                self._add_flow(datapath, PRIORITY_HIGH, match, actions)
                self.logger.info(
                    "[QoS] HIGH   priority=%d | ICMP | %s → %s | port %s",
                    PRIORITY_HIGH, src_ip, dst_ip, out_port)

            elif tcp_pkt:
                # ── MEDIUM PRIORITY: TCP ─────────────
                match = parser.OFPMatch(
                    in_port=in_port,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=6,          # TCP protocol number
                    ipv4_src=src_ip,
                    ipv4_dst=dst_ip
                )
                self._add_flow(datapath, PRIORITY_MEDIUM, match, actions)
                self.logger.info(
                    "[QoS] MEDIUM priority=%d | TCP  | %s → %s | port %s",
                    PRIORITY_MEDIUM, src_ip, dst_ip, out_port)

            elif udp_pkt:
                # ── LOW PRIORITY: UDP ────────────────
                match = parser.OFPMatch(
                    in_port=in_port,
                    eth_type=ether_types.ETH_TYPE_IP,
                    ip_proto=17,         # UDP protocol number
                    ipv4_src=src_ip,
                    ipv4_dst=dst_ip
                )
                self._add_flow(datapath, PRIORITY_LOW, match, actions)
                self.logger.info(
                    "[QoS] LOW    priority=%d | UDP  | %s → %s | port %s",
                    PRIORITY_LOW, src_ip, dst_ip, out_port)

        # ── Send the current packet out ───────────────
        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data

        out = parser.OFPPacketOut(
            datapath=datapath,
            buffer_id=msg.buffer_id,
            in_port=in_port,
            actions=actions,
            data=data
        )
        datapath.send_msg(out)

    # ──────────────────────────────────────────
    #  Helper: Install a flow rule
    # ──────────────────────────────────────────
    def _add_flow(self, datapath, priority, match, actions,
                  idle_timeout=0, hard_timeout=0):
        """
        Utility to push an OpenFlow flow-mod message to a switch.

        Args:
            datapath     : the switch object
            priority     : flow entry priority (higher wins)
            match        : OFPMatch – which packets this rule applies to
            actions      : list of OFPAction – what to do with matched packets
            idle_timeout : remove rule after N seconds of inactivity (0=never)
            hard_timeout : remove rule after N seconds regardless (0=never)
        """
        ofproto = datapath.ofproto
        parser  = datapath.ofproto_parser

        # Wrap actions in an ApplyActions instruction
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(
            datapath=datapath,
            priority=priority,
            match=match,
            instructions=inst,
            idle_timeout=idle_timeout,
            hard_timeout=hard_timeout
        )
        datapath.send_msg(mod)
