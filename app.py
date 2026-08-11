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

# Define all available test keys including new additions
ALL_TEST_KEYS = [
    "chk_hw_trans", "chk_hw_cool", "chk_hw_power", "chk_hw_temp", "chk_hw_trans_presence", "chk_hw_trans_optics", "chk_hw_pse",
    "chk_sys_uptime", "chk_sys_ntp", "chk_sys_coredump", "chk_sys_reload", "chk_sys_cpu", "chk_sys_mem",
    "chk_sw_version", "chk_sw_bootloader",
    "chk_aaa_authen", "chk_aaa_authz", "chk_aaa_acct_default", "chk_aaa_acct_console",
    "chk_aaa_tacacs_src", "chk_aaa_tacacs_servers", "chk_aaa_tacacs_groups",
    "chk_aaa_radius_src", "chk_aaa_radius_servers",
    "chk_cfg_ztp", "chk_cfg_diff", "chk_cfg_banner",
    "chk_conn_ping", "chk_conn_lldp",
    "chk_int_err", "chk_int_disc", "chk_int_status",
    "chk_int_proxy_arp", "chk_int_ill_lacp", "chk_int_err_dis", "chk_int_util",
    "chk_int_ber", "chk_int_counter_det", "chk_int_ecn", "chk_int_egress_drop",
    "chk_int_optics_rx", "chk_int_optics_temp", "chk_int_pfc", "chk_int_speed",
    "chk_int_trident", "chk_int_voq", "chk_int_vrrp_mac", "chk_int_l2mtu",
    "chk_int_l3mtu", "chk_int_loopback", "chk_int_port_channel",
    "chk_int_svi", "chk_int_storm", "chk_int_ipv4",
    "chk_rt_model", "chk_rt_status", "chk_rt_size", "chk_rt_presence",
    "chk_bgp_health", "chk_stp_blocked", "chk_stp_tc", "chk_stp_root", "chk_stp_mode",
    "chk_evpn_type5", "chk_vxlan_intf", "chk_vxlan_sanity", "chk_vtep_peers",
    "chk_mlag_status", "chk_mlag_interfaces", "chk_mlag_config_sanity", "chk_mlag_reload_delay",
    "chk_igmp_snooping_global", "chk_igmp_snooping_vlans",
    "chk_sec_api_http", "chk_sec_api_https_ssl", "chk_sec_api_v4_acl", "chk_sec_api_v6_acl", "chk_sec_ssl_cert",
    "chk_sec_entropy", "chk_sec_ipsec_health", "chk_sec_ssh_v4_acl", "chk_sec_ssh_v6_acl", "chk_ssh_status", "chk_sec_telnet",
    "chk_stun_status",
    "chk_hostname", "chk_svc_dns_lookup", "chk_svc_dns_servers", "chk_svc_errdisable_rec",
    "chk_flow_tracking", "chk_lanz", "chk_log_persistent", "chk_log_accounting", "chk_log_source_intf", "chk_log_hosts",
    "chk_path_sel_health", "chk_snmp_status", "chk_snmp_community",
    "chk_vlan_internal", "chk_vlans_status"
]

default_config_rules = [
    {"Section": "", "Match": "aaa authorization exec default local", "Mode": "exact", "Absent": False, "Description": "AAA authorization"},
    {"Section": "management api http-commands", "Match": "no shutdown", "Mode": "exact", "Absent": False, "Description": "eAPI enabled"}
]

DEFAULT_PROFILES = {
    "🟢 Basic NRFU (Quick Check)": {
        "keys": ["chk_hw_trans", "chk_hw_cool", "chk_hw_power", "chk_hw_temp", "chk_sys_uptime", "chk_sys_ntp", "chk_int_err", "chk_int_status", "chk_cfg_diff"],
        "cfg_rules": []
    },
    "🔍 Deep NRFU (Full Audit)": {
        "keys": ALL_TEST_KEYS,
        "cfg_rules": default_config_rules
    },
    "⚡ Minimal Check": {
        "keys": ["chk_hw_power", "chk_sys_uptime", "chk_int_status"],
        "cfg_rules": []
    }
}

active_profiles = saved_settings.get("profiles", DEFAULT_PROFILES)

# Initialize Session State Keys if not present
saved_test_keys = saved_settings.get("selected_test_keys", None)
for k in ALL_TEST_KEYS:
    if k not in st.session_state:
        if saved_test_keys is not None:
            st.session_state[k] = (k in saved_test_keys)
        else:
            st.session_state[k] = (k in DEFAULT_PROFILES["🟢 Basic NRFU (Quick Check)"]["keys"])

# ==========================================
# STREAMLIT SIDEBAR: GLOBAL PROFILE & TAG CONTROLS
# ==========================================
with st.sidebar:
    st.title("⚙️ Profile & Settings")
    st.caption("Manage active presets & execution tags")
    
    st.markdown("---")
    st.markdown("##### 🎯 Active Profile Presets")
    
    selected_prof_name = st.selectbox(
        "Select Active Profile", 
        options=list(active_profiles.keys()),
        key="sb_selected_prof"
    )

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
            save_settings({
                "profiles": active_profiles,
                "selected_test_keys": current_keys
            })
            st.success("Saved!")

    with st.expander("➕ Create / Delete Profile"):
        new_prof_input = st.text_input("New Profile Name", placeholder="e.g. Leaf Switches", key="sb_new_prof")
        if st.button("Create Profile", use_container_width=True):
            if new_prof_input.strip():
                current_keys = [k for k in ALL_TEST_KEYS if st.session_state.get(k, False)]
                active_profiles[new_prof_input.strip()] = {
                    "keys": current_keys,
                    "cfg_rules": st.session_state.get("cfg_rules_data", default_config_rules)
                }
                save_settings({"profiles": active_profiles, "selected_test_keys": current_keys})
                st.success(f"Created '{new_prof_input.strip()}'!")
                st.rerun()

        st.divider()
        del_prof_select = st.selectbox("Delete Profile", options=list(active_profiles.keys()), key="sb_del_prof")
        if st.button("Delete Profile", use_container_width=True, type="secondary"):
            if len(active_profiles) > 1:
                del active_profiles[del_prof_select]
                save_settings({"profiles": active_profiles})
                st.success(f"Deleted '{del_prof_select}'!")
                st.rerun()

    st.markdown("---")
    st.markdown("##### 🏷️ Filter Tags")
    st.text_input(
        "Filter Tags (comma-separated)", 
        value=saved_settings.get("catalog_tags", ""),
        placeholder="e.g. leaf, demo",
        key="input_catalog_tags"
    )

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
    st.markdown("Enter the credentials used to connect to your Arista switches.")
    
    if "anta_user" not in st.session_state:
        st.session_state.anta_user = saved_settings.get("anta_user", "arista")
    if "anta_pass" not in st.session_state:
        st.session_state.anta_pass = saved_settings.get("anta_pass", "arista")
        
    st.session_state.anta_user = st.text_input("Username", value=st.session_state.anta_user, key="input_anta_user")
    st.session_state.anta_pass = st.text_input("Password", value=st.session_state.anta_pass, type="password", key="input_anta_pass")
    
    if st.button("💾 Save as Default Credentials", type="primary"):
        save_settings({
            "anta_user": st.session_state.anta_user,
            "anta_pass": st.session_state.anta_pass
        })
        st.success("✅ Credentials saved as default for future sessions!")

# ==========================================
# TAB 2: INVENTORY (Auto-Saving)
# ==========================================
with tab_inventory:
    st.subheader("Inventory Manager")
    st.markdown("Configure your ANTA inventory using **Hosts**, **Networks** (CIDR), or **IP Ranges**.")
    st.caption("✅ Changes made here are automatically saved in real-time.")
    
    try:
        with open("inventory.yml", "r") as f:
            inv_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        inv_data = {}

    anta_inv = inv_data.get("anta_inventory", {})
    
    # Process Hosts
    raw_hosts = anta_inv.get("hosts", [])
    hosts_prep = []
    for h in raw_hosts:
        item = dict(h)
        if isinstance(item.get("tags"), list):
            item["tags"] = ", ".join(item["tags"])
        hosts_prep.append(item)
    df_hosts = pd.DataFrame(hosts_prep)
    for col in ["host", "name", "port", "tags", "disable_cache", "use_session_auth"]:
        if col not in df_hosts.columns:
            df_hosts[col] = False if "cache" in col or "auth" in col else None

    # Process Networks
    raw_networks = anta_inv.get("networks", [])
    net_prep = []
    for n in raw_networks:
        item = dict(n)
        if isinstance(item.get("tags"), list):
            item["tags"] = ", ".join(item["tags"])
        net_prep.append(item)
    df_networks = pd.DataFrame(net_prep)
    for col in ["network", "tags", "disable_cache", "use_session_auth"]:
        if col not in df_networks.columns:
            df_networks[col] = False if "cache" in col or "auth" in col else None

    # Process Ranges
    raw_ranges = anta_inv.get("ranges", [])
    rng_prep = []
    for r in raw_ranges:
        item = dict(r)
        if isinstance(item.get("tags"), list):
            item["tags"] = ", ".join(item["tags"])
        rng_prep.append(item)
    df_ranges = pd.DataFrame(rng_prep)
    for col in ["start", "end", "tags", "disable_cache", "use_session_auth"]:
        if col not in df_ranges.columns:
            df_ranges[col] = False if "cache" in col or "auth" in col else None

    sub_hosts, sub_networks, sub_ranges = st.tabs(["🖥️ Specific Hosts", "🌐 Networks (CIDR)", "🔢 IP Ranges"])

    with sub_hosts:
        edited_hosts = st.data_editor(
            df_hosts,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "host": st.column_config.TextColumn("IP / Hostname", required=True),
                "name": st.column_config.TextColumn("Display Name (Optional)"),
                "port": st.column_config.NumberColumn("eAPI Port", default=443, format="%d"),
                "tags": st.column_config.TextColumn("Tags (comma-separated, e.g. leaf, demo)"),
                "disable_cache": st.column_config.CheckboxColumn("Disable Cache"),
                "use_session_auth": st.column_config.CheckboxColumn("Session Auth"),
            }
        )

    with sub_networks:
        edited_networks = st.data_editor(
            df_networks,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "network": st.column_config.TextColumn("Network (CIDR)", required=True),
                "tags": st.column_config.TextColumn("Tags (comma-separated)"),
                "disable_cache": st.column_config.CheckboxColumn("Disable Cache"),
                "use_session_auth": st.column_config.CheckboxColumn("Session Auth"),
            }
        )

    with sub_ranges:
        edited_ranges = st.data_editor(
            df_ranges,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "start": st.column_config.TextColumn("Start IP", required=True),
                "end": st.column_config.TextColumn("End IP", required=True),
                "tags": st.column_config.TextColumn("Tags (comma-separated)"),
                "disable_cache": st.column_config.CheckboxColumn("Disable Cache"),
                "use_session_auth": st.column_config.CheckboxColumn("Session Auth"),
            }
        )

    def parse_editor_data(df, primary_col):
        records = []
        if df is None or df.empty:
            return records
        for row in df.to_dict(orient="records"):
            if pd.isna(row.get(primary_col)) or not str(row.get(primary_col)).strip():
                continue
            item = {}
            for k, v in row.items():
                if pd.isna(v) or v is None:
                    continue
                if k == "tags":
                    if isinstance(v, str) and v.strip():
                        t_list = [t.strip() for t in v.split(",") if t.strip()]
                        if t_list: item["tags"] = t_list
                elif k == "port":
                    try:
                        item["port"] = int(v)
                    except (ValueError, TypeError):
                        pass
                elif isinstance(v, bool):
                    if v: item[k] = True
                else:
                    str_val = str(v).strip()
                    if str_val: item[k] = str_val
            records.append(item)
        return records

    final_hosts = parse_editor_data(edited_hosts, "host")
    final_networks = parse_editor_data(edited_networks, "network")
    final_ranges = parse_editor_data(edited_ranges, "start")

    new_inv_dict = {"anta_inventory": {}}
    if final_hosts: new_inv_dict["anta_inventory"]["hosts"] = final_hosts
    if final_networks: new_inv_dict["anta_inventory"]["networks"] = final_networks
    if final_ranges: new_inv_dict["anta_inventory"]["ranges"] = final_ranges

    with open("inventory.yml", "w") as f:
        yaml.safe_dump(new_inv_dict, f, sort_keys=False)

# ==========================================
# TAB 3: CATALOG BUILDER (Sleek Clean Layout)
# ==========================================
with tab_catalog:
    st.subheader("📋 Test Catalog Builder")
    st.caption("Select category navigation on the left to configure test suites.")

    nav_side_col, main_content_col = st.columns([1.1, 3.5], gap="large")

    with nav_side_col:
        st.markdown("#### 📂 Categories")
        categories_map = {
            "🔌 Hardware": "Hardware",
            "💻 System": "System",
            "💿 Software": "Software",
            "🔐 AAA Suite": "AAA",
            "⚙️ Configuration": "Configuration",
            "🌐 Connectivity": "Connectivity",
            "🌐 Interfaces": "Interfaces",
            "🗺️ Routing Generic": "Routing Generic",
            "🗺️ Routing BGP": "Routing BGP",
            "🛡️ STP": "STP",
            "☁️ EVPN & VXLAN": "EVPN & VXLAN",
            "🤝 MLAG": "MLAG",
            "📡 Multicast": "Multicast",
            "🔒 Security": "Security",
            "📞 STUN": "STUN",
            "🛠️ Services": "Services",
            "🌊 Flow Tracking": "Flow Tracking",
            "📊 LANZ": "LANZ",
            "📝 Logging": "Logging",
            "🛤️ Path Selection": "Path Selection",
            "🖧 SNMP": "SNMP",
            "🏢 VLAN": "VLAN",
            "🧩 Advanced (Custom YAML)": "Custom YAML"
        }

        selected_cat_label = st.radio(
            "Select Category",
            options=list(categories_map.keys()),
            label_visibility="collapsed"
        )
        selected_cat = categories_map[selected_cat_label]

    with main_content_col:
        st.markdown(f"### {selected_cat_label}")
        
        def bind_checkbox(label, key):
            return st.checkbox(label, value=st.session_state.get(key, False), key=key)

        # 1. HARDWARE
        if selected_cat == "Hardware":
            chk_hw_trans = bind_checkbox("Verify Transceivers Manufacturers (`VerifyTransceiversManufacturers`)", key="chk_hw_trans")
            st.text_input("Expected Manufacturers (comma-separated)", value=st.session_state.get("param_hw_trans_mfg", "Arista Networks, ARISTA"), key="param_hw_trans_mfg", disabled=not chk_hw_trans)
            
            st.divider()
            chk_hw_trans_presence = bind_checkbox("Verify Transceivers Presence (`VerifyTransceiversPresence`)", key="chk_hw_trans_presence")
            st.text_input("Interfaces to check presence (comma-separated)", value=st.session_state.get("param_hw_trans_pres_intfs", "Ethernet1, Ethernet2"), key="param_hw_trans_pres_intfs", disabled=not chk_hw_trans_presence)

            st.divider()
            bind_checkbox("Verify Transceivers Optics Status (`VerifyTransceiversOptics`)", key="chk_hw_trans_optics")

            st.divider()
            bind_checkbox("Verify System Cooling (`VerifyEnvironmentSystemCooling`)", key="chk_hw_cool")
            
            st.divider()
            chk_hw_power = bind_checkbox("Verify Power Supplies (`VerifyEnvironmentPower`)", key="chk_hw_power")
            st.text_input("Accepted Power States (comma-separated)", value=st.session_state.get("param_hw_power_states", "ok"), key="param_hw_power_states", disabled=not chk_hw_power)
            
            st.divider()
            bind_checkbox("Verify Temperature (`VerifyTemperature`)", key="chk_hw_temp")

            st.divider()
            bind_checkbox("Verify PSE Status - PoE (`VerifyPseStatus`)", key="chk_hw_pse")

        # 2. SYSTEM
        elif selected_cat == "System":
            chk_sys_uptime = bind_checkbox("Verify Minimum Uptime (`VerifyUptime`)", key="chk_sys_uptime")
            st.number_input("Minimum Uptime (seconds)", value=st.session_state.get("param_sys_uptime_val", 60), min_value=1, key="param_sys_uptime_val", disabled=not chk_sys_uptime)
            
            st.divider()
            bind_checkbox("Verify NTP Status (`VerifyNTP`)", key="chk_sys_ntp")
            
            st.divider()
            bind_checkbox("Verify No Coredumps (`VerifyCoredump`)", key="chk_sys_coredump")
            
            st.divider()
            bind_checkbox("Verify Reload Cause (`VerifyReloadCause`)", key="chk_sys_reload")

            st.divider()
            chk_sys_cpu = bind_checkbox("Verify CPU Utilization (`VerifyCPUUtilization`)", key="chk_sys_cpu")
            st.number_input("Max Allowed CPU Utilization (%)", value=st.session_state.get("param_sys_cpu_val", 75), min_value=1, max_value=100, key="param_sys_cpu_val", disabled=not chk_sys_cpu)

            st.divider()
            chk_sys_mem = bind_checkbox("Verify Memory Utilization (`VerifyMemoryUtilization`)", key="chk_sys_mem")
            st.number_input("Max Allowed Memory Utilization (%)", value=st.session_state.get("param_sys_mem_val", 80), min_value=1, max_value=100, key="param_sys_mem_val", disabled=not chk_sys_mem)

        # 3. SOFTWARE
        elif selected_cat == "Software":
            chk_sw_version = bind_checkbox("Verify EOS Version (`VerifyEOSVersion`)", key="chk_sw_version")
            st.text_input("Expected EOS Version (e.g. 4.30.2F)", value=st.session_state.get("param_sw_version_val", "4.30.2F"), key="param_sw_version_val", disabled=not chk_sw_version)

            st.divider()
            chk_sw_bootloader = bind_checkbox("Verify Bootloader Version (`VerifyBootloaderVersion`)", key="chk_sw_bootloader")
            st.text_input("Expected Bootloader Version", value=st.session_state.get("param_sw_bootloader_val", ""), key="param_sw_bootloader_val", disabled=not chk_sw_bootloader)

        # 4. AAA
        elif selected_cat == "AAA":
            chk_aaa_authen = bind_checkbox("Verify Authentication Methods (`VerifyAuthenMethods`)", key="chk_aaa_authen")
            c_a1, c_a2 = st.columns(2)
            with c_a1: st.text_input("Expected Auth Method", value=st.session_state.get("param_aaa_method", "local"), key="param_aaa_method", disabled=not chk_aaa_authen)
            with c_a2: st.selectbox("Auth Type", ["login", "enable"], key="param_aaa_type", disabled=not chk_aaa_authen)

            st.divider()
            chk_aaa_authz = bind_checkbox("Verify Authorization Methods (`VerifyAuthzMethods`)", key="chk_aaa_authz")
            st.text_input("Expected Authz Method (comma-separated)", value=st.session_state.get("param_aaa_authz_method", "group tacacs+"), key="param_aaa_authz_method", disabled=not chk_aaa_authz)

            st.divider()
            chk_aaa_acct_default = bind_checkbox("Verify Accounting Default Methods (`VerifyAcctDefaultMethods`)", key="chk_aaa_acct_default")
            st.text_input("Acct Default Methods (comma-separated)", value=st.session_state.get("param_aaa_acct_def_methods", "group tacacs+, local"), key="param_aaa_acct_def_methods", disabled=not chk_aaa_acct_default)

            st.divider()
            chk_aaa_acct_console = bind_checkbox("Verify Accounting Console Methods (`VerifyAcctConsoleMethods`)", key="chk_aaa_acct_console")
            st.text_input("Acct Console Methods (comma-separated)", value=st.session_state.get("param_aaa_acct_con_methods", "local"), key="param_aaa_acct_con_methods", disabled=not chk_aaa_acct_console)

            st.divider()
            chk_aaa_tacacs_src = bind_checkbox("Verify TACACS Source Interface (`VerifyTacacsSourceIntf`)", key="chk_aaa_tacacs_src")
            c_t1, c_t2 = st.columns(2)
            with c_t1: st.text_input("TACACS Source Interface", value=st.session_state.get("param_aaa_tacacs_src_intf", "Management1"), key="param_aaa_tacacs_src_intf", disabled=not chk_aaa_tacacs_src)
            with c_t2: st.text_input("TACACS VRF", value=st.session_state.get("param_aaa_tacacs_src_vrf", "default"), key="param_aaa_tacacs_src_vrf", disabled=not chk_aaa_tacacs_src)

            st.divider()
            chk_aaa_tacacs_servers = bind_checkbox("Verify TACACS Servers (`VerifyTacacsServers`)", key="chk_aaa_tacacs_servers")
            st.text_input("TACACS Server IPs (comma-separated)", value=st.session_state.get("param_aaa_tacacs_srv_ips", "10.1.1.1, 10.1.1.2"), key="param_aaa_tacacs_srv_ips", disabled=not chk_aaa_tacacs_servers)

            st.divider()
            chk_aaa_tacacs_groups = bind_checkbox("Verify TACACS Server Groups (`VerifyTacacsServerGroups`)", key="chk_aaa_tacacs_groups")
            st.text_input("TACACS Group Names (comma-separated)", value=st.session_state.get("param_aaa_tacacs_grp_names", "TACACS-SERVERS"), key="param_aaa_tacacs_grp_names", disabled=not chk_aaa_tacacs_groups)

            st.divider()
            chk_aaa_radius_src = bind_checkbox("Verify RADIUS Source Interface (`VerifyRadiusSourceIntf`)", key="chk_aaa_radius_src")
            c_r1, c_r2 = st.columns(2)
            with c_r1: st.text_input("RADIUS Source Interface", value=st.session_state.get("param_aaa_radius_src_intf", "Management1"), key="param_aaa_radius_src_intf", disabled=not chk_aaa_radius_src)
            with c_r2: st.text_input("RADIUS VRF", value=st.session_state.get("param_aaa_radius_src_vrf", "default"), key="param_aaa_radius_src_vrf", disabled=not chk_aaa_radius_src)

            st.divider()
            chk_aaa_radius_servers = bind_checkbox("Verify RADIUS Servers (`VerifyRadiusServers`)", key="chk_aaa_radius_servers")
            st.text_input("RADIUS Server IPs (comma-separated)", value=st.session_state.get("param_aaa_radius_srv_ips", "10.2.2.1"), key="param_aaa_radius_srv_ips", disabled=not chk_aaa_radius_servers)

        # 5. CONFIGURATION
        elif selected_cat == "Configuration":
            st.markdown("##### Dynamic Running Config Rules (`VerifyRunningConfig`)")
            if "cfg_rules_data" not in st.session_state:
                st.session_state.cfg_rules_data = saved_settings.get("cfg_rules_data", default_config_rules)
                
            edited_cfg_rules = st.data_editor(
                pd.DataFrame(st.session_state.cfg_rules_data),
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Section": st.column_config.TextColumn("Section (Optional)"),
                    "Match": st.column_config.TextColumn("Match String", required=True),
                    "Mode": st.column_config.SelectboxColumn("Mode", options=["exact", "contains", "regex"], default="exact"),
                    "Absent": st.column_config.CheckboxColumn("Absent?"),
                    "Description": st.column_config.TextColumn("Description")
                }
            )
            st.session_state.cfg_rules_data = edited_cfg_rules.to_dict("records")

            st.divider()
            chk_cfg_ztp = bind_checkbox("Verify Zero Touch Provisioning (`VerifyZeroTouch`)", key="chk_cfg_ztp")
            st.checkbox("ZTP Should Be Disabled", value=st.session_state.get("param_cfg_ztp_disabled", True), key="param_cfg_ztp_disabled", disabled=not chk_cfg_ztp)

            st.divider()
            bind_checkbox("Verify Running-Config vs Startup-Config Diff (`VerifyRunningConfigDiff`)", key="chk_cfg_diff")

            st.divider()
            chk_cfg_banner = bind_checkbox("Verify System Banner (`VerifyBanner`)", key="chk_cfg_banner")
            c_bn1, c_bn2 = st.columns(2)
            with c_bn1: st.selectbox("Banner Type", ["login", "motd"], key="param_cfg_banner_type", disabled=not chk_cfg_banner)
            with c_bn2: st.text_input("Expected Banner Text", value=st.session_state.get("param_cfg_banner_text", "Authorized Access Only"), key="param_cfg_banner_text", disabled=not chk_cfg_banner)

        # 6. CONNECTIVITY
        elif selected_cat == "Connectivity":
            chk_conn_ping = bind_checkbox("Verify IP Reachability (`VerifyReachability`)", key="chk_conn_ping")
            c_p1, c_p2 = st.columns(2)
            with c_p1: st.text_input("Destination IP", value=st.session_state.get("param_conn_dest", "8.8.8.8"), key="param_conn_dest", disabled=not chk_conn_ping)
            with c_p2: st.text_input("VRF (Ping)", value=st.session_state.get("param_conn_vrf", "default"), key="param_conn_vrf", disabled=not chk_conn_ping)
            
            st.divider()
            chk_conn_lldp = bind_checkbox("Verify LLDP Neighbor (`VerifyLLDPNeighbors`)", key="chk_conn_lldp")
            c_l1, c_l2, c_l3 = st.columns(3)
            with c_l1: st.text_input("Local Port", value=st.session_state.get("param_conn_lldp_port", "Ethernet1"), key="param_conn_lldp_port", disabled=not chk_conn_lldp)
            with c_l2: st.text_input("Neighbor Device Name", value=st.session_state.get("param_conn_lldp_device", "Switch-2"), key="param_conn_lldp_device", disabled=not chk_conn_lldp)
            with c_l3: st.text_input("Neighbor Port", value=st.session_state.get("param_conn_lldp_neighbor_port", "Ethernet1"), key="param_conn_lldp_neighbor_port", disabled=not chk_conn_lldp)

        # 7. INTERFACES
        elif selected_cat == "Interfaces":
            st.text_input("Interfaces to check status (Comma-separated)", value=st.session_state.get("param_target_intfs_input", "Ethernet1, Management1"), key="param_target_intfs_input")
            st.divider()
            bind_checkbox("Verify Interfaces Status (`VerifyInterfacesStatus`)", key="chk_int_status")
            bind_checkbox("Verify Interface Errors (`VerifyInterfaceErrors`)", key="chk_int_err")
            bind_checkbox("Verify Interface Discards (`VerifyInterfaceDiscards`)", key="chk_int_disc")
            st.divider()
            i_col1, i_col2 = st.columns(2)
            with i_col1:
                chk_int_speed = bind_checkbox("Verify Interfaces Speed", key="chk_int_speed")
                col_sp1, col_sp2 = st.columns(2)
                with col_sp1: st.text_input("Speed Intf", value=st.session_state.get("param_int_speed_intf", "Ethernet1"), key="param_int_speed_intf", disabled=not chk_int_speed)
                with col_sp2: st.number_input("Speed (Mbps)", value=st.session_state.get("param_int_speed_val", 1000), key="param_int_speed_val", disabled=not chk_int_speed)

                chk_int_l2mtu = bind_checkbox("Verify L2 MTU", key="chk_int_l2mtu")
                st.number_input("L2 MTU Value", value=st.session_state.get("param_int_l2mtu_val", 9214), key="param_int_l2mtu_val", disabled=not chk_int_l2mtu)
                
                chk_int_loopback = bind_checkbox("Verify Loopback Count", key="chk_int_loopback")
                st.number_input("Loopback Count", value=st.session_state.get("param_int_loopback_val", 1), key="param_int_loopback_val", disabled=not chk_int_loopback)
                
                chk_int_proxy_arp = bind_checkbox("Verify IP Proxy ARP", key="chk_int_proxy_arp")
                st.text_input("Proxy ARP Intfs (comma-sep)", value=st.session_state.get("param_int_proxy_arp_intf", "Vlan1"), key="param_int_proxy_arp_intf", disabled=not chk_int_proxy_arp)
                
                chk_int_vrrp_mac = bind_checkbox("Verify IP VRRP Mac", key="chk_int_vrrp_mac")
                st.text_input("VRRP MAC Address", value=st.session_state.get("param_int_vrrp_mac_val", "00:00:00:00:00:00"), key="param_int_vrrp_mac_val", disabled=not chk_int_vrrp_mac)
                
                chk_int_ipv4 = bind_checkbox("Verify Interface IPv4", key="chk_int_ipv4")
                col_ip1, col_ip2 = st.columns(2)
                with col_ip1: st.text_input("IPv4 Intf Name", value=st.session_state.get("param_int_ipv4_intf", "Ethernet1"), key="param_int_ipv4_intf", disabled=not chk_int_ipv4)
                with col_ip2: st.text_input("Primary IP CIDR", value=st.session_state.get("param_int_ipv4_ip", "10.0.0.1/24"), key="param_int_ipv4_ip", disabled=not chk_int_ipv4)

                bind_checkbox("Verify Illegal LACP", key="chk_int_ill_lacp")
                bind_checkbox("Verify Interface ErrDisabled", key="chk_int_err_dis")
                bind_checkbox("Verify Interface Utilization", key="chk_int_util")
                bind_checkbox("Verify Interfaces BER", key="chk_int_ber")
            with i_col2:
                chk_int_l3mtu = bind_checkbox("Verify L3 MTU", key="chk_int_l3mtu")
                st.number_input("L3 MTU Value", value=st.session_state.get("param_int_l3mtu_val", 1500), key="param_int_l3mtu_val", disabled=not chk_int_l3mtu)
                
                bind_checkbox("Verify Counter Details", key="chk_int_counter_det")
                bind_checkbox("Verify ECN Counters", key="chk_int_ecn")
                bind_checkbox("Verify Optics RX Power", key="chk_int_optics_rx")
                bind_checkbox("Verify Optics Temp", key="chk_int_optics_temp")
                bind_checkbox("Verify PFC Counters", key="chk_int_pfc")
                bind_checkbox("Verify Trident Counters", key="chk_int_trident")
                bind_checkbox("Verify Voq / Egress Drops", key="chk_int_voq")
                bind_checkbox("Verify Egress Queue Drops", key="chk_int_egress_drop")
                bind_checkbox("Verify Port Channels", key="chk_int_port_channel")
                bind_checkbox("Verify SVI", key="chk_int_svi")
                bind_checkbox("Verify Storm Control Drops", key="chk_int_storm")

        # 8. ROUTING GENERIC
        elif selected_cat == "Routing Generic":
            chk_rt_model = bind_checkbox("Verify Routing Protocol Model (`VerifyRoutingProtocolModel`)", key="chk_rt_model")
            st.selectbox("Protocol Model", ["multi-agent", "ribd"], key="param_rt_model_val", disabled=not chk_rt_model)
            
            st.divider()
            bind_checkbox("Verify IPv4 Unicast Routing Status (`VerifyRoutingStatus`)", key="chk_rt_status")
            
            st.divider()
            chk_rt_size = bind_checkbox("Verify Routing Table Size (`VerifyRoutingTableSize`)", key="chk_rt_size")
            col_min, col_max = st.columns(2)
            with col_min: st.number_input("Min Routes", value=st.session_state.get("param_rt_size_min", 1), min_value=1, key="param_rt_size_min", disabled=not chk_rt_size)
            with col_max: st.number_input("Max Routes", value=st.session_state.get("param_rt_size_max", 1000), min_value=1, key="param_rt_size_max", disabled=not chk_rt_size)
            
            st.divider()
            chk_rt_presence = bind_checkbox("Verify IPv4 Route Presence (`VerifyIPv4RoutePresencePerVRF`)", key="chk_rt_presence")
            c_rp1, c_rp2 = st.columns(2)
            with c_rp1: st.text_input("Route Prefix", value=st.session_state.get("param_rt_prefix", "10.0.0.0/24"), key="param_rt_prefix", disabled=not chk_rt_presence)
            with c_rp2: st.text_input("VRF (Route Presence)", value=st.session_state.get("param_rt_vrf", "default"), key="param_rt_vrf", disabled=not chk_rt_presence)

        # 9. ROUTING BGP
        elif selected_cat == "Routing BGP":
            chk_bgp_health = bind_checkbox("Verify BGP Peers Health (`VerifyBGPPeersHealth`)", key="chk_bgp_health")
            st.text_input("BGP VRF", value=st.session_state.get("param_bgp_vrf", "default"), key="param_bgp_vrf", disabled=not chk_bgp_health)

        # 10. STP (UPDATED WITH ROOT & MODE)
        elif selected_cat == "STP":
            bind_checkbox("Verify STP Blocked Ports (`VerifySTPBlockedPorts`)", key="chk_stp_blocked")
            
            st.divider()
            chk_stp_tc = bind_checkbox("Verify STP Topology Changes (`VerifyStpTopologyChanges`)", key="chk_stp_tc")
            st.number_input("Max Allowed Topology Changes Threshold", min_value=0, value=st.session_state.get("param_stp_tc_threshold", 1), step=1, key="param_stp_tc_threshold", disabled=not chk_stp_tc)

            st.divider()
            chk_stp_root = bind_checkbox("Verify STP Root Bridge (`VerifySTPRoot`)", key="chk_stp_root")
            st.text_input("Expected STP Root Bridge Bridge ID / Priority", value=st.session_state.get("param_stp_root_id", ""), key="param_stp_root_id", disabled=not chk_stp_root)

            st.divider()
            chk_stp_mode = bind_checkbox("Verify STP Operating Mode (`VerifySTPMode`)", key="chk_stp_mode")
            st.selectbox("Expected STP Mode", ["mstp", "rapid-pvst", "pvst"], key="param_stp_mode_val", disabled=not chk_stp_mode)

        # 11. EVPN & VXLAN (UPDATED WITH VTEP PEERS)
        elif selected_cat == "EVPN & VXLAN":
            chk_evpn_type5 = bind_checkbox("Verify EVPN Type 5 Routes (`VerifyEVPNType5Routes`)", key="chk_evpn_type5")
            c_ev1, c_ev2 = st.columns(2)
            with c_ev1: st.text_input("Network Prefix", value=st.session_state.get("param_evpn_prefix", "10.10.10.0/24"), key="param_evpn_prefix", disabled=not chk_evpn_type5)
            with c_ev2: st.number_input("VNI", value=st.session_state.get("param_evpn_vni", 10010), key="param_evpn_vni", disabled=not chk_evpn_type5)
            
            st.divider()
            bind_checkbox("Verify VXLAN1 Interface (`VerifyVxlan1Interface`)", key="chk_vxlan_intf")
            
            st.divider()
            bind_checkbox("Verify VXLAN Config Sanity (`VerifyVxlanConfigSanity`)", key="chk_vxlan_sanity")

            st.divider()
            chk_vtep_peers = bind_checkbox("Verify VTEP Peers (`VerifyVtepPeers`)", key="chk_vtep_peers")
            st.text_input("Expected VTEP Peer IPs (comma-separated)", value=st.session_state.get("param_vtep_peers_ips", "10.0.0.2, 10.0.0.3"), key="param_vtep_peers_ips", disabled=not chk_vtep_peers)

        # 12. MLAG
        elif selected_cat == "MLAG":
            bind_checkbox("Verify MLAG Status (`VerifyMlagStatus`)", key="chk_mlag_status")
            st.divider()
            bind_checkbox("Verify MLAG Interfaces (`VerifyMlagInterfaces`)", key="chk_mlag_interfaces")
            st.divider()
            bind_checkbox("Verify MLAG Config Sanity (`VerifyMlagConfigSanity`)", key="chk_mlag_config_sanity")
            st.divider()
            chk_mlag_reload_delay = bind_checkbox("Verify MLAG Reload Delay (`VerifyMlagReloadDelay`)", key="chk_mlag_reload_delay")
            c_md1, c_md2 = st.columns(2)
            with c_md1: st.number_input("Reload Delay (sec)", value=st.session_state.get("param_mlag_reload_delay", 300), key="param_mlag_reload_delay", disabled=not chk_mlag_reload_delay)
            with c_md2: st.number_input("Non-MLAG Delay (sec)", value=st.session_state.get("param_mlag_non_mlag_delay", 330), key="param_mlag_non_mlag_delay", disabled=not chk_mlag_reload_delay)

        # 13. MULTICAST
        elif selected_cat == "Multicast":
            chk_igmp_snooping_global = bind_checkbox("Verify IGMP Snooping Global Status (`VerifyIGMPSnoopingGlobal`)", key="chk_igmp_snooping_global")
            st.checkbox("Global IGMP Snooping Should Be Enabled", value=st.session_state.get("param_igmp_global_enabled", True), key="param_igmp_global_enabled", disabled=not chk_igmp_snooping_global)

            st.divider()
            chk_igmp_snooping_vlans = bind_checkbox("Verify IGMP Snooping per VLANs (`VerifyIGMPSnoopingVlans`)", key="chk_igmp_snooping_vlans")
            st.text_input("VLANs and Expected Status (e.g. 10:True, 12:False)", value=st.session_state.get("param_igmp_vlans_mapping", "10:True, 12:False"), key="param_igmp_vlans_mapping", disabled=not chk_igmp_snooping_vlans)

        # 14. SECURITY
        elif selected_cat == "Security":
            bind_checkbox("Verify eAPI HTTP Status (`VerifyAPIHttpStatus`)", key="chk_sec_api_http")
            
            st.divider()
            chk_sec_api_https_ssl = bind_checkbox("Verify eAPI HTTPS SSL Profile (`VerifyAPIHttpsSSL`)", key="chk_sec_api_https_ssl")
            st.text_input("eAPI SSL Profile Name", value=st.session_state.get("param_sec_api_ssl_profile", "default"), key="param_sec_api_ssl_profile", disabled=not chk_sec_api_https_ssl)

            st.divider()
            c_sec1, c_sec2 = st.columns(2)
            with c_sec1:
                chk_sec_api_v4_acl = bind_checkbox("Verify eAPI IPv4 ACL (`VerifyAPIIPv4Acl`)", key="chk_sec_api_v4_acl")
                st.text_input("eAPI IPv4 ACL Name", value=st.session_state.get("param_sec_api_v4_acl_name", "ACL-EAPI-V4"), key="param_sec_api_v4_acl_name", disabled=not chk_sec_api_v4_acl)
                st.text_input("eAPI IPv4 VRF", value=st.session_state.get("param_sec_api_v4_acl_vrf", "default"), key="param_sec_api_v4_acl_vrf", disabled=not chk_sec_api_v4_acl)
            with c_sec2:
                chk_sec_api_v6_acl = bind_checkbox("Verify eAPI IPv6 ACL (`VerifyAPIIPv6Acl`)", key="chk_sec_api_v6_acl")
                st.text_input("eAPI IPv6 ACL Name", value=st.session_state.get("param_sec_api_v6_acl_name", "ACL-EAPI-V6"), key="param_sec_api_v6_acl_name", disabled=not chk_sec_api_v6_acl)
                st.text_input("eAPI IPv6 VRF", value=st.session_state.get("param_sec_api_v6_acl_vrf", "default"), key="param_sec_api_v6_acl_vrf", disabled=not chk_sec_api_v6_acl)

            st.divider()
            chk_sec_ssl_cert = bind_checkbox("Verify SSL Certificates (`VerifyAPISSLCertificate`)", key="chk_sec_ssl_cert")
            st.number_input("Cert Expiry Threshold (Days)", value=st.session_state.get("param_sec_ssl_cert_days", 30), min_value=1, key="param_sec_ssl_cert_days", disabled=not chk_sec_ssl_cert)

            st.divider()
            bind_checkbox("Verify Hardware Entropy (`VerifyHardwareEntropy`)", key="chk_sec_entropy")

            st.divider()
            bind_checkbox("Verify IPSec Connections Health (`VerifyIPSecConnHealth`)", key="chk_sec_ipsec_health")

            st.divider()
            c_ssh1, c_ssh2 = st.columns(2)
            with c_ssh1:
                chk_sec_ssh_v4_acl = bind_checkbox("Verify SSH IPv4 ACL (`VerifySSHIPv4Acl`)", key="chk_sec_ssh_v4_acl")
                st.text_input("SSH IPv4 ACL Name", value=st.session_state.get("param_sec_ssh_v4_acl_name", "ACL-SSH-V4"), key="param_sec_ssh_v4_acl_name", disabled=not chk_sec_ssh_v4_acl)
            with c_ssh2:
                chk_sec_ssh_v6_acl = bind_checkbox("Verify SSH IPv6 ACL (`VerifySSHIPv6Acl`)", key="chk_sec_ssh_v6_acl")
                st.text_input("SSH IPv6 ACL Name", value=st.session_state.get("param_sec_ssh_v6_acl_name", "ACL-SSH-V6"), key="param_sec_ssh_v6_acl_name", disabled=not chk_sec_ssh_v6_acl)

            st.divider()
            bind_checkbox("Verify SSH Service Status (`VerifySSHStatus`)", key="chk_ssh_status")

            st.divider()
            bind_checkbox("Verify Telnet Status (`VerifyTelnetStatus` - Ensure Disabled)", key="chk_sec_telnet")

        # 15. STUN
        elif selected_cat == "STUN":
            chk_stun_status = bind_checkbox("Verify STUN Server Status (`VerifyStunServer`)", key="chk_stun_status")
            st.text_input("Expected STUN Server URL/IP", value=st.session_state.get("param_stun_server", "stun.l.google.com"), key="param_stun_server", disabled=not chk_stun_status)

        # 16. SERVICES
        elif selected_cat == "Services":
            chk_hostname = bind_checkbox("Verify Hostname (`VerifyHostname`)", key="chk_hostname")
            st.text_input("Expected Hostname", value=st.session_state.get("param_service_hostname", "Switch-1"), key="param_service_hostname", disabled=not chk_hostname)

            st.divider()
            chk_svc_dns_lookup = bind_checkbox("Verify DNS Name Resolution (`VerifyDNSLookup`)", key="chk_svc_dns_lookup")
            st.text_input("Domain Names to Resolve (comma-separated)", value=st.session_state.get("param_svc_dns_domains", "arista.com, google.com"), key="param_svc_dns_domains", disabled=not chk_svc_dns_lookup)

            st.divider()
            chk_svc_dns_servers = bind_checkbox("Verify Configured DNS Servers (`VerifyDNSServers`)", key="chk_svc_dns_servers")
            c_dns1, c_dns2 = st.columns(2)
            with c_dns1: st.text_input("DNS Server IPs (comma-separated)", value=st.session_state.get("param_svc_dns_srv_ips", "8.8.8.8, 1.1.1.1"), key="param_svc_dns_srv_ips", disabled=not chk_svc_dns_servers)
            with c_dns2: st.text_input("DNS Servers VRF", value=st.session_state.get("param_svc_dns_srv_vrf", "default"), key="param_svc_dns_srv_vrf", disabled=not chk_svc_dns_servers)

            st.divider()
            bind_checkbox("Verify Errdisable Recovery (`VerifyErrdisableRecovery`)", key="chk_svc_errdisable_rec")

        # 17. FLOW TRACKING
        elif selected_cat == "Flow Tracking":
            chk_flow_tracking = bind_checkbox("Verify Hardware Flow Tracker Status (`VerifyHardwareFlowTrackerStatus`)", key="chk_flow_tracking")
            st.text_input("Tracker Name", value=st.session_state.get("param_flow_tracker_name", "FLOW-TRACKER"), key="param_flow_tracker_name", disabled=not chk_flow_tracking)

        # 18. LANZ
        elif selected_cat == "LANZ":
            bind_checkbox("Verify LANZ Status (`VerifyLANZ`)", key="chk_lanz")

        # 19. LOGGING
        elif selected_cat == "Logging":
            bind_checkbox("Verify Persistent Logging (`VerifyLoggingPersistent`)", key="chk_log_persistent")
            st.divider()
            bind_checkbox("Verify Logging Accounting (`VerifyLoggingAccounting`)", key="chk_log_accounting")
            st.divider()
            chk_log_source_intf = bind_checkbox("Verify Logging Source Interface (`VerifyLoggingSourceIntf`)", key="chk_log_source_intf")
            c_ls1, c_ls2 = st.columns(2)
            with c_ls1: st.text_input("Source VRF", value=st.session_state.get("param_log_src_vrf", "default"), key="param_log_src_vrf", disabled=not chk_log_source_intf)
            with c_ls2: st.text_input("Source Intf", value=st.session_state.get("param_log_src_intf", "Loopback0"), key="param_log_src_intf", disabled=not chk_log_source_intf)
            st.divider()
            chk_log_hosts = bind_checkbox("Verify Logging Hosts (`VerifyLoggingHosts`)", key="chk_log_hosts")
            c_lh1, c_lh2 = st.columns(2)
            with c_lh1: st.text_input("Host IPs (comma-sep)", value=st.session_state.get("param_log_hosts_ips", "10.0.0.1"), key="param_log_hosts_ips", disabled=not chk_log_hosts)
            with c_lh2: st.text_input("Hosts VRF", value=st.session_state.get("param_log_hosts_vrf", "default"), key="param_log_hosts_vrf", disabled=not chk_log_hosts)

        # 20. PATH SELECTION
        elif selected_cat == "Path Selection":
            bind_checkbox("Verify Path Selection Health (`VerifyPathsHealth`)", key="chk_path_sel_health")

        # 21. SNMP (UPDATED WITH COMMUNITY)
        elif selected_cat == "SNMP":
            chk_snmp_status = bind_checkbox("Verify SNMP Status (`VerifySnmpStatus`)", key="chk_snmp_status")
            st.text_input("SNMP VRF", value=st.session_state.get("param_snmp_vrf", "default"), key="param_snmp_vrf", disabled=not chk_snmp_status)

            st.divider()
            chk_snmp_community = bind_checkbox("Verify SNMP Communities (`VerifySnmpCommunity`)", key="chk_snmp_community")
            st.text_input("Expected SNMP Community Names (comma-separated)", value=st.session_state.get("param_snmp_communities", "public, private"), key="param_snmp_communities", disabled=not chk_snmp_community)

        # 22. VLAN (UPDATED WITH VLANS STATUS)
        elif selected_cat == "VLAN":
            chk_vlan_internal = bind_checkbox("Verify VLAN Internal Allocation Policy (`VerifyVlanInternalPolicy`)", key="chk_vlan_internal")
            st.selectbox("Allocation Policy", ["ascending", "descending"], key="param_vlan_alloc_policy", disabled=not chk_vlan_internal)
            col_v1, col_v2 = st.columns(2)
            with col_v1: st.number_input("Start VLAN ID", min_value=1, max_value=4094, value=st.session_state.get("param_vlan_start_id", 1006), key="param_vlan_start_id", disabled=not chk_vlan_internal)
            with col_v2: st.number_input("End VLAN ID", min_value=1, max_value=4094, value=st.session_state.get("param_vlan_end_id", 4094), key="param_vlan_end_id", disabled=not chk_vlan_internal)

            st.divider()
            chk_vlans_status = bind_checkbox("Verify Specific VLANs Status & Names (`VerifyVlans`)", key="chk_vlans_status")
            st.text_input("VLAN IDs to check (comma-separated)", value=st.session_state.get("param_vlans_list", "10, 20, 30"), key="param_vlans_list", disabled=not chk_vlans_status)

        # 23. CUSTOM YAML
        elif selected_cat == "Custom YAML":
            st.markdown("Paste custom YAML config for advanced ANTA tests.")
            default_custom = "# anta.tests.system:\n#   - VerifyUptime:\n#       minimum: 10\n"
            st.text_area("Custom YAML Input", value=st.session_state.get("param_custom_yaml", default_custom), height=200, key="param_custom_yaml")

    # --- AUTO-SAVE CATALOG GENERATION FROM SESSION STATE ---
    catalog_dict = {}
    parsed_tags = [t.strip() for t in st.session_state.get("input_catalog_tags", "").split(",") if t.strip()]
    
    def add_test(module, test_dict):
        if module not in catalog_dict:
            catalog_dict[module] = []
        
        for test_name, params in test_dict.items():
            test_body = {}
            if isinstance(params, dict):
                test_body.update(params)
            
            if parsed_tags:
                test_body["filters"] = {"tags": parsed_tags}
            
            val = test_body if test_body else None
            catalog_dict[module].append({test_name: val})

    # Hardware
    if st.session_state.get("chk_hw_trans", False): 
        mfg_val = st.session_state.get("param_hw_trans_mfg", "Arista Networks, ARISTA")
        add_test("anta.tests.hardware", {"VerifyTransceiversManufacturers": {"manufacturers": [m.strip() for m in mfg_val.split(",") if m.strip()]}})
    if st.session_state.get("chk_hw_trans_presence", False):
        pres_val = st.session_state.get("param_hw_trans_pres_intfs", "Ethernet1, Ethernet2")
        add_test("anta.tests.hardware", {"VerifyTransceiversPresence": {"interfaces": [{"name": i.strip()} for i in pres_val.split(",") if i.strip()]}})
    if st.session_state.get("chk_hw_trans_optics", False): add_test("anta.tests.hardware", {"VerifyTransceiversOptics": None})
    if st.session_state.get("chk_hw_cool", False): add_test("anta.tests.hardware", {"VerifyEnvironmentSystemCooling": None})
    if st.session_state.get("chk_hw_power", False): 
        pwr_val = st.session_state.get("param_hw_power_states", "ok")
        add_test("anta.tests.hardware", {"VerifyEnvironmentPower": {"states": [s.strip() for s in pwr_val.split(",") if s.strip()]}})
    if st.session_state.get("chk_hw_temp", False): add_test("anta.tests.hardware", {"VerifyTemperature": None})
    if st.session_state.get("chk_hw_pse", False): add_test("anta.tests.hardware", {"VerifyPseStatus": None})
        
    # System
    if st.session_state.get("chk_sys_uptime", False): add_test("anta.tests.system", {"VerifyUptime": {"minimum": int(st.session_state.get("param_sys_uptime_val", 60))}})
    if st.session_state.get("chk_sys_ntp", False): add_test("anta.tests.system", {"VerifyNTP": None})
    if st.session_state.get("chk_sys_coredump", False): add_test("anta.tests.system", {"VerifyCoredump": None})
    if st.session_state.get("chk_sys_reload", False): add_test("anta.tests.system", {"VerifyReloadCause": None})
    if st.session_state.get("chk_sys_cpu", False): add_test("anta.tests.system", {"VerifyCPUUtilization": {"minimum": int(st.session_state.get("param_sys_cpu_val", 75))}})
    if st.session_state.get("chk_sys_mem", False): add_test("anta.tests.system", {"VerifyMemoryUtilization": {"minimum": int(st.session_state.get("param_sys_mem_val", 80))}})

    # Software
    if st.session_state.get("chk_sw_version", False):
        add_test("anta.tests.software", {"VerifyEOSVersion": {"version": st.session_state.get("param_sw_version_val", "4.30.2F")}})
    if st.session_state.get("chk_sw_bootloader", False):
        b_val = st.session_state.get("param_sw_bootloader_val", "").strip()
        if b_val: add_test("anta.tests.software", {"VerifyBootloaderVersion": {"version": b_val}})

    # AAA
    if st.session_state.get("chk_aaa_authen", False): add_test("anta.tests.aaa", {"VerifyAuthenMethods": {"methods": [st.session_state.get("param_aaa_method", "local")], "types": [st.session_state.get("param_aaa_type", "login")]}})
    if st.session_state.get("chk_aaa_authz", False): add_test("anta.tests.aaa", {"VerifyAuthzMethods": {"methods": [m.strip() for m in st.session_state.get("param_aaa_authz_method", "group tacacs+").split(",") if m.strip()]}})
    if st.session_state.get("chk_aaa_acct_default", False): add_test("anta.tests.aaa", {"VerifyAcctDefaultMethods": {"methods": [m.strip() for m in st.session_state.get("param_aaa_acct_def_methods", "group tacacs+, local").split(",") if m.strip()]}})
    if st.session_state.get("chk_aaa_acct_console", False): add_test("anta.tests.aaa", {"VerifyAcctConsoleMethods": {"methods": [m.strip() for m in st.session_state.get("param_aaa_acct_con_methods", "local").split(",") if m.strip()]}})
    if st.session_state.get("chk_aaa_tacacs_src", False): add_test("anta.tests.aaa", {"VerifyTacacsSourceIntf": {"intf": st.session_state.get("param_aaa_tacacs_src_intf", "Management1"), "vrf": st.session_state.get("param_aaa_tacacs_src_vrf", "default")}})
    if st.session_state.get("chk_aaa_tacacs_servers", False): add_test("anta.tests.aaa", {"VerifyTacacsServers": {"servers": [{"server": ip.strip()} for ip in st.session_state.get("param_aaa_tacacs_srv_ips", "10.1.1.1").split(",") if ip.strip()]}})
    if st.session_state.get("chk_aaa_tacacs_groups", False): add_test("anta.tests.aaa", {"VerifyTacacsServerGroups": {"groups": [g.strip() for g in st.session_state.get("param_aaa_tacacs_grp_names", "TACACS-SERVERS").split(",") if g.strip()]}})
    if st.session_state.get("chk_aaa_radius_src", False): add_test("anta.tests.aaa", {"VerifyRadiusSourceIntf": {"intf": st.session_state.get("param_aaa_radius_src_intf", "Management1"), "vrf": st.session_state.get("param_aaa_radius_src_vrf", "default")}})
    if st.session_state.get("chk_aaa_radius_servers", False): add_test("anta.tests.aaa", {"VerifyRadiusServers": {"servers": [{"server": ip.strip()} for ip in st.session_state.get("param_aaa_radius_srv_ips", "10.2.2.1").split(",") if ip.strip()]}})

    # Configuration Tests
    if st.session_state.get("chk_cfg_ztp", False): add_test("anta.tests.configuration", {"VerifyZeroTouch": {"disabled": st.session_state.get("param_cfg_ztp_disabled", True)}})
    if st.session_state.get("chk_cfg_diff", False): add_test("anta.tests.configuration", {"VerifyRunningConfigDiff": None})
    if st.session_state.get("chk_cfg_banner", False):
        b_type = st.session_state.get("param_cfg_banner_type", "login")
        b_key = "login_banner" if b_type == "login" else "motd_banner"
        add_test("anta.tests.configuration", {"VerifyBanner": {"type": b_type, b_key: st.session_state.get("param_cfg_banner_text", "Authorized Access Only")}})

    if st.session_state.get("cfg_rules_data", None):
        cfg_rules_parsed = []
        rules_map = {}
        for row in st.session_state.cfg_rules_data:
            match_val = str(row.get("Match", "")).strip()
            if not match_val: continue
            sec_val = str(row.get("Section", "")).strip()
            mode_val = row.get("Mode", "exact")
            absent_val = bool(row.get("Absent", False))
            desc_val = str(row.get("Description", "")).strip()
            entry = {"match": match_val}
            if mode_val != "exact": entry["mode"] = mode_val
            if absent_val: entry["absent"] = True
            if desc_val: entry["description"] = desc_val
            if sec_val not in rules_map: rules_map[sec_val] = []
            rules_map[sec_val].append(entry)
        for sec, entries in rules_map.items():
            rule = {"entries": entries}
            if sec: rule["section"] = [s.strip() for s in sec.split(",")]
            cfg_rules_parsed.append(rule)
        if cfg_rules_parsed:
            add_test("anta.tests.configuration", {"VerifyRunningConfig": {"rules": cfg_rules_parsed}})

    # Connectivity
    if st.session_state.get("chk_conn_ping", False): add_test("anta.tests.connectivity", {"VerifyReachability": {"hosts": [{"destination": st.session_state.get("param_conn_dest", "8.8.8.8"), "vrf": st.session_state.get("param_conn_vrf", "default")}]}})
    if st.session_state.get("chk_conn_lldp", False):
        add_test("anta.tests.connectivity", {
            "VerifyLLDPNeighbors": {
                "neighbors": [{"port": st.session_state.get("param_conn_lldp_port", "Ethernet1"), "neighbor_device": st.session_state.get("param_conn_lldp_device", "Switch-2"), "neighbor_port": st.session_state.get("param_conn_lldp_neighbor_port", "Ethernet1")}]
            }
        })

    # Interfaces
    parsed_intfs = [i.strip() for i in st.session_state.get("param_target_intfs_input", "Ethernet1").split(",") if i.strip()]
    if st.session_state.get("chk_int_status", False) and parsed_intfs:
        add_test("anta.tests.interfaces", {"VerifyInterfacesStatus": {"interfaces": [{"name": i, "status": "up"} for i in parsed_intfs]}})
            
    if st.session_state.get("chk_int_proxy_arp", False): 
        p_intfs = [i.strip() for i in st.session_state.get("param_int_proxy_arp_intf", "Vlan1").split(",") if i.strip()]
        if p_intfs: add_test("anta.tests.interfaces", {"VerifyIPProxyARP": {"interfaces": p_intfs}})
        
    if st.session_state.get("chk_int_vrrp_mac", False): add_test("anta.tests.interfaces", {"VerifyIpVirtualRouterMac": {"mac_address": st.session_state.get("param_int_vrrp_mac_val", "00:00:00:00:00:00")}})
    if st.session_state.get("chk_int_ipv4", False): add_test("anta.tests.interfaces", {"VerifyInterfaceIPv4": {"interfaces": [{"name": st.session_state.get("param_int_ipv4_intf", "Ethernet1"), "primary_ip": st.session_state.get("param_int_ipv4_ip", "10.0.0.1/24")}]}})
    if st.session_state.get("chk_int_speed", False): add_test("anta.tests.interfaces", {"VerifyInterfacesSpeed": {"interfaces": [{"name": st.session_state.get("param_int_speed_intf", "Ethernet1"), "speed": int(st.session_state.get("param_int_speed_val", 1000))}]}})
    if st.session_state.get("chk_int_l2mtu", False): add_test("anta.tests.interfaces", {"VerifyL2MTU": {"mtu": int(st.session_state.get("param_int_l2mtu_val", 9214))}})
    if st.session_state.get("chk_int_l3mtu", False): add_test("anta.tests.interfaces", {"VerifyL3MTU": {"mtu": int(st.session_state.get("param_int_l3mtu_val", 1500))}})
    if st.session_state.get("chk_int_loopback", False): add_test("anta.tests.interfaces", {"VerifyLoopbackCount": {"number": int(st.session_state.get("param_int_loopback_val", 1))}})

    if st.session_state.get("chk_int_err", False): add_test("anta.tests.interfaces", {"VerifyInterfaceErrors": None})
    if st.session_state.get("chk_int_disc", False): add_test("anta.tests.interfaces", {"VerifyInterfaceDiscards": None})
    if st.session_state.get("chk_int_ill_lacp", False): add_test("anta.tests.interfaces", {"VerifyIllegalLACP": None})
    if st.session_state.get("chk_int_err_dis", False): add_test("anta.tests.interfaces", {"VerifyInterfaceErrDisabled": None})
    if st.session_state.get("chk_int_util", False): add_test("anta.tests.interfaces", {"VerifyInterfaceUtilization": None})
    if st.session_state.get("chk_int_trident", False): add_test("anta.tests.interfaces", {"VerifyInterfacesTridentCounters": None})
    if st.session_state.get("chk_int_port_channel", False): add_test("anta.tests.interfaces", {"VerifyPortChannels": None})
    if st.session_state.get("chk_int_svi", False): add_test("anta.tests.interfaces", {"VerifySVI": None})
    if st.session_state.get("chk_int_ber", False): add_test("anta.tests.interfaces", {"VerifyInterfacesBER": None})
    if st.session_state.get("chk_int_counter_det", False): add_test("anta.tests.interfaces", {"VerifyInterfacesCounterDetails": None})
    if st.session_state.get("chk_int_ecn", False): add_test("anta.tests.interfaces", {"VerifyInterfacesECNCounters": None})
    if st.session_state.get("chk_int_egress_drop", False): add_test("anta.tests.interfaces", {"VerifyInterfacesEgressQueueDrops": None})
    if st.session_state.get("chk_int_optics_rx", False): add_test("anta.tests.interfaces", {"VerifyInterfacesOpticsReceivePower": None})
    if st.session_state.get("chk_int_optics_temp", False): add_test("anta.tests.interfaces", {"VerifyInterfacesOpticsTemperature": None})
    if st.session_state.get("chk_int_pfc", False): add_test("anta.tests.interfaces", {"VerifyInterfacesPFCCounters": None})
    if st.session_state.get("chk_int_voq", False): add_test("anta.tests.interfaces", {"VerifyInterfacesVoqAndEgressQueueDrops": None})
    if st.session_state.get("chk_int_storm", False): add_test("anta.tests.interfaces", {"VerifyStormControlDrops": None})

    # Routing
    if st.session_state.get("chk_rt_model", False): add_test("anta.tests.routing.generic", {"VerifyRoutingProtocolModel": {"model": st.session_state.get("param_rt_model_val", "multi-agent")}})
    if st.session_state.get("chk_rt_status", False): add_test("anta.tests.routing.generic", {"VerifyRoutingStatus": {"ipv4_unicast": True}})
    if st.session_state.get("chk_rt_size", False): add_test("anta.tests.routing.generic", {"VerifyRoutingTableSize": {"minimum": int(st.session_state.get("param_rt_size_min", 1)), "maximum": int(st.session_state.get("param_rt_size_max", 1000))}})
    if st.session_state.get("chk_rt_presence", False): add_test("anta.tests.routing.generic", {"VerifyIPv4RoutePresencePerVRF": {"route_entries": [{"prefix": st.session_state.get("param_rt_prefix", "10.0.0.0/24"), "vrf": st.session_state.get("param_rt_vrf", "default")}]}})
    if st.session_state.get("chk_bgp_health", False): add_test("anta.tests.routing.bgp", {"VerifyBGPPeersHealth": {"address_families": [{"afi": "ipv4", "safi": "unicast", "vrf": st.session_state.get("param_bgp_vrf", "default")}]}})
    
    # STP
    if st.session_state.get("chk_stp_blocked", False): add_test("anta.tests.stp", {"VerifySTPBlockedPorts": None})
    if st.session_state.get("chk_stp_tc", False): add_test("anta.tests.stp", {"VerifyStpTopologyChanges": {"threshold": int(st.session_state.get("param_stp_tc_threshold", 1))}})
    if st.session_state.get("chk_stp_root", False):
        root_val = st.session_state.get("param_stp_root_id", "").strip()
        if root_val: add_test("anta.tests.stp", {"VerifySTPRoot": {"priority": root_val}})
    if st.session_state.get("chk_stp_mode", False):
        add_test("anta.tests.stp", {"VerifySTPMode": {"mode": st.session_state.get("param_stp_mode_val", "mstp")}})
        
    # EVPN / VXLAN
    if st.session_state.get("chk_evpn_type5", False): add_test("anta.tests.evpn", {"VerifyEVPNType5Routes": {"prefixes": [{"address": st.session_state.get("param_evpn_prefix", "10.10.10.0/24"), "vni": int(st.session_state.get("param_evpn_vni", 10010))}]}})
    if st.session_state.get("chk_vxlan_intf", False): add_test("anta.tests.vxlan", {"VerifyVxlan1Interface": None})
    if st.session_state.get("chk_vxlan_sanity", False): add_test("anta.tests.vxlan", {"VerifyVxlanConfigSanity": None})
    if st.session_state.get("chk_vtep_peers", False):
        vtep_ips = [ip.strip() for ip in st.session_state.get("param_vtep_peers_ips", "10.0.0.2").split(",") if ip.strip()]
        add_test("anta.tests.vxlan", {"VerifyVtepPeers": {"peers": vtep_ips}})
        
    # MLAG
    if st.session_state.get("chk_mlag_status", False): add_test("anta.tests.mlag", {"VerifyMlagStatus": None})
    if st.session_state.get("chk_mlag_interfaces", False): add_test("anta.tests.mlag", {"VerifyMlagInterfaces": None})
    if st.session_state.get("chk_mlag_config_sanity", False): add_test("anta.tests.mlag", {"VerifyMlagConfigSanity": None})
    if st.session_state.get("chk_mlag_reload_delay", False): add_test("anta.tests.mlag", {"VerifyMlagReloadDelay": {"reload_delay": int(st.session_state.get("param_mlag_reload_delay", 300)), "reload_delay_non_mlag": int(st.session_state.get("param_mlag_non_mlag_delay", 330))}})

    # Multicast
    if st.session_state.get("chk_igmp_snooping_global", False): add_test("anta.tests.multicast", {"VerifyIGMPSnoopingGlobal": {"enabled": st.session_state.get("param_igmp_global_enabled", True)}})
    if st.session_state.get("chk_igmp_snooping_vlans", False):
        v_map_str = st.session_state.get("param_igmp_vlans_mapping", "10:True, 12:False")
        vlans_dict = {}
        for pair in v_map_str.split(","):
            if ":" in pair:
                v_id, v_st = pair.split(":")
                try: vlans_dict[int(v_id.strip())] = (v_st.strip().lower() == "true")
                except ValueError: pass
        if vlans_dict: add_test("anta.tests.multicast", {"VerifyIGMPSnoopingVlans": {"vlans": vlans_dict}})

    # Security
    if st.session_state.get("chk_sec_api_http", False): add_test("anta.tests.security", {"VerifyAPIHttpStatus": None})
    if st.session_state.get("chk_sec_api_https_ssl", False): add_test("anta.tests.security", {"VerifyAPIHttpsSSL": {"profile": st.session_state.get("param_sec_api_ssl_profile", "default")}})
    if st.session_state.get("chk_sec_api_v4_acl", False): add_test("anta.tests.security", {"VerifyAPIIPv4Acl": {"acl": st.session_state.get("param_sec_api_v4_acl_name", "ACL-EAPI-V4"), "vrf": st.session_state.get("param_sec_api_v4_acl_vrf", "default")}})
    if st.session_state.get("chk_sec_api_v6_acl", False): add_test("anta.tests.security", {"VerifyAPIIPv6Acl": {"acl": st.session_state.get("param_sec_api_v6_acl_name", "ACL-EAPI-V6"), "vrf": st.session_state.get("param_sec_api_v6_acl_vrf", "default")}})
    if st.session_state.get("chk_sec_ssl_cert", False): add_test("anta.tests.security", {"VerifyAPISSLCertificate": {"minimum_expiry_days": int(st.session_state.get("param_sec_ssl_cert_days", 30))}})
    if st.session_state.get("chk_sec_entropy", False): add_test("anta.tests.security", {"VerifyHardwareEntropy": None})
    if st.session_state.get("chk_sec_ipsec_health", False): add_test("anta.tests.security", {"VerifyIPSecConnHealth": None})
    if st.session_state.get("chk_sec_ssh_v4_acl", False): add_test("anta.tests.security", {"VerifySSHIPv4Acl": {"acl": st.session_state.get("param_sec_ssh_v4_acl_name", "ACL-SSH-V4")}})
    if st.session_state.get("chk_sec_ssh_v6_acl", False): add_test("anta.tests.security", {"VerifySSHIPv6Acl": {"acl": st.session_state.get("param_sec_ssh_v6_acl_name", "ACL-SSH-V6")}})
    if st.session_state.get("chk_ssh_status", False): add_test("anta.tests.security", {"VerifySSHStatus": None})
    if st.session_state.get("chk_sec_telnet", False): add_test("anta.tests.security", {"VerifyTelnetStatus": None})

    # STUN
    if st.session_state.get("chk_stun_status", False):
        add_test("anta.tests.stun", {"VerifyStunServer": {"server": st.session_state.get("param_stun_server", "stun.l.google.com")}})

    # Services
    if st.session_state.get("chk_hostname", False): add_test("anta.tests.services", {"VerifyHostname": {"hostname": st.session_state.get("param_service_hostname", "Switch-1")}})
    if st.session_state.get("chk_svc_dns_lookup", False): 
        doms = [d.strip() for d in st.session_state.get("param_svc_dns_domains", "arista.com, google.com").split(",") if d.strip()]
        add_test("anta.tests.services", {"VerifyDNSLookup": {"domain_names": doms}})
    if st.session_state.get("chk_svc_dns_servers", False):
        ips = [ip.strip() for ip in st.session_state.get("param_svc_dns_srv_ips", "8.8.8.8, 1.1.1.1").split(",") if ip.strip()]
        add_test("anta.tests.services", {"VerifyDNSServers": {"dns_servers": [{"server": ip, "vrf": st.session_state.get("param_svc_dns_srv_vrf", "default")} for ip in ips]}})
    if st.session_state.get("chk_svc_errdisable_rec", False): add_test("anta.tests.services", {"VerifyErrdisableRecovery": None})

    # Flow Tracking
    if st.session_state.get("chk_flow_tracking", False): add_test("anta.tests.flow_tracking", {"VerifyHardwareFlowTrackerStatus": {"trackers": [{"name": st.session_state.get("param_flow_tracker_name", "FLOW-TRACKER")}]}})

    # LANZ
    if st.session_state.get("chk_lanz", False): add_test("anta.tests.lanz", {"VerifyLANZ": None})

    # Logging
    if st.session_state.get("chk_log_persistent", False): add_test("anta.tests.logging", {"VerifyLoggingPersistent": None})
    if st.session_state.get("chk_log_accounting", False): add_test("anta.tests.logging", {"VerifyLoggingAccounting": None})
    if st.session_state.get("chk_log_source_intf", False): add_test("anta.tests.logging", {"VerifyLoggingSourceIntf": {"vrf": st.session_state.get("param_log_src_vrf", "default"), "interface": st.session_state.get("param_log_src_intf", "Loopback0")}})
    if st.session_state.get("chk_log_hosts", False): add_test("anta.tests.logging", {"VerifyLoggingHosts": {"hosts": [i.strip() for i in st.session_state.get("param_log_hosts_ips", "10.0.0.1").split(",") if i.strip()], "vrf": st.session_state.get("param_log_hosts_vrf", "default")}})

    # Path Selection
    if st.session_state.get("chk_path_sel_health", False): add_test("anta.tests.path_selection", {"VerifyPathsHealth": None})

    # SNMP
    if st.session_state.get("chk_snmp_status", False): add_test("anta.tests.snmp", {"VerifySnmpStatus": {"vrf": st.session_state.get("param_snmp_vrf", "default")}})
    if st.session_state.get("chk_snmp_community", False):
        comm_val = st.session_state.get("param_snmp_communities", "public")
        add_test("anta.tests.snmp", {"VerifySnmpCommunity": {"communities": [c.strip() for c in comm_val.split(",") if c.strip()]}})

    # VLAN
    if st.session_state.get("chk_vlan_internal", False): 
        add_test("anta.tests.vlan", {
            "VerifyVlanInternalPolicy": {
                "policy": st.session_state.get("param_vlan_alloc_policy", "ascending"),
                "start_vlan_id": int(st.session_state.get("param_vlan_start_id", 1006)),
                "end_vlan_id": int(st.session_state.get("param_vlan_end_id", 4094))
            }
        })
    if st.session_state.get("chk_vlans_status", False):
        v_list = [int(v.strip()) for v in st.session_state.get("param_vlans_list", "10, 20").split(",") if v.strip().isdigit()]
        if v_list: add_test("anta.tests.vlan", {"VerifyVlans": {"vlans": v_list}})
        
    try:
        c_yaml = st.session_state.get("param_custom_yaml", "")
        if c_yaml:
            parsed_custom = yaml.safe_load(c_yaml)
            if parsed_custom and isinstance(parsed_custom, dict):
                for module, tests in parsed_custom.items():
                    if module not in catalog_dict: catalog_dict[module] = []
                    if isinstance(tests, list): catalog_dict[module].extend(tests)
                    
        with open("catalog.yml", "w") as f:
            yaml.safe_dump(catalog_dict, f, sort_keys=False)
            
        current_active_keys = [k for k in ALL_TEST_KEYS if st.session_state.get(k, False)]
        save_settings({"selected_test_keys": current_active_keys, "catalog_tags": st.session_state.get("input_catalog_tags", "")})
    except Exception as e:
        st.error(f"Failed to parse Custom YAML: {e}")

# ==========================================
# TAB 4: DASHBOARD (Runner)
# ==========================================
with tab_dashboard:
    st.subheader("Run Network Tests")
    
    run_tags_input = st.text_input(
        "🏷️ Filter NRFU Execution by Tags (Optional CLI Filter)", 
        placeholder="e.g. leaf, spine",
        key="input_run_tags",
        help="Applies '--tags' to the CLI execution to run tests only on devices/tests with matching tags."
    )
    
    if st.button("🚀 Execute Tests", type="primary", use_container_width=True):
        os.environ["ANTA_USERNAME"] = st.session_state.anta_user
        os.environ["ANTA_PASSWORD"] = st.session_state.anta_pass
        
        with st.spinner("Connecting to switches and running tests... Please wait."):
            cmd = ["anta", "nrfu"]
            if run_tags_input.strip():
                cmd.extend(["--tags", run_tags_input.strip()])
            cmd.extend(["--inventory", "inventory.yml", "--catalog", "catalog.yml", "--ignore-status", "json"])
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            output = result.stdout
            stderr_output = result.stderr or ""
            
            ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
            output_clean = ansi_escape.sub('', output)
            stderr_clean = ansi_escape.sub('', stderr_output)
            full_log = output_clean + "\n" + stderr_clean
            
            try:
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
                
                if "ValidationError" in full_log or "CRITICAL Failed to parse the catalog" in full_log:
                    st.error("🚨 **Catalog Validation Error (ValidationError)**\nOne of the selected tests requires additional parameters or has invalid inputs. Expand the log below to see which test failed validation.")
                    with st.expander("View Validation Error Details", expanded=True):
                        st.code(full_log, language=None)
                
                elif "No tests scheduled to run" in full_log:
                    st.warning("⚠️ **Notice:** ANTA skipped running tests because a tag filter in the catalog or execution filter does not match any device in Inventory.")
                
                elif not data:
                    st.error("No test results received from ANTA. Please ensure tests are selected and tag filters are correct.")
                    with st.expander("View Full Raw Output"):
                        st.code(full_log, language=None)
                else:
                    df = pd.DataFrame(data)
                    
                    if 'messages' in df.columns:
                        df['messages'] = df['messages'].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
                    
                    total_tests = len(df)
                    passed = len(df[df['result'] == 'success'])
                    failed = len(df[df['result'] == 'failure'])
                    error = len(df[df['result'] == 'error']) if 'error' in df['result'].values else 0
                    skipped = len(df[df['result'] == 'skipped']) if 'skipped' in df['result'].values else 0
                    
                    st.subheader("📊 Test Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Tests", total_tests)
                    col2.metric("✅ Passed", passed)
                    col3.metric("❌ Failed", failed)
                    col4.metric("🚨 Error / Exception", error)
                    
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
                                    st.error(row['full_message'])
                                    if idx < fail_count:
                                        st.divider()
            except Exception as e:
                st.error(f"Error parsing results: {e}")
                with st.expander("View Full Raw Output"):
                    st.code(full_log, language=None)

# ==========================================
# TAB 5: RAW CLI (Custom Commands)
# ==========================================
with tab_cli:
    st.subheader("🛠️ Raw EOS Command Runner")
    st.markdown("Use this tab to run ad-hoc commands on a specific device.")
    
    try:
        with open("inventory.yml", "r") as f:
            inv_data = yaml.safe_load(f) or {}
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
            os.environ["ANTA_USERNAME"] = st.session_state.anta_user
            os.environ["ANTA_PASSWORD"] = st.session_state.anta_pass
            
            with st.spinner(f"Running '{cmd_input}' on {selected_label}..."):
                exec_cmd = [
                    "anta", "debug", "run-cmd", 
                    "--command", cmd_input,
                    "--inventory", "inventory.yml",
                    "--device", selected_device_id
                ]
                
                result = subprocess.run(exec_cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
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
                else:
                    st.error("Error executing command.")
                    st.code(result.stderr or result.stdout, language=None)