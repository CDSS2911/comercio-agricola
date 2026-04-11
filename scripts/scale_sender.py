import argparse
import json
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from tkinter import END, BOTH, LEFT, RIGHT, Y, messagebox, ttk
import tkinter as tk
from tkinter import filedialog

import serial
from serial.tools import list_ports


APP_NAME = "Scale Sender"
DEFAULT_CONFIG_NAME = "Pesa principal"
GUIDE_FILENAME = "Guia_Configuracion_Pesas.pdf"
STARTUP_LAUNCHER_NAME = "Iniciar Envio de Pesas.bat"
GUIDE_LINES = [
    "Guia rapida de configuracion de pesas",
    "",
    "1. Conecte la pesa al puerto USB del computador.",
    "2. Abra la aplicacion Configurador de Pesas.",
    "3. Seleccione la configuracion deseada o cree una nueva.",
    "4. Verifique: URL del servidor, ID de la pesa, token, puerto COM.",
    "5. Pulse Iniciar envio.",
    "6. Coloque un huevo en la pesa y confirme en el estado que fue enviado.",
    "7. Para usar varias pesas, cree una configuracion por cada una.",
    "",
    "Consejos:",
    "- Si no sabe el puerto, pulse Actualizar puertos.",
    "- Si la red falla, revise internet y URL del servidor.",
    "- No cierre el programa mientras este pesando.",
    "",
    "Soporte:",
    "Contacte al administrador de la granja para ajustes avanzados.",
]


@dataclass
class ScaleConfig:
    name: str = DEFAULT_CONFIG_NAME
    base_url: str = "http://hrentubolsillo.org"
    pesa_id: int = 1
    token: str = "Cdss_29112002"
    port: str = "COM15"
    baud: int = 9600
    tol: float = 1.0
    reset_threshold: float = 1.0
    stable_count: int = 1
    min_interval: float = 0.0
    serial_timeout: float = 0.005
    poll_sleep: float = 0.001

    @classmethod
    def from_dict(cls, data):
        merged = asdict(cls())
        merged.update(data or {})
        return cls(
            name=str(merged.get("name", DEFAULT_CONFIG_NAME)).strip() or DEFAULT_CONFIG_NAME,
            base_url=str(merged.get("base_url", "")).strip() or "http://hrentubolsillo.org",
            pesa_id=int(merged.get("pesa_id", 1)),
            token=str(merged.get("token", "")).strip(),
            port=str(merged.get("port", "COM15")).strip() or "COM15",
            baud=int(merged.get("baud", 9600)),
            tol=float(merged.get("tol", 1.0)),
            reset_threshold=float(merged.get("reset_threshold", 1.0)),
            stable_count=int(merged.get("stable_count", 1)),
            min_interval=float(merged.get("min_interval", 0.0)),
            serial_timeout=float(merged.get("serial_timeout", 0.005)),
            poll_sleep=float(merged.get("poll_sleep", 0.001)),
        )

    def validate(self):
        if not self.base_url.startswith(("http://", "https://")):
            raise ValueError("La URL debe iniciar en http:// o https://")
        if self.pesa_id <= 0:
            raise ValueError("El ID de pesa debe ser mayor a 0")
        if not self.token:
            raise ValueError("El token no puede estar vacio")
        if not self.port:
            raise ValueError("El puerto COM no puede estar vacio")
        if self.baud <= 0:
            raise ValueError("Baudios debe ser mayor a 0")


class ConfigStore:
    def __init__(self):
        appdata = os.environ.get("APPDATA", str(Path.home()))
        self.folder = Path(appdata) / "ScaleSender"
        self.path = self.folder / "scale_configs.json"
        self.folder.mkdir(parents=True, exist_ok=True)

    def load(self):
        if not self.path.exists():
            return [ScaleConfig()]
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rows = data if isinstance(data, list) else [data]
            items = [ScaleConfig.from_dict(row) for row in rows]
            return items or [ScaleConfig()]
        except Exception:
            return [ScaleConfig()]

    def save(self, configs):
        payload = [asdict(c) for c in configs]
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def bcd_digits(byte_value):
    return (byte_value >> 4) & 0xF, byte_value & 0xF


def decode_weight_from_frame(frame):
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


class WeightSenderService:
    def __init__(self):
        self.running = threading.Event()
        self.send_queue = queue.Queue(maxsize=256)
        self.serial_port = None
        self.read_thread = None
        self.sender_thread = None

    def start(self, config, log_callback):
        if self.running.is_set():
            raise RuntimeError("El envio ya esta en ejecucion")

        config.validate()
        self.url = f"{config.base_url}/inventario/pesas/{config.pesa_id}/pesar/auto"
        self.token = config.token
        self.config = config
        self.log_callback = log_callback

        self.serial_port = serial.Serial(
            port=config.port,
            baudrate=config.baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=config.serial_timeout,
        )

        self.running.set()
        self.read_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self.sender_thread = threading.Thread(target=self._sender_loop, daemon=True)
        self.read_thread.start()
        self.sender_thread.start()
        self._log(f"Escuchando pesa en {config.port} y enviando a {self.url}")

    def stop(self):
        if not self.running.is_set():
            return
        self.running.clear()
        try:
            if self.read_thread:
                self.read_thread.join(timeout=1.5)
        except Exception:
            pass
        try:
            if self.sender_thread:
                self.sender_thread.join(timeout=1.5)
        except Exception:
            pass
        try:
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
        except Exception:
            pass
        self._log("Envio detenido.")

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)

    def _sender_loop(self):
        while self.running.is_set() or not self.send_queue.empty():
            try:
                item = self.send_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                status, body = post_weight(self.url, self.token, item)
                self._log(f"Enviado {item:.1f} g -> {status} {body}")
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="ignore")
                self._log(f"HTTP {exc.code}: {body}")
            except Exception as exc:
                self._log(f"Error enviando peso: {exc}")
            finally:
                self.send_queue.task_done()

    def _reader_loop(self):
        last_read = None
        stable = 0
        last_sent_time = 0.0
        armed = True
        buffer = bytearray()

        while self.running.is_set():
            n = self.serial_port.in_waiting
            if n <= 0:
                n = 1
            data = self.serial_port.read(n)
            if not data:
                time.sleep(self.config.poll_sleep)
                continue

            buffer.extend(data)

            while len(buffer) >= 6:
                start = buffer.find(b"\xFF\x42")
                if start < 0:
                    buffer.clear()
                    break
                if len(buffer) < start + 6:
                    if start > 0:
                        del buffer[:start]
                    break

                frame = bytes(buffer[start : start + 6])
                del buffer[: start + 6]
                weight = decode_weight_from_frame(frame)
                if weight is None:
                    continue

                if 0.0 <= weight <= self.config.reset_threshold:
                    stable = 0
                    last_read = None
                    armed = True
                    continue

                if last_read is not None and abs(weight - last_read) <= self.config.tol:
                    stable += 1
                else:
                    stable = 1
                    last_read = weight

                if stable >= self.config.stable_count and armed:
                    now = time.time()
                    if now - last_sent_time >= self.config.min_interval:
                        try:
                            self.send_queue.put_nowait(weight)
                            last_sent_time = now
                            armed = False
                        except Exception as exc:
                            self._log(f"Error encolando peso: {exc}")

            time.sleep(self.config.poll_sleep)


def generate_simple_pdf(path, lines):
    safe_lines = [line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for line in lines]
    y = 790
    text_commands = ["BT", "/F1 12 Tf", "50 790 Td"]
    current_y = 790
    for idx, line in enumerate(safe_lines):
        if idx == 0:
            text_commands.append(f"({line}) Tj")
            continue
        target_y = y - idx * 18
        step = target_y - current_y
        current_y = target_y
        text_commands.append(f"0 {step} Td")
        text_commands.append(f"({line}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>endobj\n"
    )
    objects.append(b"4 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    objects.append(f"5 0 obj<< /Length {len(stream)} >>stream\n".encode("latin-1") + stream + b"\nendstream\nendobj\n")

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    content = bytearray(header)
    offsets = [0]
    for obj in objects:
        offsets.append(len(content))
        content.extend(obj)

    xref_start = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n".encode("latin-1"))
    content.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        content.extend(f"{off:010d} 00000 n \n".encode("latin-1"))

    content.extend(
        f"trailer<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("latin-1")
    )
    Path(path).write_bytes(content)


def create_desktop_launcher():
    desktop = Path.home() / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    exe_path = Path(sys.executable if getattr(sys, "frozen", False) else Path(__file__).resolve())
    launcher_path = desktop / "Abrir Configurador de Pesas.bat"
    launcher_content = f'@echo off\nstart "" "{exe_path}"\n'
    launcher_path.write_text(launcher_content, encoding="utf-8")
    return launcher_path


def create_startup_launcher(config_name=None):
    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    startup_dir.mkdir(parents=True, exist_ok=True)
    launcher_path = startup_dir / STARTUP_LAUNCHER_NAME

    if getattr(sys, "frozen", False):
        exe_path = str(Path(sys.executable).resolve())
        cmd = f'"{exe_path}" --gui --auto-start'
    else:
        py_exe = sys.executable
        script = str(Path(__file__).resolve())
        cmd = f'"{py_exe}" "{script}" --gui --auto-start'

    if config_name:
        safe_name = config_name.replace('"', "")
        cmd = f'{cmd} --auto-config-name "{safe_name}"'

    launcher_content = f'@echo off\nstart "" {cmd}\n'
    launcher_path.write_text(launcher_content, encoding="utf-8")
    return launcher_path


def remove_startup_launcher():
    startup_dir = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    launcher_path = startup_dir / STARTUP_LAUNCHER_NAME
    if launcher_path.exists():
        launcher_path.unlink()
        return True, launcher_path
    return False, launcher_path


class ScaleSenderGUI:
    def __init__(self, root, auto_start=False, auto_config_name=None):
        self.root = root
        self.root.title("Configurador de Pesas")
        self.root.geometry("1100x700")
        self.root.minsize(980, 640)

        self.store = ConfigStore()
        self.configs = self.store.load()
        self.service = WeightSenderService()
        self.log_queue = queue.Queue()

        self.selected_index = None
        self.vars = {
            "name": tk.StringVar(),
            "base_url": tk.StringVar(),
            "pesa_id": tk.StringVar(),
            "token": tk.StringVar(),
            "port": tk.StringVar(),
            "baud": tk.StringVar(),
            "tol": tk.StringVar(),
            "reset_threshold": tk.StringVar(),
            "stable_count": tk.StringVar(),
            "min_interval": tk.StringVar(),
            "serial_timeout": tk.StringVar(),
            "poll_sleep": tk.StringVar(),
        }
        self.status_var = tk.StringVar(value="Listo")

        self._build_ui()
        self._load_list()
        if auto_config_name:
            self._select_config_by_name(auto_config_name)
        self.auto_start = auto_start
        self._poll_logs()
        if self.auto_start:
            self.root.after(800, self.auto_start_service)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill=BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=LEFT, fill=Y, padx=(0, 12))

        ttk.Label(left, text="Pesas configuradas").pack(anchor="w")
        list_frame = ttk.Frame(left)
        list_frame.pack(fill=Y, expand=True, pady=(6, 8))
        self.listbox = tk.Listbox(list_frame, height=20, width=32)
        self.listbox.pack(side=LEFT, fill=Y)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        ttk.Button(left, text="Nueva pesa", command=self.new_config).pack(fill="x", pady=2)
        ttk.Button(left, text="Guardar cambios", command=self.save_current).pack(fill="x", pady=2)
        ttk.Button(left, text="Eliminar pesa", command=self.delete_current).pack(fill="x", pady=2)

        right = ttk.Frame(main)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        form = ttk.LabelFrame(right, text="Configuracion", padding=10)
        form.pack(fill="x")

        fields = [
            ("Nombre", "name"),
            ("URL servidor", "base_url"),
            ("ID pesa", "pesa_id"),
            ("Token", "token"),
            ("Puerto COM", "port"),
            ("Baudios", "baud"),
            ("Tolerancia", "tol"),
            ("Reset threshold", "reset_threshold"),
            ("Lecturas estables", "stable_count"),
            ("Intervalo minimo", "min_interval"),
            ("Timeout serial", "serial_timeout"),
            ("Pausa lectura", "poll_sleep"),
        ]
        for row, (label, key) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            entry = ttk.Entry(form, textvariable=self.vars[key], width=45)
            entry.grid(row=row, column=1, sticky="ew", pady=4)
        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Actualizar puertos", command=self.refresh_ports).pack(side=LEFT, padx=(0, 8))
        ttk.Button(actions, text="Instalar acceso directo", command=self.install_shortcut).pack(side=LEFT, padx=(0, 8))
        ttk.Button(actions, text="Activar inicio automatico", command=self.install_startup).pack(side=LEFT, padx=(0, 8))
        ttk.Button(actions, text="Quitar inicio automatico", command=self.remove_startup).pack(side=LEFT, padx=(0, 8))
        ttk.Button(actions, text="Descargar guia PDF", command=self.download_guide).pack(side=LEFT)

        run_actions = ttk.Frame(right)
        run_actions.pack(fill="x", pady=(10, 0))
        ttk.Button(run_actions, text="Iniciar envio", command=self.start_service).pack(side=LEFT, padx=(0, 8))
        ttk.Button(run_actions, text="Detener envio", command=self.stop_service).pack(side=LEFT)
        ttk.Label(run_actions, textvariable=self.status_var).pack(side=RIGHT)

        log_frame = ttk.LabelFrame(right, text="Estado", padding=8)
        log_frame.pack(fill=BOTH, expand=True, pady=(10, 0))
        self.log_text = tk.Text(log_frame, wrap="word", height=16)
        self.log_text.pack(fill=BOTH, expand=True)

    def _log(self, msg):
        self.log_queue.put(msg)

    def _poll_logs(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.insert(END, f"{time.strftime('%H:%M:%S')} - {msg}\n")
                self.log_text.see(END)
        except queue.Empty:
            pass
        self.root.after(150, self._poll_logs)

    def _load_list(self):
        self.listbox.delete(0, END)
        for cfg in self.configs:
            self.listbox.insert(END, cfg.name)
        if self.configs:
            self.listbox.selection_set(0)
            self.on_select(None)

    def on_select(self, _event):
        selection = self.listbox.curselection()
        if not selection:
            return
        self.selected_index = selection[0]
        cfg = self.configs[self.selected_index]
        for key, value in asdict(cfg).items():
            self.vars[key].set(str(value))

    def _select_config_by_name(self, config_name):
        wanted = config_name.strip().lower()
        for idx, cfg in enumerate(self.configs):
            if cfg.name.strip().lower() == wanted:
                self.listbox.selection_clear(0, END)
                self.listbox.selection_set(idx)
                self.on_select(None)
                return True
        return False

    def _config_from_form(self):
        return ScaleConfig(
            name=self.vars["name"].get().strip() or DEFAULT_CONFIG_NAME,
            base_url=self.vars["base_url"].get().strip(),
            pesa_id=int(self.vars["pesa_id"].get().strip()),
            token=self.vars["token"].get().strip(),
            port=self.vars["port"].get().strip(),
            baud=int(self.vars["baud"].get().strip()),
            tol=float(self.vars["tol"].get().strip()),
            reset_threshold=float(self.vars["reset_threshold"].get().strip()),
            stable_count=int(self.vars["stable_count"].get().strip()),
            min_interval=float(self.vars["min_interval"].get().strip()),
            serial_timeout=float(self.vars["serial_timeout"].get().strip()),
            poll_sleep=float(self.vars["poll_sleep"].get().strip()),
        )

    def new_config(self):
        cfg = ScaleConfig(name=f"Pesa {len(self.configs) + 1}")
        self.configs.append(cfg)
        self.store.save(self.configs)
        self._load_list()
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(len(self.configs) - 1)
        self.on_select(None)
        self._log("Nueva pesa creada.")

    def save_current(self):
        if self.selected_index is None:
            messagebox.showwarning("Atencion", "Seleccione una pesa.")
            return False
        try:
            cfg = self._config_from_form()
            cfg.validate()
        except Exception as exc:
            messagebox.showerror("Error", f"Revise los campos: {exc}")
            return False
        self.configs[self.selected_index] = cfg
        self.store.save(self.configs)
        self._load_list()
        self.listbox.selection_clear(0, END)
        self.listbox.selection_set(self.selected_index)
        self.on_select(None)
        self._log("Configuracion guardada.")
        return True

    def delete_current(self):
        if self.selected_index is None:
            return
        if len(self.configs) == 1:
            messagebox.showwarning("Atencion", "Debe existir al menos una configuracion.")
            return
        if not messagebox.askyesno("Confirmar", "Desea eliminar esta pesa?"):
            return
        del self.configs[self.selected_index]
        self.store.save(self.configs)
        self.selected_index = None
        self._load_list()
        self._log("Pesa eliminada.")

    def refresh_ports(self):
        ports = [p.device for p in list_ports.comports()]
        if not ports:
            self._log("No se detectaron puertos COM.")
            messagebox.showinfo("Puertos COM", "No se detectaron puertos COM.")
            return
        joined = ", ".join(ports)
        self._log(f"Puertos detectados: {joined}")
        messagebox.showinfo("Puertos COM", f"Puertos detectados:\n{joined}")

    def install_shortcut(self):
        try:
            path = create_desktop_launcher()
            self._log(f"Acceso directo creado en: {path}")
            messagebox.showinfo("Instalacion", f"Acceso directo creado:\n{path}")
        except Exception as exc:
            messagebox.showerror("Error", f"No fue posible crear el acceso directo: {exc}")

    def install_startup(self):
        if self.selected_index is None:
            messagebox.showwarning("Atencion", "Seleccione una pesa.")
            return
        saved = self.save_current()
        if not saved or self.selected_index is None:
            return
        try:
            cfg = self.configs[self.selected_index]
            path = create_startup_launcher(cfg.name)
            self._log(f"Inicio automatico activado: {path}")
            messagebox.showinfo("Inicio automatico", f"Se activo el inicio automatico.\nArchivo:\n{path}")
        except Exception as exc:
            messagebox.showerror("Error", f"No fue posible activar inicio automatico: {exc}")

    def remove_startup(self):
        try:
            removed, path = remove_startup_launcher()
            if removed:
                self._log(f"Inicio automatico desactivado: {path}")
                messagebox.showinfo("Inicio automatico", "Inicio automatico desactivado.")
            else:
                messagebox.showinfo("Inicio automatico", "No habia inicio automatico configurado.")
        except Exception as exc:
            messagebox.showerror("Error", f"No fue posible desactivar inicio automatico: {exc}")

    def download_guide(self):
        target = filedialog.asksaveasfilename(
            title="Guardar guia PDF",
            defaultextension=".pdf",
            initialfile=GUIDE_FILENAME,
            filetypes=[("PDF", "*.pdf")],
        )
        if not target:
            return
        try:
            generate_simple_pdf(target, GUIDE_LINES)
            self._log(f"Guia guardada en: {target}")
            messagebox.showinfo("Guia", f"Guia guardada en:\n{target}")
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo crear la guia: {exc}")

    def start_service(self):
        try:
            saved = self.save_current()
            if not saved or self.selected_index is None:
                return
            cfg = self.configs[self.selected_index]
            self._start_with_config(cfg, silent=False)
        except Exception as exc:
            messagebox.showerror("Error", f"No fue posible iniciar el envio: {exc}")

    def _start_with_config(self, cfg, silent):
        self.service.start(cfg, self._log)
        self.status_var.set(f"Enviando pesos ({cfg.name})")
        if not silent:
            self._log(f"Envio iniciado con la configuracion: {cfg.name}")

    def auto_start_service(self):
        if self.selected_index is None or not self.configs:
            self._log("Auto inicio omitido: no hay configuraciones disponibles.")
            return
        if self.service.running.is_set():
            return
        cfg = self.configs[self.selected_index]
        try:
            self._start_with_config(cfg, silent=True)
            self._log("Auto inicio ejecutado correctamente.")
        except Exception as exc:
            self.status_var.set("Error en auto inicio")
            self._log(f"Error en auto inicio: {exc}")

    def stop_service(self):
        self.service.stop()
        self.status_var.set("Detenido")

    def on_close(self):
        try:
            self.service.stop()
        finally:
            self.root.destroy()


def run_cli(args):
    config = ScaleConfig(
        name="CLI",
        base_url=args.base_url,
        pesa_id=args.pesa_id,
        token=args.token,
        port=args.port,
        baud=args.baud,
        tol=args.tol,
        reset_threshold=args.reset_threshold,
        stable_count=args.stable_count,
        min_interval=args.min_interval,
        serial_timeout=args.serial_timeout,
        poll_sleep=args.poll_sleep,
    )
    config.validate()
    service = WeightSenderService()
    service.start(config, print)
    try:
        while True:
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("Deteniendo envio...")
    finally:
        service.stop()


def build_parser():
    parser = argparse.ArgumentParser(description="Envia pesos de balanza al servidor")
    parser.add_argument("--gui", action="store_true", help="Abre la interfaz grafica")
    parser.add_argument("--auto-start", action="store_true", help="Inicia el envio automaticamente al abrir interfaz")
    parser.add_argument("--auto-config-name", help="Nombre de la configuracion para auto inicio")
    parser.add_argument("--port", default="COM15")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--base-url", help="Ej: http://SERVER:5000")
    parser.add_argument("--pesa-id", type=int)
    parser.add_argument("--token")
    parser.add_argument("--stable-count", type=int, default=1)
    parser.add_argument("--min-interval", type=float, default=0.0)
    parser.add_argument("--tol", type=float, default=1.0)
    parser.add_argument("--reset-threshold", type=float, default=1.0)
    parser.add_argument("--serial-timeout", type=float, default=0.005)
    parser.add_argument("--poll-sleep", type=float, default=0.001)
    return parser


def run_gui(auto_start=False, auto_config_name=None):
    root = tk.Tk()
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    ScaleSenderGUI(root, auto_start=auto_start, auto_config_name=auto_config_name)
    root.mainloop()


def main():
    parser = build_parser()
    args = parser.parse_args()

    run_in_gui = args.gui or args.auto_start or len(sys.argv) == 1
    if run_in_gui:
        run_gui(auto_start=args.auto_start, auto_config_name=args.auto_config_name)
        return

    missing = [name for name in ("base_url", "pesa_id", "token") if getattr(args, name) in (None, "")]
    if missing:
        parser.error(f"Faltan argumentos obligatorios para modo consola: {', '.join(missing)}")
    run_cli(args)


if __name__ == "__main__":
    main()
