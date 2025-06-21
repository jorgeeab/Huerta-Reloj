import requests

# ---- PRUEBAS PARA EL CONTROL DE PLANTAS ----

# 1. Crear una Planta
print("--- Crear Planta ---")

# Ejemplo correcto
data_create_correct = {
    "accion": "crear",
    "id_planta": 1,
    "nombre": "Tomate",
    "fecha_plantacion": "2023-01-01 08:00",
    "angulo_h": 30.0,
    "angulo_y": 20.0,
    "longitud_slider": 50.0,
    "velocidad_agua": 1.0,
    "era": "Era 1"
}
response = requests.post("http://localhost:5000/plantas", json=data_create_correct)
print("Crear planta (correcto):", response.json())

# Ejemplo con un campo faltante (`angulo_y`)
data_create_incorrect = {
    "accion": "crear",
    "id_planta": 2,
    "nombre": "Lechuga",
    "fecha_plantacion": "2023-01-01 08:00",
    "angulo_h": 30.0,
    "longitud_slider": 50.0,
    "velocidad_agua": 1.0,
    "era": "Era 1"
}
response = requests.post("http://localhost:5000/plantas", json=data_create_incorrect)
print("Crear planta (incorrecto):", response.json())


# 2. Modificar una Planta
print("\n--- Modificar Planta ---")

# Ejemplo correcto
data_modify_correct = {
    "accion": "modificar",
    "id_planta": 1,
    "era": "Era 1",
    "longitud_slider": 60.0,
    "velocidad_agua": 1.2
}
response = requests.post("http://localhost:5000/plantas", json=data_modify_correct)
print("Modificar planta (correcto):", response.json())

# Ejemplo con campo inexistente (`color`)
data_modify_incorrect = {
    "accion": "modificar",
    "id_planta": 1,
    "era": "Era 1",
    "color": "Verde"
}
response = requests.post("http://localhost:5000/plantas", json=data_modify_incorrect)
print("Modificar planta (incorrecto):", response.json())


# 3. Eliminar una Planta
print("\n--- Eliminar Planta ---")

data_delete = {
    "accion": "eliminar",
    "id_planta": 1,
    "era": "Era 1"
}
response = requests.post("http://localhost:5000/plantas", json=data_delete)
print("Eliminar planta:", response.json())

# ---- PRUEBAS PARA EL CONTROL DEL ENTORNO/ROBOT ----

# 1. Actualizar Acciones del Robot
print("\n--- Actualizar Acciones del Robot ---")

# Ejemplo correcto
data_update_correct = {
    "accion": "actualizar_acciones",
    "manual_mode": 1,
    "joypad_action": "enable",
    "setpoints": {
        "slide": 200,  # Setpoint para corredera
        "angle": 45,   # Setpoint para ángulo
        "volume": 500  # Volumen requerido
    },
    "energies": {
        "slide": 120,  # Energía para corredera
        "angle": 100,  # Energía para ángulo
        "valve": 150   # Energía para válvula
    },
    "pids": {
        "slide": {"kp": 1.0, "ki": 0.5, "kd": 0.1},  # PID para corredera
        "angle": {"kp": 1.5, "ki": 0.3, "kd": 0.2}   # PID para ángulo
    }
}
response = requests.post("http://localhost:5000/entorno", json=data_update_correct)
print("Actualizar acciones (correcto):", response.json())

# Ejemplo con un campo incorrecto (`joypad_action` inválido)
data_update_incorrect = {
    "accion": "actualizar_acciones",
    "manual_mode": 1,
    "joypad_action": "start",  # valor incorrecto
    "setpoints": {
        "slide": 200,
        "angle": 45,
        "volume": 500
    }
}
response = requests.post("http://localhost:5000/entorno", json=data_update_incorrect)
print("Actualizar acciones (incorrecto):", response.json())


# 2. Obtener Estado del Robot
print("\n--- Obtener Estado del Robot ---")

# Obtener estado detallado del robot con control de tiempo y frecuencia
params_full = {
    "accion": "obtener_estado",
    "detail": "full",
    "batch_id": 1,
    "time_limit": 5,      # Limitar los datos a los primeros 5 segundos
    "interval": 0.5       # Frecuencia de observación cada 0.5 segundos
}
response = requests.post("http://localhost:5000/entorno", json=params_full)
print("Obtener estado (detallado, con control de tiempo y frecuencia):", response.json())

# Obtener observación básica
params_basic = {
    "accion": "obtener_estado",
    "detail": "observation",
    "batch_id": 1
}
response = requests.post("http://localhost:5000/entorno", json=params_basic)
print("Obtener observación (básica):", response.json())


# 3. Controlar el Entorno/Robot
print("\n--- Controlar el Entorno/Robot ---")

# Iniciar ejecución de pasos en el entorno con `execute_steps`
data_execute_steps = {
    "accion": "controlar_entorno",
    "action": "execute_steps",
    "execution_time": 10,  # Ejecuta durante 10 segundos
    "batch_id": 1,
    "action_code": """
def custom_action(obs):
    return [0, 0, 0, 0, 200, 45, 500, 1.0, 0.5, 0.1, 1.5, 0.3, 0.2, 0, 0, 0, obs[18], obs[19], 0, 0]
    """
}
response = requests.post("http://localhost:5000/entorno", json=data_execute_steps)
print("Ejecutar pasos:", response.json())

# Parar la ejecución
data_stop = {
    "accion": "controlar_entorno",
    "action": "stop",
    "batch_id": 1
}
response = requests.post("http://localhost:5000/entorno", json=data_stop)
print("Detener ejecución:", response.json())

# Resetear el entorno
data_reset = {
    "accion": "controlar_entorno",
    "action": "reset"
}
response = requests.post("http://localhost:5000/entorno", json=data_reset)
print("Resetear entorno:", response.json())
