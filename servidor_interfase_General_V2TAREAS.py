import os
import requests
import json
from datetime import datetime, timedelta

from flask import Flask, jsonify, request, send_file, make_response, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
app = Flask(__name__)
CORS(app)  # Habilita CORS para *todos* los endpoints
# Configuración correcta para el NodeMCU (Simulador en Flask)
# NODEMCU_IP = "http://127.0.0.1:5002"
NODEMCU_IP = "http://192.168.100.226"
#NODEMCU_IP = "http://192.168.100.34"
#NODEMCU_IP = "http://192.168.66.55"


DEFAULT_DB_PATH = os.path.join(os.getcwd(), 'irrigation.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DEFAULT_DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# ======================================= =================
# LISTA GLOBAL DE TAREAS CON GUARDADO Y CARGA DESDE ARCHIVO
# ========================================================
global_tasks = []  # Lista global en memoria
GLOBAL_TASKS_FILE = "global_tasks.json"  # Archivo donde se guardarán las tareas
debug_history = []

def save_global_tasks_to_file():
    """Guarda la lista global de tareas en un archivo JSON."""
    with open(GLOBAL_TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(global_tasks, f, ensure_ascii=False, indent=4)

def load_global_tasks_from_file():
    """Carga la lista global de tareas desde un archivo JSON."""
    global global_tasks
    try:
        with open(GLOBAL_TASKS_FILE, "r", encoding="utf-8") as f:
            global_tasks = json.load(f)
    except FileNotFoundError:
        global_tasks = []


# ===================== MODELOS =====================
class Version(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    version = db.Column(db.Integer, default=1)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class PIDConfig(db.Model):
    """Almacena Kp, Ki, Kd y flow_calibration."""
    id = db.Column(db.Integer, primary_key=True)
    kp = db.Column(db.Float, default=2.0)
    ki = db.Column(db.Float, default=5.0)
    kd = db.Column(db.Float, default=1.0)
    flow_calibration = db.Column(db.Float, default=1.0)

class Regimen(db.Model):
    """
    Cada Regimen con 'name', 'description'.
    Tareas asociadas en Task (relación regimen_id).
    (Ya NO tiene start_day ni start_month, etc.)
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(120), default="")

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    regimen_id = db.Column(db.Integer, db.ForeignKey('regimen.id'), nullable=False)

    name = db.Column(db.String(80), default="")
    description = db.Column(db.String(120), default="")

    day_offset = db.Column(db.Integer, default=0)
    hour = db.Column(db.Integer, default=0)
    minute = db.Column(db.Integer, default=0)
    volume = db.Column(db.Float, default=0.0)

    # Nuevos campos
    executed = db.Column(db.Boolean, default=False)
    executed_at = db.Column(db.DateTime, nullable=True)
    execution_comment = db.Column(db.String(255), default="")

class Plant(db.Model):
    """
    Planta =>
    - name, description
    - servo1pos, servo2pos
    - flow_setpoint
    - start_day, start_month, start_year
    - regimen_id
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(120), default="")

    servo1pos = db.Column(db.Integer, default=90)
    servo2pos = db.Column(db.Integer, default=90)
    flow_setpoint = db.Column(db.Float, default=1.0)

    start_day   = db.Column(db.Integer, default=1)
    start_month = db.Column(db.Integer, default=1)
    start_year  = db.Column(db.Integer, default=2023)

    regimen_id = db.Column(db.Integer, db.ForeignKey('regimen.id'), nullable=True)

def increment_version():
    cur = Version.query.order_by(Version.id.desc()).first()
    newv = cur.version + 1 if cur else 1
    db.session.add(Version(version=newv))
    db.session.commit()
    return newv

def get_current_version():
    v = Version.query.order_by(Version.id.desc()).first()
    return v.version if v else 1

# ================ INIT DB =================
def init_db():
    with app.app_context():
        db.create_all()
        # Aseguramos al menos 1 versión y 1 PID
        if not Version.query.first():
            db.session.add(Version(version=1))
        if not PIDConfig.query.first():
            db.session.add(PIDConfig())
        db.session.commit()

# ================ CRUD de PID =================
@app.route('/api/pid', methods=['GET','PUT'])
def pid_api():
    pid = PIDConfig.query.first() or PIDConfig()
    if request.method=='PUT':
        d= request.json
        pid.kp = d.get('kp', pid.kp)
        pid.ki = d.get('ki', pid.ki)
        pid.kd = d.get('kd', pid.kd)
        pid.flow_calibration= d.get('flowCalibration', pid.flow_calibration)

        db.session.add(pid)
        db.session.commit()
        v= increment_version()
        return jsonify({
            'status':'ok',
            'version': v,
            'pid_config':{
                'kp': pid.kp,
                'ki': pid.ki,
                'kd': pid.kd,
                'flowCalibration': pid.flow_calibration
            }
        })
    # GET
    return jsonify({
        'kp': pid.kp,
        'ki': pid.ki,
        'kd': pid.kd,
        'flowCalibration': pid.flow_calibration
    })

@app.route('/api/regimens', methods=['GET', 'POST', 'DELETE'])
def regimens_api():
    if request.method == 'POST':
        d = request.json
        regimen_id = d.get('id')

        if regimen_id:
            # Actualizar un régimen existente
            regimen = Regimen.query.get(regimen_id)
            if not regimen:
                return jsonify({"error": "Régimen no encontrado"}), 404

            regimen.name = d.get('name', regimen.name)
            regimen.description = d.get('description', regimen.description)
        else:
            # Crear un nuevo régimen sin tareas
            regimen = Regimen(
                name=d.get('name', ""),
                description=d.get('description', "")
            )
            db.session.add(regimen)
            db.session.commit()  # Importante: commit para disponer del ID

        db.session.commit()
        v = increment_version()

        return jsonify({
            'status': 'ok',
            'version': v,
            'regimen': {
                'id': regimen.id,
                'name': regimen.name,
                'description': regimen.description
            }
        })

    elif request.method == 'DELETE':
        d = request.json
        regimen_id = d.get('id')

        if not regimen_id:
            return jsonify({"error": "ID de régimen requerido"}), 400

        regimen = Regimen.query.get(regimen_id)
        if not regimen:
            return jsonify({"error": "Régimen no encontrado"}), 404

        # Eliminar las tareas asociadas a este régimen
        Task.query.filter_by(regimen_id=regimen_id).delete()

        # Eliminar el régimen
        db.session.delete(regimen)
        db.session.commit()
        v = increment_version()

        return jsonify({"status": "ok", "version": v, "message": "Régimen eliminado correctamente"})

    # GET => listar regímenes
    regs = Regimen.query.all()
    return jsonify([{
        'id': r.id,
        'name': r.name,
        'description': r.description
    } for r in regs])


from datetime import datetime
from flask import request, jsonify


@app.route('/api/tasks', methods=['GET', 'POST', 'DELETE'])
def tasks_api():
    # == GET ==
    if request.method == 'GET':
        regimen_id = request.args.get('regimen_id')
        if not regimen_id:
            # Si no pasas regimen_id, devolvemos lista vacía o podrías devolver todas
            return jsonify([])

        tasks = Task.query.filter_by(regimen_id=int(regimen_id)).all()
        # Retorna la lista de tareas en JSON, con todos los campos
        return jsonify([
            {
                'id': t.id,
                'regimen_id': t.regimen_id,
                'name': t.name,
                'description': t.description,
                'day_offset': t.day_offset,
                'hour': t.hour,
                'minute': t.minute,
                'volume': t.volume,
                'executed': t.executed,
                'execution_comment': t.execution_comment,
                # Convertir executed_at a ISO si no es None
                'executed_at': t.executed_at.isoformat() if t.executed_at else None
            } for t in tasks
        ])

    # == POST ==
    elif request.method == 'POST':
        d = request.json
        if not d:
            return jsonify({"error": "No data provided"}), 400

        task_id = d.get('id')  # Puede ser None o int

        if task_id:
            # Ver si existe la tarea con ese ID
            existing_task = Task.query.get(task_id)
            if existing_task:
                # == ACTUALIZAR ==
                existing_task.regimen_id = d.get('regimen_id', existing_task.regimen_id)
                existing_task.name = d.get('name', existing_task.name)
                existing_task.description = d.get('description', existing_task.description)
                existing_task.day_offset = d.get('day_offset', existing_task.day_offset)
                existing_task.hour = d.get('hour', existing_task.hour)
                existing_task.minute = d.get('minute', existing_task.minute)
                existing_task.volume = d.get('volume', existing_task.volume)

                # Campos de ejecución
                existing_task.executed = d.get('executed', existing_task.executed)
                existing_task.execution_comment = d.get('execution_comment', existing_task.execution_comment)

                # Manejo de executed_at si lo recibes como string en ISO8601
                executed_at_str = d.get('executed_at')
                if executed_at_str:
                    try:
                        existing_task.executed_at = datetime.fromisoformat(executed_at_str)
                    except ValueError:
                        existing_task.executed_at = None

                db.session.commit()
                v = increment_version()  # Si manejas versión
                return jsonify({
                    'status': 'ok',
                    'version': v,
                    'updated': True,
                    'task': {
                        'id': existing_task.id,
                        'regimen_id': existing_task.regimen_id,
                        'name': existing_task.name,
                        'description': existing_task.description,
                        'day_offset': existing_task.day_offset,
                        'hour': existing_task.hour,
                        'minute': existing_task.minute,
                        'volume': existing_task.volume,
                        'executed': existing_task.executed,
                        'execution_comment': existing_task.execution_comment,
                        'executed_at': (existing_task.executed_at.isoformat()
                                        if existing_task.executed_at else None)
                    }
                })

            else:
                # == CREAR con ID específico ==
                new_task = Task(
                    id=task_id,
                    regimen_id=d['regimen_id'],  # asumes que regimen_id siempre viene
                    name=d.get('name', ""),
                    description=d.get('description', ""),
                    day_offset=d.get('day_offset', 0),
                    hour=d.get('hour', 0),
                    minute=d.get('minute', 0),
                    volume=d.get('volume', 0.0),
                    executed=d.get('executed', False),
                    execution_comment=d.get('execution_comment', "")
                )
                # executed_at
                executed_at_str = d.get('executed_at')
                if executed_at_str:
                    try:
                        new_task.executed_at = datetime.fromisoformat(executed_at_str)
                    except ValueError:
                        new_task.executed_at = None

                db.session.add(new_task)
                db.session.commit()
                v = increment_version()
                return jsonify({
                    'status': 'ok',
                    'version': v,
                    'created': True,
                    'task': {
                        'id': new_task.id,
                        'regimen_id': new_task.regimen_id,
                        'name': new_task.name,
                        'description': new_task.description,
                        'day_offset': new_task.day_offset,
                        'hour': new_task.hour,
                        'minute': new_task.minute,
                        'volume': new_task.volume,
                        'executed': new_task.executed,
                        'execution_comment': new_task.execution_comment,
                        'executed_at': (new_task.executed_at.isoformat()
                                        if new_task.executed_at else None)
                    }
                })
        else:
            # == CREAR Nueva sin ID específico (autoincrement) ==
            new_task = Task(
                regimen_id=d['regimen_id'],
                name=d.get('name', ""),
                description=d.get('description', ""),
                day_offset=d.get('day_offset', 0),
                hour=d.get('hour', 0),
                minute=d.get('minute', 0),
                volume=d.get('volume', 0.0),
                executed=d.get('executed', False),
                execution_comment=d.get('execution_comment', "")
            )
            executed_at_str = d.get('executed_at')
            if executed_at_str:
                try:
                    new_task.executed_at = datetime.fromisoformat(executed_at_str)
                except ValueError:
                    new_task.executed_at = None

            db.session.add(new_task)
            db.session.commit()
            v = increment_version()
            return jsonify({
                'status': 'ok',
                'version': v,
                'created': True,
                'task': {
                    'id': new_task.id,
                    'regimen_id': new_task.regimen_id,
                    'name': new_task.name,
                    'description': new_task.description,
                    'day_offset': new_task.day_offset,
                    'hour': new_task.hour,
                    'minute': new_task.minute,
                    'volume': new_task.volume,
                    'executed': new_task.executed,
                    'execution_comment': new_task.execution_comment,
                    'executed_at': (new_task.executed_at.isoformat()
                                    if new_task.executed_at else None)
                }
            })

    # == DELETE ==
    elif request.method == 'DELETE':
        d = request.json
        task_id = d.get('id')
        if not task_id:
            return jsonify({"error": "Se requiere un ID de tarea para eliminar"}), 400

        task = Task.query.get(task_id)
        if not task:
            return jsonify({"error": "Tarea no encontrada"}), 404

        db.session.delete(task)
        db.session.commit()
        v = increment_version()
        return jsonify({"status": "ok", "version": v, "message": "Tarea eliminada correctamente"})


@app.route("/api/plants", methods=["GET", "POST", "DELETE"])
def plants_api():
    if request.method == "GET":
        plants = Plant.query.all()
        return jsonify([
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "servo1pos": p.servo1pos,
                "servo2pos": p.servo2pos,
                "flowSetpoint": p.flow_setpoint,
                "start_day": p.start_day,
                "start_month": p.start_month,
                "start_year": p.start_year,
                "regimen_id": p.regimen_id
            } for p in plants
        ])

    elif request.method == "POST":
        data = request.get_json()
        plant = Plant.query.filter_by(id=data.get("id")).first()

        if plant:
            plant.name = data.get("name")
            plant.description = data.get("description")
            plant.servo1pos = data.get("servo1pos")
            plant.servo2pos = data.get("servo2pos")
            plant.flow_setpoint = data.get("flowSetpoint")
            plant.start_day = data.get("start_day")
            plant.start_month = data.get("start_month")
            plant.start_year = data.get("start_year")
            plant.regimen_id = data.get("regimen_id")
        else:
            existing_plant = Plant.query.filter_by(name=data.get("name")).first()
            if existing_plant:
                return jsonify({"error": "El nombre de la planta ya existe"}), 400

            new_plant = Plant(
                name=data.get("name"),
                description=data.get("description"),
                servo1pos=data.get("servo1pos"),
                servo2pos=data.get("servo2pos"),
                flow_setpoint=data.get("flowSetpoint"),
                start_day=data.get("start_day"),
                start_month=data.get("start_month"),
                start_year=data.get("start_year"),
                regimen_id=data.get("regimen_id"),
            )
            db.session.add(new_plant)

        db.session.commit()
        return jsonify({"message": "Planta guardada correctamente"})

    elif request.method == "DELETE":
        data = request.get_json()
        plant_id = data.get("id")

        if not plant_id:
            return jsonify({"error": "Se requiere un ID de planta para eliminar"}), 400

        plant = Plant.query.get(plant_id)
        if not plant:
            return jsonify({"error": "Planta no encontrada"}), 404

        db.session.delete(plant)
        db.session.commit()
        return jsonify({"message": "Planta eliminada correctamente"})

@app.route('/api/regar', methods=['POST'])
def ejecutar_riego():
    """ Recibe una solicitud para regar una planta y la envía al NodeMCU """

    # 1) Leer JSON enviado desde el frontend
    data = request.json
    print("📥 Recibiendo solicitud de riego:", data)  # Debug en consola

    # 2) Extraer datos
    plant_id = data.get("plant_id")
    volume = data.get("volume")
    servo1pos = data.get("servo1pos")
    servo2pos = data.get("servo2pos")
    flow_setpoint = data.get("flow_setpoint")

    # 3) Validar parámetros obligatorios
    if plant_id is None or volume is None:
        return jsonify({"error": "❌ Faltan parámetros: 'plant_id' y 'volume' son obligatorios"}), 400

    # 4) Construir JSON para enviar al NodeMCU
    nodemcu_payload = {
        "plant_id": plant_id,
        "volume": volume,
        "servo1pos": servo1pos if servo1pos is not None else 90,
        "servo2pos": servo2pos if servo2pos is not None else 90,
        "flow_setpoint": flow_setpoint if flow_setpoint is not None else 1.0
    }

    print("📤 Enviando solicitud de riego al NodeMCU:", nodemcu_payload)  # Debug en consola

    try:
        # 5) Hacer la solicitud al NodeMCU
        url = f"{NODEMCU_IP}/regar"
        response = requests.post(url, json=nodemcu_payload, timeout=5)

        # 6) Analizar respuesta del NodeMCU
        if response.status_code == 200:
            return jsonify({"mensaje": f"✅ Riego ejecutado para planta {plant_id} con {volume} ml"})
        else:
            return jsonify({
                "error": f"❌ NodeMCU respondió con código {response.status_code}",
                "detalle": response.text
            }), 500

    except Exception as e:
        return jsonify({"error": f"❌ Error al comunicarse con NodeMCU: {str(e)}"}), 500

@app.route('/api/status', methods=['GET'])
def handle_status():
    global debug_history

    # 1) Obtenemos la PIDConfig y versión locales
    pid = PIDConfig.query.first() or PIDConfig()
    ver = Version.query.order_by(Version.id.desc()).first()

    node_data = {}
    debug_logs_array = []
    flowCalFactor = 0.0  # Valor por defecto si NodeMCU no lo envía

    try:
        # 2) Llamamos al NodeMCU para su /status
        response = requests.get(f"{NODEMCU_IP}/status", timeout=3)

        print("📡 Respuesta recibida desde NodeMCU:")
        print(response.text)  # Debug: vemos el contenido real

        if response.status_code == 200:
            node_data = response.json()  # parseamos el JSON
            # 3) Obtenemos los logs si existen (array)
            debug_logs_array = node_data.get('debugLogs', [])
            # Obtenemos flowCalibrationFactor si el NodeMCU lo manda
            flowCalFactor = node_data.get('flowCalibrationFactor', 1.0)

    except Exception as e:
        # Si algo falla al llamar al NodeMCU, lo anotamos como error
        error_msg = f"❌ Error al obtener el estado del NodeMCU: {str(e)}"
        print(error_msg)
        # Dejamos debug_logs_array vacío o con el error
        debug_logs_array = [error_msg]

    # 4) Validamos si 'currentFlow' está en node_data
    if 'currentFlow' not in node_data:
        print("⚠️ Error: El JSON de NodeMCU no tiene 'currentFlow'. Revísalo.")

    # 5) Construimos la respuesta JSON
    return jsonify({
        'local': {
            'pid': {
                'kp': pid.kp,
                'ki': pid.ki,
                'kd': pid.kd,
                'flowCalibration': pid.flow_calibration
            },
            'version': ver.version if ver else 1,
            'timestamp': ver.timestamp.isoformat() if ver else ''
        },
        'nodemcu': {
            'status': node_data.get('version', 'N/A'),
            'currentFlow': node_data.get('currentFlow', 0.0),
            'totalVolume': node_data.get('totalVolume', 0.0),
            'servoAngle': node_data.get('calculatedAngle', 0),
            'servo1': node_data.get('servo1', '?'),
            'servo2': node_data.get('servo2', '?'),
            'setpoint': node_data.get('setpoint', 0.0),
            'tasksRunning': node_data.get('tasksRunning', False),
            # 6) Devolvemos los logs como array
            'debugLogs': debug_logs_array,
            'feedForwardEquation': node_data.get('feedForwardEquation', ""),
            # 7) Si el NodeMCU envía su flowCalibrationFactor
            'flowCalibrationFactor': flowCalFactor
        }
    })


@app.route('/api/push_config', methods=['POST'])
def push_config():
    print("Intentando enviar configuración (versión, PID y tareas con info de planta) al NodeMCU")
    try:
        # node_ip ya tiene el "http://"
        node_ip = NODEMCU_IP
        url = f"{node_ip}/config"  # Quitar el "http://"
        print("URL de destino:", url)

        # Obtener la versión actual
        serverVer = get_current_version()
        print("Versión del servidor:", serverVer)

        # Configuración del PID
        pid = PIDConfig.query.first() or PIDConfig()
        pid_config = {
            "kp": pid.kp,
            "ki": pid.ki,
            "kd": pid.kd,
            "flowCalibration": pid.flow_calibration
        }
        print("PID Config:", pid_config)

        # Generar la lista de tareas globales
        tasks_list = []
        plants = Plant.query.all()
        for plant in plants:
            if not plant.regimen_id:
                continue
            regimen = Regimen.query.get(plant.regimen_id)
            if not regimen:
                continue
            regimen_tasks = Task.query.filter_by(regimen_id=regimen.id).all()
            for t in regimen_tasks:
                tasks_list.append({
                    "task_id": t.id,
                    "regimen_id": regimen.id,
                    "task_name": t.name,
                    "task_description": t.description,
                    "day_offset": t.day_offset,
                    "hour": t.hour,
                    "minute": t.minute,
                    "volume": t.volume,
                    "executed": False,
                    "plant_id": plant.id,
                    "plant_name": plant.name,
                    "servo1pos": plant.servo1pos,
                    "servo2pos": plant.servo2pos
                })
        print("Tareas a enviar:", tasks_list)

        data = {
            "version": serverVer,
            "pid_config": pid_config,
            "tasks": tasks_list
        }
        print("JSON a enviar:", data)

        r = requests.post(url, json=data, timeout=5)
        print("Respuesta del NodeMCU:", r.text)

        if r.status_code == 200:
            return jsonify({'msg': 'Push config ok', 'node_resp': r.text}), 200
        else:
            return jsonify({'error': 'NodeMCU error', 'code': r.status_code, 'resp': r.text}), 500

    except Exception as e:
        print("Excepción en push_config:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/api/update_tasks', methods=['POST'])
def api_update_tasks():
    """
    Actualiza las tareas existentes si coinciden en 'task_id' y validando
    que pertenezcan a la misma planta y régimen. Si no hay coincidencia,
    se crea una nueva. No borra tareas previas, solo las actualiza o reporta.
    """
    data = request.get_json()
    if "tasks" not in data:
        return jsonify({"error": "No se enviaron tareas para actualizar."}), 400

    new_tasks = data["tasks"]

    # Cargar todas las tareas existentes en un diccionario con clave (plant_id, regimen_id, task_id)
    existing_tasks = Task.query.all()
    existing_dict = { (t.regimen_id, t.id): t for t in existing_tasks }

    # Guardar mensajes de actualización/creación
    update_messages = []

    # 1) Recorrer cada tarea "nueva" recibida desde el NodeMCU
    for nt in new_tasks:
        task_id = nt["task_id"]
        regimen_id = nt["regimen_id"]
        plant_id = nt.get("plant_id")  # No está en Task, pero sí en JSON (para comparación)

        # Validar si la tarea existe en la base y coincide en régimen
        key = (regimen_id, task_id)
        db_task = existing_dict.get(key)

        if db_task:
            # Verificar si pertenece a la misma planta y régimen
            db_plant = Plant.query.get(plant_id) if plant_id else None
            if db_plant and db_plant.regimen_id == regimen_id:
                # 🔄 ACTUALIZAR CAMPOS
                update_messages.append(f"Actualizando tarea existente: id={task_id}, plant_id={plant_id}")

                db_task.name = nt["name"]
                db_task.description = nt["description"]
                db_task.day_offset = nt["day_offset"]
                db_task.hour = nt["hour"]
                db_task.minute = nt["minute"]
                db_task.volume = nt["volume"]
                db_task.executed = nt.get("executed", db_task.executed)
                db_task.execution_comment = nt.get("execution_comment", db_task.execution_comment)

                # Si viene 'executed_at', convertir a datetime
                if "executed_at" in nt and nt["executed_at"]:
                    try:
                        db_task.executed_at = datetime.fromisoformat(nt["executed_at"])
                    except ValueError:
                        db_task.executed_at = None  # Si hay error en el formato

                # Marcar tarea como "procesada"
                del existing_dict[key]
            else:
                # 🔴 Si el régimen o planta no coinciden, se debe crear una nueva
                update_messages.append(f"Tarea {task_id} no coincide con planta {plant_id}. Creando nueva.")

                new_task = Task(
                    id=task_id,
                    regimen_id=nt["regimen_id"],
                    name=nt["name"],
                    description=nt["description"],
                    day_offset=nt["day_offset"],
                    hour=nt["hour"],
                    minute=nt["minute"],
                    volume=nt["volume"],
                    executed=nt.get("executed", False),
                    execution_comment=nt.get("execution_comment", "")
                )
                if "executed_at" in nt and nt["executed_at"]:
                    try:
                        new_task.executed_at = datetime.fromisoformat(nt["executed_at"])
                    except ValueError:
                        new_task.executed_at = None
                db.session.add(new_task)

        else:
            # 🔵 CREAR NUEVA TAREA SI NO EXISTE
            update_messages.append(f"Creando nueva tarea: id={task_id}, plant_id={plant_id}")

            new_task = Task(
                id=task_id,
                regimen_id=nt["regimen_id"],
                name=nt["name"],
                description=nt["description"],
                day_offset=nt["day_offset"],
                hour=nt["hour"],
                minute=nt["minute"],
                volume=nt["volume"],
                executed=nt.get("executed", False),
                execution_comment=nt.get("execution_comment", "")
            )
            if "executed_at" in nt and nt["executed_at"]:
                try:
                    new_task.executed_at = datetime.fromisoformat(nt["executed_at"])
                except ValueError:
                    new_task.executed_at = None
            db.session.add(new_task)

    # 2) Verificar si quedaron tareas en el diccionario que no fueron mencionadas
    if existing_dict:
        leftover_ids = list(existing_dict.keys())
        update_messages.append(f"Tareas en la base no mencionadas en el NodeMCU: {leftover_ids}")

    db.session.commit()

    # Retorna un mensaje de confirmación con los detalles de lo que ocurrió
    return jsonify({
        "message": "Se completó la actualización/creación de tareas.",
        "details": update_messages
    }), 200


@app.route('/api/load_custom_database', methods=['POST'])
def api_load_custom_database():
    """Carga una base de datos SQLite personalizada."""
    data = request.get_json()
    db_path = data.get("db_path")
    if not db_path:
        return jsonify({"error": "Se requiere la ruta del archivo de la base de datos."}), 400

    if not os.path.exists(db_path):
        return jsonify({"error": "El archivo de la base de datos no existe."}), 400

    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    global db
    db = SQLAlchemy(app)
    return jsonify({"message": "Base de datos cargada correctamente.", "reload": True})


@app.route('/api/download_tasks', methods=['GET'])
def api_download_tasks():
    """Genera un archivo JSON con la lista de tareas y lo ofrece para descarga."""
    tasks = Task.query.all()
    tasks_list = [
        {
            "task_id": t.id,
            "regimen_id": t.regimen_id,
            "name": t.name,
            "description": t.description,
            "day_offset": t.day_offset,
            "hour": t.hour,
            "minute": t.minute,
            "volume": t.volume
        } for t in tasks
    ]
    file_path = "tasks_backup.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(tasks_list, f, ensure_ascii=False, indent=4)
    return send_file(file_path, as_attachment=True)

def start_tasks():
    try:
        # NOTA: NODEMCU_IP ya contiene "http://"
        url = f"{NODEMCU_IP}/startTasks"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return jsonify({'status': 'ok', 'message': 'Tareas iniciadas en NodeMCU'})
        else:
            return jsonify({'error': f'Error en NodeMCU: {response.status_code}', 'resp': response.text}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stop_tasks', methods=['GET'])
def stop_tasks():
    try:
        url = f"{NODEMCU_IP}/stopTasks"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return jsonify({'status': 'ok', 'message': 'Tareas detenidas en NodeMCU'})
        else:
            return jsonify({'error': f'Error en NodeMCU: {response.status_code}', 'resp': response.text}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/task_timeline', methods=['GET'])
def task_timeline():
    tasks_timeline = []

    plants = Plant.query.all()
    for plant in plants:
        if not plant.regimen_id:
            continue

        regimen = Regimen.query.get(plant.regimen_id)
        if not regimen:
            continue

        regimen_tasks = Task.query.filter_by(regimen_id=regimen.id).all()

        for task in regimen_tasks:
            try:
                start_date = datetime(plant.start_year, plant.start_month, plant.start_day)
                task_date = start_date + timedelta(days=task.day_offset)

                tasks_timeline.append({
                    "plant_id": plant.id,
                    "plant_name": plant.name,
                    "regimen_id": regimen.id,
                    "regimen_name": regimen.name,
                    "task_id": task.id,
                    "task_name": task.name,
                    "task_description": task.description,
                    "date": task_date.strftime("%Y-%m-%d"),
                    "volume": task.volume
                })
            except Exception as e:
                print(f"Error procesando tarea '{task.name}' de la planta '{plant.name}': {str(e)}")

    tasks_timeline.sort(key=lambda x: x['date'])
    return jsonify(tasks_timeline)

# =================== NUEVOS ENDPOINTS PARA LA LISTA GLOBAL DE TAREAS ===================

@app.route('/api/global_tasks', methods=['GET', 'POST', 'DELETE'])
def global_tasks_api():
    """
    GET: Devuelve la lista global de tareas.
    POST: Agrega una nueva tarea a la lista global. Si no se envía un ID, se asigna uno automáticamente.
    DELETE: Elimina una tarea de la lista global (se requiere enviar el 'id' de la tarea en JSON).
    """
    global global_tasks
    if request.method == "GET":
        return jsonify(global_tasks)
    elif request.method == "POST":
        task = request.get_json()
        if not task:
            return jsonify({"error": "No se proporcionaron datos de tarea"}), 400
        # Asignar un ID si no se incluye
        if "id" not in task:
            new_id = max([t.get("id", 0) for t in global_tasks], default=0) + 1
            task["id"] = new_id
        global_tasks.append(task)
        return jsonify({"status": "ok", "task": task})
    elif request.method == "DELETE":
        data = request.get_json()
        if not data or "id" not in data:
            return jsonify({"error": "Se requiere el ID de la tarea a eliminar"}), 400
        task_id = data["id"]
        for t in global_tasks:
            if t.get("id") == task_id:
                global_tasks.remove(t)
                return jsonify({"status": "ok", "message": f"Tarea {task_id} eliminada."})
        return jsonify({"error": "Tarea no encontrada"}), 404

@app.route('/api/global_tasks/save', methods=['POST'])
def save_global_tasks_endpoint():
    """Guarda la lista global de tareas en el archivo."""
    try:
        save_global_tasks_to_file()
        return jsonify({"status": "ok", "message": "Lista global de tareas guardada en archivo."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/global_tasks/load', methods=['GET'])
def load_global_tasks_endpoint():
    """Carga la lista global de tareas desde el archivo y la devuelve."""
    try:
        load_global_tasks_from_file()
        return jsonify({"status": "ok", "tasks": global_tasks})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
@app.route('/api/calibrate_flow', methods=['GET'])
def calibrate_flow():
    """
    Endpoint para iniciar la calibración del flow en el NodeMCU.
    Este endpoint llama al endpoint /calibrateFeedForward del NodeMCU y retorna la respuesta.
    """
    try:
        url = f"{NODEMCU_IP}/calibrateFeedForward"
        # Ajusta el timeout si el proceso de calibración puede tardar más
        response = requests.get(url, timeout=20)
        if response.status_code == 200:
            return jsonify({
                'status': 'ok',
                'message': 'Calibración completada en el NodeMCU',
                'node_response': response.text
            })
        else:
            return jsonify({
                'error': f'NodeMCU respondió con código {response.status_code}',
                'node_response': response.text
            }), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/feed_forward', methods=['GET'])
def get_feed_forward_table():
    """
    Consulta al NodeMCU el endpoint /getFeedForward y devuelve la tabla feed‑forward.
    """
    try:
        # Se hace la petición al NodeMCU para obtener la tabla feed‑forward
        response = requests.get(f"{NODEMCU_IP}/getFeedForward", timeout=5)
        if response.status_code == 200:
            # Se retorna el JSON recibido del NodeMCU
            return jsonify(response.json())
        else:
            return jsonify({
                "error": f"NodeMCU respondió con código {response.status_code}",
                "detail": response.text
            }), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ================ Manejo de Errores ================
@app.errorhandler(404)
def not_found(e):
    return make_response(jsonify({'error': 'Not found'}), 404)

@app.errorhandler(400)
def bad_request(e):
    return make_response(jsonify({'error': 'Bad request'}), 400)

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return make_response(jsonify({'error': 'Server error'}), 500)

@app.route('/')
def serve_index():
    return render_template('index.html')

if __name__=='__main__':
    init_db()
    # Cargamos la lista global de tareas desde el archivo al iniciar el servidor
    load_global_tasks_from_file()
    app.run(host='0.0.0.0', port=5000, debug=False)
