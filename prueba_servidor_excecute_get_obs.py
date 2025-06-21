import requests

# URL del servidor Flask
url = 'http://127.0.0.1:5000/controlar_entorno'

# Código de acción personalizado que utiliza observaciones para ajustar las acciones y setpoints dinámicamente
action_code = """
def custom_action(obs):
    import numpy as np

    # Reemplazar NaN por ceros en las observaciones
    obs = np.nan_to_num(obs, nan=0.0)

    # Definir parámetros iniciales y setpoints dinámicos basados en el tiempo de ejecución
    execution_time = obs[21]  # Suponiendo que el tiempo de ejecución está en obs[21]

    # Ajustar el setpoint de X en función de una función sinusoidal
    X_Requerido = 200 + 100 * np.sin(execution_time / 5.0)

    # Ajustar el setpoint del ángulo basado en una función cosenoidal
    A_Requerido = 45 + 30 * np.cos(execution_time / 10.0)

    # Ajuste de los setpoints de volumen y flujo basados en el tiempo
    setpoint_volumen = 500 + 200 * np.sin(execution_time / 15.0)
    setpoint_flow = 50 + 20 * np.cos(execution_time / 20.0)

    # Definir las ganancias del PID para volumen y flujo (valores fijos en este caso)
    kp_volumen, ki_volumen, kd_volumen = 1.2, 0.8, 0.5
    kp_flow, ki_flow, kd_flow = 1.0, 0.5, 0.3

    # Control manual o automático, en este caso lo dejamos en automático (0)
    modoManual = 0

    # Generar la lista de acciones
    action = [
        modoManual,  # [0] modoManual: 0 para automático
        0,  # [1] EMA: Energía del motor angular
        0,  # [2] EMX: Energía del motor lineal
        0,  # [3] EMV: Energía de la bomba
        X_Requerido,  # [4] X_Requerido: setpoint del deslizador X
        A_Requerido,  # [5] A_Requerido: setpoint del ángulo
        setpoint_volumen,  # [6] Vol_requerido: setpoint de volumen
        kp_volumen,  # [7] kpX: Ganancia proporcional para el volumen
        ki_volumen,  # [8] kiX: Ganancia integral para el volumen
        kd_volumen,  # [9] kdX: Ganancia derivativa para el volumen
        kp_flow,  # [10] kpA: Ganancia proporcional para el flujo
        ki_flow,  # [11] kiA: Ganancia integral para el flujo
        kd_flow,  # [12] kdA: Ganancia derivativa para el flujo
        0,  # [13] resetVolumen
        0,  # [14] resetMotorXFlag
        0,  # [15] resetMotorAFlag
        obs[18],  # [16] stepsPerMM
        obs[19],  # [17] stepsPerDegree
        0,  # [18] (valor no utilizado)
        0  # [19] (valor no utilizado)
    ]

    return np.array(action, dtype=np.float32)
"""

# Datos para la solicitud POST
data = {
    "action": "execute_steps",
    "execution_time": 15,  # Ejecutar el entorno durante 15 segundos para ver la variación en tiempo real
    "variable_filtro": "volumen",  # Filtrar para obtener solo los datos de la variable 'volumen'
    "duracion_tiempo": 10,  # Obtener los datos de los últimos 10 segundos
    "action_code": action_code  # El código Python que define la función 'custom_action'
}

# Realizar la solicitud POST al servidor
response = requests.post(url, json=data)

# Imprimir la respuesta del servidor
print("Estado de la respuesta:", response.status_code)
print("Respuesta del servidor:", response.json())
