from flask import Flask, request, jsonify
from basic_gym_env.basic_env import BasicEnv
from basic_gym_env.interfaz import Interfaz
import threading
import time
import os

# Crear una instancia de la aplicación Flask
app = Flask(__name__)

# Bloqueo para manejar el acceso concurrente al entorno
env_lock = threading.Lock()

# Variables para manejar la interfaz y su estado
interface_app = None  # Instancia de la interfaz gráfica
interface_thread = None  # Hilo en el que se ejecuta la interfaz
interface_running = threading.Event()  # Evento para indicar si la interfaz está corriendo

# Variable global para el entorno, inicialmente None
env = None


# Verificar si la interfaz está abierta antes de procesar otras solicitudes
def interface_check():
    if interface_running.is_set():
        return jsonify({'error': 'La interfaz está abierta, cierre la interfaz antes de continuar'}), 400
    return None


# Validar los detalles de la planta
def validar_planta_details(planta_details):
    required_fields = ['Nombre de la Planta', 'Regimen', 'Dia Uno', 'Posición X', 'Posición Y', 'Posición Z',
                       'Velocidad de Agua']
    for field in required_fields:
        if planta_details.get(field) is None:
            return False
    return True


# Validar los detalles de una tarea del régimen
def validar_tarea_details(tarea_details):
    required_fields = ['Tarea', 'Numero_Día', 'Hora', 'Tiempo de Ejecución (s)', 'Magnitud', 'Unidades']
    for field in required_fields:
        if tarea_details.get(field) is None:
            return False
    return True


# Endpoint para agregar una planta
@app.route('/agregar_planta', methods=['POST'])
def agregar_planta():
    """
    Agrega una nueva planta al entorno.
    Espera recibir un JSON con los detalles de la planta y la era.
    """
    data = request.get_json()
    planta_details = data.get('planta_details')
    era = data.get('era')

    if planta_details is not None and era is not None and validar_planta_details(planta_details):
        with env_lock:
            env.agregar_planta(planta_details, era)
        return jsonify({'status': 'Planta agregada con éxito'}), 200
    else:
        return jsonify({'error': 'Faltan los detalles de la planta o la era'}), 400


# Endpoint para modificar una planta
@app.route('/modificar_planta', methods=['POST'])
def modificar_planta():
    """
    Modifica los detalles de una planta en el entorno.
    Espera recibir un JSON con la era, el índice de la planta y los valores actualizados.
    """
    data = request.get_json()
    era = data.get('era')
    fila = data.get('fila')  # Índice de la planta a modificar
    updated_values = data.get('updated_values')

    if era is not None and fila is not None and updated_values is not None and validar_planta_details(updated_values):
        with env_lock:
            env.modificar_planta(era, fila, updated_values)
        return jsonify({'status': 'Planta modificada con éxito'}), 200
    else:
        return jsonify({'error': 'Faltan datos para modificar la planta o los valores no son válidos'}), 400


# Endpoint para eliminar una planta
@app.route('/eliminar_planta', methods=['POST'])
def eliminar_planta():
    """
    Elimina una planta del entorno.
    Espera recibir un JSON con la era y el índice de la planta a eliminar.
    """
    data = request.get_json()
    era = data.get('era')
    fila = data.get('fila')  # Índice de la planta a eliminar

    if era is not None and fila is not None:
        with env_lock:
            env.eliminar_planta(era, fila)
        return jsonify({'status': 'Planta eliminada con éxito'}), 200
    else:
        return jsonify({'error': 'Faltan datos para eliminar la planta'}), 400


# Endpoint para agregar un régimen
@app.route('/agregar_regimen', methods=['POST'])
def agregar_regimen():
    """
    Agrega un nuevo régimen al entorno.
    Espera recibir un JSON con el nombre del régimen y las tareas.
    """
    data = request.get_json()
    regimen_name = data.get('regimen_name')
    tareas = data.get('tareas')

    if regimen_name and tareas:
        for tarea in tareas:
            if not validar_tarea_details(tarea):
                return jsonify({'error': 'Los detalles de la tarea del régimen no son válidos'}), 400

        with env_lock:
            env.agregar_regimen(regimen_name, tareas)
        return jsonify({'status': 'Régimen agregado con éxito'}), 200
    else:
        return jsonify({'error': 'Faltan los detalles del régimen o el nombre del régimen'}), 400


# Endpoint para modificar una tarea en un régimen
@app.route('/modificar_tarea', methods=['POST'])
def modificar_tarea():
    """
    Modifica una tarea en un régimen.
    Espera recibir un JSON con el régimen, el índice de la tarea y los valores actualizados.
    """
    data = request.get_json()
    regimen = data.get('regimen')
    fila = data.get('fila')  # Índice de la tarea
    updated_values = data.get('updated_values')

    if regimen is not None and fila is not None and updated_values is not None and validar_tarea_details(
            updated_values):
        with env_lock:
            env.modificar_tarea(regimen, fila, updated_values)
        return jsonify({'status': 'Tarea modificada con éxito'}), 200
    else:
        return jsonify({'error': 'Faltan datos para modificar la tarea o los valores no son válidos'}), 400


# Endpoint para listar plantas de una era específica
@app.route('/listar_plantas', methods=['GET'])
def listar_plantas_de_era():
    """
    Lista todas las plantas de una era específica.
    Espera recibir el nombre de la era como parámetro de consulta.
    """
    era = request.args.get('era')

    if era is not None:
        with env_lock:
            plantas = env.plantas_manager.listar_plantas_de_era(era)
        return jsonify({'status': 'Success', 'plantas': plantas}), 200
    else:
        return jsonify({'error': 'Falta el nombre de la era'}), 400


# Endpoint para obtener el régimen de una planta específica en una era
@app.route('/obtener_regimen', methods=['GET'])
def obtener_regimen_de_planta():
    """
    Obtiene el régimen de una planta en una era específica.
    Espera recibir el nombre de la planta y la era como parámetros de consulta.
    """
    era = request.args.get('era')
    nombre_planta = request.args.get('nombre_planta')

    if era is not None and nombre_planta is not None:
        with env_lock:
            regimen = env.plantas_manager.obtener_regimen_de_planta(era, nombre_planta)
        if regimen:
            return jsonify({'status': 'Success', 'regimen': regimen}), 200
        else:
            return jsonify({'error': 'No se encontró el régimen para la planta'}), 404
    else:
        return jsonify({'error': 'Faltan parámetros'}), 400


# Endpoint para eliminar una tarea en un régimen
@app.route('/eliminar_tarea', methods=['POST'])
def eliminar_tarea():
    """
    Elimina una tarea de un régimen.
    Espera recibir un JSON con el régimen y el índice de la tarea.
    """
    data = request.get_json()
    regimen = data.get('regimen')
    fila = data.get('fila')  # Índice de la tarea

    if regimen is not None and fila is not None:
        with env_lock:
            env.eliminar_tarea(regimen, fila)
        return jsonify({'status': 'Tarea eliminada con éxito'}), 200
    else:
        return jsonify({'error': 'Faltan datos para eliminar la tarea'}), 400


# Endpoint para abrir la interfaz gráfica
@app.route('/open_interface', methods=['POST'])
def open_interface():
    """
    Abre la interfaz gráfica en un hilo separado.
    """
    global interface_app, interface_thread

    if interface_thread and interface_thread.is_alive():
        return jsonify({'status': 'Interface is already running'}), 400

    def run_interface():
        global interface_app
        # Establecer el evento para indicar que la interfaz está corriendo
        interface_running.set()
        # Inicializar la interfaz gráfica con la instancia del entorno
        interface_app = Interfaz(
            'archivo_plantas.xlsx',
            'archivo_regimenes.xlsx',
            'archivo_ensayos.xlsx',
            env=env
        )
        # Ejecutar el bucle principal de Tkinter
        interface_app.mainloop()
        # Al salir del mainloop, limpiar la instancia y el evento
        interface_app = None
        interface_running.clear()

    # Crear y iniciar el hilo de la interfaz
    interface_thread = threading.Thread(target=run_interface)
    interface_thread.daemon = True  # Permite que el hilo se cierre al finalizar el programa principal
    interface_thread.start()

    # Esperar un momento para confirmar que la interfaz inició
    time.sleep(1)
    if interface_running.is_set():
        return jsonify({'status': 'Interface opened successfully'})
    else:
        return jsonify({'error': 'Failed to open interface'}), 500
@app.route('/set_manual_mode', methods=['POST'])
def set_manual_mode():
    """
    Cambia el modo del entorno entre automático (0) y manual (1).
    Espera recibir un JSON con el valor de 'manual_mode'.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    data = request.get_json()
    manual_mode = data.get('manual_mode')
    if manual_mode is not None:
        with env_lock:
            env.set_manual_mode(int(manual_mode))
        return jsonify({'status': 'Manual mode updated'})  # Asegúrate de devolver una respuesta
    else:
        return jsonify({'error': 'Missing manual_mode parameter'}), 400

# Endpoint para cerrar la interfaz gráfica
@app.route('/close_interface', methods=['POST'])
def close_interface():
    """
    Cierra la interfaz gráfica si está abierta.
    """
    global interface_app, interface_thread

    if interface_app is None:
        return jsonify({'status': 'Interface is not running'}), 400

    def stop_interface():
        # Llamar al método destroy de Tkinter para cerrar la interfaz
        interface_app.destroy()

    # Ejecutar la función stop_interface en el hilo de la interfaz
    interface_app.after(0, stop_interface)

    # Esperar a que el hilo de la interfaz termine
    interface_thread.join(timeout=5)

    if not interface_thread.is_alive():
        return jsonify({'status': 'Interface closed successfully'})
    else:
        return jsonify({'error': 'Failed to close interface'}), 500

# Endpoint para reiniciar el entorno
@app.route('/reset', methods=['POST'])
def reset_env():
    """
    Reinicia el entorno a su estado inicial.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    with env_lock:
        env.reset()
    return jsonify({'status': 'Environment reset successful'})



# Endpoint para establecer el setpoint de la corredera
@app.route('/set_corredera', methods=['POST'])
def set_corredera():
    """
    Establece el setpoint (posición objetivo) de la corredera.
    Espera recibir un JSON con el valor de 'setpoint'.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    data = request.get_json()
    setpoint = data.get('setpoint')
    if setpoint is not None:
        with env_lock:
            env.set_corredera(setpoint)
        return jsonify({'status': 'Setpoint corredera updated'})
    else:
        return jsonify({'error': 'Missing setpoint parameter'}), 400


# Endpoint para establecer el setpoint de la corredera
@app.route('/set_angulo', methods=['POST'])
def set_angulo():
    """
    Establece el setpoint (posición objetivo) de la corredera.
    Espera recibir un JSON con el valor de 'setpoint'.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    data = request.get_json()
    setpoint = data.get('setpoint')
    if setpoint is not None:
        with env_lock:
            env.set_angulo(setpoint)
        return jsonify({'status': 'Setpoint corredera updated'})
    else:
        return jsonify({'error': 'Missing setpoint parameter'}), 400
@app.route('/set_valvula', methods=['POST'])
def set_valvula():
    """
    Establece el setpoint (posición objetivo) de la corredera.
    Espera recibir un JSON con el valor de 'setpoint'.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    data = request.get_json()
    setpoint = data.get('setpoint')
    if setpoint is not None:
        with env_lock:
            env.set_valvula(setpoint)
        return jsonify({'status': 'Setpoint corredera updated'})
    else:
        return jsonify({'error': 'Missing setpoint parameter'}), 400
# Endpoint para ejecutar una serie de pasos durante un tiempo específico
@app.route('/execute_steps', methods=['POST'])
def execute_steps():
    """
    Ejecuta una serie de pasos en el entorno durante un tiempo especificado.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    data = request.get_json()
    execution_time = data.get('execution_time')
    if execution_time is not None:
        execution_data = []

        def run_execution():
            start_time = time.time()
            with env_lock:
                env.execution_data = []  # Reiniciar datos de ejecución
            while time.time() - start_time < execution_time:
                with env_lock:
                    # Ejecutar un paso en el entorno
                    obs, reward, done, info = env.step()
                    # Almacenar los datos de la ejecución
                    execution_data.append({
                        'observation': obs.tolist(),
                        'reward': reward
                    })

        # Ejecutar la función de ejecución en un hilo separado
        execution_thread = threading.Thread(target=run_execution)
        execution_thread.start()
        execution_thread.join()  # Esperar a que la ejecución termine

        return jsonify({
            'status': 'Execution completed',
            'data': execution_data
        })
    else:
        return jsonify({'error': 'Missing execution_time parameter'}), 400
@app.route('/close', methods=['POST'])
def close_env():
    """
    Cierra el entorno y libera los recursos.
    """
    with env_lock:
        if env is not None:
            env.close()
            return jsonify({'status': 'Environment closed'}), 200
        else:
            return jsonify({'error': 'Environment is already closed'}), 400
@app.route('/get_last_steps', methods=['GET'])
def get_last_steps():
    """
    Devuelve los últimos N pasos ejecutados.
    Espera recibir un parámetro 'n' para determinar cuántos pasos devolver.
    Si no se proporciona 'n', devolverá todos los pasos.
    """
    try:
        # Obtener el parámetro 'n' de la consulta, si no está presente devolverá todos los pasos
        n = int(request.args.get('n', len(env.execution_data)))

        # Asegurar que no se pida más pasos de los que existen
        n = min(n, len(env.execution_data))

        # Obtener los últimos 'n' pasos
        last_steps = env.execution_data[-n:]

        # Formatear los pasos para devolverlos como JSON
        formatted_steps = [{'observation': step[:-1].tolist(), 'reward': step[-1]} for step in last_steps]

        return jsonify({
            'status': 'Success',
            'steps': formatted_steps
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Endpoint para establecer los parámetros PID de la corredera
@app.route('/set_pid_corredera', methods=['POST'])
def set_pid_corredera():
    """
    Establece los parámetros PID (Kp, Ki, Kd) para la corredera.
    Espera recibir un JSON con los valores de 'kp', 'ki' y 'kd'.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    data = request.get_json()
    kp = data.get('kp')
    ki = data.get('ki')
    kd = data.get('kd')
    if kp is not None and ki is not None and kd is not None:
        with env_lock:
            env.set_pid_corredera(kp, ki, kd)
        return jsonify({'status': 'PID corredera updated'})
    else:
        return jsonify({'error': 'Missing kp, ki, or kd parameters'}), 400
# Endpoint para configurar los PID del ángulo
@app.route('/set_pid_angulo', methods=['POST'])

def set_pid_angulo():
    """
    Establece los parámetros PID para el ángulo.
    """
    data = request.get_json()
    kp = data.get('kp')
    ki = data.get('ki')
    kd = data.get('kd')
    if kp is not None and ki is not None and kd is not None:
        with env_lock:
            env.set_pid_angulo(kp, ki, kd)
        return jsonify({'status': 'PID ángulo updated'})
    else:
        return jsonify({'error': 'Missing kp, ki, or kd parameters'}), 400

# Endpoint para configurar los PID de la válvula
@app.route('/set_pid_valvula', methods=['POST'])
def set_pid_valvula():
    """
    Establece los parámetros PID para la válvula.
    """
    data = request.get_json()
    kp = data.get('kp')
    ki = data.get('ki')
    kd = data.get('kd')
    if kp is not None and ki is not None and kd is not None:
        with env_lock:
            env.set_pid_valvula(kp, ki, kd)
        return jsonify({'status': 'PID válvula updated'})
    else:
        return jsonify({'error': 'Missing kp, ki, or kd parameters'}), 400

# Endpoint para establecer la energía del motor de la corredera
@app.route('/set_energy_corredera', methods=['POST'])
def set_energy_corredera():
    """
    Establece la energía del motor de la corredera en modo manual.
    """
    data = request.get_json()
    energy = data.get('energy')
    if energy is not None:
        with env_lock:
            env.set_energy_corredera(energy)
        return jsonify({'status': 'Energy corredera updated'})
    else:
        return jsonify({'error': 'Missing energy parameter'}), 400

# Endpoint para establecer la energía del motor del ángulo
@app.route('/set_energy_angulo', methods=['POST'])
def set_energy_angulo():
    """
    Establece la energía del motor del ángulo en modo manual.
    """
    data = request.get_json()
    energy = data.get('energy')
    if energy is not None:
        with env_lock:
            env.set_energy_angulo(energy)
        return jsonify({'status': 'Energy ángulo updated'})
    else:
        return jsonify({'error': 'Missing energy parameter'}), 400

# Endpoint para establecer la energía del motor de la válvula
@app.route('/set_energy_valvula', methods=['POST'])
def set_energy_valvula():
    """
    Establece la energía del motor de la válvula en modo manual.
    """
    data = request.get_json()
    energy = data.get('energy')
    if energy is not None:
        with env_lock:
            env.set_energy_valvula(energy)
        return jsonify({'status': 'Energy válvula updated'})
    else:
        return jsonify({'error': 'Missing energy parameter'}), 400

# Endpoint para obtener la observación actual del entorno
@app.route('/get_observation', methods=['GET'])
def get_observation():
    """
    Devuelve la observación actual del entorno.
    """
    error_response = interface_check()
    if error_response:
        return error_response

    with env_lock:
        obs = env.get_observation()
    if obs is not None:
        return jsonify({'observation': obs.tolist()})
    else:
        return jsonify({'error': 'No observation available'}), 400

# Punto de entrada principal
if __name__ == '__main__':
    try:
        # Verificar si este es el proceso principal de ejecución o el proceso de recarga
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
            # Este es el proceso secundario que maneja las solicitudes
            # Inicializar el entorno aquí
            env = BasicEnv(port='COM5', baudrate=115200)
        else:
            # Este es el proceso de recarga, no inicializar el entorno
            env = None

        # Iniciar el servidor Flask en modo de depuración en el puerto 5000
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        # Si se interrumpe la ejecución (Ctrl+C), cerrar el entorno correctamente
        if env is not None:
            with env_lock:
                env.close()
        print("Server stopped and environment closed.")
