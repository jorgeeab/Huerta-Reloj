import os
import time
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from basic_gym_env.basic_env import BasicEnv  # Importa la clase BasicEnv
import numpy as np
# Variables globales
protocols = {}
current_protocol_id = None
stop_thread = False
env = None

# Inicializar el entorno (solo si no existe ya)
if 'env' not in globals() or env is None:
    env = BasicEnv(port='COM13', baudrate=115200)
    print("Entorno inicializado correctamente.")

# Inicia un lote de observación al arrancar el servidor
env.start_observing()

# Hilo de ejecución de protocolos y almacenamiento de observaciones
def run_protocol_loop():
    global current_protocol_id, stop_thread, env
    while not stop_thread:
        if env is None:
            time.sleep(1)  # Esperar y verificar nuevamente
            continue

        obs = env.get_observation()  # Obtener observaciones del entorno

        # Imprimir las observaciones para verificar los datos recibidos
        if obs is not None:
            print("Observaciones recibidas:", obs)
        else:
            print("No se recibieron observaciones.")

        # Grabar observaciones incluso si no hay protocolo activo
        env.store_serial_data(obs_data=obs)

        # Ejecutar lógica del protocolo si hay uno activo
        if current_protocol_id in protocols:
            protocol_func = protocols[current_protocol_id]['func']
            protocol_params = protocols[current_protocol_id]['params']

            action = protocol_func(obs, protocol_params)

            env.step(action)
           # time.sleep(0.3)  # Reducir consumo de recursos si no hay protocolo activo

        else:
            time.sleep(0.5)  # Reducir consumo de recursos si no hay protocolo activo


# Iniciar el hilo del protocolo
protocol_thread = threading.Thread(target=run_protocol_loop, daemon=True)
protocol_thread.start()

# Configuración de Flask
app = Flask(__name__)
CORS(app)

# Funciones auxiliares para cargar protocolos
def load_protocol_from_code(code_str, func_name='protocol_main'):
    local_env = {}
    # Utilizar el contexto global, donde se encuentra 'env'
    exec(code_str, globals(), local_env)
    return local_env[func_name]


# Rutas del servidor
@app.route('/stop', methods=['POST'])
def stop():
    """Detiene los motores y desactiva cualquier protocolo activo."""
    global current_protocol_id
    message = env.detener_motores()
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

    # Mapa de claves a índices en current_action
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

    # Por cada clave en el data, si existe en action_map, actualizar el valor
    for key, index in action_map.items():
        if key in data:
            value = data[key]

            # Limitamos el valor a los límites del espacio de acción
            low = env.action_space.low[index]
            high = env.action_space.high[index]
            clipped_value = np.clip(value, low, high)

            # Algunas variables se interpretan como enteros (ej. modoManual, banderas de reset)
            if key in ["modoManual", "resetVolumen", "resetMotorXFlag", "resetMotorAFlag"]:
                clipped_value = int(clipped_value)

            new_action[index] = clipped_value

    # Ejecutar la acción actualizada en el entorno
    obs, reward, done, info = env.step(new_action)

    # current_action se actualiza dentro de step, asegurar que esté sincronizada
    current_action = env.current_action.tolist()
    observation_names = env.variable_names
    observation_dict = dict(zip(observation_names, obs[:len(observation_names)]))

    return jsonify({
        "message": "Acción actualizada con éxito.",
        "action": current_action,
        "observation": observation_dict,
        "reward": reward,
        "done": done,
        "info": info
    })


@app.route('/update_reward_requirements', methods=['POST'])
def update_reward_requirements():
    """Actualiza los requerimientos del entorno."""
    data = request.json
    message = env.update_requirements(**data)
    return jsonify({"message": message})

@app.route('/list_protocols', methods=['GET'])
def list_protocols():
    """Devuelve la lista de protocolos disponibles."""
    proto_list = [
        {
            "id": pid,
            "params": pdata['params'],
            "description": pdata.get('description', "")
        }
        for pid, pdata in protocols.items()
    ]
    return jsonify(proto_list)

@app.route('/create_protocol', methods=['POST'])
def create_protocol():
    """Crea un nuevo protocolo a partir de código."""
    data = request.json
    pid = data['id']
    code = data['code']
    params = data.get('params', {})
    description = data.get('description', "")
    try:
        func = load_protocol_from_code(code)
        protocols[pid] = {
            "func": func,
            "params": params,
            "description": description
        }
        return jsonify({"message": f"Protocolo '{pid}' creado con éxito."})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/activate_protocol', methods=['POST'])
def activate_protocol():
    """Activa un protocolo existente."""
    data = request.json
    pid = data['id']
    if pid not in protocols:
        return jsonify({"error": f"No existe protocolo con id {pid}"}), 404
    global current_protocol_id
    current_protocol_id = pid
    return jsonify({"message": f"Protocolo '{pid}' activado."})

@app.route('/observations', methods=['GET'])
def get_observations_info():
    """Devuelve los nombres de las variables de observación del entorno."""
    obs_names = env.variable_names
    return jsonify({"observations": obs_names})

@app.route('/actions', methods=['GET'])
def get_actions_info():
    """Devuelve los límites y nombres de las acciones disponibles en el entorno."""
    action_info = {
        "names": [
            "modoManual", "EMA", "EMX", "EMV",
            "X_Requerido", "A_Requerido", "Vol_requerido",
            "kpX", "kiX", "kdX", "kpA", "kiA", "kdA",
            "resetVolumen", "resetMotorXFlag", "resetMotorAFlag",
            "stepsPerMM", "stepsPerDegree", "unused1", "unused2"
        ],
        "low": env.action_space.low.tolist(),
        "high": env.action_space.high.tolist()
    }
    return jsonify(action_info)

@app.route('/update_protocol_code', methods=['POST'])
def update_protocol_code():
    """Actualiza el código de un protocolo existente."""
    data = request.json
    pid = data['id']
    code = data['code']
    if pid not in protocols:
        return jsonify({"error": f"No existe protocolo con id {pid}"}), 404
    try:
        func = load_protocol_from_code(code)
        protocols[pid]['func'] = func
        return jsonify({"message": f"Código del protocolo '{pid}' actualizado correctamente."})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/update_protocol_params', methods=['POST'])
def update_protocol_params():
    """Actualiza los parámetros de un protocolo existente."""
    data = request.json
    pid = data['id']
    new_params = data.get('params', {})
    if pid not in protocols:
        return jsonify({"error": f"No existe protocolo con id {pid}"}), 404
    protocols[pid]['params'] = new_params
    return jsonify({"message": f"Parámetros del protocolo '{pid}' actualizados correctamente."})

@app.route('/start_observing', methods=['POST'])
def start_observing():
    """Inicia la observación de datos en el entorno."""
    data = request.json if request.json else {}
    batch_id = data.get('batch_id', None)
    message = env.start_observing(batch_id)
    return jsonify({"message": message})

@app.route('/stop_observing', methods=['POST'])
def stop_observing():
    """Detiene la observación y devuelve los datos capturados."""
    data = env.stop_observing()
    return jsonify(data)

@app.route('/latest_observations', methods=['GET'])
def latest_observations():
    """Devuelve las últimas observaciones registradas."""
    tiempo = float(request.args.get('tiempo', 10.0))
    intervalo = float(request.args.get('intervalo', 1.0))

    # Obtener las observaciones recientes
    data = env.get_latest_observations(tiempo=tiempo, intervalo=intervalo)

    if not data:
        return jsonify({"error": "No se encontraron observaciones recientes."}), 400

    return jsonify(data)

# Finalización segura del servidor y del hilo
if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        stop_thread = True  # Detener el hilo
        if protocol_thread.is_alive():
            protocol_thread.join()
        if env:
            env.close()  # Cerrar el entorno correctamente
