import network
import time
from secrets import secrets

def do_connect(ssid=secrets['ssid'], psk=secrets['password']):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.disconnect()
    time.sleep(2)

    print("Connecting to WiFi...")
    wlan.connect(ssid, psk)

    timeout = 20
    while timeout > 0:
        status = wlan.status()
        print("status:", status)

        if status in (
            network.STAT_WRONG_PASSWORD,
            network.STAT_NO_AP_FOUND,
            network.STAT_CONNECT_FAIL,
        ):
            raise RuntimeError(f"WiFi failed, status={status}")

        if status == network.STAT_GOT_IP:
            break

        timeout -= 1
        time.sleep(1)

    if wlan.status() != network.STAT_GOT_IP:
        raise RuntimeError(f"WiFi timeout, status={wlan.status()}")

    ip = wlan.ifconfig()[0]
    print("Connected, IP:", ip)
    return ip

