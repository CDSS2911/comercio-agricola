import argparse
import json
import queue
import threading
import time
import urllib.request
import urllib.error

import serial


def bcd_digits(byte):
    return (byte >> 4) & 0xF, byte & 0xF


def decode_weight_from_frame(frame):
    # Esperado: ff 42 XX YY 00 00
    if len(frame) < 6 or frame[0] != 0xFF or frame[1] != 0x42:
        return None
    xx = frame[2]
    yy = frame[3]
    d1, d2 = bcd_digits(yy)
    d3, d4 = bcd_digits(xx)
    return (d1 * 1000 + d2 * 100 + d3 * 10 + d4) / 10.0


def post_weight(url, token, peso, roto=False, timeout=5):
    payload = json.dumps({"peso": peso, "roto": roto}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Scale-Token", token)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read().decode("utf-8", errors="ignore")


def main():
    parser = argparse.ArgumentParser(description="Envia pesos de balanza al servidor")
    parser.add_argument("--port", default="COM15")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--base-url", required=True, help="Ej: http://SERVER:5000")
    parser.add_argument("--pesa-id", type=int, required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--stable-count", type=int, default=1)
    parser.add_argument("--min-interval", type=float, default=0.0)
    parser.add_argument("--tol", type=float, default=1.0)
    parser.add_argument("--reset-threshold", type=float, default=1.0)
    parser.add_argument("--serial-timeout", type=float, default=0.005)
    parser.add_argument("--poll-sleep", type=float, default=0.001)
    args = parser.parse_args()

    url = f"{args.base_url}/inventario/pesas/{args.pesa_id}/pesar/auto"

    ser = serial.Serial(
        port=args.port,
        baudrate=args.baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=args.serial_timeout,
    )

    last_read = None
    stable = 0
    last_sent = None
    last_sent_time = 0.0
    armed = True
    buffer = bytearray()
    send_queue = queue.Queue(maxsize=256)
    running = threading.Event()
    running.set()

    def sender_loop():
        while running.is_set() or not send_queue.empty():
            try:
                item = send_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                status, body = post_weight(url, args.token, item)
                print(f"Enviado {item:.1f} g -> {status} {body}")
            except urllib.error.HTTPError as e:
                print(f"HTTP {e.code}: {e.read().decode('utf-8', errors='ignore')}")
            except Exception as e:
                print(f"Error enviando peso: {e}")
            finally:
                send_queue.task_done()

    sender_thread = threading.Thread(target=sender_loop, daemon=True)
    sender_thread.start()

    try:
        while True:
            # Leer todo lo disponible para minimizar latencia.
            n = ser.in_waiting
            if n <= 0:
                n = 1
            data = ser.read(n)
            if not data:
                time.sleep(args.poll_sleep)
                continue

            buffer.extend(data)

            while len(buffer) >= 6:
                start = buffer.find(b"\xFF\x42")
                if start < 0:
                    buffer.clear()
                    break
                if len(buffer) < start + 6:
                    # Esperar a completar frame
                    if start > 0:
                        del buffer[:start]
                    break

                frame = bytes(buffer[start : start + 6])
                del buffer[: start + 6]
                weight = decode_weight_from_frame(frame)
                if weight is None:
                    continue

                # Rearme solo en rango de reset: 0.0g a RESET_THRESHOLD.
                if 0.0 <= weight <= args.reset_threshold:
                    stable = 0
                    last_read = None
                    armed = True
                    last_sent = None
                    continue

                if last_read is not None and abs(weight - last_read) <= args.tol:
                    stable += 1
                else:
                    stable = 1
                    last_read = weight

                if stable >= args.stable_count and armed:
                    now = time.time()
                    if now - last_sent_time >= args.min_interval:
                        try:
                            send_queue.put_nowait(weight)
                            last_sent = weight
                            last_sent_time = now
                            armed = False
                        except Exception as e:
                            print(f"Error encolando peso: {e}")

            time.sleep(args.poll_sleep)
    finally:
        running.clear()
        try:
            sender_thread.join(timeout=1.0)
        except Exception:
            pass
        ser.close()


if __name__ == "__main__":
    main()
