import os
import requests
from datetime import datetime
from flask import Flask, jsonify, request, make_response, render_template
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta  # Agregar importación

app = Flask(__name__)

# Configuración correcta para el NodeMCU (Simulador en Flask)
#NODEMCU_IP = "http://127.0.0.1:5002"
NODEMCU_IP = "http://192.168.100.208"

# Ajusta la ruta de tu DB local
DB_PATH = os.path.join(os.getcwd(),'irrigation.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


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
    """
    Task asociada a un Regimen.
    name, description, day_offset, hour, minute, volume
    Sin flow_setpoint (lo coge la Planta).
    """
    id = db.Column(db.Integer, primary_key=True)
    regimen_id = db.Column(db.Integer, db.ForeignKey('regimen.id'), nullable=False)

    name = db.Column(db.String(80), default="")
    description = db.Column(db.String(120), default="")

    day_offset = db.Column(db.Integer, default=0)
    hour       = db.Column(db.Integer, default=0)
    minute     = db.Column(db.Integer, default=0)
    volume     = db.Column(db.Float, default=0.0)


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
        # Aseguramos al menos 1 version y 1 PID
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
                name=d.get('name', ""),  # Evita errores si 'name' no está en la solicitud
                description=d.get('description', "")
            )
            db.session.add(regimen)
            db.session.commit()  # 🔥 Importante: Commit antes de leer regimen.id

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


@app.route('/api/tasks', methods=['GET', 'POST', 'DELETE'])
def tasks_api():
    if request.method == 'POST':
        d = request.json
        new_task = Task(
            regimen_id=d['regimen_id'],
            name=d.get('name', ""),
            description=d.get('description', ""),
            day_offset=d.get('day_offset', 0),
            hour=d.get('hour', 0),
            minute=d.get('minute', 0),
            volume=d.get('volume', 0.0)
        )
        db.session.add(new_task)
        db.session.commit()
        v = increment_version()
        return jsonify({
            'status': 'ok',
            'version': v,
            'task': {
                'id': new_task.id,
                'regimen_id': new_task.regimen_id,
                'name': new_task.name,
                'description': new_task.description,
                'day_offset': new_task.day_offset,
                'hour': new_task.hour,
                'minute': new_task.minute,
                'volume': new_task.volume
            }
        })

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

    # GET => Filtrar tareas solo del régimen seleccionado
    regimen_id = request.args.get('regimen_id')
    if not regimen_id:
        return jsonify([])  # Si no hay regimen_id, devolver lista vacía

    tasks = Task.query.filter_by(regimen_id=int(regimen_id)).all()
    return jsonify([{
        'id': t.id,
        'regimen_id': t.regimen_id,
        'name': t.name,
        'description': t.description,
        'day_offset': t.day_offset,
        'hour': t.hour,
        'minute': t.minute,
        'volume': t.volume
    } for t in tasks])




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
            # Actualizar valores si la planta ya existe
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
            # Verificar si el nombre ya existe
            existing_plant = Plant.query.filter_by(name=data.get("name")).first()
            if existing_plant:
                return jsonify({"error": "El nombre de la planta ya existe"}), 400

            # Crear nueva planta
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
    data = request.json
    plant_id = data.get("id")
    volumen = data.get("volumen")

    if not plant_id or not volumen:
        return jsonify({"error": "Faltan parámetros: id y volumen"}), 400

    try:
        # Enviar solicitud al NodeMCU

        url = f"http://{NODEMCU_IP}/regar?id={plant_id}&vol={volumen}"
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return jsonify({"mensaje": f"Riego ejecutado para planta {plant_id}"})
        else:
            return jsonify({"error": f"NodeMCU respondió con código {response.status_code}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/status', methods=['GET'])
def handle_status():

    # Datos locales de la BD
    pid = PIDConfig.query.first() or PIDConfig()
    ver = Version.query.order_by(Version.id.desc()).first()

    # Datos del NodeMCU
    node_data = {}
    debug_log = ""

    try:
        response = requests.get(f"{NODEMCU_IP}/status", timeout=3)  # 🔥 Asegurar que usa la URL completa correctamente
        print(response)
        if response.status_code == 200:
            node_data = response.json()
            debug_log = node_data.get('debugLog', 'No debug log available')

    except Exception as e:
        debug_log = f"Error retrieving NodeMCU status: {str(e)}"
        print(debug_log)
    # Combinar toda la información
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
            'servoAngle': node_data.get('servoAngle', 0),
            'servo1': node_data.get('servo1', '?'),
            'servo2': node_data.get('servo2', '?'),
            'tasksRunning': node_data.get('tasksRunning', False),
            'debugLog': debug_log
        }
    })


# ================ /api/esp_status => Mantener endpoint existente ================
@app.route('/api/esp_status', methods=['GET'])
def esp_status():
    """Endpoint independiente para solo datos del NodeMCU"""
    try:
        node_ip = NODEMCU_IP
        r = requests.get(f"http://{node_ip}/status", timeout=5)
        return r.text, r.status_code, {'Content-Type': 'application/json'}
    except Exception as e:
        return jsonify({'error': str(e), 'debugLog': ''}), 500

@app.route('/api/push_config', methods=['POST'])
def push_config():
    """
    Envía al NodeMCU un JSON que contiene:
      - version: la versión actual del servidor.
      - pid_config: los parámetros del PID.
      - tasks: la lista de tareas global, donde cada tarea incluye:
          - task_id, regimen_id, task_name, task_description,
          - day_offset, hour, minute, volume, executed,
          - plant_id, plant_name, servo1pos, servo2pos.
    """
    print("Intentando enviar configuración (versión, PID y tareas con info de planta) al NodeMCU")
    try:
        # Dirección del NodeMCU (ajusta si es necesario)
        node_ip = NODEMCU_IP  # Ejemplo: "http://192.168.100.208"
        url = f"http://{node_ip}/config"
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
        # Se recorre la lista de plantas para agregar, por cada una, las tareas asociadas a su régimen.
        plants = Plant.query.all()
        for plant in plants:
            if not plant.regimen_id:
                continue
            regimen = Regimen.query.get(plant.regimen_id)
            if not regimen:
                continue
            # Obtener todas las tareas asociadas al régimen de la planta
            regimen_tasks = Task.query.filter_by(regimen_id=regimen.id).all()
            for t in regimen_tasks:
                tasks_list.append({
                    "task_id": t.id,
                    "regimen_id": regimen.id,
                    "task_name": t.name,
                    "task_description": t.description,
                    "day_offset": t.day_offset,  # Se utiliza el valor tal cual está en la BD
                    "hour": t.hour,
                    "minute": t.minute,
                    "volume": t.volume,
                    "executed": False,  # Se envía como False (o según el valor en la BD)
                    "plant_id": plant.id,
                    "plant_name": plant.name,
                    "servo1pos": plant.servo1pos,
                    "servo2pos": plant.servo2pos
                })
        print("Tareas a enviar:", tasks_list)

        # Armar el JSON final
        data = {
            "version": serverVer,
            "pid_config": pid_config,
            "tasks": tasks_list
        }
        print("JSON a enviar:", data)

        # Enviar el JSON al NodeMCU vía POST
        r = requests.post(url, json=data, timeout=5)
        print("Respuesta del NodeMCU:", r.text)

        if r.status_code == 200:
            return jsonify({'msg': 'Push config ok', 'node_resp': r.text}), 200
        else:
            return jsonify({'error': 'NodeMCU error', 'code': r.status_code, 'resp': r.text}), 500

    except Exception as e:
        print("Excepción en push_config:", str(e))
        return jsonify({'error': str(e)}), 500


@app.route('/api/task_timeline', methods=['GET'])
def task_timeline():
    """
    Devuelve una lista completa de tareas ordenadas por fecha, considerando todas las plantas y regímenes.
    """
    tasks_timeline = []

    plants = Plant.query.all()
    for plant in plants:
        # Si una planta no tiene régimen, no podemos asignarle tareas.
        if not plant.regimen_id:
            continue

        regimen = Regimen.query.get(plant.regimen_id)
        if not regimen:
            continue  # Si el régimen no existe, pasamos a la siguiente planta.

        # Obtener todas las tareas asociadas al régimen de la planta
        regimen_tasks = Task.query.filter_by(regimen_id=regimen.id).all()

        for task in regimen_tasks:
            try:
                # Calcular la fecha de ejecución de la tarea
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

    # Ordenar por fecha de ejecución ascendente
    tasks_timeline.sort(key=lambda x: x['date'])

    return jsonify(tasks_timeline)


# ================ Manejo de Errores ================
@app.errorhandler(404)
def not_found(e):
    return make_response(jsonify({'error':'Not found'}),404)

@app.errorhandler(400)
def bad_request(e):
    return make_response(jsonify({'error':'Bad request'}),400)

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return make_response(jsonify({'error':'Server error'}),500)


@app.route('/')
def serve_index():
    return render_template('index.html')


if __name__=='__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)
