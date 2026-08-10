import streamlit as st
import subprocess
import json
import pandas as pd
import yaml
import os
import re

# Configure the web page layout
st.set_page_config(page_title="ANTA Dashboard", layout="wide")

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

st.title("🚀 Arista ANTA Web GUI (v2.3)")
st.markdown("Manage your devices, tests, and run validations without writing any code.")
st.divider()

# --- Setup Tabs ---
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
        
    st.session_state.anta_user = st.text_input("Username", value=st.session_state.anta_user)
    st.session_state.anta_pass = st.text_input("Password", value=st.session_state.anta_pass, type="password")
    
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
# TAB 3: CATALOG (Auto-Saving UI)
# ==========================================
with tab_catalog:
    st.subheader("📋 Test Catalog Builder")
    st.caption("Select tests manually or load preset profiles to configure your validation suite.")

    ALL_TEST_KEYS = [
        "chk_hw_trans", "chk_hw_cool", "chk_hw_power", "chk_hw_temp",
        "chk_sys_uptime", "chk_sys_ntp", "chk_sys_coredump", "chk_sys_reload",
        "chk_aaa_authen", "chk_conn_ping", "chk_conn_lldp",
        "chk_cfg_aaa", "chk_cfg_no_enable", "chk_cfg_eapi", "chk_cfg_no_http", "chk_cfg_syslog", "chk_cfg_no_plaintext_sec",
        "chk_int_err", "chk_int_disc", "chk_int_status",
        "chk_int_proxy_arp", "chk_int_ill_lacp", "chk_int_err_dis", "chk_int_util",
        "chk_int_ber", "chk_int_counter_det", "chk_int_ecn", "chk_int_egress_drop",
        "chk_int_optics_rx", "chk_int_optics_temp", "chk_int_pfc", "chk_int_speed",
        "chk_int_trident", "chk_int_voq", "chk_int_vrrp_mac", "chk_int_l2mtu",
        "chk_int_l3mtu", "chk_int_loopback", "chk_int_port_channel",
        "chk_int_svi", "chk_int_storm", "chk_int_ipv4",
        "chk_rt_model", "chk_rt_status", "chk_rt_size", "chk_rt_presence",
        "chk_bgp_health", "chk_stp_blocked", "chk_stp_tc",
        "chk_evpn_type5", "chk_vxlan_intf", "chk_vxlan_sanity",
        "chk_mlag_status", "chk_mlag_interfaces", "chk_mlag_config_sanity", "chk_mlag_reload_delay",
        "chk_igmp_snooping_global", "chk_ssh_status", "chk_hostname",
        "chk_flow_tracking", "chk_lanz", "chk_log_persistent", "chk_log_accounting", "chk_log_source_intf", "chk_log_hosts",
        "chk_path_sel_health", "chk_snmp_status", "chk_vlan_internal"
    ]

    default_config_rules = [
        {"Section": "", "Match": "aaa authorization exec default local", "Mode": "exact", "Absent": False, "Description": "AAA authorization"},
        {"Section": "management api http-commands", "Match": "no shutdown", "Mode": "exact", "Absent": False, "Description": "eAPI enabled"}
    ]

    DEFAULT_PROFILES = {
        "🟢 Basic NRFU (Quick Check)": {
            "keys": ["chk_hw_trans", "chk_hw_cool", "chk_hw_power", "chk_hw_temp", "chk_sys_uptime", "chk_sys_ntp", "chk_int_err", "chk_int_status"],
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

    # --- Profile Toolbar ---
    with st.container(border=True):
        st.markdown("##### 🎯 Active Profile")
        
        prof_col1, prof_col2, prof_col3 = st.columns([3, 1.5, 1.5])

        with prof_col1:
            selected_prof_name = st.selectbox(
                "Active Profile Preset", 
                options=list(active_profiles.keys()),
                label_visibility="collapsed"
            )

        with prof_col2:
            if st.button("📂 Load Profile", use_container_width=True, type="primary"):
                p_data = active_profiles.get(selected_prof_name, {})
                p_keys = set(p_data.get("keys", []))
                for k in ALL_TEST_KEYS:
                    st.session_state[k] = (k in p_keys)
                st.session_state.cfg_rules_data = p_data.get("cfg_rules", default_config_rules)
                save_settings({"selected_test_keys": list(p_keys)})
                st.success(f"✅ Loaded '{selected_prof_name}'!")
                st.rerun()

        with prof_col3:
            if st.button("💾 Save Changes to Active Profile", use_container_width=True):
                current_keys = [k for k in ALL_TEST_KEYS if st.session_state.get(k, False)]
                active_profiles[selected_prof_name] = {
                    "keys": current_keys,
                    "cfg_rules": st.session_state.get("cfg_rules_data", default_config_rules)
                }
                save_settings({
                    "profiles": active_profiles,
                    "selected_test_keys": current_keys
                })
                st.success(f"✅ Saved changes to '{selected_prof_name}'!")

        # Separate Expanders for Clear Action Distinction
        st.divider()
        c_exp1, c_exp2 = st.columns(2)
        
        with c_exp1:
            with st.expander("➕ Create New Profile"):
                new_prof_input = st.text_input("New Profile Name", placeholder="e.g. Spine Switches Profile")
                if st.button("Save Current Selection as New Profile", use_container_width=True):
                    if new_prof_input.strip():
                        current_keys = [k for k in ALL_TEST_KEYS if st.session_state.get(k, False)]
                        active_profiles[new_prof_input.strip()] = {
                            "keys": current_keys,
                            "cfg_rules": st.session_state.get("cfg_rules_data", default_config_rules)
                        }
                        save_settings({"profiles": active_profiles, "selected_test_keys": current_keys})
                        st.success(f"✅ Created profile '{new_prof_input.strip()}'!")
                        st.rerun()
                    else:
                        st.error("Please enter a valid profile name.")

        with c_exp2:
            with st.expander("🗑️ Delete Existing Profile"):
                del_prof_select = st.selectbox("Select Profile to Delete", options=list(active_profiles.keys()))
                if st.button("Delete Selected Profile", use_container_width=True, type="secondary"):
                    if len(active_profiles) > 1:
                        del active_profiles[del_prof_select]
                        save_settings({"profiles": active_profiles})
                        st.success(f"✅ Deleted '{del_prof_select}'!")
                        st.rerun()
                    else:
                        st.error("Cannot delete the last remaining profile.")

    # --- Quick Actions Toolbar ---
    if "expand_state" not in st.session_state:
        st.session_state.expand_state = False

    def toggle_select_all():
        current_all_selected = all(st.session_state.get(k, False) for k in ALL_TEST_KEYS)
        new_state = not current_all_selected
        for k in ALL_TEST_KEYS:
            st.session_state[k] = new_state

    def toggle_expand():
        st.session_state.expand_state = not st.session_state.expand_state

    tb_col1, tb_col2, tb_col3 = st.columns([2, 2, 3])

    with tb_col1:
        is_all_selected = all(st.session_state.get(k, False) for k in ALL_TEST_KEYS)
        select_label = "❌ Deselect All" if is_all_selected else "✅ Select All"
        st.button(select_label, on_click=toggle_select_all, use_container_width=True)

    with tb_col2:
        expand_label = "📁 Collapse Categories" if st.session_state.expand_state else "📂 Expand Categories"
        st.button(expand_label, on_click=toggle_expand, use_container_width=True)

    with tb_col3:
        test_tags_input = st.text_input(
            "Filter Tags", 
            value=saved_settings.get("catalog_tags", ""),
            placeholder="🏷️ Filter Tags (e.g. leaf, demo)",
            label_visibility="collapsed"
        )

    st.markdown("---")

    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("🔌 Hardware Tests", expanded=st.session_state.expand_state):
            hw_trans = st.checkbox("Verify Transceivers Manufacturers", key="chk_hw_trans")
            hw_cool = st.checkbox("Verify System Cooling", key="chk_hw_cool")
            hw_power = st.checkbox("Verify Power Supplies", key="chk_hw_power")
            hw_temp = st.checkbox("Verify Temperature", key="chk_hw_temp")
            
        with st.expander("💻 System Tests", expanded=st.session_state.expand_state):
            sys_uptime = st.checkbox("Verify Minimum Uptime", key="chk_sys_uptime")
            sys_uptime_val = st.number_input("Minimum Uptime (seconds)", value=60, disabled=not sys_uptime)
            sys_ntp = st.checkbox("Verify NTP Status", key="chk_sys_ntp")
            sys_coredump = st.checkbox("Verify No Coredumps", key="chk_sys_coredump")
            sys_reload = st.checkbox("Verify Reload Cause", key="chk_sys_reload")

        with st.expander("🔐 AAA Tests", expanded=st.session_state.expand_state):
            aaa_authen = st.checkbox("Verify Authentication Methods", key="chk_aaa_authen")
            aaa_method = st.text_input("Expected Method", "local", disabled=not aaa_authen)
            aaa_type = st.selectbox("Authentication Type", ["login", "enable"], disabled=not aaa_authen)

        with st.expander("⚙️ Configuration Tests (VerifyRunningConfig)", expanded=st.session_state.expand_state):
            st.markdown("Build dynamic `VerifyRunningConfig` rules. Leave **Section** empty to match top-level commands. Separate nested sections with a comma.")
            
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

        with st.expander("🌐 Connectivity Tests", expanded=st.session_state.expand_state):
            conn_ping = st.checkbox("Verify IP Reachability (Ping)", key="chk_conn_ping")
            conn_dest = st.text_input("Destination IP", "8.8.8.8", disabled=not conn_ping)
            conn_vrf = st.text_input("VRF (Ping)", "default", disabled=not conn_ping)
            st.divider()
            conn_lldp = st.checkbox("Verify LLDP Neighbor", key="chk_conn_lldp")
            conn_lldp_port = st.text_input("Local Port", "Ethernet1", disabled=not conn_lldp)
            conn_lldp_device = st.text_input("Neighbor Device Name", "Switch-2", disabled=not conn_lldp)
            conn_lldp_neighbor_port = st.text_input("Neighbor Port", "Ethernet1", disabled=not conn_lldp)

        with st.expander("🤝 MLAG Tests", expanded=st.session_state.expand_state):
            mlag_status = st.checkbox("Verify MLAG Status", key="chk_mlag_status")
            mlag_interfaces = st.checkbox("Verify MLAG Interfaces", key="chk_mlag_interfaces")
            mlag_config = st.checkbox("Verify MLAG Config Sanity", key="chk_mlag_config_sanity")
            mlag_delay = st.checkbox("Verify MLAG Reload Delay", key="chk_mlag_reload_delay")
            c_md1, c_md2 = st.columns(2)
            with c_md1:
                mlag_reload_delay = st.number_input("Reload Delay", value=300, disabled=not mlag_delay)
            with c_md2:
                mlag_non_mlag_delay = st.number_input("Non-MLAG Delay", value=330, disabled=not mlag_delay)

        with st.expander("📡 Multicast Tests", expanded=st.session_state.expand_state):
            igmp_snoop = st.checkbox("Verify IGMP Snooping Global", key="chk_igmp_snooping_global")

        with st.expander("🔒 Security Tests", expanded=st.session_state.expand_state):
            ssh_status = st.checkbox("Verify SSH Status", key="chk_ssh_status")

        with st.expander("🛠️ Services Tests", expanded=st.session_state.expand_state):
            svc_hostname = st.checkbox("Verify Hostname", key="chk_hostname")
            service_hostname = st.text_input("Expected Hostname", "Switch-1", disabled=not svc_hostname)

    with col2:
        with st.expander("🌐 Interface Tests", expanded=st.session_state.expand_state):
            target_intfs_input = st.text_input(
                "Interfaces to check (Comma-separated. Used by Status test)", 
                "Ethernet1, Management1"
            )
            
            st.divider()
            int_err = st.checkbox("Verify Interface Errors", key="chk_int_err")
            int_disc = st.checkbox("Verify Interface Discards", key="chk_int_disc")
            int_status = st.checkbox("Verify Interfaces Status", key="chk_int_status")
            
            st.markdown("##### Extended Interface Tests")
            i_col1, i_col2 = st.columns(2)
            with i_col1:
                int_speed = st.checkbox("Verify Interfaces Speed", key="chk_int_speed")
                col_sp1, col_sp2 = st.columns(2)
                with col_sp1:
                    int_speed_intf = st.text_input("Speed Intf", "Ethernet1", disabled=not int_speed)
                with col_sp2:
                    int_speed_val = st.number_input("Speed", value=100, max_value=1000, disabled=not int_speed)

                int_l2mtu = st.checkbox("Verify L2 MTU", key="chk_int_l2mtu")
                int_l2mtu_val = st.number_input("L2 MTU Value", value=9214, disabled=not int_l2mtu)
                
                int_loopback = st.checkbox("Verify Loopback Count", key="chk_int_loopback")
                int_loopback_val = st.number_input("Loopback Count", value=1, disabled=not int_loopback)
                
                int_proxy_arp = st.checkbox("Verify IP Proxy ARP", key="chk_int_proxy_arp")
                int_proxy_arp_intf = st.text_input("Proxy ARP Intfs (comma-sep)", "Vlan1", disabled=not int_proxy_arp)
                
                int_vrrp_mac = st.checkbox("Verify IP VRRP Mac", key="chk_int_vrrp_mac")
                int_vrrp_mac_val = st.text_input("VRRP MAC", "00:00:00:00:00:00", disabled=not int_vrrp_mac)
                
                int_ipv4 = st.checkbox("Verify Interface IPv4", key="chk_int_ipv4")
                col_ip1, col_ip2 = st.columns(2)
                with col_ip1:
                    int_ipv4_intf = st.text_input("IPv4 Intf Name", "Ethernet1", disabled=not int_ipv4)
                with col_ip2:
                    int_ipv4_ip = st.text_input("Primary IP", "10.0.0.1/24", disabled=not int_ipv4)

                int_ill_lacp = st.checkbox("Verify Illegal LACP", key="chk_int_ill_lacp")
                int_err_dis = st.checkbox("Verify Interface ErrDisabled", key="chk_int_err_dis")
                int_util = st.checkbox("Verify Interface Utilization", key="chk_int_util")
                int_ber = st.checkbox("Verify Interfaces BER", key="chk_int_ber")
            with i_col2:
                int_l3mtu = st.checkbox("Verify L3 MTU", key="chk_int_l3mtu")
                int_l3mtu_val = st.number_input("L3 MTU Value", value=1500, disabled=not int_l3mtu)
                
                int_counter_det = st.checkbox("Verify Counter Details", key="chk_int_counter_det")
                int_ecn = st.checkbox("Verify ECN Counters", key="chk_int_ecn")
                int_optics_rx = st.checkbox("Verify Optics RX Power", key="chk_int_optics_rx")
                int_optics_temp = st.checkbox("Verify Optics Temp", key="chk_int_optics_temp")
                int_pfc = st.checkbox("Verify PFC Counters", key="chk_int_pfc")
                int_trident = st.checkbox("Verify Trident Counters", key="chk_int_trident")
                int_voq = st.checkbox("Verify Voq / Egress Drops", key="chk_int_voq")
                int_egress_drop = st.checkbox("Verify Egress Queue Drops", key="chk_int_egress_drop")
                int_port_channel = st.checkbox("Verify Port Channels", key="chk_int_port_channel")
                int_svi = st.checkbox("Verify SVI", key="chk_int_svi")
                int_storm = st.checkbox("Verify Storm Control Drops", key="chk_int_storm")

        with st.expander("🗺️ Routing Generic Tests", expanded=st.session_state.expand_state):
            rt_model = st.checkbox("Verify Routing Protocol Model", key="chk_rt_model")
            rt_model_val = st.selectbox("Protocol Model", ["multi-agent", "ribd"], disabled=not rt_model)
            rt_status = st.checkbox("Verify IPv4 Unicast Routing Status", key="chk_rt_status")
            rt_size = st.checkbox("Verify Routing Table Size (Default VRF)", key="chk_rt_size")
            col_min, col_max = st.columns(2)
            with col_min:
                rt_size_min = st.number_input("Min Routes", value=1, min_value=1, disabled=not rt_size)
            with col_max:
                rt_size_max = st.number_input("Max Routes", value=1000, min_value=1, disabled=not rt_size)
            rt_presence = st.checkbox("Verify IPv4 Route Presence", key="chk_rt_presence")
            rt_prefix = st.text_input("Route Prefix", "10.0.0.0/24", disabled=not rt_presence)
            rt_vrf = st.text_input("VRF (Route Presence)", "default", disabled=not rt_presence)
            
        with st.expander("🗺️ Routing BGP Tests", expanded=st.session_state.expand_state):
            bgp_health = st.checkbox("Verify BGP Peers Health", key="chk_bgp_health")
            bgp_vrf = st.text_input("BGP VRF", "default", disabled=not bgp_health)

        with st.expander("🛡️ STP Tests", expanded=st.session_state.expand_state):
            stp_blocked = st.checkbox("Verify STP Blocked Ports (Ensure None)", key="chk_stp_blocked")
            stp_tc = st.checkbox("Verify STP Topology Changes", key="chk_stp_tc")
            stp_tc_threshold = st.number_input("Max Allowed Topology Changes (Threshold)", min_value=0, value=1, step=1, disabled=not stp_tc)

        with st.expander("☁️ EVPN & VXLAN Tests", expanded=st.session_state.expand_state):
            evpn_type5 = st.checkbox("Verify EVPN Type 5 Routes", key="chk_evpn_type5")
            evpn_prefix = st.text_input("Network Prefix", "10.10.10.0/24", disabled=not evpn_type5)
            evpn_vni = st.number_input("VNI", value=10010, disabled=not evpn_type5)
            st.divider()
            vxlan_intf = st.checkbox("Verify VXLAN1 Interface", key="chk_vxlan_intf")
            vxlan_sanity = st.checkbox("Verify VXLAN Config Sanity", key="chk_vxlan_sanity")
            
        with st.expander("🌊 Flow Tracking Tests", expanded=st.session_state.expand_state):
            flow_tracking = st.checkbox("Verify Hardware Flow Tracker Status", key="chk_flow_tracking")
            flow_tracker_name = st.text_input("Tracker Name", "FLOW-TRACKER", disabled=not flow_tracking)

        with st.expander("📊 LANZ Tests", expanded=st.session_state.expand_state):
            lanz_status = st.checkbox("Verify LANZ Status", key="chk_lanz")

        with st.expander("📝 Logging Tests", expanded=st.session_state.expand_state):
            log_persistent = st.checkbox("Verify Persistent Logging", key="chk_log_persistent")
            log_accounting = st.checkbox("Verify Logging Accounting", key="chk_log_accounting")
            
            log_src = st.checkbox("Verify Logging Source Interface", key="chk_log_source_intf")
            c_ls1, c_ls2 = st.columns(2)
            with c_ls1:
                log_src_vrf = st.text_input("Source VRF", "default", disabled=not log_src)
            with c_ls2:
                log_src_intf = st.text_input("Source Intf", "Loopback0", disabled=not log_src)
                
            log_hosts = st.checkbox("Verify Logging Hosts", key="chk_log_hosts")
            c_lh1, c_lh2 = st.columns(2)
            with c_lh1:
                log_hosts_ips = st.text_input("Host IPs (comma-sep)", "10.0.0.1", disabled=not log_hosts)
            with c_lh2:
                log_hosts_vrf = st.text_input("Hosts VRF", "default", disabled=not log_hosts)

        with st.expander("🛤️ Path Selection Tests", expanded=st.session_state.expand_state):
            path_sel_health = st.checkbox("Verify Path Selection Health", key="chk_path_sel_health")

        with st.expander("🖧 SNMP Tests", expanded=st.session_state.expand_state):
            snmp_status = st.checkbox("Verify SNMP Status", key="chk_snmp_status")
            snmp_vrf = st.text_input("SNMP VRF", "default", disabled=not snmp_status)

        with st.expander("🏢 VLAN Tests", expanded=st.session_state.expand_state):
            vlan_internal = st.checkbox("Verify VLAN Internal Allocation", key="chk_vlan_internal")
            vlan_alloc_policy = st.selectbox("Allocation Policy", ["ascending", "descending"], disabled=not vlan_internal)

    st.markdown("### 🧩 Advanced (Custom ANTA Tests)")
    st.markdown("Paste custom YAML config for supported tests.")
    
    default_custom = "# anta.tests.system:\n#   - VerifyUptime:\n#       minimum: 10\n"
    custom_yaml = st.text_area("Custom YAML", value=default_custom, height=150)
    
    st.divider()

    # --- AUTO-SAVE CATALOG LOGIC ---
    catalog_dict = {}
    parsed_tags = [t.strip() for t in test_tags_input.split(",") if t.strip()] if test_tags_input else []
    
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
    if hw_trans: add_test("anta.tests.hardware", {"VerifyTransceiversManufacturers": {"manufacturers": ["Arista Networks", "ARISTA"]}})
    if hw_cool: add_test("anta.tests.hardware", {"VerifyEnvironmentSystemCooling": None})
    if hw_power: add_test("anta.tests.hardware", {"VerifyEnvironmentPower": {"states": ["ok"]}})
    if hw_temp: add_test("anta.tests.hardware", {"VerifyTemperature": None})
        
    # System
    if sys_uptime: add_test("anta.tests.system", {"VerifyUptime": {"minimum": int(sys_uptime_val)}})
    if sys_ntp: add_test("anta.tests.system", {"VerifyNTP": None})
    if sys_coredump: add_test("anta.tests.system", {"VerifyCoredump": None})
    if sys_reload: add_test("anta.tests.system", {"VerifyReloadCause": None})

    # AAA
    if aaa_authen: add_test("anta.tests.aaa", {"VerifyAuthenMethods": {"methods": [aaa_method], "types": [aaa_type]}})

    # Configuration Tests
    if st.session_state.cfg_rules_data:
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
                rule["section"] = [s.strip() for s in sec.split(",")]
            cfg_rules_parsed.append(rule)
            
        if cfg_rules_parsed:
            add_test("anta.tests.configuration", {"VerifyRunningConfig": {"rules": cfg_rules_parsed}})

    # Connectivity
    if conn_ping: add_test("anta.tests.connectivity", {"VerifyReachability": {"hosts": [{"destination": conn_dest, "vrf": conn_vrf}]}})
    if conn_lldp:
        add_test("anta.tests.connectivity", {
            "VerifyLLDPNeighbors": {
                "neighbors": [
                    {"port": conn_lldp_port, "neighbor_device": conn_lldp_device, "neighbor_port": conn_lldp_neighbor_port}
                ]
            }
        })

    # Interfaces Parsing Logic
    parsed_intfs = [i.strip() for i in target_intfs_input.split(",") if i.strip()]

    if int_status and parsed_intfs:
        interfaces_obj = [{"name": i, "status": "up"} for i in parsed_intfs]
        add_test("anta.tests.interfaces", {"VerifyInterfacesStatus": {"interfaces": interfaces_obj}})
            
    if int_proxy_arp: 
        p_intfs = [i.strip() for i in int_proxy_arp_intf.split(",") if i.strip()]
        if p_intfs: add_test("anta.tests.interfaces", {"VerifyIPProxyARP": {"interfaces": p_intfs}})
        
    if int_vrrp_mac: add_test("anta.tests.interfaces", {"VerifyIpVirtualRouterMac": {"mac_address": int_vrrp_mac_val}})
    if int_ipv4: add_test("anta.tests.interfaces", {"VerifyInterfaceIPv4": {"interfaces": [{"name": int_ipv4_intf, "primary_ip": int_ipv4_ip}]}})
    if int_speed: add_test("anta.tests.interfaces", {"VerifyInterfacesSpeed": {"interfaces": [{"name": int_speed_intf, "speed": int(int_speed_val)}]}})
    if int_l2mtu: add_test("anta.tests.interfaces", {"VerifyL2MTU": {"mtu": int(int_l2mtu_val)}})
    if int_l3mtu: add_test("anta.tests.interfaces", {"VerifyL3MTU": {"mtu": int(int_l3mtu_val)}})
    if int_loopback: add_test("anta.tests.interfaces", {"VerifyLoopbackCount": {"number": int(int_loopback_val)}})

    if int_err: add_test("anta.tests.interfaces", {"VerifyInterfaceErrors": None})
    if int_disc: add_test("anta.tests.interfaces", {"VerifyInterfaceDiscards": None})
    if int_ill_lacp: add_test("anta.tests.interfaces", {"VerifyIllegalLACP": None})
    if int_err_dis: add_test("anta.tests.interfaces", {"VerifyInterfaceErrDisabled": None})
    if int_util: add_test("anta.tests.interfaces", {"VerifyInterfaceUtilization": None})
    if int_trident: add_test("anta.tests.interfaces", {"VerifyInterfacesTridentCounters": None})
    if int_port_channel: add_test("anta.tests.interfaces", {"VerifyPortChannels": None})
    if int_svi: add_test("anta.tests.interfaces", {"VerifySVI": None})
    if int_ber: add_test("anta.tests.interfaces", {"VerifyInterfacesBER": None})
    if int_counter_det: add_test("anta.tests.interfaces", {"VerifyInterfacesCounterDetails": None})
    if int_ecn: add_test("anta.tests.interfaces", {"VerifyInterfacesECNCounters": None})
    if int_egress_drop: add_test("anta.tests.interfaces", {"VerifyInterfacesEgressQueueDrops": None})
    if int_optics_rx: add_test("anta.tests.interfaces", {"VerifyInterfacesOpticsReceivePower": None})
    if int_optics_temp: add_test("anta.tests.interfaces", {"VerifyInterfacesOpticsTemperature": None})
    if int_pfc: add_test("anta.tests.interfaces", {"VerifyInterfacesPFCCounters": None})
    if int_voq: add_test("anta.tests.interfaces", {"VerifyInterfacesVoqAndEgressQueueDrops": None})
    if int_storm: add_test("anta.tests.interfaces", {"VerifyStormControlDrops": None})

    # Routing
    if rt_model: add_test("anta.tests.routing.generic", {"VerifyRoutingProtocolModel": {"model": rt_model_val}})
    if rt_status: add_test("anta.tests.routing.generic", {"VerifyRoutingStatus": {"ipv4_unicast": True}})
    if rt_size: add_test("anta.tests.routing.generic", {"VerifyRoutingTableSize": {"minimum": int(rt_size_min), "maximum": int(rt_size_max)}})
    if rt_presence: add_test("anta.tests.routing.generic", {"VerifyIPv4RoutePresencePerVRF": {"route_entries": [{"prefix": rt_prefix, "vrf": rt_vrf}]}})
    if bgp_health: add_test("anta.tests.routing.bgp", {"VerifyBGPPeersHealth": {"address_families": [{"afi": "ipv4", "safi": "unicast", "vrf": bgp_vrf}]}})
    
    # STP
    if stp_blocked: add_test("anta.tests.stp", {"VerifySTPBlockedPorts": None})
    if stp_tc: add_test("anta.tests.stp", {"VerifyStpTopologyChanges": {"threshold": int(stp_tc_threshold)}})
        
    # EVPN / VXLAN
    if evpn_type5: add_test("anta.tests.evpn", {"VerifyEVPNType5Routes": {"prefixes": [{"address": evpn_prefix, "vni": int(evpn_vni)}]}})
    if vxlan_intf: add_test("anta.tests.vxlan", {"VerifyVxlan1Interface": None})
    if vxlan_sanity: add_test("anta.tests.vxlan", {"VerifyVxlanConfigSanity": None})
        
    # MLAG
    if mlag_status: add_test("anta.tests.mlag", {"VerifyMlagStatus": None})
    if mlag_interfaces: add_test("anta.tests.mlag", {"VerifyMlagInterfaces": None})
    if mlag_config: add_test("anta.tests.mlag", {"VerifyMlagConfigSanity": None})
    if mlag_delay: add_test("anta.tests.mlag", {"VerifyMlagReloadDelay": {"reload_delay": int(mlag_reload_delay), "reload_delay_non_mlag": int(mlag_non_mlag_delay)}})

    # Multicast
    if igmp_snoop: add_test("anta.tests.multicast", {"VerifyIGMPSnoopingGlobal": {"enabled": True}})

    # Security
    if ssh_status: add_test("anta.tests.security", {"VerifySSHStatus": None})

    # Services
    if svc_hostname: add_test("anta.tests.services", {"VerifyHostname": {"hostname": service_hostname}})

    # Flow Tracking
    if flow_tracking: add_test("anta.tests.flow_tracking", {"VerifyHardwareFlowTrackerStatus": {"trackers": [{"name": flow_tracker_name}]}})

    # LANZ
    if lanz_status: add_test("anta.tests.lanz", {"VerifyLANZ": None})

    # Logging
    if log_persistent: add_test("anta.tests.logging", {"VerifyLoggingPersistent": None})
    if log_accounting: add_test("anta.tests.logging", {"VerifyLoggingAccounting": None})
    if log_src: add_test("anta.tests.logging", {"VerifyLoggingSourceIntf": {"vrf": log_src_vrf, "interface": log_src_intf}})
    if log_hosts: add_test("anta.tests.logging", {"VerifyLoggingHosts": {"hosts": [i.strip() for i in log_hosts_ips.split(",") if i.strip()], "vrf": log_hosts_vrf}})

    # Path Selection
    if path_sel_health: add_test("anta.tests.path_selection", {"VerifyPathsHealth": None})

    # SNMP
    if snmp_status: add_test("anta.tests.snmp", {"VerifySnmpStatus": {"vrf": snmp_vrf}})

    # VLAN
    if vlan_internal: add_test("anta.tests.vlan", {"VerifyVlanInternalPolicy": {"policy": vlan_alloc_policy, "start_vlan_id": 1006, "end_vlan_id": 4094}})
        
    try:
        parsed_custom = yaml.safe_load(custom_yaml)
        if parsed_custom and isinstance(parsed_custom, dict):
            for module, tests in parsed_custom.items():
                if module not in catalog_dict:
                    catalog_dict[module] = []
                if isinstance(tests, list):
                    catalog_dict[module].extend(tests)
                    
        with open("catalog.yml", "w") as f:
            yaml.safe_dump(catalog_dict, f, sort_keys=False)
            
        # Persist active test selections immediately
        current_active_keys = [k for k in ALL_TEST_KEYS if st.session_state.get(k, False)]
        save_settings({"selected_test_keys": current_active_keys, "catalog_tags": test_tags_input})
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
        
        selected_label = st.selectbox("Select Device", options=options_list, index=default_index)
        selected_device_id = device_map[selected_label]
        
        cmd_input = st.text_input("Enter EOS Command", value="show mac address-table")
        
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