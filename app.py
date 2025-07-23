from flask import Flask, render_template, request, jsonify, redirect, url_for
from serial.tools import list_ports
import threading
import time
from basic_gym_env.basic_env import BasicEnv  # Asegúrate de que basic_env.py está en el mismo directorio

app = Flask(__name__)

# Instancia global del entorno
env = BasicEnv("COM8")


def get_available_ports():
    """Return a list of available serial port device names."""
    return [port.device for port in list_ports.comports()]

# Bloqueo para operaciones seguras en hilos múltiples
env_lock = threading.Lock()
def background_task():
    while True:
        with env_lock:
            env.step()
        time.sleep(0.1)  # Ajusta el intervalo según tus necesidades

# Iniciar el hilo de fondo
threading.Thread(target=background_task, daemon=True).start()
@app.route('/', methods=['GET', 'POST'])
def robot_control():
    if request.method == 'POST':
        # Procesar los datos del formulario
        data = request.form

        # Modo manual
        manual_mode = data.get('manual_mode') == 'on'
        with env_lock:
            env.set_manual_mode(int(manual_mode))

        # Joypad
        joypad_enabled = data.get('joypad_enabled') == 'on'
        if joypad_enabled:
            env.enable_joypad()
        else:
            env.disable_joypad()

        # Setpoints y energías
        with env_lock:
            if not manual_mode:
                # Setpoints
                setpoint_corredera = data.get('setpoint_corredera', '0')
                setpoint_angulo = data.get('setpoint_angulo', '0')
                setpoint_water = data.get('setpoint_water', '0')

                env.set_corredera(float(setpoint_corredera))
                env.set_angulo(float(setpoint_angulo))
                env.set_valvula(float(setpoint_water))
            else:
                # Energías
                energia_corredera = data.get('energia_corredera', '0')
                energia_angulo = data.get('energia_angulo', '0')
                energia_valvula = data.get('energia_valvula', '0')

                env.set_energy_corredera(float(energia_corredera))
                env.set_energy_angulo(float(energia_angulo))
                env.set_energy_valvula(float(energia_valvula))

            # PID
            pid_params = {}
            for pid in ['corredera', 'angulo', 'valvula']:
                kp = data.get(f'kp_{pid}', '0')
                ki = data.get(f'ki_{pid}', '0')
                kd = data.get(f'kd_{pid}', '0')
                pid_params[pid] = (float(kp), float(ki), float(kd))

            env.set_pid_corredera(*pid_params['corredera'])
            env.set_pid_angulo(*pid_params['angulo'])
            # Asumiendo que tienes un método para el PID de la válvula
            # env.set_pid_valvula(*pid_params['valvula'])

    # Obtener el estado actual
    with env_lock:
        observation = env.get_observation()
        if observation is not None:
            obs_list = observation.tolist()
            obs_dict = dict(zip(env.variable_names, obs_list))
        else:
            obs_dict = {}
        serial_connected = env.ser is not None and env.ser.is_open

    available_ports = get_available_ports()

    return render_template('robot_control.html',
                           obs=obs_dict,
                           current_port=env.port,
                           serial_connected=serial_connected,
                           available_ports=available_ports)
@app.route('/get_observation')
def get_observation():
    with env_lock:
        observation = env.get_observation()
        if observation is not None:
            obs_list = observation.tolist()
            obs_dict = dict(zip(env.variable_names, obs_list))
            return jsonify(obs_dict)
        else:
            return jsonify({'error': 'No hay observación disponible'}), 500


@app.route('/available_ports')
def available_ports():
    """Return the list of serial ports as JSON."""
    ports = get_available_ports()
    return jsonify({'ports': ports})
@app.route('/simulate_key', methods=['POST'])
def simulate_key():
    key = request.json.get('key')
    # Aquí puedes manejar las acciones asociadas a cada tecla
    if key:
        with env_lock:
            # Lógica para manejar la tecla presionada
            env.handle_key_press(key)
        return jsonify({'status': 'Key processed'}), 200
    else:
        return jsonify({'error': 'No key provided'}), 400

@app.route('/update_port', methods=['POST'])
def update_port():
    new_port = request.form.get('serial_port')
    if new_port:
        with env_lock:
            env.change_port(new_port)
    return redirect(url_for('robot_control'))

@app.route('/toggle_connection', methods=['POST'])
def toggle_connection():
    with env_lock:
        if env.ser is None or not env.ser.is_open:
            env.connect_serial()
        else:
            env.disconnect_serial()
    return redirect(url_for('robot_control'))
if __name__ == '__main__':
    app.run(debug=False)
