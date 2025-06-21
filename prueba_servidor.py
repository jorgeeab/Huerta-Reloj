import requests

# URL of the Flask server
url = 'http://127.0.0.1:5000/controlar_entorno'

# Start a new batch
start_batch_data = {
    "action": "start_batch"
}
response = requests.post(url, json=start_batch_data)
if response.status_code == 200:
    batch_id = response.json().get('batch_id')
    print(f"Batch iniciado con batch_id: {batch_id}")
else:
    print("Error al iniciar el batch")
    exit(1)

# Custom action code (your existing action_code)
action_code = """
def custom_action(obs):
    import numpy as np

    # Replace NaN with zeros
    obs = np.nan_to_num(obs, nan=0.0)

    # Define setpoints
    setpoint_volumen = 500  # Target volume
    setpoint_flow = 50  # Target flow

    # PID parameters
    kp_volumen = 1.0
    ki_volumen = 0.1
    kd_volumen = 0.05

    kp_flow = 1.0
    ki_flow = 0.1
    kd_flow = 0.05

    # Errors
    error_volumen = setpoint_volumen - obs[2]
    error_flow = setpoint_flow - obs[3]

    # PID outputs (simplified)
    output_volumen = kp_volumen * error_volumen
    output_flow = kp_flow * error_flow

    # Adjust setpoints for X_Requerido and A_Requerido
    execution_time = obs[21]
    X_Requerido = 200 + 100 * np.sin(execution_time / 10.0)
    A_Requerido = 45 + 15 * np.cos(execution_time / 5.0)

    # Action list
    action = [
        0,  # modoManual: 0 for automatic
        0,  # EMA
        0,  # EMX
        0,  # EMV
        X_Requerido,
        A_Requerido,
        setpoint_volumen,
        kp_volumen,
        ki_volumen,
        kd_volumen,
        kp_flow,
        ki_flow,
        kd_flow,
        0,  # resetVolumen
        0,  # resetMotorXFlag
        0,  # resetMotorAFlag
        obs[18],  # stepsPerMM
        obs[19],  # stepsPerDegree
        0,
        0
    ]

    return np.array(action, dtype=np.float32)
"""

# Data for the POST request
data = {
    "action": "execute_steps",
    "execution_time": 10,  # Run the environment for 10 seconds
    "batch_id": batch_id,  # Use the batch_id from start_batch
    "action_code": action_code
}

# Make the POST request to the server
response = requests.post(url, json=data)

# Print the server's response
print("Estado de la respuesta:", response.status_code)
print("Respuesta del servidor:", response.json())
