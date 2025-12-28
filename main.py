import machine
import socket
import neopixel
import ujson
from do_connect import *

# WS2811/WS2812 strip setup
LED_PIN = 18
NUM_PIXELS = 100
np = neopixel.NeoPixel(machine.Pin(LED_PIN), NUM_PIXELS)

# Logging and reconnect cooldown
LOG_FILE = "log.txt"
COOLDOWN = 10  # seconds

# LED state tracking
led_state = "CustomRGB"
lightLevel = 0.2
last_set_color = None  # remembers last non-off RGB + light_level
is_on = True  # True if LEDs are on, False if turned off


# --- Set LED strip ---
def set_strip(rgb=None, level=None, turn_off=False):
    global led_state, last_set_color, lightLevel, is_on

    if level is not None:
        lightLevel = max(0, min(1, level))

    if turn_off:
        rbg = (0, 0, 0)
        is_on = False
    else:
        if rgb is None:
            if last_set_color is not None:
                rgb = last_set_color["rgb"]
            else:
                rgb = [255, 0, 255]
        if not isinstance(rgb, (list, tuple)) or len(rgb) != 3:
            print("Invalid RGB value:", rgb)
            return

        rbg = (rgb[0], rgb[2], rgb[1])
        rbg = tuple(int(c * lightLevel) for c in rbg)
        is_on = True

    for i in range(NUM_PIXELS):
        np[i] = rbg
    np.write()

    led_state = "CustomRGB" if not turn_off else "Off"
    if not turn_off and rbg != (0, 0, 0):
        last_set_color = {"rgb": rgb, "light_level": lightLevel}

    print("LED strip set to:", led_state, "with level", lightLevel, "is_on:", is_on)

# --- Serve HTTP requests ---
def serve(connection):
    import ure
    global last_set_color, led_state, lightLevel, is_on

    while True:
        client, addr = connection.accept()
        request = client.recv(1024).decode()

        try:
            method, path, _ = request.split(" ", 2)
        except ValueError:
            client.close()
            continue

        response_code = "200 OK"
        response_body = {"current": led_state, "last": last_set_color, "is_on": is_on}

        # --- POST request ---
        if method == "POST":
            if "\r\n\r\n" in request:
                body = request.split("\r\n\r\n", 1)[1].strip()
                try:
                    data = ujson.loads(body)
                    rgb = data.get("rgb")
                    level = data.get("light_level")

                    if rgb is not None and isinstance(rgb, list) and len(rgb) == 3:
                        set_strip(rgb, level)
                        response_code = "201 Created"
                    elif rgb is None and level is not None:
                        set_strip(level=level)
                        response_code = "201 Created"
                    else:
                        response_code = "400 Bad Request"
                        response_body = {"error": "Provide 'rgb' as list or 'light_level'"}

                    response_body = {
                        "current": {"rgb": last_set_color["rgb"], "light_level": lightLevel} if last_set_color else None,
                        "last": last_set_color,
                        "is_on": is_on
                    }

                except Exception as e:
                    response_code = "400 Bad Request"
                    response_body = {"error": "Invalid JSON", "details": str(e)}

        # --- GET request ---
        elif method == "GET":
            if "/set?" in path:
                match = ure.search(r"r=([0-9]+)&g=([0-9]+)&b=([0-9]+)&light_level=([0-9.]+)", path)
                if match:
                    try:
                        rgb = [int(match.group(1)), int(match.group(2)), int(match.group(3))]
                        level = float(match.group(4))
                        set_strip(rgb, level)
                        response_code = "201 Created"
                        response_body = {
                            "current": {"rgb": last_set_color["rgb"], "light_level": lightLevel},
                            "last": last_set_color,
                            "is_on": is_on
                        }
                    except ValueError:
                        response_code = "400 Bad Request"
                        response_body = {"error": "Invalid RGB or light_level value"}
                else:
                    response_code = "400 Bad Request"
                    response_body = {"error": "Missing or invalid parameters"}

            elif "/set_light?" in path:
                match = ure.search(r"light_level=([0-9.]+)", path)
                if match:
                    try:
                        level = float(match.group(1))
                        set_strip(level=level)
                        response_code = "201 Created"
                        response_body = {
                            "current": {"rgb": last_set_color["rgb"], "light_level": lightLevel},
                            "last": last_set_color,
                            "is_on": is_on
                        }
                    except ValueError:
                        response_code = "400 Bad Request"
                        response_body = {"error": "Invalid light_level value"}
                else:
                    response_code = "400 Bad Request"
                    response_body = {"error": "Missing or invalid light_level"}

            elif "/Off" in path:
                set_strip(turn_off=True)
                response_code = "201 Created"
                response_body = {
                    "current": {"rgb": [0, 0, 0], "light_level": 0},
                    "last": last_set_color,
                    "is_on": is_on
                }

            elif "/On" in path:
                if last_set_color:
                    set_strip(last_set_color["rgb"], last_set_color["light_level"])
                else:
                    set_strip([255, 0, 255], 0.5)
                response_code = "201 Created"
                response_body = {
                    "current": {"rgb": last_set_color["rgb"], "light_level": last_set_color["light_level"] if last_set_color else 0.5},
                    "last": last_set_color,
                    "is_on": is_on
                }

            elif "/CheckState" in path:
                response_body = {
                    "current": {"rgb": last_set_color["rgb"], "light_level": last_set_color["light_level"]} if last_set_color else None,
                    "last": last_set_color,
                    "is_on": is_on
                }
                if last_set_color is None and not is_on:
                    response_code = "204 No Content"

            else:
                response_code = "400 Bad Request"
                response_body = {"error": "Unknown request", "is_on": is_on}

        # --- Send response ---
        response_json = ujson.dumps(response_body)
        client.send(f"HTTP/1.1 {response_code}\nContent-Type: application/json\n\n{response_json}".encode())
        client.close()
        print(f"Request: {method} {path}, Response: {response_code}, is_on: {is_on}")



# --- File + console logger ---
def log(msg):
    try:
        ts = time.time()
    except:
        ts = 0

    line = "[{}] {}\n".format(ts, msg)

    # Print to serial
    print(line, end="")

    # Append to log file
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    except Exception as e:
        print("Log write failed:", e)


# --- Open socket ---
def open_socket(ip):
    addr = (ip, 80)
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    #Log only errors
    #log("Listening on {}:80".format(ip))
    return s


# --- Main loop ---
try:
    #Log only errors
    #log("System start")

    while True:
        #Log only errors
        #log("Attempting WiFi connection...")

        try:
            ip = do_connect()
        except Exception as e:
            #Log only errors
            #log("do_connect exception: {}".format(e))
            #Log only errors
            #log("Cooldown {}s before retry".format(COOLDOWN))
            time.sleep(COOLDOWN)
            continue

        if not ip:
            log("do_connect returned no IP")
            time.sleep(COOLDOWN)
            continue
        #Log only errors
        #log("Connected, IP: {}".format(ip))

        try:
            sock = open_socket(ip)
            serve(sock)
        except Exception as e:
            log("Server error: {}".format(e))
        finally:
            try:
                sock.close()
                #Log only errors
                #log("Socket closed")
            except:
                pass
        #Log only errors
        #log("Restarting connection loop")
        time.sleep(COOLDOWN)

except KeyboardInterrupt:
    log("KeyboardInterrupt: resetting")
    set_strip(turn_off=True)
    machine.reset()



