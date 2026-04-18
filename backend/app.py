#!/usr/bin/env python3
import os
import subprocess
import time
import socket
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        return e.output.decode('utf-8').strip()

def get_hostname():
    try:
        with open('/etc/hostname', 'r') as f:
            return f.read().strip()
    except Exception:
        return "LocalTest"

# ... (skipping some code logically or wait, I need to replace the whole block or just the end)

def ensure_ap_mode():
    hostname = get_hostname()
    # Encode SSID to bytes. Enforce 32 byte limit by truncating.
    ap_ssid = f"armbiansetup-{hostname}".encode("utf-8")[:32]
    # Decode back to string, ignoring any invalid characters that may arise from truncation.
    ap_ssid = ap_ssid.decode("utf-8", "ignore")
    # Check if AP is already running
    active_ap = run_cmd("nmcli -t -f DEVICE,TYPE,STATE dev | grep wifi | grep connected")
    if active_ap:
        pass # Depending on robust logic, we could tear down existing wifi, but let's just make sure hotpsot is up if not connected.
    
    # Try creating hotspot
    # Find wifi device
    wifi_devs = run_cmd("nmcli -t -f DEVICE,TYPE dev | grep wifi | cut -d: -f1").split('\n')
    if not wifi_devs or not wifi_devs[0]:
        return False
    dev = wifi_devs[0]
    
    # Enable wifi if disabled
    run_cmd(f"nmcli radio wifi on")
    # Start hotspot
    print(f"Starting Hotspot on {dev} with SSID {ap_ssid}")
    res = run_cmd(f"nmcli dev wifi hotspot ifname {dev} ssid {ap_ssid} password armbian1234")
    return True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/wifi/scan')
def scan_wifi():
    import shutil
    if not shutil.which("nmcli"):
        return jsonify([{"ssid": "Wifi Network Scanning Unavailable", "security": "none", "signal": 0}])
        
    devs = run_cmd("nmcli -t -f DEVICE,TYPE dev | grep wifi | cut -d: -f1").split('\n')
    dev = devs[0] if devs and devs[0] else None
    if not dev:
        return jsonify([])
    
    # Rescan
    run_cmd(f"nmcli dev wifi rescan ifname {dev}")
    time.sleep(2)
    # Get list
    lines = run_cmd(f"nmcli -t -f SSID,SECURITY,SIGNAL dev wifi list ifname {dev}").split('\n')
    networks = []
    seen = set()
    for line in lines:
        if not line: continue
        parts = line.split(':')
        if len(parts) >= 3:
            ssid = parts[0].replace('\\:', ':')
            if not ssid or ssid in seen: continue
            seen.add(ssid)
            networks.append({
                'ssid': ssid,
                'security': parts[1],
                'signal': int(parts[2]) if parts[2].isdigit() else 0
            })
    networks.sort(key=lambda x: x['signal'], reverse=True)
    return jsonify(networks)

@app.route('/api/setup', methods=['POST'])
def setup():
    data = request.json
    
    content = ""
    # Network Settings
    content += 'PRESET_NET_CHANGE_DEFAULTS="1"\n'
    content += f'PRESET_NET_ETHERNET_ENABLED="{data.get("ethEnabled", "1")}"\n'
    
    wifi_ssid = data.get('wifiSsid')
    if wifi_ssid:
        content += 'PRESET_NET_WIFI_ENABLED="1"\n'
        content += f'PRESET_NET_WIFI_SSID="{wifi_ssid}"\n'
        wifi_pass = data.get('wifiPass')
        if wifi_pass:
            content += f'PRESET_NET_WIFI_KEY="{wifi_pass}"\n'
        cc = data.get("wifiCountryCode", "GB")
        if not cc: cc = "GB"
        content += f'PRESET_NET_WIFI_COUNTRYCODE="{cc}"\n'
        content += 'PRESET_CONNECT_WIRELESS="y"\n'
    else:
        content += 'PRESET_NET_WIFI_ENABLED="0"\n'
        
    if data.get('useStaticIp'):
        content += 'PRESET_NET_USE_STATIC="1"\n'
        content += f'PRESET_NET_STATIC_IP="{data.get("staticIp", "")}"\n'
        content += f'PRESET_NET_STATIC_MASK="{data.get("staticMask", "")}"\n'
        content += f'PRESET_NET_STATIC_GATEWAY="{data.get("staticGw", "")}"\n'
        content += f'PRESET_NET_STATIC_DNS="{data.get("staticDns", "")}"\n'
    else:
        content += 'PRESET_NET_USE_STATIC="0"\n'
        
    # System
    content += 'SET_LANG_BASED_ON_LOCATION="n"\n'
    # For armbian autoconfig, the locale should be e.g. en_US.UTF-8, not containing the second UTF-8 like the select has. Let's fix it here
    locale_val = data.get("locale", "en_US.UTF-8").split()[0]
    content += f'PRESET_LOCALE="{locale_val}"\n'
    content += f'PRESET_TIMEZONE="{data.get("timezone", "UTC")}"\n'
    
    # Root
    content += f'PRESET_ROOT_PASSWORD="{data.get("rootPass", "")}"\n'
    if data.get('rootKey'):
        content += f'PRESET_ROOT_KEY="{data.get("rootKey", "")}"\n'
        
    # User
    content += f'PRESET_USER_NAME="{data.get("userName", "")}"\n'
    content += f'PRESET_USER_PASSWORD="{data.get("userPass", "")}"\n'
    if data.get('userKey'):
        content += f'PRESET_USER_KEY="{data.get("userKey", "")}"\n'
    if data.get('realName'):
        content += f'PRESET_DEFAULT_REALNAME="{data.get("realName", "")}"\n'
    content += f'PRESET_USER_SHELL="{data.get("userShell", "/bin/bash")}"\n'
    
    # Write to file
    try:
        with open("/root/.not_logged_in_yet", "w") as f:
            f.write(content)
    except Exception as e:
        print("Failed to write conf", e)
        # Try local write for testing context
        with open(".not_logged_in_yet", "w") as f:
            f.write(content)

    # Disable this web config service
    os.system("systemctl disable armbian-web-config.service &")
    
    # Enable the native first login script to run on boot
    os.system("systemctl enable armbian-headless-firstlogin.service &")
    
    # Schedule a reboot rather than running firstlogin directly to apply properly
    os.system("(sleep 3 && reboot) &")
    
    return jsonify({"status": "success", "wifi": bool(wifi_ssid)})

if __name__ == '__main__':
    try:
        ensure_ap_mode()
    except Exception as e:
        print("Skipping AP mode: ", e)
    app.run(host='0.0.0.0', port=8080)
