import os
import time
import threading
import sqlite3
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np

# Ajusta si tu basic_gym_env está en otra ubicación:
from basic_gym_env.basic_env import BasicEnv

# Variables globales
protocols = {}            # Diccionario en memoria con la info de los protocolos
current_protocol_id = None
stop_thread = False
env = None

DATABASE = 'protocols.db'

# -----------------------------------------------------------------------------
# INICIALIZAR ENTORNO SOLO SI NO EXISTE
# -----------------------------------------------------------------------------
if 'env' not in globals() or env is None:
    env = BasicEnv(port='COM5', baudrate=115200)
    print("Entorno inicializado correctamente.")

# Inicia un lote de observación al arrancar el servidor
env.start_observing()

# -----------------------------------------------------------------------------
# FUNCIONES DE BASE DE DATOS
# -----------------------------------------------------------------------------

def init_db():
    """Crea la tabla de protocolos si no existe (sin columna de 'params')."""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS protocols (
            pid TEXT PRIMARY KEY,
            code TEXT,
            description TEXT
        )
    ''')
    conn.commit()
    conn.close()

def load_protocols_from_db():
    """
    Carga todos los protocolos desde la base de datos y los almacena en la variable global `protocols`.
    Ya no se maneja la parte de 'config'.
    """
    global protocols
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT pid, code, description FROM protocols')
    rows = cursor.fetchall()
    conn.close()

    for pid, code, description in rows:
        init_func, main_func, end_func = load_protocol_from_code(code)
        protocols[pid] = {
            "init": init_func,
            "main": main_func,
            "end": end_func,
            "description": description,
            "code": code
        }
    print(f"Protocolos cargados desde la base de datos: {list(protocols.keys())}")

def save_protocol_to_db(pid, code, description):
    """
    Guarda o actualiza un protocolo en la base de datos.
    Ya no se maneja la parte de 'config'.
    """
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('SELECT pid FROM protocols WHERE pid = ?', (pid,))
    exists = cursor.fetchone()

    if exists:
        # Actualizar
        cursor.execute(
            'UPDATE protocols SET code=?, description=? WHERE pid=?',
            (code, description, pid)
        )
    else:
        # Insertar
        cursor.execute(
            'INSERT INTO protocols (pid, code, description) VALUES (?,?,?)',
            (pid, code, description)
        )

    conn.commit()
    conn.close()

def load_protocol_from_code(code_str):
    """
    Ejecuta el string `code_str` en un entorno local para obtener tres funciones
    con la firma (env):
      - protocol_init(env)
      - protocol_main(env)
      - protocol_end(env)
    Retorna (init_func, main_func, end_func).
    """
    local_env = {}
    exec(code_str, globals(), local_env)

    init_func = local_env.get('protocol_init', lambda env: None)
    main_func = local_env.get('protocol_main', lambda env: env.current_action)
    end_func  = local_env.get('protocol_end',  lambda env: None)

    return init_func, main_func, end_func

# -----------------------------------------------------------------------------
# HILO PRINCIPAL DE EJECUCIÓN DEL PROTOCOLO
# -----------------------------------------------------------------------------
def run_protocol_loop():
    global current_protocol_id, stop_thread, env

    while not stop_thread:
        try:
            if env is None:
                time.sleep(1)
                continue

            # Obtener la observación
            obs = env.get_observation()
            env.store_serial_data(obs_data=obs)

            # Ejecutar la main de protocolo si hay uno activo
            if current_protocol_id in protocols:
                protocol_main = protocols[current_protocol_id]['main']
                action = protocol_main(env)
                env.step(action)
            else:
                time.sleep(0.5)

        except Exception as e:
            # Captura cualquier excepción
            print(f"Error en run_protocol_loop: {e}")
            # OPCIONAL: puedes desactivar el protocolo activo, loguear, etc.
            # current_protocol_id = None
            # time.sleep(2)  # Pausa para evitar bucles incesantes si el error persiste
            # Y luego continuar el while
            pass


# -----------------------------------------------------------------------------
# INICIALIZACIÓN DE BD Y PROTOCOLOS
# -----------------------------------------------------------------------------
init_db()
load_protocols_from_db()

# Iniciar el hilo del protocolo
protocol_thread = threading.Thread(target=run_protocol_loop, daemon=True)
protocol_thread.start()

# -----------------------------------------------------------------------------
# FLASK: CREACIÓN DE LA APLICACIÓN
# -----------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)

# -----------------------------------------------------------------------------
# RUTAS
# -----------------------------------------------------------------------------

@app.route('/stop', methods=['POST'])
def stop():
    """
    Detiene los motores y desactiva cualquier protocolo activo.
    Llama a 'protocol_end(env)' si hay un protocolo activo.
    """
    global current_protocol_id
    message = env.detener_motores()

    if current_protocol_id in protocols:
        end_func = protocols[current_protocol_id]['end']
        end_func(env)

    current_protocol_id = None
    return jsonify({"message": message})

@app.route('/update_actuators', methods=['POST'])
def update_actuators():
    """
    Actualiza los actuadores del robot enviando una acción directamente al entorno.
    Cada clave del JSON es opcional. Si no se proporciona, se mantiene el valor actual.
    Además, devuelve una observación completa del entorno junto con las acciones aplicadas.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No se recibió ningún JSON."}), 400

    # Mapeo de claves JSON a índices de la acción
    action_map = {
        "modoManual": 0,
        "EMA": 1,
        "EMX": 2,
        "EMV": 3,
        "X_Requerido": 4,
        "A_Requerido": 5,
        "Vol_requerido": 6,
        "kpX": 7,
        "kiX": 8,
        "kdX": 9,
        "kpA": 10,
        "kiA": 11,
        "kdA": 12,
        "resetVolumen": 13,
        "resetMotorXFlag": 14,
        "resetMotorAFlag": 15,
        "stepsPerMM": 16,
        "stepsPerDegree": 17,
        "unused1": 18,
        "unused2": 19
    }

    # Copiamos la acción actual para modificarla
    new_action = env.current_action.copy()

    # Procesamos los datos recibidos
    for key, index in action_map.items():
        if key in data:
            value = data[key]
            low = env.action_space.low[index]
            high = env.action_space.high[index]
            clipped_value = np.clip(value, low, high)

            # Algunos índices deben ser valores enteros
            if key in ["modoManual", "resetVolumen", "resetMotorXFlag", "resetMotorAFlag"]:
                clipped_value = int(clipped_value)

            new_action[index] = clipped_value

    # Ejecutar un paso del entorno
    obs, reward, done, info = env.step(new_action)

    # Convertir 'current_action' a floats de Python
    current_action = env.current_action.astype(float).tolist()

    # Convertir la observación a floats nativos
    obs_converted = obs.astype(float).tolist()
    observation_dict = dict(zip(env.variable_names, obs_converted))

    reward = float(reward)

    return jsonify({
        "message": "Acción actualizada con éxito.",
        "action": current_action,
        "observation": observation_dict,
        "reward": reward,
        "done": done,
        "info": info
    })


@app.route('/list_protocols', methods=['GET'])
def list_protocols():
    """
    Devuelve la lista de protocolos disponibles (sin mostrar el código).
    Se muestra 'id' y 'description'. (Ya no se maneja la parte de 'config'.)
    """
    proto_list = []
    for pid, proto in protocols.items():
        proto_list.append({
            "id": pid,
            "description": proto.get("description", "")
        })
    return jsonify(proto_list)

@app.route('/create_protocol', methods=['POST'])
def create_protocol():
    """
    Crea un nuevo protocolo desde código.
    - id (str) y code (str) son obligatorios.
    - description (str) es opcional.
    """
    print("[DEBUG] Entrando a create_protocol...")

    data = request.json or {}
    print(f"[DEBUG] request.json: {data}")

    pid         = data.get('id')
    code        = data.get('code')
    description = data.get('description', "")

    print(f"[DEBUG] Extraído pid='{pid}', code length={len(code) if code else '0'}, "
          f"description='{description}'")

    # Validaciones mínimas
    if not pid or not code:
        print("[DEBUG] Faltan 'id' o 'code'.")
        return jsonify({"error": "Se requiere 'id' y 'code' para crear un protocolo."}), 400

    # Evitar duplicados
    if pid in protocols:
        print(f"[DEBUG] El protocolo con id='{pid}' ya existe en memoria.")
        return jsonify({"error": f"Ya existe un protocolo con id '{pid}'."}), 400

    try:
        print("[DEBUG] Cargando funciones init, main, end del código recibido.")
        init_func, main_func, end_func = load_protocol_from_code(code)
        print("[DEBUG] Carga de funciones completada sin errores.")

        # Guardar en memoria
        protocols[pid] = {
            "init": init_func,
            "main": main_func,
            "end": end_func,
            "description": description,
            "code": code
        }
        print(f"[DEBUG] Protocol '{pid}' creado en la variable 'protocols'.")

        # Guardar en BD
        print("[DEBUG] Guardando en la base de datos...")
        save_protocol_to_db(pid, code, description)
        print("[DEBUG] Protocolo guardado en BD exitosamente.")

        return jsonify({"message": f"Protocolo '{pid}' creado con éxito."})
    except Exception as e:
        print(f"[DEBUG] Excepción al crear protocolo: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/activate_protocol', methods=['POST'])
def activate_protocol():
    """
    Activa un protocolo existente: llama a su protocol_init(env),
    espera 10 segundos, y devuelve las observaciones de ese periodo.
    """
    global current_protocol_id

    data = request.json or {}
    pid = data.get('id')

    if not pid:
        return jsonify({"error": "Se requiere 'id' para activar un protocolo."}), 400

    if pid not in protocols:
        return jsonify({"error": f"No existe protocolo con id '{pid}'"}), 404

    # Si hay un protocolo activo, llamar su 'end'
    if current_protocol_id in protocols:
        old_end = protocols[current_protocol_id]['end']
        old_end(env)

    current_protocol_id = pid

    # Llamar init del nuevo
    new_init = protocols[pid]['init']
    new_init(env)

    # Espera 10 segundos (bloquea la ejecución)
    time.sleep(10)

    # Usar env.get_latest_observations para obtener las observaciones recientes
    tiempo = 10.0  # Últimos 10 segundos
    intervalo = 1.0  # Intervalo de 1 segundo
    data = env.get_latest_observations(tiempo=tiempo, intervalo=intervalo)

    if not data:
        return jsonify({"error": "No se encontraron observaciones recientes."}), 400

    return jsonify({
        "message": f"Protocolo '{pid}' activado.",
        "observaciones": data
    })


@app.route('/view_protocol/<pid>', methods=['GET'])
def view_protocol(pid):
    """
    Devuelve la información completa de un protocolo específico:
      - id
      - code
      - description
    (Ya no se maneja la parte de 'config'.)
    """
    if pid not in protocols:
        return jsonify({"error": f"No existe protocolo con id '{pid}'"}), 404

    proto = protocols[pid]
    return jsonify({
        "id": pid,
        "code": proto.get("code", ""),
        "description": proto.get("description", "")
    })

@app.route('/delete_protocol/<pid>', methods=['DELETE'])
def delete_protocol(pid):
    """
    Elimina un protocolo tanto de la base de datos como de 'protocols'.
    Si el protocolo está activo, se desactiva antes.
    """
    global current_protocol_id

    if pid not in protocols:
        return jsonify({"error": f"No existe protocolo con id '{pid}'"}), 404

    # Si está activo, terminar
    if current_protocol_id == pid:
        end_func = protocols[pid]['end']
        end_func(env)
        current_protocol_id = None

    # Eliminar de la base de datos
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM protocols WHERE pid=?', (pid,))
    conn.commit()
    conn.close()

    del protocols[pid]
    return jsonify({"message": f"Protocolo '{pid}' eliminado con éxito."})



@app.route('/latest_observations', methods=['GET'])
def latest_observations():
    """
    Devuelve las últimas observaciones registradas.
    Parámetros (query):
      - tiempo (float): segundos de observaciones recientes
      - intervalo (float): intervalo en segundos
    """
    tiempo = float(request.args.get('tiempo', 10.0))
    intervalo = float(request.args.get('intervalo', 1.0))

    data = env.get_latest_observations(tiempo=tiempo, intervalo=intervalo)
    if not data:
        return jsonify({"error": "No se encontraron observaciones recientes."}), 400

    return jsonify(data)

# -----------------------------------------------------------------------------
# RUTA ADICIONAL: Actualizar el código de un protocolo y reactivarlo
# -----------------------------------------------------------------------------
@app.route('/update_protocol_code', methods=['POST'])
def update_protocol_code():
    """
    Actualiza el código de un protocolo y lo reactiva si está activo.
    Espera 10 segundos después de la reactivación y devuelve las observaciones recientes.
    """
    global current_protocol_id

    data = request.json or {}
    pid = data.get('id')
    new_code = data.get('code')

    if not pid or not new_code:
        return jsonify({"error": "Se requiere 'id' y 'code' para actualizar un protocolo."}), 400

    if pid not in protocols:
        return jsonify({"error": f"No existe protocolo con id '{pid}'"}), 404

    try:
        # Ver si está activo
        was_active = (current_protocol_id == pid)

        # Si estaba activo, llamamos su end
        if was_active:
            old_end = protocols[pid]['end']
            old_end(env)

        # Cargar nuevas funciones
        init_func, main_func, end_func = load_protocol_from_code(new_code)

        # Actualizar en memoria
        protocols[pid]['init'] = init_func
        protocols[pid]['main'] = main_func
        protocols[pid]['end'] = end_func
        protocols[pid]['code'] = new_code

        # Mantener description
        current_description = protocols[pid].get('description', "")

        # Guardar en BD
        save_protocol_to_db(pid, new_code, current_description)

        # Si estaba activo, reactivarlo con las nuevas funciones
        if was_active:
            current_protocol_id = pid
            init_func(env)

        # Esperar 10 segundos
        time.sleep(10)

        # Obtener las observaciones recientes
        tiempo = 10.0  # Últimos 10 segundos
        intervalo = 1.0  # Intervalo de 1 segundo
        data = env.get_latest_observations(tiempo=tiempo, intervalo=intervalo)

        if not data:
            return jsonify({"error": "No se encontraron observaciones recientes."}), 400

        return jsonify({
            "message": f"Código del protocolo '{pid}' actualizado correctamente.",
            "observaciones": data
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400



# -----------------------------------------------------------------------------
# EJECUCIÓN DEL SERVIDOR
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    try:
        # Comienza Flask
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        stop_thread = True
        if protocol_thread.is_alive():
            protocol_thread.join()
        if env:
            env.close()
