from flask import Flask, request, jsonify
from basic_gym_env.basic_env import BasicEnv
import threading
import time
import os
import numpy as np
import inspect

# Crear una instancia de la aplicación Flask
app = Flask(__name__)

# Inicializar el entorno BasicEnv una sola vez al inicio
env = BasicEnv(port='COM8', baudrate=115200)

# Endpoint para configurar el entorno
@app.route('/actualizar_acciones', methods=['POST'])
def configurar():
    try:
        data = request.get_json()
        if data is None:
            return jsonify({'error': 'Solicitud inválida: se esperaba JSON en el cuerpo de la solicitud'}), 400

        # Configurar modo manual
        manual_mode = data.get('manual_mode')
        if manual_mode is not None:
            env.set_manual_mode(int(manual_mode))

        # Habilitar o deshabilitar joypad
        joypad_action = data.get('joypad_action')
        if joypad_action == 'enable':
            env.enable_joypad()
        elif joypad_action == 'disable':
            env.disable_joypad()

        # Configurar setpoints
        setpoints = data.get('setpoints')
        if setpoints:
            for component, value in setpoints.items():
                if component == 'slide':
                    env.set_corredera(value)
                elif component == 'angle':
                    env.set_angulo(value)
                elif component == 'volume':
                    env.set_volumen_requerido(value)

        # Configurar energías
        energies = data.get('energies')
        if energies:
            for component, value in energies.items():
                if component == 'slide':
                    env.set_energy_corredera(value)
                elif component == 'angle':
                    env.set_energy_angulo(value)
                elif component == 'valve':
                    env.set_energy_valvula(value)

        # Configurar PIDs
        pids = data.get('pids')
        if pids:
            for component, pid_values in pids.items():
                kp = pid_values.get('kp')
                ki = pid_values.get('ki')
                kd = pid_values.get('kd')
                if kp is not None and ki is not None and kd is not None:
                    if component == 'slide':
                        env.set_pid_corredera(kp, ki, kd)
                    elif component == 'angle':
                        env.set_pid_angulo(kp, ki, kd)

        # Reseteo del entorno
        resets = data.get('reset')
        if resets:
            for component, value in resets.items():
                if component == 'slide':
                    env.reset_X(value)
                elif component == 'angle':
                    env.reset_A(value)
                elif component == 'volume':
                    env.reset_volumen()
                elif component == 'time':
                    env.reset()

        configs = data.get('calibrate')
        if configs:
            for component, value in configs.items():
                if component == 'slide':
                    env.calibrate_StepsPerMM(value)
                elif component == 'angle':
                    env.calibrate_stepsPerDegree(value)

        env.step()
        return jsonify({'status': 'Configuración actualizada'}), 200

    except Exception as e:
        # Capturar y mostrar cualquier excepción que ocurra
        return jsonify({'error': f'Error en el servidor: {str(e)}'}), 500


# Endpoint para obtener el estado del entorno
@app.route('/estado', methods=['GET'])
def obtener_estado():
    detail_level = request.args.get('detail', 'observation')
    batch_id = int(request.args.get('batch_id', 1))  # Obtener el batch_id de los parámetros de la solicitud
    if env is not None:
        if detail_level == 'full':
            state = {
                'current_action': env.current_action.tolist(),
                'simulation_time': env.simulation_time,
                'manual_mode': env.manual_mode,
                'execution_data': env.get_steps_from_batch(batch_id),
            }
            return jsonify({'status': 'Success', 'state': state}), 200
        else:
            obs = env.get_observation()
            if obs is not None:
                return jsonify({'observation': obs.tolist()}), 200
            else:
                return jsonify({'error': 'No hay observación disponible'}), 400
    else:
        return jsonify({'error': 'El entorno no está inicializado'}), 400


# Variable global para controlar si se debe detener la ejecución
stop_execution = False


@app.route('/controlar_entorno', methods=['POST'])
def controlar_entorno():
    global stop_execution
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Solicitud inválida: se esperaba JSON en el cuerpo de la solicitud'}), 400

    action = data.get('action')
    action_code = data.get('action_code')  # Código Python que se usará para definir la función de acción
    batch_id = data.get('batch_id', 1)  # Usar el batch_id proporcionado o un valor por defecto

    # Crear la función de acción solo si se proporciona un código de acción personalizado
    action_function = None
    if action_code:
        try:
            local_variables = {}
            exec(action_code, {}, local_variables)
            if 'custom_action' in local_variables:
                action_function = local_variables['custom_action']
            else:
                return jsonify({'error': 'El código no definió una función llamada custom_action'}), 400
        except Exception as e:
            return jsonify({'error': f'Error al interpretar el código de acción: {str(e)}'}), 400

    # Agregar la acción para iniciar la lectura del batch
    if action == 'start_batch':
        if env is not None:
            batch_id = env.start_batch(batch_id)
            return jsonify({'status': 'Batch iniciado', 'batch_id': batch_id}), 200
        else:
            return jsonify({'error': 'El entorno no está inicializado'}), 400


    if action == 'execute_steps':

        execution_time = data.get('execution_time')

        start_time = time.time()

        env.execution_data = []  # Limpiar los datos de la ejecución anterior

        while time.time() - start_time < execution_time:

            # Obtener las observaciones actuales

            obs = env.get_observation()

            if action_function and obs is not None:

                calculated_action = action_function(obs)  # Generar la acción con la función especificada

                obs, reward, done, info = env.step(calculated_action)

            else:

                # Ejecutar el paso predeterminado del entorno sin ninguna acción personalizada

                obs, reward, done, info = env.step()

            # Asegurarse de que los datos se almacenen

            env.store_serial_data(sent_data=str(calculated_action), received_data=str(obs))

            time.sleep(0.3)  # Esperar un pequeño intervalo entre pasos

        # Obtener los pasos almacenados después de la ejecución

        pasos_ejecutados = env.get_steps_from_batch(batch_id)

        return jsonify({

            'status': 'Ejecución completada',

            'data': pasos_ejecutados  # Devolver los datos de los pasos ejecutados

        }), 200

    # Acción para detener la ejecución y terminar el batch
    elif action == 'stop':
        # Detener la ejecución en curso
        stop_execution = True
        detener_motores()

        # Finalizar la lectura del batch
        if batch_id is not None:
            pasos_ejecutados = env.get_steps_from_batch(batch_id)
            return jsonify({'status': 'Ejecución detenida exitosamente', 'batch_data': pasos_ejecutados}), 200
        else:
            return jsonify({'status': 'Ejecución detenida exitosamente'}), 200

    elif action == 'reset':
        env.reset()
        return jsonify({'status': 'Entorno reiniciado con éxito'}), 200

    else:
        return jsonify({'error': 'Acción inválida'}), 400
def detener_motores():
    """
    Función para detener los motores estableciendo su energía en cero,
    manteniendo el resto de las configuraciones del entorno sin cambios.
    """
    # Obtener la acción actual del entorno y solo modificar la energía de los motores
    stop_action = env.current_action  # Mantener la configuración actual del entorno

    # Modificar solo los valores de energía de los motores
    stop_action[0] = 1  # modo manual encendido
    stop_action[1] = 0  # Energía del motor angular a 0
    stop_action[2] = 0  # Energía del motor lineal a 0
    stop_action[3] = 0  # Energía de la bomba a 0

    env.step(stop_action)
    print("Energía de los motores establecida en cero, otras configuraciones mantenidas.")


if __name__ == '__main__':
    # Punto de entrada principal
    try:
        print("Iniciando servidor Flask con entorno BasicEnv.")
        app.run(host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        if env is not None:
            env.close()
        print("Servidor detenido y entorno cerrado.")