from flask import Flask, request, jsonify
import threading
import time
from datetime import datetime, timedelta  # Agregar importación



app = Flask(__name__)

# ========== VARIABLES SIMULADAS ==========
status = {
    "version": 1,
    "tasksRunning": False,
    "currentFlow": 0.0,
    "totalVolume": 0.0,
    "servoAngle": 0,
    "servo1": 90,
    "servo2": 90,
    "setpoint": 0.0,
    "Kp": 2.0,
    "Ki": 5.0,
    "Kd": 1.0,
    "flowCalibration": 1.0,
    "debugLog": "",
}

# ========== SIMULACIÓN DE FLUJO ==========
def simulate_flow():
    while True:
        if status["setpoint"] > 0:
            status["currentFlow"] = status["setpoint"] * status["flowCalibration"]
            status["totalVolume"] += status["currentFlow"] * 0.2  # Simulación de flujo acumulado
        else:
            status["currentFlow"] = 0

        time.sleep(0.2)

# Iniciar la simulación en un hilo separado
flow_thread = threading.Thread(target=simulate_flow, daemon=True)
flow_thread.start()

# ========== ENDPOINTS ==========

@app.route("/status", methods=["GET"])
def get_status():
    return jsonify(status)

@app.route("/startStopTasks", methods=["GET"])
def start_stop_tasks():
    run = request.args.get("run")
    if run is None:
        return "Falta el parámetro ?run=0|1", 400

    status["tasksRunning"] = run == "1"
    msg = "Tareas INICIADAS" if status["tasksRunning"] else "Tareas DETENIDAS"
    status["debugLog"] += f"[{time.time()}] {msg}\n"
    return msg

@app.route("/control", methods=["GET"])
def control():
    if status["tasksRunning"]:
        return "Control bloqueado - Tareas en ejecución", 403

    if "servo1" in request.args:
        status["servo1"] = int(request.args["servo1"])
    if "servo2" in request.args:
        status["servo2"] = int(request.args["servo2"])
    if "flow" in request.args:
        status["setpoint"] = float(request.args["flow"])

    status["debugLog"] += f"[{time.time()}] Control actualizado: Servo1={status['servo1']} Servo2={status['servo2']} Flow={status['setpoint']}\n"
    return "Control actualizado"

@app.route("/config", methods=["POST","GET"])
def config():
    print("configurando")
    data = request.json

    if not data:
        return "Error: No se recibió JSON", 400

    if "version" in data:
        status["version"] = data["version"]
    if "valveConfig" in data:
        status["Kp"] = data["valveConfig"].get("Kp", status["Kp"])
        status["Ki"] = data["valveConfig"].get("Ki", status["Ki"])
        status["Kd"] = data["valveConfig"].get("Kd", status["Kd"])
        status["flowCalibration"] = data["valveConfig"].get("flowCalibration", status["flowCalibration"])

    status["debugLog"] += f"[{time.time()}] Configuración recibida: {data}\n"
    return "Configuración aplicada correctamente"

@app.route("/regar", methods=["GET"])
def regar():
    plant_id = request.args.get("id")
    volumen = request.args.get("vol")

    if not plant_id or not volumen:
        return "Faltan parámetros: ?id=PLANT_ID&vol=VOL_ML", 400

    plant_id = int(plant_id)
    volumen = float(volumen)

    status["debugLog"] += f"[{time.time()}] Riego ejecutado en planta {plant_id} con {volumen}ml\n"
    return f"Riego ejecutado para planta {plant_id} con {volumen}ml"





if __name__ == "__main__":
    print("🚀 Simulador de NodeMCU corriendo en http://127.0.0.1:5002")
    app.run(host="0.0.0.0", port=5002, debug=False)
