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
    ap_ssid = f"{hostname}-armbiansetup"
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
    
    # 1. Update Root Password
    root_pass = data.get('rootPass')
    if root_pass:
        run_cmd(f"echo 'root:{root_pass}' | chpasswd")
    
    # 2. Add User and Password
    username = data.get('userName')
    user_pass = data.get('userPass')
    if username and user_pass:
        # Check if user exists
        if run_cmd(f"id -u {username}"):
            pass # User might exist
        else:
            run_cmd(f"useradd -m -s /bin/bash {username}")
        # Add to groups
        groups = "sudo,netdev,audio,video,plugdev,users,dialout,bluetooth,docker"
        run_cmd(f"usermod -aG {groups} {username} 2>/dev/null || true")
        run_cmd(f"echo '{username}:{user_pass}' | chpasswd")
        
    # 3. Timezone and Locale
    timezone = data.get('timezone')
    if timezone:
        run_cmd(f"timedatectl set-timezone {timezone}")
        run_cmd("dpkg-reconfigure -f noninteractive tzdata")
    
    locale = data.get('locale')
    if locale:
        run_cmd(f"sed -i 's/# {locale}/{locale}/' /etc/locale.gen")
        run_cmd(f"locale-gen {locale}")
        run_cmd(f"update-locale LANG={locale.split(' ')[0]}")
    
    # 4. Wifi Setup
    wifi_ssid = data.get('wifiSsid')
    wifi_pass = data.get('wifiPass')
    has_wifi = False
    if wifi_ssid:
        # Create the NetworkManager profile without connecting immediately (which disrupts the AP)
        run_cmd(f"nmcli con add type wifi ifname '*' con-name '{wifi_ssid}' autoconnect yes ssid '{wifi_ssid}'")
        if wifi_pass:
            run_cmd(f"nmcli con modify '{wifi_ssid}' wifi-sec.key-mgmt wpa-psk wifi-sec.psk '{wifi_pass}'")
        has_wifi = True
    
    # Cleanup and Signal done
    if os.path.exists('/root/.not_logged_in_yet'):
        os.remove('/root/.not_logged_in_yet')
    os.system("killall armbian-firstlogin || true")
    
    # Disable service
    os.system("systemctl disable armbian-web-config.service &")
    
    # Schedule reboot
    os.system("(sleep 3 && nmcli con down $(get_hostname)-armbiansetup || true && reboot) &")
    
    return jsonify({"status": "success", "wifi": has_wifi})

if __name__ == '__main__':
    try:
        ensure_ap_mode()
    except Exception as e:
        print("Skipping AP mode: ", e)
    app.run(host='0.0.0.0', port=8080)
