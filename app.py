import streamlit as st
import subprocess
import json
import pandas as pd
import yaml
import os
import re
import uuid
import fcntl
from contextlib import contextmanager
from anta.catalog import AntaCatalog

NRFU_SUBPROCESS_TIMEOUT = 600
CLI_SUBPROCESS_TIMEOUT = 60

# Configure the web page layout
st.set_page_config(page_title="ANTA Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- Cross-session file locking ---
# Concurrent users share settings.json/inventory.yml on disk; without a lock,
# overlapping read-modify-write cycles silently drop each other's changes or
# hand back a partially-written file to a concurrent reader.
@contextmanager
def locked_file(path):
    lock_path = f"{path}.lock"
    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)

def _atomic_write(path, write_fn):
    # Write-then-rename so any reader (including the external `anta` CLI
    # subprocess, which doesn't participate in our flock) always sees either
    # the old or the new file in full, never a partially-written one.
    tmp_path = f"{path}.tmp.{uuid.uuid4().hex}"
    with open(tmp_path, "w") as f:
        write_fn(f)
    os.replace(tmp_path, path)

# --- Persistent Settings Helper ---
SETTINGS_FILE = "settings.json"

def load_settings():
    with locked_file(SETTINGS_FILE):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

def save_settings(data_dict):
    with locked_file(SETTINGS_FILE):
        current = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    current = json.load(f)
            except Exception:
                current = {}
        current.update(data_dict)
        _atomic_write(SETTINGS_FILE, lambda f: json.dump(current, f, indent=4))

# --- Persistent Inventory Helper ---
INVENTORY_FILE = "inventory.yml"

def load_inventory():
    with locked_file(INVENTORY_FILE):
        try:
            with open(INVENTORY_FILE, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

def save_inventory(inv_payload):
    with locked_file(INVENTORY_FILE):
        _atomic_write(INVENTORY_FILE, lambda f: yaml.safe_dump(inv_payload, f, sort_keys=False))

saved_settings = load_settings()

# Complete list of test keys
ALL_TEST_KEYS = [
    # AAA
    "chk_aaa_authen", "chk_aaa_authz", "chk_aaa_acct_default", "chk_aaa_acct_console",
    "chk_aaa_tacacs_src", "chk_aaa_tacacs_servers", "chk_aaa_tacacs_groups",
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
    "chk_hw_supervisor", "chk_hw_temp", "chk_hw_trans", "chk_hw_trans_temp",
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
    "chk_bgp_drop_stats", "chk_bgp_peer_group", "chk_bgp_md5", "chk_bgp_mp_caps", "chk_bgp_peer_route_limit",
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

# Initialize master state dictionary per user session
if "master_test_states" not in st.session_state:
    st.session_state["master_test_states"] = {}
    saved_test_keys = saved_settings.get("selected_test_keys", None)
    for k in ALL_TEST_KEYS:
        if saved_test_keys is not None:
            st.session_state["master_test_states"][k] = (k in saved_test_keys)
        else:
            st.session_state["master_test_states"][k] = (k in DEFAULT_PROFILES["🟢 Basic NRFU (Quick Check)"]["keys"])

# Ensure every key exists in session_state for rendering
for k in ALL_TEST_KEYS:
    if k not in st.session_state:
        st.session_state[k] = st.session_state["master_test_states"].get(k, False)

def update_test_state(key):
    st.session_state["master_test_states"][key] = st.session_state[key]

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
                is_sel = (k in p_keys)
                st.session_state["master_test_states"][k] = is_sel
                st.session_state[k] = is_sel
            st.session_state.cfg_rules_data = p_data.get("cfg_rules", default_config_rules)
            save_settings({"selected_test_keys": list(p_keys)})
            st.success(f"Loaded '{selected_prof_name}'!")
            st.rerun()

    with col_prof2:
        if st.button("💾 Save", use_container_width=True):
            current_keys = [k for k in ALL_TEST_KEYS if st.session_state["master_test_states"].get(k, False)]
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
    selected_count = sum(1 for k in ALL_TEST_KEYS if st.session_state["master_test_states"].get(k, False))
    st.metric("📋 Selected Tests", f"{selected_count} / {len(ALL_TEST_KEYS)}")

    def toggle_select_all():
        current_all_selected = all(st.session_state["master_test_states"].get(k, False) for k in ALL_TEST_KEYS)
        new_state = not current_all_selected
        for k in ALL_TEST_KEYS:
            st.session_state["master_test_states"][k] = new_state
            st.session_state[k] = new_state

    is_all_selected = all(st.session_state["master_test_states"].get(k, False) for k in ALL_TEST_KEYS)
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
# TAB 2: INVENTORY
# ==========================================
with tab_inventory:
    st.subheader("Inventory Manager")
    inv_data = load_inventory()

    anta_inv = inv_data.get("anta_inventory", {})
    df_hosts = pd.DataFrame([dict(h) for h in anta_inv.get("hosts", [])])
    df_networks = pd.DataFrame([dict(n) for n in anta_inv.get("networks", [])])
    df_ranges = pd.DataFrame([dict(r) for r in anta_inv.get("ranges", [])])

    sub_hosts, sub_networks, sub_ranges = st.tabs(["🖥️ Specific Hosts", "🌐 Networks (CIDR)", "🔢 IP Ranges"])
    with sub_hosts: edited_hosts = st.data_editor(df_hosts, num_rows="dynamic", use_container_width=True, key="editor_hosts")
    with sub_networks: edited_networks = st.data_editor(df_networks, num_rows="dynamic", use_container_width=True, key="editor_networks")
    with sub_ranges: edited_ranges = st.data_editor(df_ranges, num_rows="dynamic", use_container_width=True, key="editor_ranges")

    if st.button("💾 Save Default Inventory.yml", type="primary"):
        inv_payload = {
            "anta_inventory": {
                "hosts": edited_hosts.dropna(how="all").to_dict("records"),
                "networks": edited_networks.dropna(how="all").to_dict("records"),
                "ranges": edited_ranges.dropna(how="all").to_dict("records")
            }
        }
        save_inventory(inv_payload)
        st.success("✅ Inventory.yml saved successfully!")

# ==========================================
# TAB 3: CATALOG BUILDER (PARAMETRIZED)
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
        def bind_cb(label, key):
            return st.checkbox(
                label,
                value=st.session_state["master_test_states"].get(key, False),
                key=key,
                on_change=update_test_state,
                args=(key,)
            )

        def render_list_editor(label, param_key, default_rows):
            data_key = f"data_{param_key}"
            if data_key not in st.session_state:
                st.session_state[data_key] = default_rows
            st.caption(label)
            edited = st.data_editor(pd.DataFrame(st.session_state[data_key]), num_rows="dynamic", use_container_width=True, key=f"editor_{param_key}")
            st.session_state[data_key] = edited.to_dict("records")
            return st.session_state[data_key]

        def expand_csv_fields(rows, fields):
            out = []
            for r in rows:
                nr = dict(r)
                for f in fields:
                    nr[f] = [v.strip() for v in str(r.get(f, "")).split(",") if v.strip()]
                out.append(nr)
            return out

        if selected_cat == "AAA":
            bind_cb("Verify Authentication Methods (`VerifyAuthenMethods`)", "chk_aaa_authen")
            if st.session_state["master_test_states"].get("chk_aaa_authen"):
                c1, c2 = st.columns(2)
                with c1: st.text_input("Expected Auth Methods (comma-separated)", value=st.session_state.get("param_aaa_authen_methods", "local"), key="param_aaa_authen_methods")
                with c2: st.selectbox("Auth Type", ["login", "enable", "dot1x"], key="param_aaa_authen_types")
            
            bind_cb("Verify Authorization Methods (`VerifyAuthzMethods`)", "chk_aaa_authz")
            if st.session_state["master_test_states"].get("chk_aaa_authz"):
                c1, c2 = st.columns(2)
                with c1: st.text_input("Expected Authz Methods (comma-separated)", value=st.session_state.get("param_aaa_authz_methods", "group tacacs+"), key="param_aaa_authz_methods")
                with c2: st.selectbox("Authz Type", ["exec", "commands"], key="param_aaa_authz_types")
            
            bind_cb("Verify Accounting Default (`VerifyAcctDefaultMethods`)", "chk_aaa_acct_default")
            if st.session_state["master_test_states"].get("chk_aaa_acct_default"):
                c1, c2 = st.columns(2)
                with c1: st.text_input("Acct Default Methods (comma-separated)", value=st.session_state.get("param_aaa_acct_def_methods", "group tacacs+, local"), key="param_aaa_acct_def_methods")
                with c2: st.selectbox("Acct Default Type", ["exec", "system", "commands", "dot1x"], key="param_aaa_acct_def_types")

            bind_cb("Verify Accounting Console (`VerifyAcctConsoleMethods`)", "chk_aaa_acct_console")
            if st.session_state["master_test_states"].get("chk_aaa_acct_console"):
                c1, c2 = st.columns(2)
                with c1: st.text_input("Acct Console Methods (comma-separated)", value=st.session_state.get("param_aaa_acct_con_methods", "local"), key="param_aaa_acct_con_methods")
                with c2: st.selectbox("Acct Console Type", ["exec", "system", "commands", "dot1x"], key="param_aaa_acct_con_types")
            
            bind_cb("Verify TACACS Source Intf (`VerifyTacacsSourceIntf`)", "chk_aaa_tacacs_src")
            if st.session_state["master_test_states"].get("chk_aaa_tacacs_src"):
                st.text_input("TACACS Source Interface", value=st.session_state.get("param_aaa_tacacs_intf", "Management1"), key="param_aaa_tacacs_intf")
            
            bind_cb("Verify TACACS Servers (`VerifyTacacsServers`)", "chk_aaa_tacacs_servers")
            if st.session_state["master_test_states"].get("chk_aaa_tacacs_servers"):
                st.text_input("TACACS Server IPs (comma-separated)", value=st.session_state.get("param_aaa_tacacs_ips", "10.1.1.1"), key="param_aaa_tacacs_ips")
            
            bind_cb("Verify TACACS Server Groups (`VerifyTacacsServerGroups`)", "chk_aaa_tacacs_groups")
            if st.session_state["master_test_states"].get("chk_aaa_tacacs_groups"):
                st.text_input("TACACS Group Names (comma-separated)", value=st.session_state.get("param_aaa_tacacs_groups_val", "TACACS-SERVERS"), key="param_aaa_tacacs_groups_val")

        elif selected_cat == "AVT_BFD":
            bind_cb("Verify AVT Path Health (`VerifyAVTPathHealth`)", "chk_avt_path")
            
            bind_cb("Verify AVT Role (`VerifyAVTRole`)", "chk_avt_role")
            if st.session_state["master_test_states"].get("chk_avt_role"):
                st.selectbox("AVT Role", ["edge", "core", "path-finder"], key="param_avt_role_val")
                
            bind_cb("Verify AVT Specific Path (`VerifyAVTSpecificPath`)", "chk_avt_specific_path")
            if st.session_state["master_test_states"].get("chk_avt_specific_path"):
                col1, col2, col3, col4 = st.columns(4)
                with col1: st.text_input("AVT Name", value=st.session_state.get("param_avt_spec_name", "AVT1"), key="param_avt_spec_name")
                with col2: st.text_input("Destination IP", value=st.session_state.get("param_avt_spec_dest", "10.0.0.1"), key="param_avt_spec_dest")
                with col3: st.text_input("Next Hop IP", value=st.session_state.get("param_avt_spec_next_hop", "10.0.0.2"), key="param_avt_spec_next_hop")
                with col4: st.text_input("VRF", value=st.session_state.get("param_avt_spec_vrf", "default"), key="param_avt_spec_vrf")

            st.divider()
            bind_cb("Verify BFD Peers Health (`VerifyBFDPeersHealth`)", "chk_bfd_health")
            
            bind_cb("Verify BFD Peers Intervals (`VerifyBFDPeersIntervals`)", "chk_bfd_intervals")
            if st.session_state["master_test_states"].get("chk_bfd_intervals"):
                col1, col2, col3, col4, col5 = st.columns(5)
                with col1: st.text_input("BFD Peer Address", value=st.session_state.get("param_bfd_int_ip", "10.0.0.1"), key="param_bfd_int_ip")
                with col2: st.text_input("BFD Peer VRF", value=st.session_state.get("param_bfd_int_vrf", "default"), key="param_bfd_int_vrf")
                with col3: st.number_input("Tx Interval (ms)", value=st.session_state.get("param_bfd_tx", 300), key="param_bfd_tx")
                with col4: st.number_input("Rx Interval (ms)", value=st.session_state.get("param_bfd_rx", 300), key="param_bfd_rx")
                with col5: st.number_input("Multiplier", value=st.session_state.get("param_bfd_mult", 3), key="param_bfd_mult")

            bind_cb("Verify BFD Reg Protocols (`VerifyBFDPeersRegProtocols`)", "chk_bfd_protocols")
            if st.session_state["master_test_states"].get("chk_bfd_protocols"):
                col1, col2, col3 = st.columns(3)
                with col1: st.text_input("BFD Reg Protocol Address", value=st.session_state.get("param_bfd_proto_ip", "10.0.0.1"), key="param_bfd_proto_ip")
                with col2: st.text_input("BFD Reg Protocol VRF", value=st.session_state.get("param_bfd_proto_vrf", "default"), key="param_bfd_proto_vrf")
                with col3: st.text_input("Protocols (comma-separated)", value=st.session_state.get("param_bfd_proto_list", "bgp"), key="param_bfd_proto_list")

            bind_cb("Verify BFD Specific Peers (`VerifyBFDSpecificPeers`)", "chk_bfd_specific")
            if st.session_state["master_test_states"].get("chk_bfd_specific"):
                col1, col2 = st.columns(2)
                with col1: st.text_input("BFD Specific Peer Address", value=st.session_state.get("param_bfd_spec_ip", "10.0.0.1"), key="param_bfd_spec_ip")
                with col2: st.text_input("BFD Specific Peer VRF", value=st.session_state.get("param_bfd_spec_vrf", "default"), key="param_bfd_spec_vrf")

        elif selected_cat == "Configuration":
            st.markdown("##### Dynamic Running Config Rules (`VerifyRunningConfig`)")
            bind_cb("Verify Running Config Rules (`VerifyRunningConfig`)", "chk_cfg_rules")
            if st.session_state["master_test_states"].get("chk_cfg_rules"):
                if "cfg_rules_data" not in st.session_state:
                    st.session_state.cfg_rules_data = saved_settings.get("cfg_rules_data", default_config_rules)
                edited_cfg_rules = st.data_editor(pd.DataFrame(st.session_state.cfg_rules_data), num_rows="dynamic", use_container_width=True, key="editor_cfg_rules")
                st.session_state.cfg_rules_data = edited_cfg_rules.to_dict("records")
            
            bind_cb("Verify Running Config Diffs (`VerifyRunningConfigDiffs`)", "chk_cfg_diff")
            
            bind_cb("Verify Running Config Lines (`VerifyRunningConfigLines`)", "chk_cfg_lines")
            if st.session_state["master_test_states"].get("chk_cfg_lines"):
                st.text_input("Regex Patterns (comma-separated)", value=st.session_state.get("param_cfg_lines_regex", "router bgp"), key="param_cfg_lines_regex")
            
            bind_cb("Verify Zero Touch (`VerifyZeroTouch`)", "chk_cfg_ztp")
            
            bind_cb("Verify Login Banner (`VerifyBannerLogin`)", "chk_cfg_banner_login")
            if st.session_state["master_test_states"].get("chk_cfg_banner_login"):
                st.text_input("Expected Login Banner", value=st.session_state.get("param_banner_login_text", "Authorized Access Only"), key="param_banner_login_text")
            
            bind_cb("Verify MOTD Banner (`VerifyBannerMotd`)", "chk_cfg_banner_motd")
            if st.session_state["master_test_states"].get("chk_cfg_banner_motd"):
                st.text_input("Expected MOTD Banner", value=st.session_state.get("param_banner_motd_text", "Welcome"), key="param_banner_motd_text")

        elif selected_cat == "Connectivity":
            bind_cb("Verify LLDP Neighbors (`VerifyLLDPNeighbors`)", "chk_conn_lldp")
            if st.session_state["master_test_states"].get("chk_conn_lldp"):
                col1, col2, col3 = st.columns(3)
                with col1: st.text_input("LLDP Local Port", value=st.session_state.get("param_conn_lldp_port", "Ethernet1"), key="param_conn_lldp_port")
                with col2: st.text_input("Neighbor Device Name", value=st.session_state.get("param_conn_lldp_dev", "switch2"), key="param_conn_lldp_dev")
                with col3: st.text_input("Neighbor Port", value=st.session_state.get("param_conn_lldp_neighbor_port", "Ethernet1"), key="param_conn_lldp_neighbor_port")

            bind_cb("Verify Reachability (`VerifyReachability`)", "chk_conn_ping")
            if st.session_state["master_test_states"].get("chk_conn_ping"):
                st.text_input("Ping Destination IP(s) (comma-separated)", value=st.session_state.get("param_conn_dest", "8.8.8.8"), key="param_conn_dest")

        elif selected_cat == "CVX":
            bind_cb("Verify Active CVX Connections (`VerifyActiveCVXConnections`)", "chk_cvx_active")
            if st.session_state["master_test_states"].get("chk_cvx_active"):
                st.number_input("Connections Count", value=st.session_state.get("param_cvx_active_cnt", 1), key="param_cvx_active_cnt")

            bind_cb("Verify CVX Cluster Status (`VerifyCVXClusterStatus`)", "chk_cvx_cluster")
            if st.session_state["master_test_states"].get("chk_cvx_cluster"):
                col1, col2, col3 = st.columns(3)
                with col1: st.selectbox("CVX Role", ["Master", "Standby", "Disconnected"], key="param_cvx_role")
                with col2: st.text_input("CVX Peer Name (hostname)", value=st.session_state.get("param_cvx_peer_name", "cvx-red-2"), key="param_cvx_peer_name")
                with col3: st.selectbox("Registration State", ["Connecting", "Connected", "Registration error", "Registration complete", "Unexpected peer state"], key="param_cvx_reg_state")

            bind_cb("Verify Management CVX (`VerifyManagementCVX`)", "chk_cvx_mgmt")
            if st.session_state["master_test_states"].get("chk_cvx_mgmt"):
                st.checkbox("Management CVX Enabled", value=st.session_state.get("param_cvx_mgmt_enabled", True), key="param_cvx_mgmt_enabled")

            bind_cb("Verify MCS Client Mounts (`VerifyMcsClientMounts`)", "chk_cvx_client_mounts")
            
            bind_cb("Verify MCS Server Mounts (`VerifyMcsServerMounts`)", "chk_cvx_server_mounts")
            if st.session_state["master_test_states"].get("chk_cvx_server_mounts"):
                st.number_input("Server Mounts Count", value=st.session_state.get("param_cvx_mcs_cnt", 1), key="param_cvx_mcs_cnt")

        elif selected_cat == "EVPN_VXLAN":
            bind_cb("Verify EVPN Type 5 Routes (`VerifyEVPNType5Routes`)", "chk_evpn_type5")
            if st.session_state["master_test_states"].get("chk_evpn_type5"):
                col1, col2 = st.columns(2)
                with col1: st.text_input("EVPN Prefix", value=st.session_state.get("param_evpn_prefix", "10.0.0.0/24"), key="param_evpn_prefix")
                with col2: st.number_input("EVPN VNI", value=st.session_state.get("param_evpn_vni", 10010), key="param_evpn_vni")
                
            bind_cb("Verify VXLAN Conn Settings (`VerifyVxlan1ConnSettings`)", "chk_vxlan_conn")
            if st.session_state["master_test_states"].get("chk_vxlan_conn"):
                st.text_input("VXLAN Source Interface", value=st.session_state.get("param_vxlan_src_intf", "Loopback1"), key="param_vxlan_src_intf")
                st.number_input("VXLAN UDP Port", value=st.session_state.get("param_vxlan_udp_port", 4789), key="param_vxlan_udp_port")
            bind_cb("Verify VXLAN Interface (`VerifyVxlan1Interface`)", "chk_vxlan_intf")
            bind_cb("Verify VXLAN VVTEP IPs (`VerifyVxlan1VVTEPIPAddresses`)", "chk_vxlan_vvtep")
            if st.session_state["master_test_states"].get("chk_vxlan_vvtep"):
                st.text_input("VVTEP IPv4 Address", value=st.session_state.get("param_vxlan_vvtep_v4", "10.255.1.1"), key="param_vxlan_vvtep_v4")
                st.text_input("VVTEP IPv6 Address (optional)", value=st.session_state.get("param_vxlan_vvtep_v6", ""), key="param_vxlan_vvtep_v6")
            bind_cb("Verify VXLAN Config Sanity (`VerifyVxlanConfigSanity`)", "chk_vxlan_sanity")
            bind_cb("Verify VXLAN VNI Binding (`VerifyVxlanVniBinding`)", "chk_vxlan_vni_binding")
            if st.session_state["master_test_states"].get("chk_vxlan_vni_binding"):
                render_list_editor("VNI Bindings (VNI -> VLAN/VRF)", "param_vxlan_vni_bindings", [{'vni': 10010, 'binding': '10'}])
            bind_cb("Verify VXLAN VTEP (`VerifyVxlanVtep`)", "chk_vxlan_vtep")
            if st.session_state["master_test_states"].get("chk_vxlan_vtep"):
                st.text_input("Expected VTEP Peer IPs (comma-separated)", value=st.session_state.get("param_vxlan_vteps", "10.1.1.1"), key="param_vxlan_vteps")

        elif selected_cat == "FieldNotices":
            bind_cb("Verify Field Notice 44 Resolution (`VerifyFieldNotice44Resolution`)", "chk_fn_fn44")
            bind_cb("Verify Field Notice 72 Resolution (`VerifyFieldNotice72Resolution`)", "chk_fn_fn72")

        elif selected_cat == "Flow_GreenT":
            bind_cb("Verify Hardware Flow Tracker (`VerifyHardwareFlowTrackerStatus`)", "chk_flow_tracking")
            if st.session_state["master_test_states"].get("chk_flow_tracking"):
                st.text_input("Tracker Name", value=st.session_state.get("param_flow_tracker_name", "FLOW-TRACKER"), key="param_flow_tracker_name")

            bind_cb("Verify GreenT Policy (`VerifyGreenT`)", "chk_greent_policy")
            bind_cb("Verify GreenT Counters (`VerifyGreenTCounters`)", "chk_greent_counters")

        elif selected_cat == "Hardware":
            bind_cb("Verify Linecards Absence (`VerifyAbsenceOfLinecards`)", "chk_hw_linecards")
            if st.session_state["master_test_states"].get("chk_hw_linecards"):
                st.text_input("Serial Numbers (comma-separated)", value=st.session_state.get("param_hw_linecards_sn", "SN12345"), key="param_hw_linecards_sn")

            bind_cb("Verify Adverse Drops (`VerifyAdverseDrops`)", "chk_hw_drops")
            bind_cb("Verify Chassis Health (`VerifyChassisHealth`)", "chk_hw_chassis")
            
            bind_cb("Verify Environment Cooling (`VerifyEnvironmentCooling`)", "chk_hw_cooling_fans")
            if st.session_state["master_test_states"].get("chk_hw_cooling_fans"):
                st.text_input("Accepted Cooling States", value=st.session_state.get("param_hw_cooling_states", "ok"), key="param_hw_cooling_states")

            bind_cb("Verify Environment Power (`VerifyEnvironmentPower`)", "chk_hw_power")
            bind_cb("Verify Environment System Cooling (`VerifyEnvironmentSystemCooling`)", "chk_hw_sys_cooling")
            bind_cb("Verify Hardware Capacity (`VerifyHardwareCapacityUtilization`)", "chk_hw_capacity")
            bind_cb("Verify Hardware Inventory (`VerifyInventory`)", "chk_hw_inventory")
            bind_cb("Verify Module Status (`VerifyModuleStatus`)", "chk_hw_module")
            bind_cb("Verify PCIe Errors (`VerifyPCIeErrors`)", "chk_hw_pcie")
            bind_cb("Verify Supervisor Redundancy (`VerifySupervisorRedundancy`)", "chk_hw_supervisor")
            bind_cb("Verify Temperature (`VerifyTemperature`)", "chk_hw_temp")
            
            bind_cb("Verify Transceivers Manufacturers (`VerifyTransceiversManufacturers`)", "chk_hw_trans")
            if st.session_state["master_test_states"].get("chk_hw_trans"):
                st.text_input("Expected Manufacturers (comma-separated)", value=st.session_state.get("param_hw_mfg", "Arista Networks, ARISTA"), key="param_hw_mfg")
            
            bind_cb("Verify Transceivers Temperature (`VerifyTransceiversTemperature`)", "chk_hw_trans_temp")

        elif selected_cat == "Interfaces":
            bind_cb("Verify Proxy ARP (`VerifyIPProxyARP`)", "chk_int_proxy_arp")
            if st.session_state["master_test_states"].get("chk_int_proxy_arp"):
                st.text_input("Interfaces (comma-separated)", value=st.session_state.get("param_int_proxy_arp_ifaces", "Ethernet1"), key="param_int_proxy_arp_ifaces")
            bind_cb("Verify Illegal LACP (`VerifyIllegalLACP`)", "chk_int_ill_lacp")
            bind_cb("Verify Interface Discards (`VerifyInterfaceDiscards`)", "chk_int_disc")
            bind_cb("Verify Interface ErrDisabled (`VerifyInterfaceErrDisabled`)", "chk_int_err_dis")
            bind_cb("Verify Interface Errors (`VerifyInterfaceErrors`)", "chk_int_err")
            
            bind_cb("Verify Interface IPv4 (`VerifyInterfaceIPv4`)", "chk_int_ipv4")
            if st.session_state["master_test_states"].get("chk_int_ipv4"):
                col1, col2 = st.columns(2)
                with col1: st.text_input("Interface Name", value=st.session_state.get("param_int_v4_name", "Ethernet1"), key="param_int_v4_name")
                with col2: st.text_input("Primary IPv4 CIDR", value=st.session_state.get("param_int_v4_ip", "10.0.0.1/24"), key="param_int_v4_ip")

            bind_cb("Verify Interface Utilization (`VerifyInterfaceUtilization`)", "chk_int_util")
            bind_cb("Verify Interfaces BER (`VerifyInterfacesBER`)", "chk_int_ber")
            bind_cb("Verify Counter Details (`VerifyInterfacesCounterDetails`)", "chk_int_counter_det")
            bind_cb("Verify ECN Counters (`VerifyInterfacesECNCounters`)", "chk_int_ecn")
            bind_cb("Verify Egress Queue Drops (`VerifyInterfacesEgressQueueDrops`)", "chk_int_egress_drop")
            bind_cb("Verify Optics RX Power (`VerifyInterfacesOpticsReceivePower`)", "chk_int_optics_rx")
            bind_cb("Verify Optics Temp (`VerifyInterfacesOpticsTemperature`)", "chk_int_optics_temp")
            bind_cb("Verify PFC Counters (`VerifyInterfacesPFCCounters`)", "chk_int_pfc")
            
            bind_cb("Verify Interfaces Speed (`VerifyInterfacesSpeed`)", "chk_int_speed")
            if st.session_state["master_test_states"].get("chk_int_speed"):
                col1, col2 = st.columns(2)
                with col1: st.text_input("Speed Intf Name", value=st.session_state.get("param_int_speed_name", "Ethernet1"), key="param_int_speed_name")
                with col2: st.number_input("Expected Speed (Mbps)", value=st.session_state.get("param_int_speed_val", 1000), key="param_int_speed_val")

            bind_cb("Verify Interfaces Status (`VerifyInterfacesStatus`)", "chk_int_status")
            if st.session_state["master_test_states"].get("chk_int_status"):
                st.text_input("Target Interfaces (comma-separated)", value=st.session_state.get("param_target_intfs_input", "Ethernet1, Management1"), key="param_target_intfs_input")

            bind_cb("Verify Trident Counters (`VerifyInterfacesTridentCounters`)", "chk_int_trident")
            bind_cb("Verify VoQ Drops (`VerifyInterfacesVoqAndEgressQueueDrops`)", "chk_int_voq")
            bind_cb("Verify Virtual Router MAC (`VerifyIpVirtualRouterMac`)", "chk_int_vrrp_mac")
            if st.session_state["master_test_states"].get("chk_int_vrrp_mac"):
                st.text_input("Virtual Router MAC Address", value=st.session_state.get("param_int_vrrp_mac", "00:1c:73:00:dc:01"), key="param_int_vrrp_mac")
            
            bind_cb("Verify L2 MTU (`VerifyL2MTU`)", "chk_int_l2mtu")
            if st.session_state["master_test_states"].get("chk_int_l2mtu"):
                st.number_input("L2 MTU Value", value=st.session_state.get("param_int_l2mtu_val", 9214), key="param_int_l2mtu_val")

            bind_cb("Verify L3 MTU (`VerifyL3MTU`)", "chk_int_l3mtu")
            if st.session_state["master_test_states"].get("chk_int_l3mtu"):
                st.number_input("L3 MTU Value", value=st.session_state.get("param_int_l3mtu_val", 1500), key="param_int_l3mtu_val")

            bind_cb("Verify LACP Status (`VerifyLACPInterfacesStatus`)", "chk_int_lacp_status")
            if st.session_state["master_test_states"].get("chk_int_lacp_status"):
                render_list_editor("LACP Interfaces", "param_int_lacp_ifaces", [{'name': 'Ethernet1', 'portchannel': 'Port-Channel100'}])
            bind_cb("Verify Loopback Count (`VerifyLoopbackCount`)", "chk_int_loopback")
            if st.session_state["master_test_states"].get("chk_int_loopback"):
                st.number_input("Expected Loopback Count", value=st.session_state.get("param_int_loopback_num", 1), key="param_int_loopback_num")
            bind_cb("Verify Port Channels (`VerifyPortChannels`)", "chk_int_port_channel")
            bind_cb("Verify SVI (`VerifySVI`)", "chk_int_svi")
            bind_cb("Verify Storm Control Drops (`VerifyStormControlDrops`)", "chk_int_storm")

        elif selected_cat == "Logging":
            bind_cb("Verify LANZ Status (`VerifyLANZ`)", "chk_lanz")
            st.divider()
            bind_cb("Verify Logging Accounting (`VerifyLoggingAccounting`)", "chk_log_accounting")
            bind_cb("Verify Logging Entries (`VerifyLoggingEntries`)", "chk_log_entries")
            if st.session_state["master_test_states"].get("chk_log_entries"):
                render_list_editor("Logging Entries", "param_log_entries", [{'regex_match': '.*ACCOUNTING-5-EXEC.*', 'severity_level': 'informational', 'last_number_messages': 10}])
            bind_cb("Verify Logging Errors (`VerifyLoggingErrors`)", "chk_log_errors")
            bind_cb("Verify Logging Hostname (`VerifyLoggingHostname`)", "chk_log_hostname")
            bind_cb("Verify Logging Hosts (`VerifyLoggingHosts`)", "chk_log_hosts")
            if st.session_state["master_test_states"].get("chk_log_hosts"):
                st.text_input("Syslog Server IPs (comma-separated)", value=st.session_state.get("param_log_hosts_list", "10.0.0.1"), key="param_log_hosts_list")
                st.text_input("VRF", value=st.session_state.get("param_log_hosts_vrf", "default"), key="param_log_hosts_vrf")
            bind_cb("Verify Logs Generation (`VerifyLoggingLogsGeneration`)", "chk_log_generation")
            bind_cb("Verify Persistent Logging (`VerifyLoggingPersistent`)", "chk_log_persistent")
            bind_cb("Verify Source Interface (`VerifyLoggingSourceIntf`)", "chk_log_source_intf")
            if st.session_state["master_test_states"].get("chk_log_source_intf"):
                st.text_input("Source Interface", value=st.session_state.get("param_log_src_intf", "Management1"), key="param_log_src_intf")
                st.text_input("VRF", value=st.session_state.get("param_log_src_intf_vrf", "default"), key="param_log_src_intf_vrf")
            bind_cb("Verify Logging Timestamp (`VerifyLoggingTimestamp`)", "chk_log_timestamp")
            bind_cb("Verify Syslog Logging (`VerifySyslogLogging`)", "chk_log_syslog")

        elif selected_cat == "MLAG_Multicast":
            bind_cb("Verify MLAG Config Sanity (`VerifyMlagConfigSanity`)", "chk_mlag_config_sanity")
            bind_cb("Verify MLAG Dual Primary (`VerifyMlagDualPrimary`)", "chk_mlag_dual_primary")
            if st.session_state["master_test_states"].get("chk_mlag_dual_primary"):
                st.number_input("Detection Delay (sec)", value=st.session_state.get("param_mlag_dp_delay", 200), key="param_mlag_dp_delay")
                st.checkbox("Errdisable Interfaces on Detection", value=st.session_state.get("param_mlag_dp_errdisabled", False), key="param_mlag_dp_errdisabled")
                st.number_input("Recovery Delay (sec)", value=st.session_state.get("param_mlag_dp_recovery", 60), key="param_mlag_dp_recovery")
                st.number_input("Recovery Delay Non-MLAG (sec)", value=st.session_state.get("param_mlag_dp_recovery_non", 60), key="param_mlag_dp_recovery_non")
            bind_cb("Verify MLAG Interfaces (`VerifyMlagInterfaces`)", "chk_mlag_interfaces")
            bind_cb("Verify MLAG Primary Priority (`VerifyMlagPrimaryPriority`)", "chk_mlag_priority")
            if st.session_state["master_test_states"].get("chk_mlag_priority"):
                st.number_input("Expected Primary Priority", value=st.session_state.get("param_mlag_primary_prio", 32760), key="param_mlag_primary_prio")
            
            bind_cb("Verify MLAG Reload Delay (`VerifyMlagReloadDelay`)", "chk_mlag_reload_delay")
            if st.session_state["master_test_states"].get("chk_mlag_reload_delay"):
                col1, col2 = st.columns(2)
                with col1: st.number_input("Reload Delay (sec)", value=st.session_state.get("param_mlag_delay", 300), key="param_mlag_delay")
                with col2: st.number_input("Non-MLAG Delay (sec)", value=st.session_state.get("param_mlag_non_delay", 330), key="param_mlag_non_delay")

            bind_cb("Verify MLAG Status (`VerifyMlagStatus`)", "chk_mlag_status")
            st.divider()
            bind_cb("Verify IGMP Snooping Global (`VerifyIGMPSnoopingGlobal`)", "chk_igmp_snooping_global")
            if st.session_state["master_test_states"].get("chk_igmp_snooping_global"):
                st.checkbox("IGMP Snooping Enabled", value=st.session_state.get("param_igmp_global_enabled", True), key="param_igmp_global_enabled")
            bind_cb("Verify IGMP Snooping VLANs (`VerifyIGMPSnoopingVlans`)", "chk_igmp_snooping_vlans")
            if st.session_state["master_test_states"].get("chk_igmp_snooping_vlans"):
                render_list_editor("IGMP Snooping VLANs", "param_igmp_vlans", [{'vlan_id': 10, 'enabled': True}])

        elif selected_cat == "Path_Profiles":
            bind_cb("Verify Paths Health (`VerifyPathsHealth`)", "chk_path_sel_health")
            bind_cb("Verify Specific Path (`VerifySpecificPath`)", "chk_path_sel_specific")
            if st.session_state["master_test_states"].get("chk_path_sel_specific"):
                render_list_editor("DPS Paths", "param_path_sel_paths", [{'peer': '10.255.0.1', 'path_group': 'internet', 'source_address': '100.64.3.2', 'destination_address': '100.64.1.2'}])
            st.divider()
            bind_cb("Verify TCAM Profile (`VerifyTcamProfile`)", "chk_tcam_profile")
            if st.session_state["master_test_states"].get("chk_tcam_profile"):
                st.text_input("Expected TCAM Profile", value=st.session_state.get("param_tcam_profile", "default"), key="param_tcam_profile")
            bind_cb("Verify Unified Forwarding Table Mode (`VerifyUnifiedForwardingTableMode`)", "chk_uft_mode")
            if st.session_state["master_test_states"].get("chk_uft_mode"):
                st.text_input("Expected UFT Mode (0-4 or flexible)", value=st.session_state.get("param_uft_mode", "flexible"), key="param_uft_mode")

        elif selected_cat == "PTP":
            bind_cb("Verify PTP Grandmaster (`VerifyPtpGMStatus`)", "chk_ptp_gm")
            if st.session_state["master_test_states"].get("chk_ptp_gm"):
                st.text_input("Expected Grandmaster ID", value=st.session_state.get("param_ptp_gmid", "0xEC:46:70:FF:FE:00:00:00"), key="param_ptp_gmid")
            bind_cb("Verify PTP Lock Status (`VerifyPtpLockStatus`)", "chk_ptp_lock")
            bind_cb("Verify PTP Mode Status (`VerifyPtpModeStatus`)", "chk_ptp_mode")
            bind_cb("Verify PTP Offset (`VerifyPtpOffset`)", "chk_ptp_offset")
            bind_cb("Verify PTP Port Mode (`VerifyPtpPortModeStatus`)", "chk_ptp_port_mode")

        elif selected_cat == "BGP":
            bind_cb("Verify BGP Adv Communities (`VerifyBGPAdvCommunities`)", "chk_bgp_adv_communities")
            if st.session_state["master_test_states"].get("chk_bgp_adv_communities"):
                render_list_editor("BGP Peers", "param_bgp_advcomm_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            bind_cb("Verify BGP Exchanged Routes (`VerifyBGPExchangedRoutes`)", "chk_bgp_exchanged_routes")
            if st.session_state["master_test_states"].get("chk_bgp_exchanged_routes"):
                render_list_editor("BGP Peers (routes as CIDR, comma-separated within cell)", "param_bgp_exch_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'advertised_routes': '10.0.0.0/24', 'received_routes': '10.0.1.0/24'}])
            bind_cb("Verify BGP NLRI Acceptance (`VerifyBGPNlriAcceptance`)", "chk_bgp_nlri")
            if st.session_state["master_test_states"].get("chk_bgp_nlri"):
                render_list_editor("BGP Peers (capabilities comma-separated within cell)", "param_bgp_nlri_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'capabilities': 'ipv4Unicast'}])
            bind_cb("Verify BGP Peer ASN Cap (`VerifyBGPPeerASNCap`)", "chk_bgp_asn_cap")
            if st.session_state["master_test_states"].get("chk_bgp_asn_cap"):
                render_list_editor("BGP Peers", "param_bgp_asncap_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            
            bind_cb("Verify BGP Peer Count (`VerifyBGPPeerCount`)", "chk_bgp_peer_count")
            if st.session_state["master_test_states"].get("chk_bgp_peer_count"):
                col1, col2 = st.columns(2)
                with col1: st.text_input("BGP VRF Name", value=st.session_state.get("param_bgp_cnt_vrf", "default"), key="param_bgp_cnt_vrf")
                with col2: st.number_input("Expected Peer Count", value=st.session_state.get("param_bgp_cnt_num", 2), key="param_bgp_cnt_num")

            bind_cb("Verify BGP Peer Drop Stats (`VerifyBGPPeerDropStats`)", "chk_bgp_drop_stats")
            if st.session_state["master_test_states"].get("chk_bgp_drop_stats"):
                render_list_editor("BGP Peers", "param_bgp_dropstats_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            bind_cb("Verify BGP Peer Group (`VerifyBGPPeerGroup`)", "chk_bgp_peer_group")
            if st.session_state["master_test_states"].get("chk_bgp_peer_group"):
                render_list_editor("BGP Peers", "param_bgp_peergroup_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'peer_group': 'PG-SPINE'}])
            bind_cb("Verify BGP Peer MD5 Auth (`VerifyBGPPeerMD5Auth`)", "chk_bgp_md5")
            if st.session_state["master_test_states"].get("chk_bgp_md5"):
                render_list_editor("BGP Peers", "param_bgp_md5_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            bind_cb("Verify BGP Peer MP Caps (`VerifyBGPPeerMPCaps`)", "chk_bgp_mp_caps")
            if st.session_state["master_test_states"].get("chk_bgp_mp_caps"):
                render_list_editor("BGP Peers (capabilities comma-separated within cell)", "param_bgp_mpcaps_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'capabilities': 'ipv4Unicast'}])
            bind_cb("Verify BGP Peer Route Limit (`VerifyBGPPeerRouteLimit`)", "chk_bgp_peer_route_limit")
            if st.session_state["master_test_states"].get("chk_bgp_peer_route_limit"):
                render_list_editor("BGP Peers", "param_bgp_routelimit_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'maximum_routes': 12000, 'warning_limit': 10000}])
            bind_cb("Verify BGP Peer Refresh Cap (`VerifyBGPPeerRouteRefreshCap`)", "chk_bgp_refresh_cap")
            if st.session_state["master_test_states"].get("chk_bgp_refresh_cap"):
                render_list_editor("BGP Peers", "param_bgp_refresh_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            bind_cb("Verify BGP Peer Session (`VerifyBGPPeerSession`)", "chk_bgp_peer_session")
            if st.session_state["master_test_states"].get("chk_bgp_peer_session"):
                render_list_editor("BGP Peers", "param_bgp_session_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            bind_cb("Verify BGP Peer Session RIBD (`VerifyBGPPeerSessionRibd`)", "chk_bgp_peer_session_ribd")
            if st.session_state["master_test_states"].get("chk_bgp_peer_session_ribd"):
                render_list_editor("BGP Peers", "param_bgp_session_ribd_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            bind_cb("Verify BGP Peer TTL (`VerifyBGPPeerTtlMultiHops`)", "chk_bgp_ttl")
            if st.session_state["master_test_states"].get("chk_bgp_ttl"):
                render_list_editor("BGP Peers", "param_bgp_ttl_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'ttl': 1, 'max_ttl_hops': 1}])
            bind_cb("Verify BGP Update Errors (`VerifyBGPPeerUpdateErrors`)", "chk_bgp_update_errors")
            if st.session_state["master_test_states"].get("chk_bgp_update_errors"):
                render_list_editor("BGP Peers", "param_bgp_updateerr_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])
            bind_cb("Verify BGP Peers Health (`VerifyBGPPeersHealth`)", "chk_bgp_health")
            if st.session_state["master_test_states"].get("chk_bgp_health"):
                render_list_editor("Address Families", "param_bgp_health_afs", [{'afi': 'ipv4', 'safi': 'unicast', 'vrf': 'default'}])
            bind_cb("Verify BGP Peers Health RIBD (`VerifyBGPPeersHealthRibd`)", "chk_bgp_health_ribd")
            bind_cb("Verify BGP Redistribution (`VerifyBGPRedistribution`)", "chk_bgp_redistribution")
            bind_cb("Verify BGP Route ECMP (`VerifyBGPRouteECMP`)", "chk_bgp_ecmp")
            if st.session_state["master_test_states"].get("chk_bgp_ecmp"):
                render_list_editor("BGP Routes", "param_bgp_ecmp_routes", [{'prefix': '10.0.0.0/24', 'vrf': 'default', 'ecmp_count': 2}])
            bind_cb("Verify BGP Route Paths (`VerifyBGPRoutePaths`)", "chk_bgp_route_paths")
            if st.session_state["master_test_states"].get("chk_bgp_route_paths"):
                render_list_editor("BGP Routes (path nexthops, comma-separated within cell; origin fixed to Igp)", "param_bgp_route_paths", [{'prefix': '10.0.0.0/24', 'vrf': 'default', 'paths_nexthop': '10.0.0.1'}])
            
            bind_cb("Verify BGP Specific Peers (`VerifyBGPSpecificPeers`)", "chk_bgp_specific_peers")
            if st.session_state["master_test_states"].get("chk_bgp_specific_peers"):
                col1, col2 = st.columns(2)
                with col1: st.text_input("Neighbor Address(es) (comma-separated)", value=st.session_state.get("param_bgp_spec_ip", "10.0.0.2"), key="param_bgp_spec_ip")
                with col2: st.text_input("Neighbor VRF", value=st.session_state.get("param_bgp_spec_vrf", "default"), key="param_bgp_spec_vrf")

            bind_cb("Verify BGP Timers (`VerifyBGPTimers`)", "chk_bgp_timers")
            if st.session_state["master_test_states"].get("chk_bgp_timers"):
                render_list_editor("BGP Peers", "param_bgp_timers_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'hold_time': 180, 'keep_alive_time': 60}])
            bind_cb("Verify BGP Route Maps (`VerifyBgpRouteMaps`)", "chk_bgp_route_maps")
            if st.session_state["master_test_states"].get("chk_bgp_route_maps"):
                render_list_editor("BGP Peers", "param_bgp_routemaps_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'inbound_route_map': 'RM-IN', 'outbound_route_map': 'RM-OUT'}])
            bind_cb("Verify EVPN Type 2 Route (`VerifyEVPNType2Route`)", "chk_bgp_evpn_type2")
            if st.session_state["master_test_states"].get("chk_bgp_evpn_type2"):
                render_list_editor("VXLAN Endpoints", "param_bgp_evpn2_endpoints", [{'address': '192.168.20.102', 'vni': 10020}])

        elif selected_cat == "Routing_Generic":
            bind_cb("Verify IPv4 Route Next Hops (`VerifyIPv4RouteNextHops`)", "chk_rt_nexthops")
            if st.session_state["master_test_states"].get("chk_rt_nexthops"):
                col1, col2 = st.columns(2)
                with col1: st.text_input("Target Prefix", value=st.session_state.get("param_rt_nh_prefix", "10.0.0.0/24"), key="param_rt_nh_prefix")
                with col2: st.text_input("Expected Next Hops (comma-separated)", value=st.session_state.get("param_rt_nh_ips", "10.100.0.1"), key="param_rt_nh_ips")

            bind_cb("Verify IPv4 Route Presence Per Prefix (`VerifyIPv4RoutePresencePerPrefix`)", "chk_rt_presence_prefix")
            if st.session_state["master_test_states"].get("chk_rt_presence_prefix"):
                st.text_input("Prefixes to check (comma-separated)", value=st.session_state.get("param_rt_pres_prefixes", "10.0.0.0/24"), key="param_rt_pres_prefixes")

            bind_cb("Verify IPv4 Route Presence Per VRF (`VerifyIPv4RoutePresencePerVRF`)", "chk_rt_presence_vrf")
            if st.session_state["master_test_states"].get("chk_rt_presence_vrf"):
                render_list_editor("Route Entries", "param_rt_pervrf_entries", [{'prefix': '10.0.0.0/24', 'vrf': 'default'}])
            bind_cb("Verify IPv4 Route Type (`VerifyIPv4RouteType`)", "chk_rt_route_type")
            if st.session_state["master_test_states"].get("chk_rt_route_type"):
                render_list_editor("Route Entries", "param_rt_type_entries", [{'prefix': '10.0.0.0/24', 'vrf': 'default', 'route_type': 'connected'}])
            bind_cb("Verify Routing Protocol Model (`VerifyRoutingProtocolModel`)", "chk_rt_model")
            bind_cb("Verify Routing Status (`VerifyRoutingStatus`)", "chk_rt_status")
            
            bind_cb("Verify Routing Table Size (`VerifyRoutingTableSize`)", "chk_rt_size")
            if st.session_state["master_test_states"].get("chk_rt_size"):
                col1, col2 = st.columns(2)
                with col1: st.number_input("Minimum Routes", value=st.session_state.get("param_rt_sz_min", 1), key="param_rt_sz_min")
                with col2: st.number_input("Maximum Routes", value=st.session_state.get("param_rt_sz_max", 10000), key="param_rt_sz_max")

            st.divider()
            bind_cb("Verify ISIS Graceful Restart (`VerifyISISGracefulRestart`)", "chk_isis_graceful")
            if st.session_state["master_test_states"].get("chk_isis_graceful"):
                render_list_editor("IS-IS Instances", "param_isis_graceful_inst", [{'name': 'CORE-ISIS', 'vrf': 'default', 'graceful_restart': True, 'graceful_restart_helper': True}])
            bind_cb("Verify ISIS Interface Mode (`VerifyISISInterfaceMode`)", "chk_isis_intf_mode")
            if st.session_state["master_test_states"].get("chk_isis_intf_mode"):
                render_list_editor("IS-IS Interfaces", "param_isis_intfmode", [{'name': 'Ethernet1', 'vrf': 'default', 'mode': 'point-to-point'}])
            bind_cb("Verify ISIS Neighbor Count (`VerifyISISNeighborCount`)", "chk_isis_neighbor_cnt")
            if st.session_state["master_test_states"].get("chk_isis_neighbor_cnt"):
                render_list_editor("IS-IS Interfaces", "param_isis_neighbor_cnt", [{'name': 'Ethernet1', 'vrf': 'default', 'count': 1}])
            bind_cb("Verify ISIS Neighbor State (`VerifyISISNeighborState`)", "chk_isis_neighbor_state")
            bind_cb("Verify ISIS SR Adj (`VerifyISISSegmentRoutingAdjacencySegments`)", "chk_isis_sr_adj")
            if st.session_state["master_test_states"].get("chk_isis_sr_adj"):
                render_list_editor("IS-IS Instances", "param_isis_sr_adj_inst", [{'name': 'CORE-ISIS', 'vrf': 'default'}])
            bind_cb("Verify ISIS SR Dataplane (`VerifyISISSegmentRoutingDataplane`)", "chk_isis_sr_dataplane")
            if st.session_state["master_test_states"].get("chk_isis_sr_dataplane"):
                render_list_editor("IS-IS Instances", "param_isis_sr_dp_inst", [{'name': 'CORE-ISIS', 'vrf': 'default', 'dataplane': 'MPLS'}])
            bind_cb("Verify ISIS SR Tunnels (`VerifyISISSegmentRoutingTunnels`)", "chk_isis_sr_tunnels")
            if st.session_state["master_test_states"].get("chk_isis_sr_tunnels"):
                render_list_editor("Tunnels", "param_isis_sr_tunnels", [{'endpoint': '1.0.0.122/32'}])
            st.divider()
            bind_cb("Verify OSPF Max LSA (`VerifyOSPFMaxLSA`)", "chk_ospf_max_lsa")
            bind_cb("Verify OSPF Neighbor Count (`VerifyOSPFNeighborCount`)", "chk_ospf_neighbor_cnt")
            if st.session_state["master_test_states"].get("chk_ospf_neighbor_cnt"):
                st.number_input("Expected Neighbor Count (FULL state)", value=st.session_state.get("param_ospf_neighbor_cnt", 1), key="param_ospf_neighbor_cnt")
            bind_cb("Verify OSPF Neighbor State (`VerifyOSPFNeighborState`)", "chk_ospf_neighbor_state")
            bind_cb("Verify OSPF Specific Neighbors (`VerifyOSPFSpecificNeighbors`)", "chk_ospf_specific_neighbors")
            if st.session_state["master_test_states"].get("chk_ospf_specific_neighbors"):
                render_list_editor("OSPF Neighbors", "param_ospf_specific_neighbors", [{'instance': 100, 'vrf': 'default', 'ip_address': '10.1.255.46', 'local_interface': 'Ethernet2', 'area_id': '0', 'state': 'full'}])

        elif selected_cat == "Security":
            bind_cb("Verify API HTTP Status (`VerifyAPIHttpStatus`)", "chk_sec_api_http")
            bind_cb("Verify API HTTPS SSL (`VerifyAPIHttpsSSL`)", "chk_sec_api_https_ssl")
            if st.session_state["master_test_states"].get("chk_sec_api_https_ssl"):
                st.text_input("eAPI HTTPS SSL Profile", value=st.session_state.get("param_sec_https_profile", "eAPI_SSL_Profile"), key="param_sec_https_profile")
            bind_cb("Verify API IPv4 ACL (`VerifyAPIIPv4Acl`)", "chk_sec_api_v4_acl")
            if st.session_state["master_test_states"].get("chk_sec_api_v4_acl"):
                st.number_input("Expected IPv4 ACL Count", value=st.session_state.get("param_sec_api_v4_num", 1), key="param_sec_api_v4_num")
                st.text_input("VRF", value=st.session_state.get("param_sec_api_v4_vrf", "default"), key="param_sec_api_v4_vrf")
            bind_cb("Verify API IPv6 ACL (`VerifyAPIIPv6Acl`)", "chk_sec_api_v6_acl")
            if st.session_state["master_test_states"].get("chk_sec_api_v6_acl"):
                st.number_input("Expected IPv6 ACL Count", value=st.session_state.get("param_sec_api_v6_num", 1), key="param_sec_api_v6_num")
                st.text_input("VRF", value=st.session_state.get("param_sec_api_v6_vrf", "default"), key="param_sec_api_v6_vrf")
            bind_cb("Verify SSL Cert (`VerifyAPISSLCertificate`)", "chk_sec_ssl_cert")
            if st.session_state["master_test_states"].get("chk_sec_ssl_cert"):
                render_list_editor("SSL Certificates", "param_sec_ssl_certs", [{'certificate_name': 'ARISTA_SIGNING_CA.crt', 'expiry_threshold': 30, 'common_name': 'Arista Networks Internal IT CA', 'encryption_algorithm': 'RSA', 'key_size': 2048}])
            bind_cb("Verify Login Banner (`VerifyBannerLogin`)", "chk_sec_banner_login")
            if st.session_state["master_test_states"].get("chk_sec_banner_login"):
                st.text_input("Expected Login Banner", value=st.session_state.get("param_sec_banner_login_text", "Authorized Access Only"), key="param_sec_banner_login_text")
            bind_cb("Verify MOTD Banner (`VerifyBannerMotd`)", "chk_sec_banner_motd")
            if st.session_state["master_test_states"].get("chk_sec_banner_motd"):
                st.text_input("Expected MOTD Banner", value=st.session_state.get("param_sec_banner_motd_text", "Welcome"), key="param_sec_banner_motd_text")
            bind_cb("Verify Hardware Entropy (`VerifyHardwareEntropy`)", "chk_sec_entropy")
            bind_cb("Verify IPSec Health (`VerifyIPSecConnHealth`)", "chk_sec_ipsec_health")
            
            bind_cb("Verify IPv4 ACL (`VerifyIPv4ACL`)", "chk_sec_v4_acl")
            if st.session_state["master_test_states"].get("chk_sec_v4_acl"):
                col1, col2, col3 = st.columns(3)
                with col1: st.text_input("IPv4 Access List Name", value=st.session_state.get("param_sec_v4_acl_name", "ACL-MGMT"), key="param_sec_v4_acl_name")
                with col2: st.number_input("Entry Sequence", value=st.session_state.get("param_sec_v4_seq", 10), key="param_sec_v4_seq")
                with col3: st.selectbox("Action", ["permit", "deny"], key="param_sec_v4_act")

            bind_cb("Verify SSH FIPS (`VerifySSHFIPSRestrictions`)", "chk_sec_fips")
            bind_cb("Verify SSH IPv4 ACL (`VerifySSHIPv4Acl`)", "chk_sec_ssh_v4_acl")
            if st.session_state["master_test_states"].get("chk_sec_ssh_v4_acl"):
                st.number_input("Expected IPv4 ACL Count", value=st.session_state.get("param_sec_ssh_v4_num", 1), key="param_sec_ssh_v4_num")
                st.text_input("VRF", value=st.session_state.get("param_sec_ssh_v4_vrf", "default"), key="param_sec_ssh_v4_vrf")
            bind_cb("Verify SSH IPv6 ACL (`VerifySSHIPv6Acl`)", "chk_sec_ssh_v6_acl")
            if st.session_state["master_test_states"].get("chk_sec_ssh_v6_acl"):
                st.number_input("Expected IPv6 ACL Count", value=st.session_state.get("param_sec_ssh_v6_num", 1), key="param_sec_ssh_v6_num")
                st.text_input("VRF", value=st.session_state.get("param_sec_ssh_v6_vrf", "default"), key="param_sec_ssh_v6_vrf")
            bind_cb("Verify SSH Status (`VerifySSHStatus`)", "chk_ssh_status")
            bind_cb("Verify Specific IPSec (`VerifySpecificIPSecConn`)", "chk_sec_ipsec_specific")
            if st.session_state["master_test_states"].get("chk_sec_ipsec_specific"):
                render_list_editor("IPSec Peers", "param_sec_ipsec_conns", [{'peer': '10.0.0.1', 'vrf': 'default'}])
            bind_cb("Verify Telnet Status (`VerifyTelnetStatus`)", "chk_sec_telnet")

        elif selected_cat == "Services":
            bind_cb("Verify DNS Lookup (`VerifyDNSLookup`)", "chk_svc_dns_lookup")
            if st.session_state["master_test_states"].get("chk_svc_dns_lookup"):
                st.text_input("Domains to Resolve (comma-separated)", value=st.session_state.get("param_svc_dns_domains", "arista.com"), key="param_svc_dns_domains")

            bind_cb("Verify DNS Servers (`VerifyDNSServers`)", "chk_svc_dns_servers")
            if st.session_state["master_test_states"].get("chk_svc_dns_servers"):
                col1, col2, col3 = st.columns(3)
                with col1: st.text_input("DNS Server IPs (comma-separated)", value=st.session_state.get("param_svc_dns_ips", "8.8.8.8"), key="param_svc_dns_ips")
                with col2: st.text_input("VRF", value=st.session_state.get("param_svc_dns_vrf", "default"), key="param_svc_dns_vrf")
                with col3: st.number_input("Priority", value=st.session_state.get("param_svc_dns_prio", 1), key="param_svc_dns_prio")

            bind_cb("Verify Errdisable Recovery (`VerifyErrdisableRecovery`)", "chk_svc_errdisable_rec")
            if st.session_state["master_test_states"].get("chk_svc_errdisable_rec"):
                render_list_editor("Errdisable Reasons", "param_svc_errdisable_reasons", [{'reason': 'acl', 'interval': 30, 'status': 'Enabled'}])
            
            bind_cb("Verify Hostname (`VerifyHostname`)", "chk_hostname")
            if st.session_state["master_test_states"].get("chk_hostname"):
                st.text_input("Expected Hostname", value=st.session_state.get("param_service_hostname", "Switch-1"), key="param_service_hostname")

        elif selected_cat == "SNMP":
            bind_cb("Verify SNMP Contact (`VerifySnmpContact`)", "chk_snmp_contact")
            if st.session_state["master_test_states"].get("chk_snmp_contact"):
                st.text_input("Expected Contact Email/String", value=st.session_state.get("param_snmp_contact_val", "admin@domain.com"), key="param_snmp_contact_val")

            bind_cb("Verify SNMP Errors (`VerifySnmpErrorCounters`)", "chk_snmp_errors")
            bind_cb("Verify SNMP Group (`VerifySnmpGroup`)", "chk_snmp_group")
            if st.session_state["master_test_states"].get("chk_snmp_group"):
                render_list_editor("SNMP Groups", "param_snmp_groups", [{'group_name': 'GROUP1', 'version': 'v2c'}])
            bind_cb("Verify SNMP Logging (`VerifySnmpHostLogging`)", "chk_snmp_logging")
            if st.session_state["master_test_states"].get("chk_snmp_logging"):
                render_list_editor("SNMP Hosts", "param_snmp_log_hosts", [{'hostname': '192.168.1.100', 'vrf': 'default'}])
            
            bind_cb("Verify SNMP IPv4 ACL (`VerifySnmpIPv4Acl`)", "chk_snmp_v4_acl")
            if st.session_state["master_test_states"].get("chk_snmp_v4_acl"):
                col1, col2 = st.columns(2)
                with col1: st.number_input("SNMP IPv4 ACL Number", value=st.session_state.get("param_snmp_v4_acl_num", 10), key="param_snmp_v4_acl_num")
                with col2: st.text_input("VRF", value=st.session_state.get("param_snmp_v4_acl_vrf", "default"), key="param_snmp_v4_acl_vrf")

            bind_cb("Verify SNMP IPv6 ACL (`VerifySnmpIPv6Acl`)", "chk_snmp_v6_acl")
            if st.session_state["master_test_states"].get("chk_snmp_v6_acl"):
                col1, col2 = st.columns(2)
                with col1: st.number_input("SNMP IPv6 ACL Number", value=st.session_state.get("param_snmp_v6_acl_num", 10), key="param_snmp_v6_acl_num")
                with col2: st.text_input("VRF", value=st.session_state.get("param_snmp_v6_acl_vrf", "default"), key="param_snmp_v6_acl_vrf")

            bind_cb("Verify SNMP Location (`VerifySnmpLocation`)", "chk_snmp_location")
            if st.session_state["master_test_states"].get("chk_snmp_location"):
                st.text_input("Expected Location String", value=st.session_state.get("param_snmp_location_val", "DataCenter-Rack1"), key="param_snmp_location_val")

            bind_cb("Verify SNMP Notification (`VerifySnmpNotificationHost`)", "chk_snmp_notification")
            if st.session_state["master_test_states"].get("chk_snmp_notification"):
                render_list_editor("SNMP Notification Hosts", "param_snmp_notif_hosts", [{'hostname': '192.168.1.100', 'vrf': 'default', 'notification_type': 'trap', 'version': 'v2c', 'community_string': 'public'}])
            bind_cb("Verify SNMP PDU (`VerifySnmpPDUCounters`)", "chk_snmp_pdu")
            bind_cb("Verify SNMP Source Intf (`VerifySnmpSourceInterface`)", "chk_snmp_source")
            if st.session_state["master_test_states"].get("chk_snmp_source"):
                render_list_editor("Source Interfaces", "param_snmp_src_ifaces", [{'interface': 'Management1', 'vrf': 'default'}])
            
            bind_cb("Verify SNMP Status (`VerifySnmpStatus`)", "chk_snmp_status")
            if st.session_state["master_test_states"].get("chk_snmp_status"):
                st.text_input("SNMP VRF", value=st.session_state.get("param_snmp_vrf", "default"), key="param_snmp_vrf")

            bind_cb("Verify SNMP User (`VerifySnmpUser`)", "chk_snmp_user")
            if st.session_state["master_test_states"].get("chk_snmp_user"):
                render_list_editor("SNMP Users", "param_snmp_users", [{'username': 'snmp-user', 'group_name': 'GROUP1', 'version': 'v3', 'auth_type': 'MD5', 'priv_type': 'AES-128'}])

        elif selected_cat == "Software":
            bind_cb("Verify EOS Extensions (`VerifyEOSExtensions`)", "chk_sw_extensions")
            
            bind_cb("Verify EOS Version (`VerifyEOSVersion`)", "chk_sw_version")
            if st.session_state["master_test_states"].get("chk_sw_version"):
                st.text_input("Expected EOS Version", value=st.session_state.get("param_sw_ver", "4.30.2F"), key="param_sw_ver")
            
            bind_cb("Verify TerminAttr Version (`VerifyTerminAttrVersion`)", "chk_sw_terminattr")
            if st.session_state["master_test_states"].get("chk_sw_terminattr"):
                st.text_input("Expected TerminAttr Version", value=st.session_state.get("param_sw_terminattr_ver", "1.28.0"), key="param_sw_terminattr_ver")

        elif selected_cat == "STP":
            bind_cb("Verify STP Blocked Ports (`VerifySTPBlockedPorts`)", "chk_stp_blocked")
            bind_cb("Verify STP Counters (`VerifySTPCounters`)", "chk_stp_counters")
            bind_cb("Verify STP Disabled VLANs (`VerifySTPDisabledVlans`)", "chk_stp_disabled_vlans")
            if st.session_state["master_test_states"].get("chk_stp_disabled_vlans"):
                st.text_input("Disabled VLAN IDs (comma-separated)", value=st.session_state.get("param_stp_disabled_vlans", "10, 20"), key="param_stp_disabled_vlans")
            bind_cb("Verify STP Forwarding Ports (`VerifySTPForwardingPorts`)", "chk_stp_forwarding")
            if st.session_state["master_test_states"].get("chk_stp_forwarding"):
                st.text_input("VLAN IDs to Verify Forwarding (comma-separated)", value=st.session_state.get("param_stp_forwarding_vlans", "10, 20"), key="param_stp_forwarding_vlans")
            bind_cb("Verify STP Mode (`VerifySTPMode`)", "chk_stp_mode")
            if st.session_state["master_test_states"].get("chk_stp_mode"):
                st.selectbox("STP Mode", ['mstp', 'rstp', 'rapidPvst'], key="param_stp_mode_val")
                st.text_input("VLAN IDs to Verify Mode (comma-separated)", value=st.session_state.get("param_stp_mode_vlans", "10, 20"), key="param_stp_mode_vlans")
            bind_cb("Verify STP Root Priority (`VerifySTPRootPriority`)", "chk_stp_root_priority")
            if st.session_state["master_test_states"].get("chk_stp_root_priority"):
                st.number_input("Expected Root Priority", value=st.session_state.get("param_stp_root_priority", 32768), key="param_stp_root_priority")
                st.text_input("VLAN/MST Instance IDs (empty = all) (comma-separated)", value=st.session_state.get("param_stp_root_instances", ""), key="param_stp_root_instances")
            bind_cb("Verify STP Topology Changes (`VerifyStpTopologyChanges`)", "chk_stp_tc")
            if st.session_state["master_test_states"].get("chk_stp_tc"):
                st.number_input("Max Allowed Topology Changes", value=st.session_state.get("param_stp_tc_threshold", 10), key="param_stp_tc_threshold")

        elif selected_cat == "STUN":
            bind_cb("Verify STUN Client (`VerifyStunClient`)", "chk_stun_client")
            if st.session_state["master_test_states"].get("chk_stun_client"):
                render_list_editor("STUN Clients", "param_stun_client_list", [{'source_address': '172.18.3.2', 'public_address': '172.18.3.21', 'source_port': 4500, 'public_port': 6006}])
            bind_cb("Verify STUN Client Translation (`VerifyStunClientTranslation`)", "chk_stun_client_trans")
            if st.session_state["master_test_states"].get("chk_stun_client_trans"):
                render_list_editor("STUN Clients", "param_stun_client_trans_list", [{'source_address': '172.18.3.2', 'public_address': '172.18.3.21', 'source_port': 4500, 'public_port': 6006}])
            
            bind_cb("Verify STUN Server (`VerifyStunServer`)", "chk_stun_status")

        elif selected_cat == "System":
            bind_cb("Verify Agent Logs (`VerifyAgentLogs`)", "chk_sys_agent_logs")
            bind_cb("Verify CPU Utilization (`VerifyCPUUtilization`)", "chk_sys_cpu")
            bind_cb("Verify Coredump (`VerifyCoredump`)", "chk_sys_coredump")
            bind_cb("Verify File Presence (`VerifyFilePresence`)", "chk_sys_file_presence")
            if st.session_state["master_test_states"].get("chk_sys_file_presence"):
                st.text_input("Flash Files (comma-separated)", value=st.session_state.get("param_sys_files_val", "flash:/boot-config"), key="param_sys_files_val")

            bind_cb("Verify File System Util (`VerifyFileSystemUtilization`)", "chk_sys_fs_util")
            bind_cb("Verify Flash Util (`VerifyFlashUtilization`)", "chk_sys_flash_util")
            bind_cb("Verify Maintenance (`VerifyMaintenance`)", "chk_sys_maintenance")
            bind_cb("Verify Memory Utilization (`VerifyMemoryUtilization`)", "chk_sys_mem")
            bind_cb("Verify NTP (`VerifyNTP`)", "chk_sys_ntp")
            bind_cb("Verify NTP Associations (`VerifyNTPAssociations`)", "chk_sys_ntp_assoc")
            if st.session_state["master_test_states"].get("chk_sys_ntp_assoc"):
                st.text_input("Expected NTP Servers (comma-separated)", value=st.session_state.get("param_sys_ntp_servers_val", "10.0.0.1"), key="param_sys_ntp_servers_val")

            bind_cb("Verify Reload Cause (`VerifyReloadCause`)", "chk_sys_reload")
            
            bind_cb("Verify Uptime (`VerifyUptime`)", "chk_sys_uptime")
            if st.session_state["master_test_states"].get("chk_sys_uptime"):
                st.number_input("Min Uptime (seconds)", value=st.session_state.get("param_sys_uptime_val", 60), min_value=1, key="param_sys_uptime_val")

        elif selected_cat == "VLAN":
            bind_cb("Verify Dynamic VLAN Source (`VerifyDynamicVlanSource`)", "chk_vlan_dynamic")
            if st.session_state["master_test_states"].get("chk_vlan_dynamic"):
                st.text_input("Dynamic VLAN Sources (comma-separated)", value=st.session_state.get("param_vlan_dyn_sources", "evpn, mlagsync"), key="param_vlan_dyn_sources")
                st.checkbox("Strict Mode", value=st.session_state.get("param_vlan_dyn_strict", False), key="param_vlan_dyn_strict")
            
            bind_cb("Verify Internal VLAN Policy (`VerifyVlanInternalPolicy`)", "chk_vlan_internal")
            if st.session_state["master_test_states"].get("chk_vlan_internal"):
                col1, col2, col3 = st.columns(3)
                with col1: st.selectbox("Policy", ["ascending", "descending"], key="param_vlan_policy")
                with col2: st.number_input("Start VLAN ID", value=st.session_state.get("param_vlan_start", 1006), key="param_vlan_start")
                with col3: st.number_input("End VLAN ID", value=st.session_state.get("param_vlan_end", 4094), key="param_vlan_end")

            bind_cb("Verify VLAN Status (`VerifyVlanStatus`)", "chk_vlan_status")
            if st.session_state["master_test_states"].get("chk_vlan_status"):
                render_list_editor("VLANs", "param_vlan_status_list", [{'vlan_id': 10, 'status': 'active'}])

        elif selected_cat == "Custom":
            st.text_area("Custom YAML Input", value=st.session_state.get("param_custom_yaml", "# anta.tests...\n"), height=250, key="param_custom_yaml")

    # Build Catalog Dictionary for Current Session
    catalog_dict = {}
    parsed_tags = [t.strip() for t in st.session_state.get("input_catalog_tags", "").split(",") if t.strip()]

    def add_test(module, test_name, params=None):
        if module not in catalog_dict: catalog_dict[module] = []
        body = dict(params) if isinstance(params, dict) else {}
        if parsed_tags: body["filters"] = {"tags": parsed_tags}
        catalog_dict[module].append({test_name: body if body else None})

    key_to_test_map = {
        "chk_aaa_authen": ("anta.tests.aaa", "VerifyAuthenMethods", {
            "methods": [m.strip() for m in st.session_state.get("param_aaa_authen_methods", "local").split(",") if m.strip()],
            "types": [st.session_state.get("param_aaa_authen_types", "login")]
        }),
        "chk_aaa_authz": ("anta.tests.aaa", "VerifyAuthzMethods", {
            "methods": [m.strip() for m in st.session_state.get("param_aaa_authz_methods", "group tacacs+").split(",") if m.strip()],
            "types": [st.session_state.get("param_aaa_authz_types", "exec")]
        }),
        "chk_aaa_acct_default": ("anta.tests.aaa", "VerifyAcctDefaultMethods", {
            "methods": [m.strip() for m in st.session_state.get("param_aaa_acct_def_methods", "group tacacs+, local").split(",") if m.strip()],
            "types": [st.session_state.get("param_aaa_acct_def_types", "exec")]
        }),
        "chk_aaa_acct_console": ("anta.tests.aaa", "VerifyAcctConsoleMethods", {
            "methods": [m.strip() for m in st.session_state.get("param_aaa_acct_con_methods", "local").split(",") if m.strip()],
            "types": [st.session_state.get("param_aaa_acct_con_types", "exec")]
        }),
        "chk_aaa_tacacs_src": ("anta.tests.aaa", "VerifyTacacsSourceIntf", {"intf": st.session_state.get("param_aaa_tacacs_intf", "Management1")}),
        "chk_aaa_tacacs_servers": ("anta.tests.aaa", "VerifyTacacsServers", {"servers": [ip.strip() for ip in st.session_state.get("param_aaa_tacacs_ips", "10.1.1.1").split(",") if ip.strip()]}),
        "chk_aaa_tacacs_groups": ("anta.tests.aaa", "VerifyTacacsServerGroups", {"groups": [g.strip() for g in st.session_state.get("param_aaa_tacacs_groups_val", "TACACS-SERVERS").split(",") if g.strip()]}),
        
        "chk_avt_path": ("anta.tests.avt", "VerifyAVTPathHealth", None),
        "chk_avt_role": ("anta.tests.avt", "VerifyAVTRole", {"role": st.session_state.get("param_avt_role_val", "edge")}),
        "chk_avt_specific_path": ("anta.tests.avt", "VerifyAVTSpecificPath", {
            "avt_paths": [{
                "avt_name": st.session_state.get("param_avt_spec_name", "AVT1"),
                "destination": st.session_state.get("param_avt_spec_dest", "10.0.0.1"),
                "next_hop": st.session_state.get("param_avt_spec_next_hop", "10.0.0.2"),
                "vrf": st.session_state.get("param_avt_spec_vrf", "default")
            }]
        }),
        "chk_bfd_health": ("anta.tests.bfd", "VerifyBFDPeersHealth", None),
        "chk_bfd_intervals": ("anta.tests.bfd", "VerifyBFDPeersIntervals", {
            "bfd_peers": [{
                "peer_address": st.session_state.get("param_bfd_int_ip", "10.0.0.1"),
                "vrf": st.session_state.get("param_bfd_int_vrf", "default"),
                "tx_interval": int(st.session_state.get("param_bfd_tx", 300)),
                "rx_interval": int(st.session_state.get("param_bfd_rx", 300)),
                "multiplier": int(st.session_state.get("param_bfd_mult", 3))
            }]
        }),
        "chk_bfd_protocols": ("anta.tests.bfd", "VerifyBFDPeersRegProtocols", {
            "bfd_peers": [{
                "peer_address": st.session_state.get("param_bfd_proto_ip", "10.0.0.1"),
                "vrf": st.session_state.get("param_bfd_proto_vrf", "default"),
                "protocols": [p.strip() for p in st.session_state.get("param_bfd_proto_list", "bgp").split(",") if p.strip()]
            }]
        }),
        "chk_bfd_specific": ("anta.tests.bfd", "VerifyBFDSpecificPeers", {
            "bfd_peers": [{
                "peer_address": st.session_state.get("param_bfd_spec_ip", "10.0.0.1"),
                "vrf": st.session_state.get("param_bfd_spec_vrf", "default")
            }]
        }),

        "chk_cfg_diff": ("anta.tests.configuration", "VerifyRunningConfigDiffs", None),
        "chk_cfg_lines": ("anta.tests.configuration", "VerifyRunningConfigLines", {"regex_patterns": [l.strip() for l in st.session_state.get("param_cfg_lines_regex", "router bgp").split(",") if l.strip()]}),
        "chk_cfg_ztp": ("anta.tests.configuration", "VerifyZeroTouch", None),
        "chk_cfg_banner_login": ("anta.tests.security", "VerifyBannerLogin", {"login_banner": st.session_state.get("param_banner_login_text", "Authorized Access Only")}),
        "chk_cfg_banner_motd": ("anta.tests.security", "VerifyBannerMotd", {"motd_banner": st.session_state.get("param_banner_motd_text", "Welcome")}),

        "chk_conn_lldp": ("anta.tests.connectivity", "VerifyLLDPNeighbors", {
            "neighbors": [{
                "port": st.session_state.get("param_conn_lldp_port", "Ethernet1"),
                "neighbor_device": st.session_state.get("param_conn_lldp_dev", "switch2"),
                "neighbor_port": st.session_state.get("param_conn_lldp_neighbor_port", "Ethernet1")
            }]
        }),
        "chk_conn_ping": ("anta.tests.connectivity", "VerifyReachability", {"hosts": [{"destination": dest.strip()} for dest in st.session_state.get("param_conn_dest", "8.8.8.8").split(",") if dest.strip()]}),

        "chk_cvx_active": ("anta.tests.cvx", "VerifyActiveCVXConnections", {"connections_count": int(st.session_state.get("param_cvx_active_cnt", 1))}),
        "chk_cvx_cluster": ("anta.tests.cvx", "VerifyCVXClusterStatus", {
            "role": st.session_state.get("param_cvx_role", "Master"),
            "peer_status": [{
                "peer_name": st.session_state.get("param_cvx_peer_name", "cvx-red-2"),
                "registration_state": st.session_state.get("param_cvx_reg_state", "Registration complete")
            }]
        }),
        "chk_cvx_mgmt": ("anta.tests.cvx", "VerifyManagementCVX", {"enabled": bool(st.session_state.get("param_cvx_mgmt_enabled", True))}),
        "chk_cvx_client_mounts": ("anta.tests.cvx", "VerifyMcsClientMounts", None),
        "chk_cvx_server_mounts": ("anta.tests.cvx", "VerifyMcsServerMounts", {"connections_count": int(st.session_state.get("param_cvx_mcs_cnt", 1))}),

        "chk_evpn_type5": ("anta.tests.evpn", "VerifyEVPNType5Routes", {"prefixes": [{"address": st.session_state.get("param_evpn_prefix", "10.0.0.0/24"), "vni": int(st.session_state.get("param_evpn_vni", 10010))}]}),
        "chk_fn_fn44": ("anta.tests.field_notices", "VerifyFieldNotice44Resolution", None),
        "chk_fn_fn72": ("anta.tests.field_notices", "VerifyFieldNotice72Resolution", None),
        "chk_flow_tracking": ("anta.tests.flow_tracking", "VerifyHardwareFlowTrackerStatus", {"trackers": [{"name": st.session_state.get("param_flow_tracker_name", "FLOW-TRACKER")}]}),
        "chk_greent_policy": ("anta.tests.greent", "VerifyGreenT", None),
        "chk_greent_counters": ("anta.tests.greent", "VerifyGreenTCounters", None),

        "chk_hw_linecards": ("anta.tests.hardware", "VerifyAbsenceOfLinecards", {"serial_numbers": [sn.strip() for sn in st.session_state.get("param_hw_linecards_sn", "SN12345").split(",") if sn.strip()]}),
        "chk_hw_drops": ("anta.tests.hardware", "VerifyAdverseDrops", None),
        "chk_hw_chassis": ("anta.tests.hardware", "VerifyChassisHealth", None),
        "chk_hw_cooling_fans": ("anta.tests.hardware", "VerifyEnvironmentCooling", {"states": [s.strip() for s in st.session_state.get("param_hw_cooling_states", "ok").split(",") if s.strip()]}),
        "chk_hw_power": ("anta.tests.hardware", "VerifyEnvironmentPower", {"states": ["ok"]}),
        "chk_hw_sys_cooling": ("anta.tests.hardware", "VerifyEnvironmentSystemCooling", None),
        "chk_hw_capacity": ("anta.tests.hardware", "VerifyHardwareCapacityUtilization", None),
        "chk_hw_inventory": ("anta.tests.hardware", "VerifyInventory", None),
        "chk_hw_module": ("anta.tests.hardware", "VerifyModuleStatus", None),
        "chk_hw_pcie": ("anta.tests.hardware", "VerifyPCIeErrors", None),
        "chk_hw_supervisor": ("anta.tests.hardware", "VerifySupervisorRedundancy", None),
        "chk_hw_temp": ("anta.tests.hardware", "VerifyTemperature", None),
        "chk_hw_trans": ("anta.tests.hardware", "VerifyTransceiversManufacturers", {"manufacturers": [m.strip() for m in st.session_state.get("param_hw_mfg", "Arista Networks").split(",") if m.strip()]}),
        "chk_hw_trans_temp": ("anta.tests.hardware", "VerifyTransceiversTemperature", None),

        "chk_int_ipv4": ("anta.tests.interfaces", "VerifyInterfaceIPv4", {"interfaces": [{"name": st.session_state.get("param_int_v4_name", "Ethernet1"), "primary_ip": st.session_state.get("param_int_v4_ip", "10.0.0.1/24")}]}),
        "chk_int_speed": ("anta.tests.interfaces", "VerifyInterfacesSpeed", {"interfaces": [{"name": st.session_state.get("param_int_speed_name", "Ethernet1"), "speed": int(st.session_state.get("param_int_speed_val", 1000))}]}),
        "chk_int_status": ("anta.tests.interfaces", "VerifyInterfacesStatus", {"interfaces": [{"name": i.strip(), "status": "up"} for i in st.session_state.get("param_target_intfs_input", "Ethernet1").split(",") if i.strip()]}),
        "chk_int_l2mtu": ("anta.tests.interfaces", "VerifyL2MTU", {"mtu": int(st.session_state.get("param_int_l2mtu_val", 9214))}),
        "chk_int_l3mtu": ("anta.tests.interfaces", "VerifyL3MTU", {"mtu": int(st.session_state.get("param_int_l3mtu_val", 1500))}),

        "chk_sw_extensions": ("anta.tests.software", "VerifyEOSExtensions", None),
        "chk_sw_version": ("anta.tests.software", "VerifyEOSVersion", {"versions": [st.session_state.get("param_sw_ver", "4.30.2F")]}),
        "chk_sw_terminattr": ("anta.tests.software", "VerifyTerminAttrVersion", {"versions": [st.session_state.get("param_sw_terminattr_ver", "1.28.0")]}),

        "chk_sys_agent_logs": ("anta.tests.system", "VerifyAgentLogs", None),
        "chk_sys_cpu": ("anta.tests.system", "VerifyCPUUtilization", None),
        "chk_sys_coredump": ("anta.tests.system", "VerifyCoredump", None),
        "chk_sys_file_presence": ("anta.tests.system", "VerifyFilePresence", {"filenames": [f.strip() for f in st.session_state.get("param_sys_files_val", "flash:/boot-config").split(",") if f.strip()]}),
        "chk_sys_fs_util": ("anta.tests.system", "VerifyFileSystemUtilization", None),
        "chk_sys_flash_util": ("anta.tests.system", "VerifyFlashUtilization", None),
        "chk_sys_maintenance": ("anta.tests.system", "VerifyMaintenance", None),
        "chk_sys_mem": ("anta.tests.system", "VerifyMemoryUtilization", None),
        "chk_sys_ntp": ("anta.tests.system", "VerifyNTP", None),
        "chk_sys_ntp_assoc": ("anta.tests.system", "VerifyNTPAssociations", {"ntp_servers": [{"server_address": s.strip(), "stratum": 1} for s in st.session_state.get("param_sys_ntp_servers_val", "10.0.0.1").split(",") if s.strip()]}),
        "chk_sys_reload": ("anta.tests.system", "VerifyReloadCause", None),
        "chk_sys_uptime": ("anta.tests.system", "VerifyUptime", {"minimum": int(st.session_state.get("param_sys_uptime_val", 60))}),

        "chk_mlag_reload_delay": ("anta.tests.mlag", "VerifyMlagReloadDelay", {"reload_delay": int(st.session_state.get("param_mlag_delay", 300)), "reload_delay_non_mlag": int(st.session_state.get("param_mlag_non_delay", 330))}),
        "chk_bgp_peer_count": ("anta.tests.routing.bgp", "VerifyBGPPeerCount", {"address_families": [{"afi": "ipv4", "safi": "unicast", "vrf": st.session_state.get("param_bgp_cnt_vrf", "default"), "num_peers": int(st.session_state.get("param_bgp_cnt_num", 2))}]}),
        "chk_bgp_specific_peers": ("anta.tests.routing.bgp", "VerifyBGPSpecificPeers", {
            "address_families": [{
                "afi": "ipv4",
                "safi": "unicast",
                "vrf": st.session_state.get("param_bgp_spec_vrf", "default"),
                "peers": [ip.strip() for ip in st.session_state.get("param_bgp_spec_ip", "10.0.0.2").split(",") if ip.strip()]
            }]
        }),
        "chk_rt_nexthops": ("anta.tests.routing.generic", "VerifyIPv4RouteNextHops", {"route_entries": [{"prefix": st.session_state.get("param_rt_nh_prefix", "10.0.0.0/24"), "nexthops": [ip.strip() for ip in st.session_state.get("param_rt_nh_ips", "10.100.0.1").split(",") if ip.strip()]}]}),
        "chk_rt_presence_prefix": ("anta.tests.routing.generic", "VerifyIPv4RoutePresencePerPrefix", {"route_entries": [{"prefix": p.strip(), "vrf": "default"} for p in st.session_state.get("param_rt_pres_prefixes", "10.0.0.0/24").split(",") if p.strip()]}),
        "chk_rt_size": ("anta.tests.routing.generic", "VerifyRoutingTableSize", {"minimum": int(st.session_state.get("param_rt_sz_min", 1)), "maximum": int(st.session_state.get("param_rt_sz_max", 10000))}),
        "chk_hostname": ("anta.tests.services", "VerifyHostname", {"hostname": st.session_state.get("param_service_hostname", "Switch-1")}),
        
        "chk_snmp_contact": ("anta.tests.snmp", "VerifySnmpContact", {"contact": st.session_state.get("param_snmp_contact_val", "admin@domain.com")}),
        "chk_snmp_location": ("anta.tests.snmp", "VerifySnmpLocation", {"location": st.session_state.get("param_snmp_location_val", "DataCenter-Rack1")}),
        "chk_snmp_v4_acl": ("anta.tests.snmp", "VerifySnmpIPv4Acl", {"number": int(st.session_state.get("param_snmp_v4_acl_num", 10)), "vrf": st.session_state.get("param_snmp_v4_acl_vrf", "default")}),
        "chk_snmp_v6_acl": ("anta.tests.snmp", "VerifySnmpIPv6Acl", {"number": int(st.session_state.get("param_snmp_v6_acl_num", 10)), "vrf": st.session_state.get("param_snmp_v6_acl_vrf", "default")}),
        "chk_snmp_status": ("anta.tests.snmp", "VerifySnmpStatus", {"vrf": st.session_state.get("param_snmp_vrf", "default")}),
        "chk_sec_v4_acl": ("anta.tests.security", "VerifyIPv4ACL", {"ipv4_access_lists": [{"name": st.session_state.get("param_sec_v4_acl_name", "ACL-MGMT"), "entries": [{"sequence": int(st.session_state.get("param_sec_v4_seq", 10)), "action": st.session_state.get("param_sec_v4_act", "permit")}]}]}),
        "chk_svc_dns_lookup": ("anta.tests.services", "VerifyDNSLookup", {"domain_names": [d.strip() for d in st.session_state.get("param_svc_dns_domains", "arista.com").split(",") if d.strip()]}),
        "chk_svc_dns_servers": ("anta.tests.services", "VerifyDNSServers", {"dns_servers": [{"server_address": ip.strip(), "vrf": st.session_state.get("param_svc_dns_vrf", "default"), "priority": int(st.session_state.get("param_svc_dns_prio", 1))} for ip in st.session_state.get("param_svc_dns_ips", "8.8.8.8").split(",") if ip.strip()]}),
        "chk_stun_status": ("anta.tests.stun", "VerifyStunServer", None),
        "chk_vlan_internal": ("anta.tests.vlan", "VerifyVlanInternalPolicy", {"policy": st.session_state.get("param_vlan_policy", "ascending"), "start_vlan_id": int(st.session_state.get("param_vlan_start", 1006)), "end_vlan_id": int(st.session_state.get("param_vlan_end", 4094))}),

        # The following tests take no required inputs; their checkboxes previously had no
        # entry here at all, so selecting them silently added nothing to the run catalog.
        "chk_bgp_adv_communities": ("anta.tests.routing.bgp", "VerifyBGPAdvCommunities", {"bgp_peers": st.session_state.get("data_param_bgp_advcomm_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_bgp_asn_cap": ("anta.tests.routing.bgp", "VerifyBGPPeerASNCap", {"bgp_peers": st.session_state.get("data_param_bgp_asncap_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_bgp_drop_stats": ("anta.tests.routing.bgp", "VerifyBGPPeerDropStats", {"bgp_peers": st.session_state.get("data_param_bgp_dropstats_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_bgp_ecmp": ("anta.tests.routing.bgp", "VerifyBGPRouteECMP", {"route_entries": st.session_state.get("data_param_bgp_ecmp_routes", [{'prefix': '10.0.0.0/24', 'vrf': 'default', 'ecmp_count': 2}])}),
        "chk_bgp_evpn_type2": ("anta.tests.routing.bgp", "VerifyEVPNType2Route", {"vxlan_endpoints": st.session_state.get("data_param_bgp_evpn2_endpoints", [{'address': '192.168.20.102', 'vni': 10020}])}),
        "chk_bgp_exchanged_routes": ("anta.tests.routing.bgp", "VerifyBGPExchangedRoutes", {"bgp_peers": expand_csv_fields(st.session_state.get("data_param_bgp_exch_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'advertised_routes': '10.0.0.0/24', 'received_routes': '10.0.1.0/24'}]), ["advertised_routes", "received_routes"])}),
        "chk_bgp_health": ("anta.tests.routing.bgp", "VerifyBGPPeersHealth", {"address_families": st.session_state.get("data_param_bgp_health_afs", [{'afi': 'ipv4', 'safi': 'unicast', 'vrf': 'default'}])}),
        "chk_bgp_health_ribd": ("anta.tests.routing.bgp", "VerifyBGPPeersHealthRibd", None),
        "chk_bgp_md5": ("anta.tests.routing.bgp", "VerifyBGPPeerMD5Auth", {"bgp_peers": st.session_state.get("data_param_bgp_md5_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_bgp_mp_caps": ("anta.tests.routing.bgp", "VerifyBGPPeerMPCaps", {"bgp_peers": expand_csv_fields(st.session_state.get("data_param_bgp_mpcaps_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'capabilities': 'ipv4Unicast'}]), ["capabilities"])}),
        "chk_bgp_nlri": ("anta.tests.routing.bgp", "VerifyBGPNlriAcceptance", {"bgp_peers": expand_csv_fields(st.session_state.get("data_param_bgp_nlri_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'capabilities': 'ipv4Unicast'}]), ["capabilities"])}),
        "chk_bgp_peer_group": ("anta.tests.routing.bgp", "VerifyBGPPeerGroup", {"bgp_peers": st.session_state.get("data_param_bgp_peergroup_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'peer_group': 'PG-SPINE'}])}),
        "chk_bgp_peer_session": ("anta.tests.routing.bgp", "VerifyBGPPeerSession", {"bgp_peers": st.session_state.get("data_param_bgp_session_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_bgp_peer_session_ribd": ("anta.tests.routing.bgp", "VerifyBGPPeerSessionRibd", {"bgp_peers": st.session_state.get("data_param_bgp_session_ribd_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_bgp_redistribution": ("anta.tests.routing.bgp", "VerifyBGPRedistribution", None),
        "chk_bgp_refresh_cap": ("anta.tests.routing.bgp", "VerifyBGPPeerRouteRefreshCap", {"bgp_peers": st.session_state.get("data_param_bgp_refresh_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_bgp_route_maps": ("anta.tests.routing.bgp", "VerifyBgpRouteMaps", {"bgp_peers": st.session_state.get("data_param_bgp_routemaps_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'inbound_route_map': 'RM-IN', 'outbound_route_map': 'RM-OUT'}])}),
        "chk_bgp_route_paths": ("anta.tests.routing.bgp", "VerifyBGPRoutePaths", {"route_entries": [
            {**{k: v for k, v in r.items() if k != "paths_nexthop"}, "paths": [{"nexthop": nh.strip(), "origin": "Igp"} for nh in str(r.get("paths_nexthop", "")).split(",") if nh.strip()]}
            for r in st.session_state.get("data_param_bgp_route_paths", [{'prefix': '10.0.0.0/24', 'vrf': 'default', 'paths_nexthop': '10.0.0.1'}])
        ]}),
        "chk_bgp_timers": ("anta.tests.routing.bgp", "VerifyBGPTimers", {"bgp_peers": st.session_state.get("data_param_bgp_timers_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'hold_time': 180, 'keep_alive_time': 60}])}),
        "chk_bgp_ttl": ("anta.tests.routing.bgp", "VerifyBGPPeerTtlMultiHops", {"bgp_peers": st.session_state.get("data_param_bgp_ttl_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'ttl': 1, 'max_ttl_hops': 1}])}),
        "chk_bgp_update_errors": ("anta.tests.routing.bgp", "VerifyBGPPeerUpdateErrors", {"bgp_peers": st.session_state.get("data_param_bgp_updateerr_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default'}])}),
        "chk_igmp_snooping_global": ("anta.tests.multicast", "VerifyIGMPSnoopingGlobal", {"enabled": bool(st.session_state.get("param_igmp_global_enabled", True))}),
        "chk_igmp_snooping_vlans": ("anta.tests.multicast", "VerifyIGMPSnoopingVlans", {"vlans": {r["vlan_id"]: r['enabled'] for r in st.session_state.get("data_param_igmp_vlans", [{'vlan_id': 10, 'enabled': True}])}}),
        "chk_int_ber": ("anta.tests.interfaces", "VerifyInterfacesBER", None),
        "chk_int_counter_det": ("anta.tests.interfaces", "VerifyInterfacesCounterDetails", None),
        "chk_int_disc": ("anta.tests.interfaces", "VerifyInterfaceDiscards", None),
        "chk_int_ecn": ("anta.tests.interfaces", "VerifyInterfacesECNCounters", None),
        "chk_int_egress_drop": ("anta.tests.interfaces", "VerifyInterfacesEgressQueueDrops", None),
        "chk_int_err": ("anta.tests.interfaces", "VerifyInterfaceErrors", None),
        "chk_int_err_dis": ("anta.tests.interfaces", "VerifyInterfaceErrDisabled", None),
        "chk_int_ill_lacp": ("anta.tests.interfaces", "VerifyIllegalLACP", None),
        "chk_int_lacp_status": ("anta.tests.interfaces", "VerifyLACPInterfacesStatus", {"interfaces": st.session_state.get("data_param_int_lacp_ifaces", [{'name': 'Ethernet1', 'portchannel': 'Port-Channel100'}])}),
        "chk_int_loopback": ("anta.tests.interfaces", "VerifyLoopbackCount", {"number": int(st.session_state.get("param_int_loopback_num", 1))}),
        "chk_int_optics_rx": ("anta.tests.interfaces", "VerifyInterfacesOpticsReceivePower", None),
        "chk_int_optics_temp": ("anta.tests.interfaces", "VerifyInterfacesOpticsTemperature", None),
        "chk_int_pfc": ("anta.tests.interfaces", "VerifyInterfacesPFCCounters", None),
        "chk_int_port_channel": ("anta.tests.interfaces", "VerifyPortChannels", None),
        "chk_int_proxy_arp": ("anta.tests.interfaces", "VerifyIPProxyARP", {"interfaces": [v.strip() for v in st.session_state.get("param_int_proxy_arp_ifaces", "Ethernet1").split(",") if v.strip()]}),
        "chk_int_storm": ("anta.tests.interfaces", "VerifyStormControlDrops", None),
        "chk_int_svi": ("anta.tests.interfaces", "VerifySVI", None),
        "chk_int_trident": ("anta.tests.interfaces", "VerifyInterfacesTridentCounters", None),
        "chk_int_util": ("anta.tests.interfaces", "VerifyInterfaceUtilization", None),
        "chk_int_voq": ("anta.tests.interfaces", "VerifyInterfacesVoqAndEgressQueueDrops", None),
        "chk_int_vrrp_mac": ("anta.tests.interfaces", "VerifyIpVirtualRouterMac", {"mac_address": st.session_state.get("param_int_vrrp_mac", "00:1c:73:00:dc:01")}),
        "chk_isis_graceful": ("anta.tests.routing.isis", "VerifyISISGracefulRestart", {"instances": st.session_state.get("data_param_isis_graceful_inst", [{'name': 'CORE-ISIS', 'vrf': 'default', 'graceful_restart': True, 'graceful_restart_helper': True}])}),
        "chk_isis_intf_mode": ("anta.tests.routing.isis", "VerifyISISInterfaceMode", {"interfaces": st.session_state.get("data_param_isis_intfmode", [{'name': 'Ethernet1', 'vrf': 'default', 'mode': 'point-to-point'}])}),
        "chk_isis_neighbor_cnt": ("anta.tests.routing.isis", "VerifyISISNeighborCount", {"interfaces": st.session_state.get("data_param_isis_neighbor_cnt", [{'name': 'Ethernet1', 'vrf': 'default', 'count': 1}])}),
        "chk_isis_neighbor_state": ("anta.tests.routing.isis", "VerifyISISNeighborState", None),
        "chk_isis_sr_adj": ("anta.tests.routing.isis", "VerifyISISSegmentRoutingAdjacencySegments", {"instances": st.session_state.get("data_param_isis_sr_adj_inst", [{'name': 'CORE-ISIS', 'vrf': 'default'}])}),
        "chk_isis_sr_dataplane": ("anta.tests.routing.isis", "VerifyISISSegmentRoutingDataplane", {"instances": st.session_state.get("data_param_isis_sr_dp_inst", [{'name': 'CORE-ISIS', 'vrf': 'default', 'dataplane': 'MPLS'}])}),
        "chk_isis_sr_tunnels": ("anta.tests.routing.isis", "VerifyISISSegmentRoutingTunnels", {"entries": st.session_state.get("data_param_isis_sr_tunnels", [{'endpoint': '1.0.0.122/32'}])}),
        "chk_lanz": ("anta.tests.lanz", "VerifyLANZ", None),
        "chk_log_accounting": ("anta.tests.logging", "VerifyLoggingAccounting", None),
        "chk_log_entries": ("anta.tests.logging", "VerifyLoggingEntries", {"logging_entries": st.session_state.get("data_param_log_entries", [{'regex_match': '.*ACCOUNTING-5-EXEC.*', 'severity_level': 'informational', 'last_number_messages': 10}])}),
        "chk_log_errors": ("anta.tests.logging", "VerifyLoggingErrors", None),
        "chk_log_generation": ("anta.tests.logging", "VerifyLoggingLogsGeneration", None),
        "chk_log_hostname": ("anta.tests.logging", "VerifyLoggingHostname", None),
        "chk_log_hosts": ("anta.tests.logging", "VerifyLoggingHosts", {"hosts": [v.strip() for v in st.session_state.get("param_log_hosts_list", "10.0.0.1").split(",") if v.strip()], "vrf": st.session_state.get("param_log_hosts_vrf", "default")}),
        "chk_log_persistent": ("anta.tests.logging", "VerifyLoggingPersistent", None),
        "chk_log_source_intf": ("anta.tests.logging", "VerifyLoggingSourceIntf", {"interface": st.session_state.get("param_log_src_intf", "Management1"), "vrf": st.session_state.get("param_log_src_intf_vrf", "default")}),
        "chk_log_syslog": ("anta.tests.logging", "VerifySyslogLogging", None),
        "chk_log_timestamp": ("anta.tests.logging", "VerifyLoggingTimestamp", None),
        "chk_mlag_config_sanity": ("anta.tests.mlag", "VerifyMlagConfigSanity", None),
        "chk_mlag_dual_primary": ("anta.tests.mlag", "VerifyMlagDualPrimary", {"detection_delay": int(st.session_state.get("param_mlag_dp_delay", 200)), "errdisabled": bool(st.session_state.get("param_mlag_dp_errdisabled", False)), "recovery_delay": int(st.session_state.get("param_mlag_dp_recovery", 60)), "recovery_delay_non_mlag": int(st.session_state.get("param_mlag_dp_recovery_non", 60))}),
        "chk_mlag_interfaces": ("anta.tests.mlag", "VerifyMlagInterfaces", None),
        "chk_mlag_priority": ("anta.tests.mlag", "VerifyMlagPrimaryPriority", {"primary_priority": int(st.session_state.get("param_mlag_primary_prio", 32760))}),
        "chk_mlag_status": ("anta.tests.mlag", "VerifyMlagStatus", None),
        "chk_ospf_max_lsa": ("anta.tests.routing.ospf", "VerifyOSPFMaxLSA", None),
        "chk_ospf_neighbor_cnt": ("anta.tests.routing.ospf", "VerifyOSPFNeighborCount", {"number": int(st.session_state.get("param_ospf_neighbor_cnt", 1))}),
        "chk_ospf_neighbor_state": ("anta.tests.routing.ospf", "VerifyOSPFNeighborState", None),
        "chk_ospf_specific_neighbors": ("anta.tests.routing.ospf", "VerifyOSPFSpecificNeighbors", {"neighbors": st.session_state.get("data_param_ospf_specific_neighbors", [{'instance': 100, 'vrf': 'default', 'ip_address': '10.1.255.46', 'local_interface': 'Ethernet2', 'area_id': '0', 'state': 'full'}])}),
        "chk_path_sel_health": ("anta.tests.path_selection", "VerifyPathsHealth", None),
        "chk_path_sel_specific": ("anta.tests.path_selection", "VerifySpecificPath", {"paths": st.session_state.get("data_param_path_sel_paths", [{'peer': '10.255.0.1', 'path_group': 'internet', 'source_address': '100.64.3.2', 'destination_address': '100.64.1.2'}])}),
        "chk_ptp_gm": ("anta.tests.ptp", "VerifyPtpGMStatus", {"gmid": st.session_state.get("param_ptp_gmid", "0xEC:46:70:FF:FE:00:00:00")}),
        "chk_ptp_lock": ("anta.tests.ptp", "VerifyPtpLockStatus", None),
        "chk_ptp_mode": ("anta.tests.ptp", "VerifyPtpModeStatus", None),
        "chk_ptp_offset": ("anta.tests.ptp", "VerifyPtpOffset", None),
        "chk_ptp_port_mode": ("anta.tests.ptp", "VerifyPtpPortModeStatus", None),
        "chk_rt_model": ("anta.tests.routing.generic", "VerifyRoutingProtocolModel", None),
        "chk_rt_presence_vrf": ("anta.tests.routing.generic", "VerifyIPv4RoutePresencePerVRF", {"route_entries": st.session_state.get("data_param_rt_pervrf_entries", [{'prefix': '10.0.0.0/24', 'vrf': 'default'}])}),
        "chk_rt_route_type": ("anta.tests.routing.generic", "VerifyIPv4RouteType", {"routes_entries": st.session_state.get("data_param_rt_type_entries", [{'prefix': '10.0.0.0/24', 'vrf': 'default', 'route_type': 'connected'}])}),
        "chk_rt_status": ("anta.tests.routing.generic", "VerifyRoutingStatus", None),
        "chk_sec_api_http": ("anta.tests.security", "VerifyAPIHttpStatus", None),
        "chk_sec_api_https_ssl": ("anta.tests.security", "VerifyAPIHttpsSSL", {"profile": st.session_state.get("param_sec_https_profile", "eAPI_SSL_Profile")}),
        "chk_sec_api_v4_acl": ("anta.tests.security", "VerifyAPIIPv4Acl", {"number": int(st.session_state.get("param_sec_api_v4_num", 1)), "vrf": st.session_state.get("param_sec_api_v4_vrf", "default")}),
        "chk_sec_api_v6_acl": ("anta.tests.security", "VerifyAPIIPv6Acl", {"number": int(st.session_state.get("param_sec_api_v6_num", 1)), "vrf": st.session_state.get("param_sec_api_v6_vrf", "default")}),
        "chk_sec_banner_login": ("anta.tests.security", "VerifyBannerLogin", {"login_banner": st.session_state.get("param_sec_banner_login_text", "Authorized Access Only")}),
        "chk_sec_banner_motd": ("anta.tests.security", "VerifyBannerMotd", {"motd_banner": st.session_state.get("param_sec_banner_motd_text", "Welcome")}),
        "chk_sec_entropy": ("anta.tests.security", "VerifyHardwareEntropy", None),
        "chk_sec_fips": ("anta.tests.security", "VerifySSHFIPSRestrictions", None),
        "chk_sec_ipsec_health": ("anta.tests.security", "VerifyIPSecConnHealth", None),
        "chk_sec_ipsec_specific": ("anta.tests.security", "VerifySpecificIPSecConn", {"ip_security_connections": st.session_state.get("data_param_sec_ipsec_conns", [{'peer': '10.0.0.1', 'vrf': 'default'}])}),
        "chk_sec_ssh_v4_acl": ("anta.tests.security", "VerifySSHIPv4Acl", {"number": int(st.session_state.get("param_sec_ssh_v4_num", 1)), "vrf": st.session_state.get("param_sec_ssh_v4_vrf", "default")}),
        "chk_sec_ssh_v6_acl": ("anta.tests.security", "VerifySSHIPv6Acl", {"number": int(st.session_state.get("param_sec_ssh_v6_num", 1)), "vrf": st.session_state.get("param_sec_ssh_v6_vrf", "default")}),
        "chk_sec_ssl_cert": ("anta.tests.security", "VerifyAPISSLCertificate", {"certificates": st.session_state.get("data_param_sec_ssl_certs", [{'certificate_name': 'ARISTA_SIGNING_CA.crt', 'expiry_threshold': 30, 'common_name': 'Arista Networks Internal IT CA', 'encryption_algorithm': 'RSA', 'key_size': 2048}])}),
        "chk_sec_telnet": ("anta.tests.security", "VerifyTelnetStatus", None),
        "chk_snmp_errors": ("anta.tests.snmp", "VerifySnmpErrorCounters", None),
        "chk_snmp_group": ("anta.tests.snmp", "VerifySnmpGroup", {"snmp_groups": st.session_state.get("data_param_snmp_groups", [{'group_name': 'GROUP1', 'version': 'v2c'}])}),
        "chk_snmp_logging": ("anta.tests.snmp", "VerifySnmpHostLogging", {"hosts": st.session_state.get("data_param_snmp_log_hosts", [{'hostname': '192.168.1.100', 'vrf': 'default'}])}),
        "chk_snmp_notification": ("anta.tests.snmp", "VerifySnmpNotificationHost", {"notification_hosts": st.session_state.get("data_param_snmp_notif_hosts", [{'hostname': '192.168.1.100', 'vrf': 'default', 'notification_type': 'trap', 'version': 'v2c', 'community_string': 'public'}])}),
        "chk_snmp_pdu": ("anta.tests.snmp", "VerifySnmpPDUCounters", None),
        "chk_snmp_source": ("anta.tests.snmp", "VerifySnmpSourceInterface", {"interfaces": st.session_state.get("data_param_snmp_src_ifaces", [{'interface': 'Management1', 'vrf': 'default'}])}),
        "chk_snmp_user": ("anta.tests.snmp", "VerifySnmpUser", {"snmp_users": st.session_state.get("data_param_snmp_users", [{'username': 'snmp-user', 'group_name': 'GROUP1', 'version': 'v3', 'auth_type': 'MD5', 'priv_type': 'AES-128'}])}),
        "chk_ssh_status": ("anta.tests.security", "VerifySSHStatus", None),
        "chk_stp_blocked": ("anta.tests.stp", "VerifySTPBlockedPorts", None),
        "chk_stp_counters": ("anta.tests.stp", "VerifySTPCounters", None),
        "chk_stp_disabled_vlans": ("anta.tests.stp", "VerifySTPDisabledVlans", {"vlans": [int(v.strip()) for v in st.session_state.get("param_stp_disabled_vlans", "10, 20").split(",") if v.strip()]}),
        "chk_stp_forwarding": ("anta.tests.stp", "VerifySTPForwardingPorts", {"vlans": [int(v.strip()) for v in st.session_state.get("param_stp_forwarding_vlans", "10, 20").split(",") if v.strip()]}),
        "chk_stp_mode": ("anta.tests.stp", "VerifySTPMode", {"mode": st.session_state.get("param_stp_mode_val", 'mstp'), "vlans": [int(v.strip()) for v in st.session_state.get("param_stp_mode_vlans", "10, 20").split(",") if v.strip()]}),
        "chk_stp_root_priority": ("anta.tests.stp", "VerifySTPRootPriority", {"priority": int(st.session_state.get("param_stp_root_priority", 32768)), "instances": [int(v.strip()) for v in st.session_state.get("param_stp_root_instances", "").split(",") if v.strip()]}),
        "chk_stp_tc": ("anta.tests.stp", "VerifyStpTopologyChanges", {"threshold": int(st.session_state.get("param_stp_tc_threshold", 10))}),
        "chk_stun_client": ("anta.tests.stun", "VerifyStunClient", {"stun_clients": st.session_state.get("data_param_stun_client_list", [{'source_address': '172.18.3.2', 'public_address': '172.18.3.21', 'source_port': 4500, 'public_port': 6006}])}),
        "chk_stun_client_trans": ("anta.tests.stun", "VerifyStunClientTranslation", {"stun_clients": st.session_state.get("data_param_stun_client_trans_list", [{'source_address': '172.18.3.2', 'public_address': '172.18.3.21', 'source_port': 4500, 'public_port': 6006}])}),
        "chk_svc_errdisable_rec": ("anta.tests.services", "VerifyErrdisableRecovery", {"reasons": st.session_state.get("data_param_svc_errdisable_reasons", [{'reason': 'acl', 'interval': 30, 'status': 'Enabled'}])}),
        "chk_tcam_profile": ("anta.tests.profiles", "VerifyTcamProfile", {"profile": st.session_state.get("param_tcam_profile", "default")}),
        "chk_uft_mode": ("anta.tests.profiles", "VerifyUnifiedForwardingTableMode", {"mode": st.session_state.get("param_uft_mode", "flexible")}),
        "chk_vlan_dynamic": ("anta.tests.vlan", "VerifyDynamicVlanSource", {"sources": [v.strip() for v in st.session_state.get("param_vlan_dyn_sources", "evpn, mlagsync").split(",") if v.strip()], "strict": bool(st.session_state.get("param_vlan_dyn_strict", False))}),
        "chk_vxlan_conn": ("anta.tests.vxlan", "VerifyVxlan1ConnSettings", {"source_interface": st.session_state.get("param_vxlan_src_intf", "Loopback1"), "udp_port": int(st.session_state.get("param_vxlan_udp_port", 4789))}),
        "chk_vxlan_intf": ("anta.tests.vxlan", "VerifyVxlan1Interface", None),
        "chk_vxlan_sanity": ("anta.tests.vxlan", "VerifyVxlanConfigSanity", None),
        "chk_vxlan_vni_binding": ("anta.tests.vxlan", "VerifyVxlanVniBinding", {"bindings": {r["vni"]: r['binding'] for r in st.session_state.get("data_param_vxlan_vni_bindings", [{'vni': 10010, 'binding': '10'}])}}),
        "chk_vxlan_vtep": ("anta.tests.vxlan", "VerifyVxlanVtep", {"vteps": [v.strip() for v in st.session_state.get("param_vxlan_vteps", "10.1.1.1").split(",") if v.strip()]}),
        "chk_vxlan_vvtep": ("anta.tests.vxlan", "VerifyVxlan1VVTEPIPAddresses", {"ipv4_address": st.session_state.get("param_vxlan_vvtep_v4", "10.255.1.1") or None, "ipv6_address": st.session_state.get("param_vxlan_vvtep_v6", "") or None}),
        "chk_bgp_peer_route_limit": ("anta.tests.routing.bgp", "VerifyBGPPeerRouteLimit", {"bgp_peers": st.session_state.get("data_param_bgp_routelimit_peers", [{'peer_address': '10.0.0.2', 'vrf': 'default', 'maximum_routes': 12000, 'warning_limit': 10000}])}),
        "chk_vlan_status": ("anta.tests.vlan", "VerifyVlanStatus", {"vlans": st.session_state.get("data_param_vlan_status_list", [{'vlan_id': 10, 'status': 'active'}])}),
    }

    # Map dynamic config rules if box is ticked
    if st.session_state["master_test_states"].get("chk_cfg_rules") and st.session_state.get("cfg_rules_data"):
        cfg_rules_parsed = []
        rules_map = {}
        
        for row in st.session_state.cfg_rules_data:
            match_val = str(row.get("Match", "")).strip()
            if not match_val:
                continue
                
            sec_val = str(row.get("Section", "")).strip()
            mode_val = row.get("Mode", "exact")
            absent_val = bool(row.get("Absent", False))
            desc_val = str(row.get("Description", "")).strip()
            
            entry = {"match": match_val}
            if mode_val != "exact": entry["mode"] = mode_val
            if absent_val: entry["absent"] = True
            if desc_val: entry["description"] = desc_val
                
            if sec_val not in rules_map:
                rules_map[sec_val] = []
            rules_map[sec_val].append(entry)
            
        for sec, entries in rules_map.items():
            rule = {"entries": entries}
            if sec:
                rule["section"] = [s.strip() for s in sec.split(",") if s.strip()]
            cfg_rules_parsed.append(rule)
            
        if cfg_rules_parsed:
            add_test("anta.tests.configuration", "VerifyRunningConfig", {"rules": cfg_rules_parsed})

    # Loop through state and dynamically append configured tests
    for k, (mod, test_cls, params) in key_to_test_map.items():
        if st.session_state["master_test_states"].get(k, False):
            add_test(mod, test_cls, params)

    # --- PER-TEST PRE-VALIDATION LOGIC (STORED IN SESSION_STATE) ---
    valid_catalog_dict = {}
    invalid_config_results = []

    for module_name, tests_list in catalog_dict.items():
        for test_entry in tests_list:
            single_test_catalog = {module_name: [test_entry]}
            try:
                # Test validity against ANTA Catalog model
                AntaCatalog.from_dict(single_test_catalog)
                
                if module_name not in valid_catalog_dict:
                    valid_catalog_dict[module_name] = []
                valid_catalog_dict[module_name].append(test_entry)
                
            except Exception as err:
                test_cls_name = list(test_entry.keys())[0] if isinstance(test_entry, dict) else str(test_entry)
                full_error_text = str(err)
                
                invalid_config_results.append({
                    "name": "Catalog Pre-Validator",
                    "categories": [module_name],
                    "description": f"{test_cls_name} (Invalid Config/Missing Parameters)",
                    "result": "error",
                    "messages": [full_error_text]
                })

    # Save to session_state so each user session has its own catalog dictionary
    st.session_state["session_valid_catalog_dict"] = valid_catalog_dict
    st.session_state["invalid_config_results"] = invalid_config_results
    save_settings({"selected_test_keys": [k for k in ALL_TEST_KEYS if st.session_state["master_test_states"].get(k, False)]})

# ==========================================
# TAB 4: DASHBOARD (Runner - Isolated Execution)
# ==========================================
with tab_dashboard:
    st.subheader("Run Network Tests")
    
    # Show active execution test count indicator
    selected_run_count = sum(1 for k in ALL_TEST_KEYS if st.session_state["master_test_states"].get(k, False))
    st.info(f"⚡ **Ready to execute {selected_run_count} selected test(s)** on configured inventory devices.")

    run_tags_input = st.text_input(
        "🏷️ Filter NRFU Execution by Tags (Optional CLI Filter)", 
        placeholder="e.g. leaf, spine",
        key="input_run_tags",
        help="Applies '--tags' to the CLI execution to run tests only on devices/tests with matching tags."
    )
    
    if st.button("🚀 Execute Tests", type="primary", use_container_width=True):
        # Build an isolated env for this run's subprocess instead of mutating the
        # shared process-wide os.environ, which would race with other concurrent
        # user sessions running in the same Streamlit process.
        run_env = os.environ.copy()
        run_env["ANTA_USERNAME"] = st.session_state.anta_user
        run_env["ANTA_PASSWORD"] = st.session_state.anta_pass

        # Unique UUID per execution run to ensure isolated parallel execution
        run_id = str(uuid.uuid4())[:8]
        run_catalog_file = f"temp_catalog_{run_id}.yml"
        run_inventory_file = f"temp_inventory_{run_id}.yml"

        full_log = ""
        with st.spinner(f"Connecting to switches and running tests (Run ID: {run_id})... Please wait."):
            try:
                # 1. Write unique catalog file for this execution run
                valid_cat = st.session_state.get("session_valid_catalog_dict", {})
                with open(run_catalog_file, "w") as f:
                    yaml.safe_dump(valid_cat, f, sort_keys=False)
                
                # 2. Write unique inventory file for this execution run
                try:
                    inv_data = load_inventory()
                except Exception:
                    inv_data = {}
                with open(run_inventory_file, "w") as f:
                    yaml.safe_dump(inv_data, f, sort_keys=False)

                # 3. Build & Execute isolated ANTA CLI command
                cmd = ["anta", "nrfu"]
                if run_tags_input.strip():
                    cmd.extend(["--tags", run_tags_input.strip()])
                cmd.extend(["--inventory", run_inventory_file, "--catalog", run_catalog_file, "--ignore-status", "json"])

                result = subprocess.run(cmd, capture_output=True, text=True, env=run_env, timeout=NRFU_SUBPROCESS_TIMEOUT)
                output = result.stdout
                stderr_output = result.stderr or ""
                
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                output_clean = ansi_escape.sub('', output)
                stderr_clean = ansi_escape.sub('', stderr_output)
                full_log = output_clean + "\n" + stderr_clean
                
                json_raw_string = output_clean
                if "JSON results" in output_clean:
                    json_raw_string = output_clean.split("JSON results")[-1]
                
                start_idx = json_raw_string.find('[')
                end_idx = json_raw_string.rfind(']')
                
                data = []
                if start_idx != -1 and end_idx != -1:
                    try:
                        data = json.loads(json_raw_string[start_idx:end_idx+1])
                    except json.JSONDecodeError:
                        pass
                
                invalid_pre_results = st.session_state.get("invalid_config_results", [])
                
                if not data and not invalid_pre_results:
                    if "No tests scheduled to run" in full_log:
                        st.warning("⚠️ **Notice:** ANTA skipped running tests because a tag filter in the catalog or execution filter does not match any device in Inventory.")
                    else:
                        st.error("No test results received from ANTA. Please ensure tests are selected and tag filters are correct.")
                        with st.expander("View Full Raw Output"):
                            st.code(full_log, language=None)
                else:
                    df_anta = pd.DataFrame(data) if data else pd.DataFrame()
                    
                    if not df_anta.empty and 'messages' in df_anta.columns:
                        df_anta['messages'] = df_anta['messages'].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
                    
                    if invalid_pre_results:
                        df_invalid = pd.DataFrame(invalid_pre_results)
                        df_invalid['messages'] = df_invalid['messages'].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
                        df = pd.concat([df_anta, df_invalid], ignore_index=True)
                    else:
                        df = df_anta
                    
                    total_tests = len(df)
                    passed = len(df[df['result'] == 'success']) if 'result' in df.columns else 0
                    failed = len(df[df['result'] == 'failure']) if 'result' in df.columns else 0
                    error = len(df[df['result'] == 'error']) if 'result' in df.columns else 0
                    skipped = len(df[df['result'] == 'skipped']) if 'result' in df.columns else 0
                    
                    st.subheader("📊 Test Summary")
                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("Total Tests", total_tests)
                    col2.metric("✅ Passed", passed)
                    col3.metric("❌ Failed", failed)
                    col4.metric("🚨 Error / Exception", error)
                    col5.metric("⏭️ Skipped", skipped)
                    
                    st.divider()
                    display_cols = ['name', 'categories', 'description', 'result', 'messages']
                    df_display = df[[col for col in display_cols if col in df.columns]].copy()
                    
                    df_display['full_message'] = df_display['messages']
                    df_display['messages'] = df_display['messages'].apply(
                        lambda x: (str(x)[:60] + '...') if isinstance(x, str) and len(str(x)) > 60 else x
                    )
                    
                    def color_result(val):
                        if val == 'success': return 'color: #28a745; font-weight: bold'
                        elif val in ['failure', 'error']: return 'color: #dc3545; font-weight: bold'
                        return 'color: #ffc107; font-weight: bold'
                    
                    styled_df = df_display.drop(columns=['full_message']).style.map(color_result, subset=['result'])
                    st.dataframe(styled_df, use_container_width=True)
                    
                    failed_df = df_display[df_display['result'].isin(['failure', 'error'])]
                    if not failed_df.empty:
                        st.divider()
                        st.subheader("🔍 Failed Tests Details (Grouped by Switch)")
                        st.markdown("Click on a switch below to expand and view all of its failing tests.")
                        
                        grouped = failed_df.groupby('name')
                        for device_name, device_failures in grouped:
                            fail_count = len(device_failures)
                            expander_label = f"❌ **{device_name}** ({fail_count} failed test{'s' if fail_count > 1 else ''})"
                            
                            with st.expander(expander_label):
                                for idx, (_, row) in enumerate(device_failures.iterrows(), start=1):
                                    test_desc = row.get('description') or row.get('categories') or f"Test #{idx}"
                                    if isinstance(test_desc, list):
                                        test_desc = ", ".join(test_desc)
                                        
                                    st.markdown(f"#### {idx}. {test_desc}")
                                    if 'categories' in row and pd.notna(row['categories']):
                                        cat_display = ", ".join(row['categories']) if isinstance(row['categories'], list) else row['categories']
                                        st.caption(f"**Category:** {cat_display}")
                                    
                                    if device_name == "Catalog Pre-Validator":
                                        st.code(row['full_message'], language="text")
                                    else:
                                        st.error(row['full_message'])
                                        
                                    if idx < fail_count:
                                        st.divider()
            except subprocess.TimeoutExpired:
                st.error(f"⏱️ Test run timed out after {NRFU_SUBPROCESS_TIMEOUT}s (Run ID: {run_id}). The device(s) may be unreachable or the test set too large.")
            except Exception as e:
                st.error(f"Error parsing results: {e}")
                if full_log:
                    with st.expander("View Full Raw Output"):
                        st.code(full_log, language=None)
            finally:
                # Cleanup temporary isolated execution files
                if os.path.exists(run_catalog_file):
                    try: os.remove(run_catalog_file)
                    except Exception: pass
                if os.path.exists(run_inventory_file):
                    try: os.remove(run_inventory_file)
                    except Exception: pass

# ==========================================
# TAB 5: RAW CLI (Custom Commands)
# ==========================================
with tab_cli:
    st.subheader("🛠️ Raw EOS Command Runner")
    st.markdown("Use this tab to run ad-hoc commands on a specific device.")
    
    try:
        inv_data = load_inventory()
        hosts = inv_data.get("anta_inventory", {}).get("hosts", [])
        
        device_map = {}
        for host in hosts:
            h_ip = host.get("host")
            h_name = host.get("name")
            if h_ip:
                anta_id = h_name if h_name else h_ip
                label = f"{h_name} ({h_ip})" if h_name else h_ip
                device_map[label] = anta_id
    except Exception:
        device_map = {}
        
    if not device_map:
        st.warning("No explicit hosts found for CLI execution. Please define hosts in 'Manage Inventory' tab.")
    else:
        options_list = list(device_map.keys())
        saved_label = saved_settings.get("default_cli_device_label", "")
        default_index = options_list.index(saved_label) if saved_label in options_list else 0
        
        selected_label = st.selectbox("Select Device", options=options_list, index=default_index, key="select_cli_device")
        selected_device_id = device_map[selected_label]
        
        cmd_input = st.text_input("Enter EOS Command", value="show mac address-table", key="input_cli_command")
        
        if st.button("Run Command", type="primary"):
            save_settings({"default_cli_device_label": selected_label})
            run_env = os.environ.copy()
            run_env["ANTA_USERNAME"] = st.session_state.anta_user
            run_env["ANTA_PASSWORD"] = st.session_state.anta_pass

            with st.spinner(f"Running '{cmd_input}' on {selected_label}..."):
                exec_cmd = [
                    "anta", "debug", "run-cmd",
                    "--command", cmd_input,
                    "--inventory", "inventory.yml",
                    "--device", selected_device_id
                ]

                try:
                    result = subprocess.run(exec_cmd, capture_output=True, text=True, env=run_env, timeout=CLI_SUBPROCESS_TIMEOUT)
                except subprocess.TimeoutExpired:
                    result = None
                    st.error(f"⏱️ Command timed out after {CLI_SUBPROCESS_TIMEOUT}s. The device may be unreachable.")

                if result is not None and result.returncode == 0:
                    st.success(f"Command executed successfully on {selected_label}!")
                    
                    try:
                        parsed_json = json.loads(result.stdout)
                        
                        def find_tables(d, found=None):
                            if found is None: found = {}
                            if isinstance(d, dict):
                                for k, v in d.items():
                                    if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                                        found[k] = v
                                    else:
                                        find_tables(v, found)
                            elif isinstance(d, list):
                                for item in d:
                                    find_tables(item, found)
                            return found
                        
                        tables = find_tables(parsed_json)
                        
                        if tables:
                            st.markdown("#### 📊 Extracted Tables")
                            for table_name, table_data in tables.items():
                                with st.expander(f"View '{table_name}'", expanded=True):
                                    st.dataframe(pd.DataFrame(table_data), use_container_width=True)
                                    
                        st.markdown("#### 📄 Full Clean Text Output")
                        clean_text = yaml.dump(parsed_json, default_flow_style=False, sort_keys=False)
                        st.code(clean_text, language=None)

                    except Exception:
                        st.markdown("#### 📄 Raw Text Output")
                        st.code(result.stdout, language=None)
                elif result is not None:
                    st.error("Error executing command.")
                    st.code(result.stderr or result.stdout, language=None)