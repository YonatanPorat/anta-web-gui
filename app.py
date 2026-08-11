import streamlit as st
import subprocess
import json
import pandas as pd
import yaml
import os
import re

# Configure the web page layout
st.set_page_config(page_title="ANTA Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- Persistent Settings Helper ---
SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_settings(data_dict):
    current = load_settings()
    current.update(data_dict)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(current, f, indent=4)

saved_settings = load_settings()

# Complete list of test keys
ALL_TEST_KEYS = [
    # AAA
    "chk_aaa_authen", "chk_aaa_authz", "chk_aaa_acct_default", "chk_aaa_acct_console",
    "chk_aaa_tacacs_src", "chk_aaa_tacacs_servers", "chk_aaa_tacacs_groups",
    "chk_aaa_radius_src", "chk_aaa_radius_servers",
    # AVT & BFD
    "chk_avt_path", "chk_avt_role", "chk_avt_specific_path",
    "chk_bfd_health", "chk_bfd_intervals", "chk_bfd_protocols", "chk_bfd_specific",
    # Configuration
    "chk_cfg_rules", "chk_cfg_diff", "chk_cfg_lines", "chk_cfg_ztp", "chk_cfg_banner_login", "chk_cfg_banner_motd",
    # Connectivity & CVX
    "chk_conn_lldp", "chk_conn_ping",
    "chk_cvx_active", "chk_cvx_cluster", "chk_cvx_mgmt", "chk_cvx_client_mounts", "chk_cvx_server_mounts",
    # EVPN & Field Notices
    "chk_evpn_type5", "chk_fn_fn44", "chk_fn_fn72",
    # Flow Tracking & GreenT
    "chk_flow_tracking", "chk_greent_policy", "chk_greent_counters",
    # Hardware
    "chk_hw_linecards", "chk_hw_drops", "chk_hw_chassis", "chk_hw_cooling_fans", "chk_hw_power",
    "chk_hw_sys_cooling", "chk_hw_capacity", "chk_hw_inventory", "chk_hw_module", "chk_hw_pcie",
    "chk_hw_supervisor", "chk_hw_temp", "chk_hw_trans", "chk_hw_trans_temp", "chk_hw_trans_presence",
    "chk_hw_trans_optics", "chk_hw_pse",
    # Interfaces
    "chk_int_proxy_arp", "chk_int_ill_lacp", "chk_int_disc", "chk_int_err_dis", "chk_int_err",
    "chk_int_ipv4", "chk_int_util", "chk_int_ber", "chk_int_counter_det", "chk_int_ecn",
    "chk_int_egress_drop", "chk_int_optics_rx", "chk_int_optics_temp", "chk_int_pfc", "chk_int_speed",
    "chk_int_status", "chk_int_trident", "chk_int_voq", "chk_int_vrrp_mac", "chk_int_l2mtu",
    "chk_int_l3mtu", "chk_int_lacp_status", "chk_int_loopback", "chk_int_port_channel", "chk_int_svi", "chk_int_storm",
    # LANZ & Logging
    "chk_lanz", "chk_log_accounting", "chk_log_entries", "chk_log_errors", "chk_log_hostname",
    "chk_log_hosts", "chk_log_generation", "chk_log_persistent", "chk_log_source_intf", "chk_log_timestamp", "chk_log_syslog",
    # MLAG & Multicast
    "chk_mlag_config_sanity", "chk_mlag_dual_primary", "chk_mlag_interfaces", "chk_mlag_priority", "chk_mlag_reload_delay", "chk_mlag_status",
    "chk_igmp_snooping_global", "chk_igmp_snooping_vlans",
    # Path Selection, Profiles, PTP
    "chk_path_sel_health", "chk_path_sel_specific", "chk_tcam_profile", "chk_uft_mode",
    "chk_ptp_gm", "chk_ptp_lock", "chk_ptp_mode", "chk_ptp_offset", "chk_ptp_port_mode",
    # Routing BGP
    "chk_bgp_adv_communities", "chk_bgp_exchanged_routes", "chk_bgp_nlri", "chk_bgp_asn_cap", "chk_bgp_peer_count",
    "chk_bgp_drop_stats", "chk_bgp_peer_group", "chk_bgp_md5", "chk_bgp_mp_caps", "chk_bgp_route_limit",
    "chk_bgp_refresh_cap", "chk_bgp_peer_session", "chk_bgp_peer_session_ribd", "chk_bgp_ttl", "chk_bgp_update_errors",
    "chk_bgp_health", "chk_bgp_health_ribd", "chk_bgp_redistribution", "chk_bgp_ecmp", "chk_bgp_route_paths",
    "chk_bgp_specific_peers", "chk_bgp_timers", "chk_bgp_route_maps", "chk_bgp_evpn_type2",
    # Routing Generic, ISIS, OSPF
    "chk_rt_nexthops", "chk_rt_presence_prefix", "chk_rt_presence_vrf", "chk_rt_route_type", "chk_rt_model",
    "chk_rt_status", "chk_rt_size",
    "chk_isis_graceful", "chk_isis_intf_mode", "chk_isis_neighbor_cnt", "chk_isis_neighbor_state", "chk_isis_sr_adj", "chk_isis_sr_dataplane", "chk_isis_sr_tunnels",
    "chk_ospf_max_lsa", "chk_ospf_neighbor_cnt", "chk_ospf_neighbor_state", "chk_ospf_specific_neighbors",
    # Security, Services, Software, STUN, System
    "chk_sec_api_http", "chk_sec_api_https_ssl", "chk_sec_api_v4_acl", "chk_sec_api_v6_acl", "chk_sec_ssl_cert",
    "chk_sec_banner_login", "chk_sec_banner_motd", "chk_sec_entropy", "chk_sec_ipsec_health", "chk_sec_v4_acl",
    "chk_sec_fips", "chk_sec_ssh_v4_acl", "chk_sec_ssh_v6_acl", "chk_ssh_status", "chk_sec_ipsec_specific", "chk_sec_telnet",
    "chk_svc_dns_lookup", "chk_svc_dns_servers", "chk_svc_errdisable_rec", "chk_hostname",
    "chk_snmp_contact", "chk_snmp_errors", "chk_snmp_group", "chk_snmp_logging", "chk_snmp_v4_acl", "chk_snmp_v6_acl",
    "chk_snmp_location", "chk_snmp_notification", "chk_snmp_pdu", "chk_snmp_source", "chk_snmp_status", "chk_snmp_user",
    "chk_sw_extensions", "chk_sw_version", "chk_sw_terminattr",
    "chk_stp_blocked", "chk_stp_counters", "chk_stp_disabled_vlans", "chk_stp_forwarding", "chk_stp_mode", "chk_stp_root_priority", "chk_stp_tc",
    "chk_stun_client", "chk_stun_client_trans", "chk_stun_status",
    "chk_sys_agent_logs", "chk_sys_cpu", "chk_sys_coredump", "chk_sys_file_presence", "chk_sys_fs_util", "chk_sys_flash_util",
    "chk_sys_maintenance", "chk_sys_mem", "chk_sys_ntp", "chk_sys_ntp_assoc", "chk_sys_reload", "chk_sys_uptime",
    # VLAN & VXLAN
    "chk_vlan_dynamic", "chk_vlan_internal", "chk_vlan_status",
    "chk_vxlan_conn", "chk_vxlan_intf", "chk_vxlan_vvtep", "chk_vxlan_sanity", "chk_vxlan_vni_binding", "chk_vxlan_vtep"
]

default_config_rules = [
    {"Section": "", "Match": "aaa authorization exec default local", "Mode": "exact", "Absent": False, "Description": "AAA authorization"},
    {"Section": "management api http-commands", "Match": "no shutdown", "Mode": "exact", "Absent": False, "Description": "eAPI enabled"}
]

DEFAULT_PROFILES = {
    "🟢 Basic NRFU (Quick Check)": {
        "keys": ["chk_hw_trans", "chk_hw_power", "chk_hw_temp", "chk_sys_uptime", "chk_sys_ntp", "chk_int_err", "chk_int_status", "chk_cfg_diff"],
        "cfg_rules": []
    },
    "🔍 Deep NRFU (Full Audit)": {
        "keys": ALL_TEST_KEYS,
        "cfg_rules": default_config_rules
    }
}

active_profiles = saved_settings.get("profiles", DEFAULT_PROFILES)

saved_test_keys = saved_settings.get("selected_test_keys", None)
for k in ALL_TEST_KEYS:
    if k not in st.session_state:
        if saved_test_keys is not None:
            st.session_state[k] = (k in saved_test_keys)
        else:
            st.session_state[k] = (k in DEFAULT_PROFILES["🟢 Basic NRFU (Quick Check)"]["keys"])

# ==========================================
# STREAMLIT SIDEBAR: GLOBAL CONTROLS
# ==========================================
with st.sidebar:
    st.title("⚙️ Profile & Settings")
    st.caption("Manage active presets & execution tags")
    
    st.markdown("---")
    st.markdown("##### 🎯 Active Profile Presets")
    
    selected_prof_name = st.selectbox("Select Active Profile", options=list(active_profiles.keys()), key="sb_selected_prof")

    col_prof1, col_prof2 = st.columns(2)
    with col_prof1:
        if st.button("📂 Load", use_container_width=True, type="primary"):
            p_data = active_profiles.get(selected_prof_name, {})
            p_keys = set(p_data.get("keys", []))
            for k in ALL_TEST_KEYS:
                st.session_state[k] = (k in p_keys)
            st.session_state.cfg_rules_data = p_data.get("cfg_rules", default_config_rules)
            save_settings({"selected_test_keys": list(p_keys)})
            st.success(f"Loaded '{selected_prof_name}'!")
            st.rerun()

    with col_prof2:
        if st.button("💾 Save", use_container_width=True):
            current_keys = [k for k in ALL_TEST_KEYS if st.session_state.get(k, False)]
            active_profiles[selected_prof_name] = {
                "keys": current_keys,
                "cfg_rules": st.session_state.get("cfg_rules_data", default_config_rules)
            }
            save_settings({"profiles": active_profiles, "selected_test_keys": current_keys})
            st.success("Saved!")

    st.markdown("---")
    st.markdown("##### 🏷️ Filter Tags")
    st.text_input("Filter Tags (comma-separated)", value=saved_settings.get("catalog_tags", ""), placeholder="e.g. leaf, demo", key="input_catalog_tags")

    st.markdown("---")
    def toggle_select_all():
        current_all_selected = all(st.session_state.get(k, False) for k in ALL_TEST_KEYS)
        new_state = not current_all_selected
        for k in ALL_TEST_KEYS:
            st.session_state[k] = new_state

    is_all_selected = all(st.session_state.get(k, False) for k in ALL_TEST_KEYS)
    select_label = "❌ Deselect All Tests" if is_all_selected else "✅ Select All Tests"
    st.button(select_label, on_click=toggle_select_all, use_container_width=True)

# ==========================================
# MAIN APP HEADER & TABS
# ==========================================
st.title("🚀 Arista ANTA Web GUI")
st.markdown("Manage devices, configure tests, and execute network validations.")
st.divider()

tab_dashboard, tab_creds, tab_inventory, tab_catalog, tab_cli = st.tabs([
    "🚀 Dashboard", "🔑 Credentials", "🌐 Manage Inventory", "📋 Manage Tests", "🛠️ Raw CLI"
])

# ==========================================
# TAB 1: CREDENTIALS
# ==========================================
with tab_creds:
    st.subheader("Device Credentials")
    if "anta_user" not in st.session_state: st.session_state.anta_user = saved_settings.get("anta_user", "arista")
    if "anta_pass" not in st.session_state: st.session_state.anta_pass = saved_settings.get("anta_pass", "arista")
        
    st.session_state.anta_user = st.text_input("Username", value=st.session_state.anta_user, key="input_anta_user")
    st.session_state.anta_pass = st.text_input("Password", value=st.session_state.anta_pass, type="password", key="input_anta_pass")
    
    if st.button("💾 Save as Default Credentials", type="primary"):
        save_settings({"anta_user": st.session_state.anta_user, "anta_pass": st.session_state.anta_pass})
        st.success("✅ Credentials saved!")

# ==========================================
# TAB 2: INVENTORY (Fixed Keys Added)
# ==========================================
with tab_inventory:
    st.subheader("Inventory Manager")
    try:
        with open("inventory.yml", "r") as f: inv_data = yaml.safe_load(f) or {}
    except FileNotFoundError: inv_data = {}

    anta_inv = inv_data.get("anta_inventory", {})
    df_hosts = pd.DataFrame([dict(h) for h in anta_inv.get("hosts", [])])
    df_networks = pd.DataFrame([dict(n) for n in anta_inv.get("networks", [])])
    df_ranges = pd.DataFrame([dict(r) for r in anta_inv.get("ranges", [])])

    sub_hosts, sub_networks, sub_ranges = st.tabs(["🖥️ Specific Hosts", "🌐 Networks (CIDR)", "🔢 IP Ranges"])
    with sub_hosts: edited_hosts = st.data_editor(df_hosts, num_rows="dynamic", use_container_width=True, key="editor_hosts")
    with sub_networks: edited_networks = st.data_editor(df_networks, num_rows="dynamic", use_container_width=True, key="editor_networks")
    with sub_ranges: edited_ranges = st.data_editor(df_ranges, num_rows="dynamic", use_container_width=True, key="editor_ranges")

# ==========================================
# TAB 3: CATALOG BUILDER (COMPLETE SUITE)
# ==========================================
with tab_catalog:
    st.subheader("📋 Test Catalog Builder")
    nav_side_col, main_content_col = st.columns([1.1, 3.5], gap="large")

    with nav_side_col:
        st.markdown("#### 📂 Categories")
        categories_map = {
            "🔐 AAA": "AAA", "🔀 AVT & BFD": "AVT_BFD", "⚙️ Configuration": "Configuration",
            "🌐 Connectivity": "Connectivity", "🖥️ CVX": "CVX", "☁️ EVPN & VXLAN": "EVPN_VXLAN",
            "⚠️ Field Notices": "FieldNotices", "🌊 Flow Tracking & GreenT": "Flow_GreenT", "🔌 Hardware": "Hardware",
            "🌐 Interfaces": "Interfaces", "📊 LANZ & Logging": "Logging", "🤝 MLAG & Multicast": "MLAG_Multicast",
            "🛤️ Path Selection & Profiles": "Path_Profiles", "⏱️ PTP": "PTP", "🗺️ Routing BGP": "BGP",
            "🗺️ Routing Generic & OSPF & ISIS": "Routing_Generic", "🔒 Security": "Security", "🛠️ Services": "Services",
            "🖧 SNMP": "SNMP", "💿 Software": "Software", "🛡️ STP": "STP", "📞 STUN": "STUN", "💻 System": "System", "🏢 VLAN": "VLAN", "🧩 Custom YAML": "Custom"
        }
        selected_cat_label = st.radio("Select Category", options=list(categories_map.keys()), label_visibility="collapsed")
        selected_cat = categories_map[selected_cat_label]

    with main_content_col:
        st.markdown(f"### {selected_cat_label}")
        def bind_cb(label, key): return st.checkbox(label, value=st.session_state.get(key, False), key=key)

        if selected_cat == "AAA":
            bind_cb("Verify Authentication Methods (`VerifyAuthenMethods`)", "chk_aaa_authen")
            st.text_input("Methods (e.g., local, group tacacs+)", value=st.session_state.get("param_aaa_authen_methods", "local"), key="param_aaa_authen_methods")
            bind_cb("Verify Authorization Methods (`VerifyAuthzMethods`)", "chk_aaa_authz")
            st.text_input("Methods (e.g., group tacacs+)", value=st.session_state.get("param_aaa_authz_methods", "group tacacs+"), key="param_aaa_authz_methods")
            bind_cb("Verify Accounting Default (`VerifyAcctDefaultMethods`)", "chk_aaa_acct_default")
            bind_cb("Verify Accounting Console (`VerifyAcctConsoleMethods`)", "chk_aaa_acct_console")
            bind_cb("Verify TACACS Source Intf (`VerifyTacacsSourceIntf`)", "chk_aaa_tacacs_src")
            st.text_input("TACACS Source Intf", value=st.session_state.get("param_aaa_tacacs_intf", "Management1"), key="param_aaa_tacacs_intf")
            bind_cb("Verify TACACS Servers (`VerifyTacacsServers`)", "chk_aaa_tacacs_servers")
            st.text_input("TACACS Server IPs", value=st.session_state.get("param_aaa_tacacs_ips", "10.1.1.1"), key="param_aaa_tacacs_ips")
            bind_cb("Verify TACACS Server Groups (`VerifyTacacsServerGroups`)", "chk_aaa_tacacs_groups")
            bind_cb("Verify RADIUS Source Intf (`VerifyRadiusSourceIntf`)", "chk_aaa_radius_src")
            bind_cb("Verify RADIUS Servers (`VerifyRadiusServers`)", "chk_aaa_radius_servers")

        elif selected_cat == "AVT_BFD":
            bind_cb("Verify AVT Path Health (`VerifyAVTPathHealth`)", "chk_avt_path")
            bind_cb("Verify AVT Role (`VerifyAVTRole`)", "chk_avt_role")
            bind_cb("Verify AVT Specific Path (`VerifyAVTSpecificPath`)", "chk_avt_specific_path")
            st.divider()
            bind_cb("Verify BFD Peers Health (`VerifyBFDPeersHealth`)", "chk_bfd_health")
            bind_cb("Verify BFD Peers Intervals (`VerifyBFDPeersIntervals`)", "chk_bfd_intervals")
            bind_cb("Verify BFD Reg Protocols (`VerifyBFDPeersRegProtocols`)", "chk_bfd_protocols")
            bind_cb("Verify BFD Specific Peers (`VerifyBFDSpecificPeers`)", "chk_bfd_specific")

        elif selected_cat == "Configuration":
            st.markdown("##### Dynamic Running Config Rules (`VerifyRunningConfig`)")
            bind_cb("Verify Running Config Rules (`VerifyRunningConfig`)", "chk_cfg_rules")
            if st.session_state.get("chk_cfg_rules"):
                if "cfg_rules_data" not in st.session_state:
                    st.session_state.cfg_rules_data = saved_settings.get("cfg_rules_data", default_config_rules)
                edited_cfg_rules = st.data_editor(pd.DataFrame(st.session_state.cfg_rules_data), num_rows="dynamic", use_container_width=True, key="editor_cfg_rules")
                st.session_state.cfg_rules_data = edited_cfg_rules.to_dict("records")
            bind_cb("Verify Running Config Diffs (`VerifyRunningConfigDiffs`)", "chk_cfg_diff")
            bind_cb("Verify Running Config Lines (`VerifyRunningConfigLines`)", "chk_cfg_lines")
            bind_cb("Verify Zero Touch (`VerifyZeroTouch`)", "chk_cfg_ztp")
            bind_cb("Verify Login Banner (`VerifyBannerLogin`)", "chk_cfg_banner_login")
            bind_cb("Verify MOTD Banner (`VerifyBannerMotd`)", "chk_cfg_banner_motd")

        elif selected_cat == "Connectivity":
            bind_cb("Verify LLDP Neighbors (`VerifyLLDPNeighbors`)", "chk_conn_lldp")
            st.text_input("LLDP Local Port", value=st.session_state.get("param_conn_lldp_port", "Ethernet1"), key="param_conn_lldp_port")
            bind_cb("Verify Reachability (`VerifyReachability`)", "chk_conn_ping")
            st.text_input("Ping Destination IP", value=st.session_state.get("param_conn_dest", "8.8.8.8"), key="param_conn_dest")

        elif selected_cat == "CVX":
            bind_cb("Verify Active CVX Connections (`VerifyActiveCVXConnections`)", "chk_cvx_active")
            bind_cb("Verify CVX Cluster Status (`VerifyCVXClusterStatus`)", "chk_cvx_cluster")
            bind_cb("Verify Management CVX (`VerifyManagementCVX`)", "chk_cvx_mgmt")
            bind_cb("Verify MCS Client Mounts (`VerifyMcsClientMounts`)", "chk_cvx_client_mounts")
            bind_cb("Verify MCS Server Mounts (`VerifyMcsServerMounts`)", "chk_cvx_server_mounts")

        elif selected_cat == "EVPN_VXLAN":
            bind_cb("Verify EVPN Type 5 Routes (`VerifyEVPNType5Routes`)", "chk_evpn_type5")
            bind_cb("Verify VXLAN Conn Settings (`VerifyVxlan1ConnSettings`)", "chk_vxlan_conn")
            bind_cb("Verify VXLAN Interface (`VerifyVxlan1Interface`)", "chk_vxlan_intf")
            bind_cb("Verify VXLAN VVTEP IPs (`VerifyVxlan1VVTEPIPAddresses`)", "chk_vxlan_vvtep")
            bind_cb("Verify VXLAN Config Sanity (`VerifyVxlanConfigSanity`)", "chk_vxlan_sanity")
            bind_cb("Verify VXLAN VNI Binding (`VerifyVxlanVniBinding`)", "chk_vxlan_vni_binding")
            bind_cb("Verify VXLAN VTEP (`VerifyVxlanVtep`)", "chk_vxlan_vtep")

        elif selected_cat == "FieldNotices":
            bind_cb("Verify Field Notice 44 Resolution (`VerifyFieldNotice44Resolution`)", "chk_fn_fn44")
            bind_cb("Verify Field Notice 72 Resolution (`VerifyFieldNotice72Resolution`)", "chk_fn_fn72")

        elif selected_cat == "Flow_GreenT":
            bind_cb("Verify Hardware Flow Tracker (`VerifyHardwareFlowTrackerStatus`)", "chk_flow_tracking")
            bind_cb("Verify GreenT Policy (`VerifyGreenT`)", "chk_greent_policy")
            bind_cb("Verify GreenT Counters (`VerifyGreenTCounters`)", "chk_greent_counters")

        elif selected_cat == "Hardware":
            bind_cb("Verify Linecards Absence (`VerifyAbsenceOfLinecards`)", "chk_hw_linecards")
            bind_cb("Verify Adverse Drops (`VerifyAdverseDrops`)", "chk_hw_drops")
            bind_cb("Verify Chassis Health (`VerifyChassisHealth`)", "chk_hw_chassis")
            bind_cb("Verify Environment Cooling (`VerifyEnvironmentCooling`)", "chk_hw_cooling_fans")
            bind_cb("Verify Environment Power (`VerifyEnvironmentPower`)", "chk_hw_power")
            bind_cb("Verify Environment System Cooling (`VerifyEnvironmentSystemCooling`)", "chk_hw_sys_cooling")
            bind_cb("Verify Hardware Capacity (`VerifyHardwareCapacityUtilization`)", "chk_hw_capacity")
            bind_cb("Verify Hardware Inventory (`VerifyInventory`)", "chk_hw_inventory")
            bind_cb("Verify Module Status (`VerifyModuleStatus`)", "chk_hw_module")
            bind_cb("Verify PCIe Errors (`VerifyPCIeErrors`)", "chk_hw_pcie")
            bind_cb("Verify Supervisor Redundancy (`VerifySupervisorRedundancy`)", "chk_hw_supervisor")
            bind_cb("Verify Temperature (`VerifyTemperature`)", "chk_hw_temp")
            bind_cb("Verify Transceivers Manufacturers (`VerifyTransceiversManufacturers`)", "chk_hw_trans")
            st.text_input("Expected Manufacturers", value=st.session_state.get("param_hw_mfg", "Arista Networks, ARISTA"), key="param_hw_mfg")
            bind_cb("Verify Transceivers Temperature (`VerifyTransceiversTemperature`)", "chk_hw_trans_temp")
            bind_cb("Verify Transceivers Presence (`VerifyTransceiversPresence`)", "chk_hw_trans_presence")
            bind_cb("Verify Transceivers Optics (`VerifyTransceiversOptics`)", "chk_hw_trans_optics")
            bind_cb("Verify PSE Status (`VerifyPseStatus`)", "chk_hw_pse")

        elif selected_cat == "Interfaces":
            bind_cb("Verify Proxy ARP (`VerifyIPProxyARP`)", "chk_int_proxy_arp")
            bind_cb("Verify Illegal LACP (`VerifyIllegalLACP`)", "chk_int_ill_lacp")
            bind_cb("Verify Interface Discards (`VerifyInterfaceDiscards`)", "chk_int_disc")
            bind_cb("Verify Interface ErrDisabled (`VerifyInterfaceErrDisabled`)", "chk_int_err_dis")
            bind_cb("Verify Interface Errors (`VerifyInterfaceErrors`)", "chk_int_err")
            bind_cb("Verify Interface IPv4 (`VerifyInterfaceIPv4`)", "chk_int_ipv4")
            bind_cb("Verify Interface Utilization (`VerifyInterfaceUtilization`)", "chk_int_util")
            bind_cb("Verify Interfaces BER (`VerifyInterfacesBER`)", "chk_int_ber")
            bind_cb("Verify Counter Details (`VerifyInterfacesCounterDetails`)", "chk_int_counter_det")
            bind_cb("Verify ECN Counters (`VerifyInterfacesECNCounters`)", "chk_int_ecn")
            bind_cb("Verify Egress Queue Drops (`VerifyInterfacesEgressQueueDrops`)", "chk_int_egress_drop")
            bind_cb("Verify Optics RX Power (`VerifyInterfacesOpticsReceivePower`)", "chk_int_optics_rx")
            bind_cb("Verify Optics Temp (`VerifyInterfacesOpticsTemperature`)", "chk_int_optics_temp")
            bind_cb("Verify PFC Counters (`VerifyInterfacesPFCCounters`)", "chk_int_pfc")
            bind_cb("Verify Interfaces Speed (`VerifyInterfacesSpeed`)", "chk_int_speed")
            bind_cb("Verify Interfaces Status (`VerifyInterfacesStatus`)", "chk_int_status")
            bind_cb("Verify Trident Counters (`VerifyInterfacesTridentCounters`)", "chk_int_trident")
            bind_cb("Verify VoQ Drops (`VerifyInterfacesVoqAndEgressQueueDrops`)", "chk_int_voq")
            bind_cb("Verify Virtual Router MAC (`VerifyIpVirtualRouterMac`)", "chk_int_vrrp_mac")
            bind_cb("Verify L2 MTU (`VerifyL2MTU`)", "chk_int_l2mtu")
            bind_cb("Verify L3 MTU (`VerifyL3MTU`)", "chk_int_l3mtu")
            bind_cb("Verify LACP Status (`VerifyLACPInterfacesStatus`)", "chk_int_lacp_status")
            bind_cb("Verify Loopback Count (`VerifyLoopbackCount`)", "chk_int_loopback")
            bind_cb("Verify Port Channels (`VerifyPortChannels`)", "chk_int_port_channel")
            bind_cb("Verify SVI (`VerifySVI`)", "chk_int_svi")
            bind_cb("Verify Storm Control Drops (`VerifyStormControlDrops`)", "chk_int_storm")

        elif selected_cat == "Logging":
            bind_cb("Verify LANZ Status (`VerifyLANZ`)", "chk_lanz")
            st.divider()
            bind_cb("Verify Logging Accounting (`VerifyLoggingAccounting`)", "chk_log_accounting")
            bind_cb("Verify Logging Entries (`VerifyLoggingEntries`)", "chk_log_entries")
            bind_cb("Verify Logging Errors (`VerifyLoggingErrors`)", "chk_log_errors")
            bind_cb("Verify Logging Hostname (`VerifyLoggingHostname`)", "chk_log_hostname")
            bind_cb("Verify Logging Hosts (`VerifyLoggingHosts`)", "chk_log_hosts")
            bind_cb("Verify Logs Generation (`VerifyLoggingLogsGeneration`)", "chk_log_generation")
            bind_cb("Verify Persistent Logging (`VerifyLoggingPersistent`)", "chk_log_persistent")
            bind_cb("Verify Source Interface (`VerifyLoggingSourceIntf`)", "chk_log_source_intf")
            bind_cb("Verify Logging Timestamp (`VerifyLoggingTimestamp`)", "chk_log_timestamp")
            bind_cb("Verify Syslog Logging (`VerifySyslogLogging`)", "chk_log_syslog")

        elif selected_cat == "MLAG_Multicast":
            bind_cb("Verify MLAG Config Sanity (`VerifyMlagConfigSanity`)", "chk_mlag_config_sanity")
            bind_cb("Verify MLAG Dual Primary (`VerifyMlagDualPrimary`)", "chk_mlag_dual_primary")
            bind_cb("Verify MLAG Interfaces (`VerifyMlagInterfaces`)", "chk_mlag_interfaces")
            bind_cb("Verify MLAG Primary Priority (`VerifyMlagPrimaryPriority`)", "chk_mlag_priority")
            bind_cb("Verify MLAG Reload Delay (`VerifyMlagReloadDelay`)", "chk_mlag_reload_delay")
            bind_cb("Verify MLAG Status (`VerifyMlagStatus`)", "chk_mlag_status")
            st.divider()
            bind_cb("Verify IGMP Snooping Global (`VerifyIGMPSnoopingGlobal`)", "chk_igmp_snooping_global")
            bind_cb("Verify IGMP Snooping VLANs (`VerifyIGMPSnoopingVlans`)", "chk_igmp_snooping_vlans")

        elif selected_cat == "Path_Profiles":
            bind_cb("Verify Paths Health (`VerifyPathsHealth`)", "chk_path_sel_health")
            bind_cb("Verify Specific Path (`VerifySpecificPath`)", "chk_path_sel_specific")
            st.divider()
            bind_cb("Verify TCAM Profile (`VerifyTcamProfile`)", "chk_tcam_profile")
            bind_cb("Verify UFT Mode (`VerifyUnifiedForwardingTableMode`)", "chk_uft_mode")

        elif selected_cat == "PTP":
            bind_cb("Verify PTP Grandmaster (`VerifyPtpGMStatus`)", "chk_ptp_gm")
            bind_cb("Verify PTP Lock Status (`VerifyPtpLockStatus`)", "chk_ptp_lock")
            bind_cb("Verify PTP Mode Status (`VerifyPtpModeStatus`)", "chk_ptp_mode")
            bind_cb("Verify PTP Offset (`VerifyPtpOffset`)", "chk_ptp_offset")
            bind_cb("Verify PTP Port Mode (`VerifyPtpPortModeStatus`)", "chk_ptp_port_mode")

        elif selected_cat == "BGP":
            bind_cb("Verify BGP Adv Communities (`VerifyBGPAdvCommunities`)", "chk_bgp_adv_communities")
            bind_cb("Verify BGP Exchanged Routes (`VerifyBGPExchangedRoutes`)", "chk_bgp_exchanged_routes")
            bind_cb("Verify BGP NLRI Acceptance (`VerifyBGPNlriAcceptance`)", "chk_bgp_nlri")
            bind_cb("Verify BGP Peer ASN Cap (`VerifyBGPPeerASNCap`)", "chk_bgp_asn_cap")
            bind_cb("Verify BGP Peer Count (`VerifyBGPPeerCount`)", "chk_bgp_peer_count")
            bind_cb("Verify BGP Peer Drop Stats (`VerifyBGPPeerDropStats`)", "chk_bgp_drop_stats")
            bind_cb("Verify BGP Peer Group (`VerifyBGPPeerGroup`)", "chk_bgp_peer_group")
            bind_cb("Verify BGP Peer MD5 Auth (`VerifyBGPPeerMD5Auth`)", "chk_bgp_md5")
            bind_cb("Verify BGP Peer MP Caps (`VerifyBGPPeerMPCaps`)", "chk_bgp_mp_caps")
            bind_cb("Verify BGP Peer Route Limit (`VerifyBGPPeerRouteLimit`)", "chk_bgp_peer_route_limit")
            bind_cb("Verify BGP Peer Refresh Cap (`VerifyBGPPeerRouteRefreshCap`)", "chk_bgp_refresh_cap")
            bind_cb("Verify BGP Peer Session (`VerifyBGPPeerSession`)", "chk_bgp_peer_session")
            bind_cb("Verify BGP Peer Session RIBD (`VerifyBGPPeerSessionRibd`)", "chk_bgp_peer_session_ribd")
            bind_cb("Verify BGP Peer TTL (`VerifyBGPPeerTtlMultiHops`)", "chk_bgp_ttl")
            bind_cb("Verify BGP Update Errors (`VerifyBGPPeerUpdateErrors`)", "chk_bgp_update_errors")
            bind_cb("Verify BGP Peers Health (`VerifyBGPPeersHealth`)", "chk_bgp_health")
            bind_cb("Verify BGP Peers Health RIBD (`VerifyBGPPeersHealthRibd`)", "chk_bgp_health_ribd")
            bind_cb("Verify BGP Redistribution (`VerifyBGPRedistribution`)", "chk_bgp_redistribution")
            bind_cb("Verify BGP Route ECMP (`VerifyBGPRouteECMP`)", "chk_bgp_ecmp")
            bind_cb("Verify BGP Route Paths (`VerifyBGPRoutePaths`)", "chk_bgp_route_paths")
            bind_cb("Verify BGP Specific Peers (`VerifyBGPSpecificPeers`)", "chk_bgp_specific_peers")
            bind_cb("Verify BGP Timers (`VerifyBGPTimers`)", "chk_bgp_timers")
            bind_cb("Verify BGP Route Maps (`VerifyBgpRouteMaps`)", "chk_bgp_route_maps")
            bind_cb("Verify EVPN Type 2 Route (`VerifyEVPNType2Route`)", "chk_bgp_evpn_type2")

        elif selected_cat == "Routing_Generic":
            bind_cb("Verify IPv4 Route Next Hops (`VerifyIPv4RouteNextHops`)", "chk_rt_nexthops")
            bind_cb("Verify IPv4 Route Presence Per Prefix (`VerifyIPv4RoutePresencePerPrefix`)", "chk_rt_presence_prefix")
            bind_cb("Verify IPv4 Route Presence Per VRF (`VerifyIPv4RoutePresencePerVRF`)", "chk_rt_presence_vrf")
            bind_cb("Verify IPv4 Route Type (`VerifyIPv4RouteType`)", "chk_rt_route_type")
            bind_cb("Verify Routing Protocol Model (`VerifyRoutingProtocolModel`)", "chk_rt_model")
            bind_cb("Verify Routing Status (`VerifyRoutingStatus`)", "chk_rt_status")
            bind_cb("Verify Routing Table Size (`VerifyRoutingTableSize`)", "chk_rt_size")
            st.divider()
            bind_cb("Verify ISIS Graceful Restart (`VerifyISISGracefulRestart`)", "chk_isis_graceful")
            bind_cb("Verify ISIS Interface Mode (`VerifyISISInterfaceMode`)", "chk_isis_intf_mode")
            bind_cb("Verify ISIS Neighbor Count (`VerifyISISNeighborCount`)", "chk_isis_neighbor_cnt")
            bind_cb("Verify ISIS Neighbor State (`VerifyISISNeighborState`)", "chk_isis_neighbor_state")
            bind_cb("Verify ISIS SR Adj (`VerifyISISSegmentRoutingAdjacencySegments`)", "chk_isis_sr_adj")
            bind_cb("Verify ISIS SR Dataplane (`VerifyISISSegmentRoutingDataplane`)", "chk_isis_sr_dataplane")
            bind_cb("Verify ISIS SR Tunnels (`VerifyISISSegmentRoutingTunnels`)", "chk_isis_sr_tunnels")
            st.divider()
            bind_cb("Verify OSPF Max LSA (`VerifyOSPFMaxLSA`)", "chk_ospf_max_lsa")
            bind_cb("Verify OSPF Neighbor Count (`VerifyOSPFNeighborCount`)", "chk_ospf_neighbor_cnt")
            bind_cb("Verify OSPF Neighbor State (`VerifyOSPFNeighborState`)", "chk_ospf_neighbor_state")
            bind_cb("Verify OSPF Specific Neighbors (`VerifyOSPFSpecificNeighbors`)", "chk_ospf_specific_neighbors")

        elif selected_cat == "Security":
            bind_cb("Verify API HTTP Status (`VerifyAPIHttpStatus`)", "chk_sec_api_http")
            bind_cb("Verify API HTTPS SSL (`VerifyAPIHttpsSSL`)", "chk_sec_api_https_ssl")
            bind_cb("Verify API IPv4 ACL (`VerifyAPIIPv4Acl`)", "chk_sec_api_v4_acl")
            bind_cb("Verify API IPv6 ACL (`VerifyAPIIPv6Acl`)", "chk_sec_api_v6_acl")
            bind_cb("Verify SSL Cert (`VerifyAPISSLCertificate`)", "chk_sec_ssl_cert")
            bind_cb("Verify Login Banner (`VerifyBannerLogin`)", "chk_sec_banner_login")
            bind_cb("Verify MOTD Banner (`VerifyBannerMotd`)", "chk_sec_banner_motd")
            bind_cb("Verify Hardware Entropy (`VerifyHardwareEntropy`)", "chk_sec_entropy")
            bind_cb("Verify IPSec Health (`VerifyIPSecConnHealth`)", "chk_sec_ipsec_health")
            bind_cb("Verify IPv4 ACL (`VerifyIPv4ACL`)", "chk_sec_v4_acl")
            bind_cb("Verify SSH FIPS (`VerifySSHFIPSRestrictions`)", "chk_sec_fips")
            bind_cb("Verify SSH IPv4 ACL (`VerifySSHIPv4Acl`)", "chk_sec_ssh_v4_acl")
            bind_cb("Verify SSH IPv6 ACL (`VerifySSHIPv6Acl`)", "chk_sec_ssh_v6_acl")
            bind_cb("Verify SSH Status (`VerifySSHStatus`)", "chk_ssh_status")
            bind_cb("Verify Specific IPSec (`VerifySpecificIPSecConn`)", "chk_sec_ipsec_specific")
            bind_cb("Verify Telnet Status (`VerifyTelnetStatus`)", "chk_sec_telnet")

        elif selected_cat == "Services":
            bind_cb("Verify DNS Lookup (`VerifyDNSLookup`)", "chk_svc_dns_lookup")
            bind_cb("Verify DNS Servers (`VerifyDNSServers`)", "chk_svc_dns_servers")
            bind_cb("Verify Errdisable Recovery (`VerifyErrdisableRecovery`)", "chk_svc_errdisable_rec")
            bind_cb("Verify Hostname (`VerifyHostname`)", "chk_hostname")

        elif selected_cat == "SNMP":
            bind_cb("Verify SNMP Contact (`VerifySnmpContact`)", "chk_snmp_contact")
            bind_cb("Verify SNMP Errors (`VerifySnmpErrorCounters`)", "chk_snmp_errors")
            bind_cb("Verify SNMP Group (`VerifySnmpGroup`)", "chk_snmp_group")
            bind_cb("Verify SNMP Logging (`VerifySnmpHostLogging`)", "chk_snmp_logging")
            bind_cb("Verify SNMP IPv4 ACL (`VerifySnmpIPv4Acl`)", "chk_snmp_v4_acl")
            bind_cb("Verify SNMP IPv6 ACL (`VerifySnmpIPv6Acl`)", "chk_snmp_v6_acl")
            bind_cb("Verify SNMP Location (`VerifySnmpLocation`)", "chk_snmp_location")
            bind_cb("Verify SNMP Notification (`VerifySnmpNotificationHost`)", "chk_snmp_notification")
            bind_cb("Verify SNMP PDU (`VerifySnmpPDUCounters`)", "chk_snmp_pdu")
            bind_cb("Verify SNMP Source Intf (`VerifySnmpSourceInterface`)", "chk_snmp_source")
            bind_cb("Verify SNMP Status (`VerifySnmpStatus`)", "chk_snmp_status")
            bind_cb("Verify SNMP User (`VerifySnmpUser`)", "chk_snmp_user")

        elif selected_cat == "Software":
            bind_cb("Verify EOS Extensions (`VerifyEOSExtensions`)", "chk_sw_extensions")
            bind_cb("Verify EOS Version (`VerifyEOSVersion`)", "chk_sw_version")
            st.text_input("Expected EOS Version", value=st.session_state.get("param_sw_ver", "4.30.2F"), key="param_sw_ver")
            bind_cb("Verify TerminAttr Version (`VerifyTerminAttrVersion`)", "chk_sw_terminattr")

        elif selected_cat == "STP":
            bind_cb("Verify STP Blocked Ports (`VerifySTPBlockedPorts`)", "chk_stp_blocked")
            bind_cb("Verify STP Counters (`VerifySTPCounters`)", "chk_stp_counters")
            bind_cb("Verify STP Disabled VLANs (`VerifySTPDisabledVlans`)", "chk_stp_disabled_vlans")
            bind_cb("Verify STP Forwarding Ports (`VerifySTPForwardingPorts`)", "chk_stp_forwarding")
            bind_cb("Verify STP Mode (`VerifySTPMode`)", "chk_stp_mode")
            bind_cb("Verify STP Root Priority (`VerifySTPRootPriority`)", "chk_stp_root_priority")
            bind_cb("Verify STP Topology Changes (`VerifyStpTopologyChanges`)", "chk_stp_tc")

        elif selected_cat == "STUN":
            bind_cb("Verify STUN Client (`VerifyStunClient`)", "chk_stun_client")
            bind_cb("Verify STUN Client Translation (`VerifyStunClientTranslation`)", "chk_stun_client_trans")
            bind_cb("Verify STUN Server (`VerifyStunServer`)", "chk_stun_status")

        elif selected_cat == "System":
            bind_cb("Verify Agent Logs (`VerifyAgentLogs`)", "chk_sys_agent_logs")
            bind_cb("Verify CPU Utilization (`VerifyCPUUtilization`)", "chk_sys_cpu")
            bind_cb("Verify Coredump (`VerifyCoredump`)", "chk_sys_coredump")
            bind_cb("Verify File Presence (`VerifyFilePresence`)", "chk_sys_file_presence")
            bind_cb("Verify File System Util (`VerifyFileSystemUtilization`)", "chk_sys_fs_util")
            bind_cb("Verify Flash Util (`VerifyFlashUtilization`)", "chk_sys_flash_util")
            bind_cb("Verify Maintenance (`VerifyMaintenance`)", "chk_sys_maintenance")
            bind_cb("Verify Memory Utilization (`VerifyMemoryUtilization`)", "chk_sys_mem")
            bind_cb("Verify NTP (`VerifyNTP`)", "chk_sys_ntp")
            bind_cb("Verify NTP Associations (`VerifyNTPAssociations`)", "chk_sys_ntp_assoc")
            bind_cb("Verify Reload Cause (`VerifyReloadCause`)", "chk_sys_reload")
            bind_cb("Verify Uptime (`VerifyUptime`)", "chk_sys_uptime")
            st.number_input("Min Uptime Sec", value=st.session_state.get("param_sys_uptime_val", 60), min_value=1, key="param_sys_uptime_val")

        elif selected_cat == "VLAN":
            bind_cb("Verify Dynamic VLAN Source (`VerifyDynamicVlanSource`)", "chk_vlan_dynamic")
            bind_cb("Verify Internal VLAN Policy (`VerifyVlanInternalPolicy`)", "chk_vlan_internal")
            bind_cb("Verify VLAN Status (`VerifyVlanStatus`)", "chk_vlan_status")

        elif selected_cat == "Custom":
            st.text_area("Custom YAML Input", value=st.session_state.get("param_custom_yaml", "# anta.tests...\n"), height=250, key="param_custom_yaml")

    # Catalog Build Logic
    catalog_dict = {}
    parsed_tags = [t.strip() for t in st.session_state.get("input_catalog_tags", "").split(",") if t.strip()]

    def add_test(module, test_name, params=None):
        if module not in catalog_dict: catalog_dict[module] = []
        body = dict(params) if isinstance(params, dict) else {}
        if parsed_tags: body["filters"] = {"tags": parsed_tags}
        catalog_dict[module].append({test_name: body if body else None})

    # Exact Key to Module & Test Class mappings
    key_to_test_map = {
        "chk_aaa_authen": ("anta.tests.aaa", "VerifyAuthenMethods", {"methods": [st.session_state.get("param_aaa_authen_methods", "local")]}),
        "chk_aaa_authz": ("anta.tests.aaa", "VerifyAuthzMethods", {"methods": [st.session_state.get("param_aaa_authz_methods", "group tacacs+")]}),
        "chk_aaa_acct_default": ("anta.tests.aaa", "VerifyAcctDefaultMethods", None),
        "chk_aaa_acct_console": ("anta.tests.aaa", "VerifyAcctConsoleMethods", None),
        "chk_aaa_tacacs_src": ("anta.tests.aaa", "VerifyTacacsSourceIntf", {"intf": st.session_state.get("param_aaa_tacacs_intf", "Management1")}),
        "chk_aaa_tacacs_servers": ("anta.tests.aaa", "VerifyTacacsServers", {"servers": [{"server": ip.strip()} for ip in st.session_state.get("param_aaa_tacacs_ips", "10.1.1.1").split(",") if ip.strip()]}),
        "chk_aaa_tacacs_groups": ("anta.tests.aaa", "VerifyTacacsServerGroups", None),
        "chk_aaa_radius_src": ("anta.tests.aaa", "VerifyRadiusSourceIntf", None),
        "chk_aaa_radius_servers": ("anta.tests.aaa", "VerifyRadiusServers", None),
        
        "chk_avt_path": ("anta.tests.avt", "VerifyAVTPathHealth", None),
        "chk_avt_role": ("anta.tests.avt", "VerifyAVTRole", None),
        "chk_avt_specific_path": ("anta.tests.avt", "VerifyAVTSpecificPath", None),
        "chk_bfd_health": ("anta.tests.bfd", "VerifyBFDPeersHealth", None),
        "chk_bfd_intervals": ("anta.tests.bfd", "VerifyBFDPeersIntervals", None),
        "chk_bfd_protocols": ("anta.tests.bfd", "VerifyBFDPeersRegProtocols", None),
        "chk_bfd_specific": ("anta.tests.bfd", "VerifyBFDSpecificPeers", None),

        "chk_cfg_diff": ("anta.tests.configuration", "VerifyRunningConfigDiffs", None),
        "chk_cfg_lines": ("anta.tests.configuration", "VerifyRunningConfigLines", None),
        "chk_cfg_ztp": ("anta.tests.configuration", "VerifyZeroTouch", None),
        "chk_cfg_banner_login": ("anta.tests.security", "VerifyBannerLogin", None),
        "chk_cfg_banner_motd": ("anta.tests.security", "VerifyBannerMotd", None),

        "chk_conn_lldp": ("anta.tests.connectivity", "VerifyLLDPNeighbors", {"neighbors": [{"port": st.session_state.get("param_conn_lldp_port", "Ethernet1")}]}),
        "chk_conn_ping": ("anta.tests.connectivity", "VerifyReachability", {"hosts": [{"destination": st.session_state.get("param_conn_dest", "8.8.8.8")}]}),

        "chk_cvx_active": ("anta.tests.cvx", "VerifyActiveCVXConnections", None),
        "chk_cvx_cluster": ("anta.tests.cvx", "VerifyCVXClusterStatus", None),
        "chk_cvx_mgmt": ("anta.tests.cvx", "VerifyManagementCVX", None),
        "chk_cvx_client_mounts": ("anta.tests.cvx", "VerifyMcsClientMounts", None),
        "chk_cvx_server_mounts": ("anta.tests.cvx", "VerifyMcsServerMounts", None),

        "chk_evpn_type5": ("anta.tests.evpn", "VerifyEVPNType5Routes", None),
        "chk_fn_fn44": ("anta.tests.field_notices", "VerifyFieldNotice44Resolution", None),
        "chk_fn_fn72": ("anta.tests.field_notices", "VerifyFieldNotice72Resolution", None),
        "chk_flow_tracking": ("anta.tests.flow_tracking", "VerifyHardwareFlowTrackerStatus", None),
        "chk_greent_policy": ("anta.tests.greent", "VerifyGreenT", None),
        "chk_greent_counters": ("anta.tests.greent", "VerifyGreenTCounters", None),

        "chk_hw_linecards": ("anta.tests.hardware", "VerifyAbsenceOfLinecards", None),
        "chk_hw_drops": ("anta.tests.hardware", "VerifyAdverseDrops", None),
        "chk_hw_chassis": ("anta.tests.hardware", "VerifyChassisHealth", None),
        "chk_hw_cooling_fans": ("anta.tests.hardware", "VerifyEnvironmentCooling", None),
        "chk_hw_power": ("anta.tests.hardware", "VerifyEnvironmentPower", None),
        "chk_hw_sys_cooling": ("anta.tests.hardware", "VerifyEnvironmentSystemCooling", None),
        "chk_hw_capacity": ("anta.tests.hardware", "VerifyHardwareCapacityUtilization", None),
        "chk_hw_inventory": ("anta.tests.hardware", "VerifyInventory", None),
        "chk_hw_module": ("anta.tests.hardware", "VerifyModuleStatus", None),
        "chk_hw_pcie": ("anta.tests.hardware", "VerifyPCIeErrors", None),
        "chk_hw_supervisor": ("anta.tests.hardware", "VerifySupervisorRedundancy", None),
        "chk_hw_temp": ("anta.tests.hardware", "VerifyTemperature", None),
        "chk_hw_trans": ("anta.tests.hardware", "VerifyTransceiversManufacturers", {"manufacturers": [m.strip() for m in st.session_state.get("param_hw_mfg", "Arista Networks").split(",") if m.strip()]}),
        "chk_hw_trans_temp": ("anta.tests.hardware", "VerifyTransceiversTemperature", None),
        "chk_hw_trans_presence": ("anta.tests.hardware", "VerifyTransceiversPresence", None),
        "chk_hw_trans_optics": ("anta.tests.hardware", "VerifyTransceiversOptics", None),
        "chk_hw_pse": ("anta.tests.hardware", "VerifyPseStatus", None),

        "chk_sw_extensions": ("anta.tests.software", "VerifyEOSExtensions", None),
        "chk_sw_version": ("anta.tests.software", "VerifyEOSVersion", {"version": st.session_state.get("param_sw_ver", "4.30.2F")}),
        "chk_sw_terminattr": ("anta.tests.software", "VerifyTerminAttrVersion", None),

        "chk_sys_agent_logs": ("anta.tests.system", "VerifyAgentLogs", None),
        "chk_sys_cpu": ("anta.tests.system", "VerifyCPUUtilization", None),
        "chk_sys_coredump": ("anta.tests.system", "VerifyCoredump", None),
        "chk_sys_file_presence": ("anta.tests.system", "VerifyFilePresence", None),
        "chk_sys_fs_util": ("anta.tests.system", "VerifyFileSystemUtilization", None),
        "chk_sys_flash_util": ("anta.tests.system", "VerifyFlashUtilization", None),
        "chk_sys_maintenance": ("anta.tests.system", "VerifyMaintenance", None),
        "chk_sys_mem": ("anta.tests.system", "VerifyMemoryUtilization", None),
        "chk_sys_ntp": ("anta.tests.system", "VerifyNTP", None),
        "chk_sys_ntp_assoc": ("anta.tests.system", "VerifyNTPAssociations", None),
        "chk_sys_reload": ("anta.tests.system", "VerifyReloadCause", None),
        "chk_sys_uptime": ("anta.tests.system", "VerifyUptime", {"minimum": int(st.session_state.get("param_sys_uptime_val", 60))})
    }

    if st.session_state.get("chk_cfg_rules") and st.session_state.get("cfg_rules_data"):
        cfg_rules_parsed = []
        for row in st.session_state.cfg_rules_data:
            match_val = str(row.get("Match", "")).strip()
            if match_val:
                cfg_rules_parsed.append({"match": match_val, "mode": row.get("Mode", "exact")})
        if cfg_rules_parsed:
            add_test("anta.tests.configuration", "VerifyRunningConfig", {"rules": cfg_rules_parsed})

    for k, (mod, test_cls, params) in key_to_test_map.items():
        if st.session_state.get(k, False):
            add_test(mod, test_cls, params)

    try:
        with open("catalog.yml", "w") as f: yaml.safe_dump(catalog_dict, f, sort_keys=False)
        save_settings({"selected_test_keys": [k for k in ALL_TEST_KEYS if st.session_state.get(k, False)]})
    except Exception as e: st.error(f"Save error: {e}")

# ==========================================
# TAB 4: DASHBOARD
# ==========================================
with tab_dashboard:
    st.subheader("Run Network Tests")
    run_tags_input = st.text_input("🏷️ Filter NRFU Execution by Tags", placeholder="e.g. leaf, spine", key="input_run_tags")
    
    if st.button("🚀 Execute Tests", type="primary", use_container_width=True):
        os.environ["ANTA_USERNAME"] = st.session_state.anta_user
        os.environ["ANTA_PASSWORD"] = st.session_state.anta_pass
        
        with st.spinner("Running tests..."):
            cmd = ["anta", "nrfu", "--inventory", "inventory.yml", "--catalog", "catalog.yml", "--ignore-status", "json"]
            if run_tags_input.strip(): cmd.extend(["--tags", run_tags_input.strip()])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            output_clean = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', result.stdout)
            
            try:
                start_idx, end_idx = output_clean.find('['), output_clean.rfind(']')
                if start_idx != -1 and end_idx != -1:
                    df = pd.DataFrame(json.loads(output_clean[start_idx:end_idx+1]))
                    st.dataframe(df, use_container_width=True)
                else:
                    st.error("No JSON output received.")
                    st.code(output_clean)
            except Exception as e:
                st.error(f"Parsing error: {e}")

# ==========================================
# TAB 5: RAW CLI
# ==========================================
with tab_cli:
    st.subheader("🛠️ Raw EOS Command Runner")
    cmd_input = st.text_input("Enter EOS Command", value="show mac address-table", key="input_cli_command")
    if st.button("Run Command", type="primary"):
        st.info("Executing debug run-cmd...")