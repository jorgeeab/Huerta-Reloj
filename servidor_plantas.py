from flask import Flask, request, jsonify, render_template, redirect, url_for, Response
import threading
import webbrowser
from basic_gym_env.basic_env import BasicEnv
from datetime import datetime
from nuevo_plantas import PlantasManager
import time
import numpy as np
from protocolos import Protocolo
import os
import json
from pathlib import Path
import cv2

app = Flask(__name__)

# ---- Camera streaming -----------------------------------------------------
camera = cv2.VideoCapture(0)


def generate_frames():
    """Capture frames from the default camera and yield them as JPEG."""
    while True:
        success, frame = camera.read()
        if not success:
            continue
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.route('/video_feed')
def video_feed():
    """Video streaming route compatible con la etiqueta <img>."""
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ----- Simple JSON storage for demo endpoints -----
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)
REGS_FILE = DATA_DIR / 'regs.json'
PLANTS_FILE = DATA_DIR / 'plants.json'
TASKS_FILE = DATA_DIR / 'tasks.json'

def _load_json(path, default):
    """Load JSON data, tolerating simple wrapper structures."""
    try:
        with open(path, 'r') as f:
            data = json.load(f)

            # If the file uses a dictionary wrapper, return the nested list.
            if isinstance(data, dict):
                # Common wrappers used in this repo
                for key in ('plants', 'regs', 'tareas', 'items'):
                    if key in data and isinstance(data[key], list):
                        return data[key]

                # Flatten "plantas_por_era" format into a simple list
                if 'plantas_por_era' in data:
                    combined = []
                    for era_items in data['plantas_por_era'].values():
                        if isinstance(era_items, list):
                            combined.extend(era_items)
                    return combined

            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def _save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

class ServidorFlask:
    def __init__(self):
        # Inicializamos la lista de logs antes de crear el entorno ya que este
        # podría llamar al logger durante su construcción.  Si ``self.logs`` no
        # existiera en ese momento se produciría un ``AttributeError``.
        self.logs = []

        # Inicializamos el entorno y el gestor de plantas
        self.env = BasicEnv(port='COM5', baudrate=115200, logger=self.log)
        self.manager = PlantasManager()
        self.manual_corredera = False
        self.manual_angulo = False
        self.manual_valvula = False

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        self.logs.append(entry)
        if len(self.logs) > 100:
            self.logs.pop(0)
        print(entry)

    # ---- Métodos de Control del Entorno ----
    def actualizar_acciones(self, data):
        try:
            self.log("Ingresando a actualizar_acciones")
            self.log(f"Data recibida: {data}")

            # Actualizar modos manuales individuales
            flags_changed = False
            for comp in ('corredera', 'angulo', 'valvula'):
                key = f'manual_{comp}'
                val = data.get(key)
                if val is not None:
                    setattr(self, key, bool(int(val)))
                    self.log(f"{key} actualizado a {val}")
                    flags_changed = True

            manual_mode = data.get('manual_mode')
            if flags_changed:
                manual_mode = int(self.manual_corredera or self.manual_angulo or self.manual_valvula)
                self.env.set_manual_mode(manual_mode)
                self.log(f"manual_mode actualizado a {manual_mode}")
            elif manual_mode is not None:
                self.env.set_manual_mode(int(manual_mode))
                self.log(f"manual_mode actualizado a {manual_mode}")
                if int(manual_mode) == 0:
                    self.manual_corredera = False
                    self.manual_angulo = False
                    self.manual_valvula = False
            manual_mode = self.env.manual_mode
            # Configurar joypad si se proporciona
            joypad_action = data.get('joypad_action')
            if joypad_action:
                if joypad_action == 'enable':
                    self.env.enable_joypad()
                    self.log("Joypad habilitado")
                elif joypad_action == 'disable':
                    self.env.disable_joypad()
                    self.log("Joypad deshabilitado")

            # Actualizar setpoints si se proporcionan
            setpoints = data.get('setpoints', {})
            for component, value in setpoints.items():
                if component == 'slide':
                    self.env.set_corredera(value)
                    self.log(f"Setpoint slide actualizado a {value}")
                elif component == 'angle':
                    self.env.set_angulo(value)
                    self.log(f"Setpoint angle actualizado a {value}")
                elif component == 'volume':
                    self.env.set_volumen_requerido(value)
                    self.log(f"Setpoint volume actualizado a {value}")
                elif component == 'valve_motor':
                    self.env.set_valvula(value)
                    self.log(f"Setpoint valve actualizado a {value}")

            # Verificar si se debe resetear el volumen
            if data.get('reset_volume', False):
                self.env.reset_volumen()
                self.log("Volumen reiniciado a cero")

            # Actualizar configuraciones de PID si se proporcionan
            pid_settings = data.get('pid_settings', {})
            if pid_settings:
                kpX = pid_settings.get('kpX')
                kiX = pid_settings.get('kiX')
                kdX = pid_settings.get('kdX')
                if kpX is not None and kiX is not None and kdX is not None:
                    self.env.set_pid_corredera(kpX, kiX, kdX)
                    self.log(f"PID de corredera actualizado: kp={kpX}, ki={kiX}, kd={kdX}")

                kpA = pid_settings.get('kpA')
                kiA = pid_settings.get('kiA')
                kdA = pid_settings.get('kdA')
                if kpA is not None and kiA is not None and kdA is not None:
                    self.env.set_pid_angulo(kpA, kiA, kdA)
                    self.log(f"PID de ángulo actualizado: kp={kpA}, ki={kiA}, kd={kdA}")

            # Actualizar calibraciones si se proporcionan
            calibrations = data.get('calibrations', {})
            if calibrations:
                stepsPerMM = calibrations.get('stepsPerMM')
                stepsPerDegree = calibrations.get('stepsPerDegree')
                if stepsPerMM is not None:
                    self.env.set_steps_per_mm(stepsPerMM)
                    self.log(f"Calibración stepsPerMM actualizada: {stepsPerMM}")
                if stepsPerDegree is not None:
                    self.env.set_steps_per_degree(stepsPerDegree)
                    self.log(f"Calibración stepsPerDegree actualizada: {stepsPerDegree}")

            # Actualizar energías de los motores en modo manual si se proporciona
            motor_energies = data.get('motor_energies', {})
            if manual_mode and isinstance(motor_energies, dict):
                energy_corredera = motor_energies.get('corredera')
                energy_angulo = motor_energies.get('angulo')
                energy_valvula = motor_energies.get('valvula')

                if energy_corredera is not None:
                    self.env.set_energy_corredera(energy_corredera)
                    self.log(f"Energía del motor de corredera actualizada a {energy_corredera}")
                if energy_angulo is not None:
                    self.env.set_energy_angulo(energy_angulo)
                    self.log(f"Energía del motor de ángulo actualizada a {energy_angulo}")
                if energy_valvula is not None:
                    self.env.set_energy_valvula(energy_valvula)
                    self.log(f"Energía del motor de válvula actualizada a {energy_valvula}")
            # Realizamos un paso de simulación con la configuración actual
            self.env.step()
            return jsonify({'status': 'Configuración del entorno actualizada'}), 200
        except Exception as e:
            self.log(f"Error en actualizar_acciones - {str(e)}")
            return jsonify({'error': f'Error en el servidor: {str(e)}'}), 500

    # En la clase ServidorFlask:

    def obtener_estado_entorno(self, tiempo=None, intervalo=None):
        try:
            if tiempo is not None or intervalo is not None:
                # Obtener observaciones representativas basadas en el intervalo de tiempo o número de pasos
                obs_data = self.env.get_steps_from_batch(batch_id=self.env.current_batch, tiempo=tiempo,
                                                         intervalo=intervalo)

                if not obs_data or 'error' in obs_data:
                    self.log("No se encontraron observaciones dentro del rango de tiempo o con el intervalo especificado")
                    return jsonify({'error': 'No se encontraron observaciones representativas'}), 400

                # Construir una lista de observaciones en formato de diccionario
                formatted_obs_list = [
                    dict(zip(self.env.variable_names, obs_values))
                    for obs_values in zip(*[obs_data[col] for col in self.env.variable_names])
                ]
                return jsonify({'state': formatted_obs_list}), 200
            else:
                # Si no se proporciona un intervalo ni tiempo, devolver la última observación
                obs = self.env.get_observation()
                if obs is not None:
                    obs_list = [float(val) for val in obs.tolist()]
                    obs_dict = dict(zip(self.env.variable_names, obs_list))
                    self.log(f"Observación obtenida: {obs_dict}")
                    return jsonify({'state': obs_dict}), 200
                else:
                    self.log("No hay observación disponible")
                    return jsonify({'error': 'No hay observación disponible'}), 400
        except Exception as e:
            self.log(f"Error en obtener_estado_entorno - {str(e)}")
            return jsonify({'error': f'Error en el servidor: {str(e)}'}), 500

    # Nuevos métodos para cada acción de controlar_entorno

    def start_batch_action(self):
        batch_id = self.env.start_batch()
        return jsonify({"status": "Batch iniciado", "batch_id": batch_id}), 200

    def execute_steps_action(self, data):
        execution_time = data.get("execution_time")
        protocolo_nombre = data.get("protocolo_nombre")
        custom_code = data.get("custom_code")
        intervalo_tiempo_observaciones = data.get("intervalo_tiempo_observaciones", 1.0)  # Valor por defecto: 1 segundo

        if not execution_time:
            return jsonify({"error": "Se requiere 'execution_time' para ejecutar pasos."}), 400

        try:
            batch_id = self.env.start_batch()
            start_time = time.time()
            self.env.execution_data = []

            protocolo = None

            if protocolo_nombre:
                try:
                    protocolo = Protocolo(nombre_protocolo=protocolo_nombre)
                    if protocolo.funcion is None:
                        return jsonify(
                            {'error': f'El protocolo "{protocolo_nombre}" no contiene una función válida.'}), 400
                except Exception as e:
                    self.log(f"Error al cargar el protocolo '{protocolo_nombre}': {e}")

            if protocolo is None and custom_code:
                try:
                    local_variables = {}
                    exec(custom_code, {}, local_variables)
                    if 'custom_action' not in local_variables or not callable(local_variables['custom_action']):
                        return jsonify({
                            "error": "El código personalizado debe contener una función llamada 'custom_action'."}), 400
                    protocolo = local_variables['custom_action']
                except Exception as e:
                    return jsonify({"error": f"Error al procesar el código personalizado: {str(e)}"}), 400

            if protocolo is None:
                def protocolo(env):
                    return env.current_action.copy()

            collected_observations = []
            while time.time() - start_time < execution_time:
                obs = self.env.get_observation()
                if obs is None:
                    self.log("No se pudo obtener la observación.")
                    continue

                # Llamamos a 'protocolo' pasando 'self.env' como argumento
                calculated_action = protocolo(self.env) if callable(protocolo) else protocolo.ejecutar(self.env)
                self.env.step(calculated_action)

                # Recolectar observaciones en intervalos especificados
                current_time = time.time()
                elapsed_time = current_time - start_time
                if (elapsed_time % intervalo_tiempo_observaciones) < 0.3:
                    obs_dict = {name: float(val) for name, val in zip(self.env.variable_names, obs)}
                    collected_observations.append({"timestamp": datetime.now().isoformat(), "variables": obs_dict})

                self.env.store_serial_data(sent_data=str(calculated_action), received_data=str(obs))
                time.sleep(0.3)

            pasos_ejecutados = self.env.get_steps_from_batch(batch_id, intervalo=intervalo_tiempo_observaciones,
                                                             tiempo=execution_time)
            return jsonify({'status': 'Ejecución completada', 'batch_id': batch_id, 'data': pasos_ejecutados,
                            'observations': collected_observations}), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            self.log(f"Error inesperado: {e}")
            return jsonify({"error": f"Error inesperado: {str(e)}"}), 500

    def stop_batch_action(self):
        batch_id = self.env.current_batch
        if not batch_id:
            return jsonify({"error": "No hay un batch activo para detener."}), 400
        self.detener_motores()
        pasos_ejecutados = self.env.get_steps_from_batch(batch_id)
        # Almacena el batch actual como último batch antes de restablecer
        self.env.last_batch = self.env.current_batch
        # Resetear el batch actual
        self.env.current_batch = None
        return jsonify(
            {'status': 'Ejecución detenida exitosamente', 'batch_id': batch_id, 'batch_data': pasos_ejecutados}), 200
    def reset_action(self):
        self.env.reset()
        return jsonify({'status': 'Entorno reiniciado con éxito'}), 200

    # Métodos auxiliares
    def detener_motores(self):
        stop_action = self.env.current_action
        stop_action[0] = 1
        stop_action[1] = 0
        stop_action[2] = 0
        stop_action[3] = 0
        self.env.step(stop_action)

    # ---- Métodos de Control de Plantas ----

    def ejecutar_accion_plantas(self, data):
        """Determina y ejecuta la acción solicitada para las plantas."""
        accion = data.get("accion")
        if accion == "crear":
            return self.crear_planta(data)
        elif accion == "modificar":
            return self.modificar_planta(data)
        elif accion == "eliminar":
            return self.eliminar_planta(data)
        else:
            return jsonify({"error": "Acción inválida"}), 400

    def crear_planta(self, data):
        mensaje = self.manager.crear_planta(
            id_planta=data.get("id_planta"),
            nombre=data.get("nombre"),
            fecha_plantacion=self.parsear_fecha(data.get("fecha_plantacion")),
            angulo_h=data.get("angulo_h"),
            angulo_y=data.get("angulo_y"),
            longitud_slider=data.get("longitud_slider"),
            velocidad_agua=data.get("velocidad_agua"),
            era=data.get("era")
        )
        return jsonify({"mensaje": mensaje})

    def modificar_planta(self, data):
        mensaje = self.manager.modificar_planta(
            id_planta=data.get("id_planta"),
            era=data.get("era"),
            **{k: v for k, v in data.items() if k not in ["accion", "id_planta", "era"]}
        )
        return jsonify({"mensaje": mensaje})

    def eliminar_planta(self, data):
        mensaje = self.manager.eliminar_planta(
            id_planta=data.get("id_planta"),
            era=data.get("era")
        )
        return jsonify({"mensaje": mensaje})

    @staticmethod
    def parsear_fecha(fecha_str):
        formatos = ['%Y-%m-%d %H:%M', '%Y-%m-%d']
        for formato in formatos:
            try:
                return datetime.strptime(fecha_str, formato)
            except (ValueError, TypeError):
                continue
        return None

# Instancia del servidor

servidor = ServidorFlask()

# --- Soporte para la interfaz web ---
# Bloqueo para acceder al entorno desde varios hilos
env_lock = threading.Lock()

def background_task():
    while True:
        with env_lock:
            servidor.env.step()
        time.sleep(0.1)

threading.Thread(target=background_task, daemon=True).start()

@app.route('/', methods=['GET', 'POST'])
def robot_control():
    if request.method == 'POST':
        data = request.form
        manual_mode = data.get('manual_mode') == 'on'
        with env_lock:
            servidor.env.set_manual_mode(int(manual_mode))

        joypad_enabled = data.get('joypad_enabled') == 'on'
        if joypad_enabled:
            servidor.env.enable_joypad()
        else:
            servidor.env.disable_joypad()

        with env_lock:
            if not manual_mode:
                setpoint_corredera = data.get('setpoint_corredera', '0')
                setpoint_angulo = data.get('setpoint_angulo', '0')
                setpoint_water = data.get('setpoint_water', '0')
                servidor.env.set_corredera(float(setpoint_corredera))
                servidor.env.set_angulo(float(setpoint_angulo))
                servidor.env.set_valvula(float(setpoint_water))
            else:
                energia_corredera = data.get('energia_corredera', '0')
                energia_angulo = data.get('energia_angulo', '0')
                energia_valvula = data.get('energia_valvula', '0')
                servidor.env.set_energy_corredera(float(energia_corredera))
                servidor.env.set_energy_angulo(float(energia_angulo))
                servidor.env.set_energy_valvula(float(energia_valvula))

            pid_params = {}
            for pid in ['corredera', 'angulo', 'valvula']:
                kp = data.get(f'kp_{pid}', '0')
                ki = data.get(f'ki_{pid}', '0')
                kd = data.get(f'kd_{pid}', '0')
                pid_params[pid] = (float(kp), float(ki), float(kd))

            servidor.env.set_pid_corredera(*pid_params['corredera'])
            servidor.env.set_pid_angulo(*pid_params['angulo'])
            # servidor.env.set_pid_valvula(*pid_params['valvula'])

    with env_lock:
        observation = servidor.env.get_observation()
        if observation is not None:
            obs_list = observation.tolist()
            obs_dict = dict(zip(servidor.env.variable_names, obs_list))
        else:
            obs_dict = {}
        serial_connected = servidor.env.ser is not None and servidor.env.ser.is_open

    # Renderizamos la interfaz completa con dashboard y calendarios
    # que utiliza los mismos endpoints del entorno Flask.
    return render_template('panel.html',
                           obs=obs_dict,
                           current_port=servidor.env.port,
                           serial_connected=serial_connected)

@app.route('/get_observation')
def get_observation():
    with env_lock:
        observation = servidor.env.get_observation()
        if observation is not None:
            obs_list = observation.tolist()
            obs_dict = dict(zip(servidor.env.variable_names, obs_list))
            return jsonify(obs_dict)
        else:
            return jsonify({'error': 'No hay observación disponible'}), 500

@app.route('/simulate_key', methods=['POST'])
def simulate_key():
    key = request.json.get('key')
    if key:
        with env_lock:
            servidor.env.handle_key_press(key)
        return jsonify({'status': 'Key processed'}), 200
    else:
        return jsonify({'error': 'No key provided'}), 400

@app.route('/update_port', methods=['POST'])
def update_port():
    new_port = request.form.get('serial_port')
    if new_port:
        servidor.log(f"Solicitud para cambiar a puerto {new_port}")
        with env_lock:
            servidor.env.change_port(new_port)
        servidor.log(f"Puerto actual: {servidor.env.port}")
    return redirect(url_for('robot_control'))

@app.route('/toggle_connection', methods=['POST'])
def toggle_connection():
    with env_lock:
        if servidor.env.ser is None or not servidor.env.ser.is_open:
            servidor.log("Intentando conectar al puerto serial")
            servidor.env.connect_serial()
        else:
            servidor.log("Desconectando del puerto serial")
            servidor.env.disconnect_serial()
    return redirect(url_for('robot_control'))

# ---- Endpoints ----

# Endpoints para las acciones de controlar_entorno

@app.route('/entorno/start_batch', methods=['POST'])
def start_batch():
    return servidor.start_batch_action()

@app.route('/entorno/execute_steps', methods=['POST'])
def execute_steps():
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos."}), 400
    return servidor.execute_steps_action(data)

@app.route('/entorno/stop_batch', methods=['POST'])
def stop_batch():
    return servidor.stop_batch_action()


@app.route('/entorno/reset', methods=['POST'])
def reset():
    return servidor.reset_action()

# Endpoints para actualizar acciones y obtener estado

@app.route('/entorno/actualizar_acciones', methods=['POST'])
def actualizar_acciones():
    data = request.json
    if not data:
        servidor.log("No se enviaron datos en la solicitud a /entorno/actualizar_acciones")
        return jsonify({"error": "No se enviaron datos."}), 400
    return servidor.actualizar_acciones(data)


@app.route('/entorno/obtener_estado', methods=['POST'])
def obtener_estado():
    data = request.json
    if not data:
        servidor.log("No se enviaron datos en la solicitud a /entorno/obtener_estado")
        data = {}

    # Extraer los parámetros 'tiempo' e 'intervalo' de los datos recibidos
    tiempo = data.get('tiempo')
    intervalo = data.get('intervalo')

    # Asegurarse de que 'tiempo' e 'intervalo' sean números (float)
    if tiempo is not None:
        try:
            tiempo = float(tiempo)
        except ValueError:
            return jsonify({"error": "'tiempo' debe ser un número."}), 400
    if intervalo is not None:
        try:
            intervalo = float(intervalo)
        except ValueError:
            return jsonify({"error": "'intervalo' debe ser un número."}), 400

    return servidor.obtener_estado_entorno(tiempo=tiempo, intervalo=intervalo)


@app.route('/protocolos', methods=['GET'])
def listar_protocolos():
    protocolos_disponibles = Protocolo.listar_protocolos()
    return jsonify({'protocolos': protocolos_disponibles}), 200

@app.route('/protocolos', methods=['POST'])
def crear_actualizar_protocolo():
    data = request.json
    nombre_protocolo = data.get("nombre_protocolo")
    codigo = data.get("codigo")
    if not nombre_protocolo or not codigo:
        return jsonify({"error": "Datos incompletos para crear o actualizar el protocolo."}), 400
    try:
        Protocolo.guardar_protocolo(nombre_protocolo, codigo)
        return jsonify({'mensaje': f'Protocolo "{nombre_protocolo}" guardado exitosamente.'}), 200
    except Exception as e:
        return jsonify({'error': f'Error al guardar el protocolo: {str(e)}'}), 500
@app.route('/protocolos', methods=['DELETE'])
def eliminar_protocolo():
    data = request.json
    nombre_protocolo = data.get("nombre_protocolo")
    if not nombre_protocolo:
        return jsonify({"error": "Se requiere 'nombre_protocolo' para eliminar."}), 400
    try:
        Protocolo.eliminar_protocolo(nombre_protocolo)
        return jsonify({'mensaje': f'Protocolo "{nombre_protocolo}" eliminado exitosamente.'}), 200
    except Exception as e:
        return jsonify({'error': f'Error al eliminar el protocolo: {str(e)}'}), 500


# Endpoint para manejar plantas
@app.route('/plantas', methods=['POST'])
def manejar_plantas():
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos."}), 400
    return servidor.ejecutar_accion_plantas(data)


# ----- Simplified API endpoints used by the front-end -----

def _get_items(path):
    return _load_json(path, [])

def _save_items(path, items):
    existing = _load_json(path, None)
    if isinstance(existing, dict):
        if 'plantas_por_era' in existing:
            existing['plantas_por_era'] = {'default': items}
            _save_json(path, existing)
            return
        if 'tareas' in existing:
            existing['tareas'] = items
            _save_json(path, existing)
            return
        if 'regs' in existing:
            existing['regs'] = items
            _save_json(path, existing)
            return

    _save_json(path, items)

@app.route('/api/regs', methods=['GET', 'POST'])
def api_regs():
    regs = _get_items(REGS_FILE)
    if request.method == 'POST':
        # Allow creating a new regimen without specifying an ID.
        id_val = request.form.get('id')
        if id_val is None or id_val == "":
            next_id = max((r.get('id', 0) for r in regs), default=0) + 1
        else:
            try:
                next_id = int(id_val)
            except ValueError:
                next_id = 0

        reg = {
            'id': next_id,
            'n': request.form.get('n', ''),
            'd': request.form.get('d', '')
        }
        regs = [r for r in regs if r.get('id') != reg['id']]
        regs.append(reg)
        _save_items(REGS_FILE, regs)
        return jsonify({'status': 'saved'})
    del_id = request.args.get('del')
    if del_id is not None:
        regs = [r for r in regs if str(r.get('id')) != del_id]
        _save_items(REGS_FILE, regs)
        return jsonify({'status': 'deleted'})
    return jsonify(regs)


@app.route('/api/plants', methods=['GET', 'POST'])
def api_plants():
    plants = _get_items(PLANTS_FILE)
    if request.method == 'POST':
        id_val = request.form.get('id')
        if id_val is None or id_val == "":
            next_id = max((p.get('id', 0) for p in plants), default=0) + 1
        else:
            try:
                next_id = int(id_val)
            except ValueError:
                next_id = 0

        plant = {
            'id': next_id,
            'reg': request.form.get('reg'),
            'n': request.form.get('n'),
            'd': request.form.get('d'),
            's1': float(request.form.get('s1', 0)),
            's2': float(request.form.get('s2', 0)),
            'sp': float(request.form.get('sp', 0)),
            'day': int(request.form.get('day', 1)),
            'mon': int(request.form.get('mon', 1)),
            'yr': int(request.form.get('yr', 2025))
        }
        plants = [p for p in plants if p.get('id') != plant['id']]
        plants.append(plant)
        _save_items(PLANTS_FILE, plants)
        return jsonify({'status': 'saved'})
    del_id = request.args.get('del')
    if del_id is not None:
        plants = [p for p in plants if str(p.get('id')) != del_id]
        _save_items(PLANTS_FILE, plants)
        return jsonify({'status': 'deleted'})
    return jsonify(plants)


@app.route('/api/tasks', methods=['GET', 'POST'])
def api_tasks():
    tasks = _get_items(TASKS_FILE)
    if request.method == 'POST':
        id_val = request.form.get('id')
        if id_val is None or id_val == "":
            next_id = max((t.get('id', 0) for t in tasks), default=0) + 1
        else:
            try:
                next_id = int(id_val)
            except ValueError:
                next_id = 0

        task = {
            'id': next_id,
            'reg': request.form.get('reg'),
            'n': request.form.get('n'),
            'off': request.form.get('off'),
            'h': request.form.get('h'),
            'm': request.form.get('m'),
            'vol': request.form.get('vol'),
            'exe': request.form.get('exe')
        }
        tasks = [t for t in tasks if t.get('id') != task['id']]
        tasks.append(task)
        _save_items(TASKS_FILE, tasks)
        return jsonify({'status': 'saved'})
    del_id = request.args.get('del')
    if del_id is not None:
        tasks = [t for t in tasks if str(t.get('id')) != del_id]
        _save_items(TASKS_FILE, tasks)
        return jsonify({'status': 'deleted'})
    return jsonify(tasks)


@app.route('/api/robots', methods=['GET', 'POST'])
def api_robots():
    if request.method == 'POST':
        # In this simplified mode we just acknowledge the selection
        return jsonify({'status': 'ok'})
    return jsonify([{'name': 'LocalRobot', 'ip': 'serial'}])


@app.route('/api/robot_info')
def api_robot_info():
    info = {
        'type': 'basic_env',
        'sensors': servidor.env.variable_names,
        # Mostrar los actuadores con nombres en español para la interfaz
        'motors': ['Corredera', 'Ángulo', 'Válvula'],
        'pidEditable': True
    }
    return jsonify(info)


@app.route('/logs')
def api_logs():
    return jsonify({'logs': servidor.logs})

# --- Compatibilidad con la interfaz avanzada -----------------
@app.route('/status')
def status():
    """Devuelve un resumen del estado actual del entorno."""
    obs = servidor.env.get_observation()
    if obs is None:
        # Intentar generar una observación realizando un paso
        try:
            servidor.env.step()
            obs = servidor.env.get_observation()
        except Exception:
            obs = None
    if obs is None:
        obs = [0.0] * len(servidor.env.variable_names)
    obs_list = obs if isinstance(obs, list) else obs.tolist()
    obs_dict = dict(zip(servidor.env.variable_names, obs_list))

    data = {
        # Valores de sensores leídos directamente del Arduino
        'flow': obs_dict.get('flowVolume', 0),
        'setpoint': servidor.env.current_action[6],
        'servo': obs_dict.get('inputV', 0),
        'x': obs_dict.get('inputX', 0),
        'a': obs_dict.get('inputA', 0),
        # Estados de modo manual por actuador
        'manualMode': servidor.env.manual_mode,
        'manualCorredera': int(servidor.manual_corredera),
        'manualAngulo': int(servidor.manual_angulo),
        'manualValvula': int(servidor.manual_valvula),
        'pidOn': servidor.env.manual_mode == 0,
        'ffOn': False,
        'Kp': servidor.env.current_action[13],
        'Ki': servidor.env.current_action[14],
        'Kd': servidor.env.current_action[15],
        'KpC': servidor.env.current_action[7],
        'KiC': servidor.env.current_action[8],
        'KdC': servidor.env.current_action[9],
        'KpA': servidor.env.current_action[10],
        'KiA': servidor.env.current_action[11],
        'KdA': servidor.env.current_action[12],
        'volReq': servidor.env.current_action[6],
        'volDispTask': 0,
        'volDispAcumDay': 0,
        'autoExecEnabled': False,
    }
    return jsonify(data)


@app.route('/control', methods=['GET', 'POST'])
def control():
    """Actualiza actuadores o parámetros PID desde la interfaz."""
    params = request.form if request.method == 'POST' else request.args

    servo = params.get('servo')
    pin = params.get('pin')
    flow = params.get('flow')
    pid = params.get('pid')

    if servo is not None:
        try:
            val = float(servo)
            if pin == '1':
                servidor.env.set_angulo(val)
            elif pin == '2':
                servidor.env.set_corredera(val)
            else:
                servidor.env.set_valvula(val)
        except ValueError:
            pass

    if flow is not None:
        try:
            servidor.env.set_valvula(float(flow))
        except ValueError:
            pass

    if pid is not None:
        servidor.env.enable_pid() if pid == '1' else servidor.env.disable_pid()

    if request.method == 'POST':
        def _flt(name):
            try:
                return float(params.get(name))
            except (TypeError, ValueError):
                return None

        kp = _flt('kp'); ki = _flt('ki'); kd = _flt('kd')
        if kp is not None and ki is not None and kd is not None:
            servidor.env.set_pid_valvula(kp, ki, kd)

        kpa = _flt('kpa'); kia = _flt('kia'); kda = _flt('kda')
        if kpa is not None and kia is not None and kda is not None:
            servidor.env.set_pid_angulo(kpa, kia, kda)

        kpc = _flt('kpc'); kic = _flt('kic'); kdc = _flt('kdc')
        if kpc is not None and kic is not None and kdc is not None:
            servidor.env.set_pid_corredera(kpc, kic, kdc)

    servidor.env.step()
    return jsonify({'status': 'ok'})


@app.route('/current_ip')
def current_ip():
    return jsonify({'ip': request.host.split(':')[0]})


@app.route('/getFeedForward')
def get_feed_forward():
    return jsonify({'flow': [], 'angle': [], 'a0': 0, 'b0': 0})


@app.route('/ejecutar_tarea')
def ejecutar_tarea():
    return jsonify({'status': 'ok'})


@app.route('/api/calibrate_pid')
def api_calibrate_pid():
    return jsonify({'kp': 0, 'ki': 0, 'kd': 0})


@app.route('/api/calibrate_flow')
def api_calibrate_flow():
    return jsonify({'status': 'ok'})



if __name__ == '__main__':
    threading.Timer(1.0, lambda: webbrowser.open('http://localhost:5000/')).start()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
