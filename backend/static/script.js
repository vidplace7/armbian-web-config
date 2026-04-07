document.addEventListener('DOMContentLoaded', () => {
    let currentStep = 1;
    let selectedWifi = null;
    let wifiListFetched = false;

    const btnNext = document.querySelectorAll('.next-btn');
    const btnPrev = document.querySelectorAll('.prev-btn');
    const finishBtn = document.getElementById('finishBtn');

    // Navigation Logic
    btnNext.forEach(btn => {
        btn.addEventListener('click', () => {
            if (validateStep(currentStep)) {
                changeStep(currentStep + 1);
                if (currentStep === 4 && !wifiListFetched) {
                    fetchWifiNetworks();
                }
            }
        });
    });

    btnPrev.forEach(btn => {
        btn.addEventListener('click', () => {
            changeStep(currentStep - 1);
        });
    });

    function changeStep(newStep) {
        document.querySelectorAll('.form-step').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.step').forEach(el => el.classList.remove('active'));
        
        document.getElementById(`step${newStep}`).classList.add('active');
        
        for (let i = 1; i <= newStep; i++) {
            document.querySelector(`.step[data-target="${i}"]`).classList.add('active');
        }
        currentStep = newStep;
    }

    function validateStep(step) {
        if (step === 1) {
            const p1 = document.getElementById('rootPass').value;
            const p2 = document.getElementById('rootPassConf').value;
            if (!p1 || p1 !== p2) {
                alert("Passwords do not match or are empty!");
                return false;
            }
        }
        if (step === 2) {
            const user = document.getElementById('userName').value;
            const p1 = document.getElementById('userPass').value;
            const p2 = document.getElementById('userPassConf').value;
            if (!user) { alert("Username is required"); return false; }
            if (!p1 || p1 !== p2) { alert("User passwords do not match"); return false; }
        }
        return true;
    }

    // WiFi Logic
    async function fetchWifiNetworks() {
        const listEl = document.getElementById('networkList');
        listEl.innerHTML = '<p class="scanning">Scanning for networks...</p>';
        wifiListFetched = true;
        try {
            const res = await fetch('/api/wifi/scan');
            const data = await res.json();
            
            listEl.innerHTML = '';
            if (data.length === 0) {
                listEl.innerHTML = '<p class="scanning">No networks found.</p>';
                return;
            }

            data.forEach(net => {
                const div = document.createElement('div');
                div.className = 'network-item';
                div.innerHTML = `<span>${net.ssid}</span> <span>${net.signal}%</span>`;
                div.onclick = () => selectNetwork(div, net.ssid, net.security);
                listEl.appendChild(div);
            });
        } catch (e) {
            listEl.innerHTML = '<p class="scanning">Failed to scan networks.</p>';
        }
    }

    function selectNetwork(el, ssid, security) {
        document.querySelectorAll('.network-item').forEach(e => e.classList.remove('selected'));
        el.classList.add('selected');
        selectedWifi = ssid;
        
        const passGroup = document.getElementById('wifiPassGroup');
        document.getElementById('selectedNetworkDisplay').innerText = ssid;
        passGroup.style.display = 'block';
    }

    // Submit Logic
    finishBtn.addEventListener('click', async () => {
        document.querySelectorAll('.form-step').forEach(el => el.classList.remove('active'));
        document.getElementById('loadingStep').classList.add('active');

        const payload = {
            rootPass: document.getElementById('rootPass').value,
            userName: document.getElementById('userName').value,
            userPass: document.getElementById('userPass').value,
            timezone: document.getElementById('timezone').value,
            locale: document.getElementById('locale').value,
            wifiSsid: selectedWifi,
            wifiPass: document.getElementById('wifiPass').value
        };

        try {
            await fetch('/api/setup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            document.getElementById('loadingStep').classList.remove('active');
            document.getElementById('doneStep').classList.add('active');
        } catch (e) {
            alert("Error during setup. Check connection or AP.");
        }
    });
});
