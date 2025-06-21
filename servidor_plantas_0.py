from flask import Flask, request, jsonify
from basic_gym_env.basic_env import BasicEnv
from datetime import datetime
from nuevo_plantas import PlantasManager
import time

app = Flask(__name__)

class ServidorFlask:
    def __init__(self):
        # Inicializamos el entorno y el gestor de plantas
        self.env = BasicEnv(port='COM5', baudrate=115200)
        self.manager = PlantasManager()

        # ---- Métodos de Control del Entorno/Robot ----

    def actualizar_acciones(self, data):
        try:
            print("Debug: Ingresando a actualizar_acciones")  # Debug
            print("Debug: Data recibida:", data)  # Debug
            manual_mode = data.get('manual_mode')
            if manual_mode is not None:
                self.env.set_manual_mode(int(manual_mode))
                print(f"Debug: manual_mode actualizado a {manual_mode}")  # Debug

            # Configurar joypad y setpoints
            joypad_action = data.get('joypad_action')
            if joypad_action == 'enable':
                self.env.enable_joypad()
                print("Debug: Joypad habilitado")  # Debug
            elif joypad_action == 'disable':
                self.env.disable_joypad()
                print("Debug: Joypad deshabilitado")  # Debug

            setpoints = data.get('setpoints', {})
            for component, value in setpoints.items():
                if component == 'slide':
                    self.env.set_corredera(value)
                    print(f"Debug: Setpoint slide actualizado a {value}")  # Debug
                elif component == 'angle':
                    self.env.set_angulo(value)
                    print(f"Debug: Setpoint angle actualizado a {value}")  # Debug
                elif component == 'volume':
                    self.env.set_volumen_requerido(value)
                    print(f"Debug: Setpoint volume actualizado a {value}")  # Debug

            self.env.step()  # Realizamos un paso de simulación con la configuración actual
            return jsonify({'status': 'Configuración del entorno actualizada'}), 200
        except Exception as e:
            print(f"Debug: Error en actualizar_acciones - {str(e)}")  # Debug
            return jsonify({'error': f'Error en el servidor: {str(e)}'}), 500

    # Dentro de la clase ServidorFlask, función `obtener_estado_entorno`

    def obtener_estado_entorno(self, data):
        try:
            print("Debug: Ingresando a obtener_estado_entorno")  # Debug
            print("Debug: Data recibida:", data)  # Debug
            detail_level = data.get('detail', 'observation')
            batch_id = int(data.get('batch_id', 1))
            time_limit = data.get('time_limit', None)
            interval = data.get('interval', 1.0)

            if detail_level == 'full':
                state = {
                    'current_action': [float(val) for val in self.env.current_action],
                    'simulation_time': float(self.env.simulation_time),
                    'manual_mode': int(self.env.manual_mode),
                    'execution_data': self.env.get_steps_from_batch(batch_id, time_limit, interval),
                }
                print("Debug: Estado completo obtenido:", state)  # Debug
                return jsonify({'status': 'Success', 'state': state}), 200
            else:
                obs = self.env.get_observation()
                if obs is not None:
                    obs_list = [float(val) for val in obs.tolist()]
                    print("Debug: Observación obtenida:", obs_list)  # Debug
                    return jsonify({'observation': obs_list}), 200
                else:
                    print("Debug: No hay observación disponible")  # Debug
                    return jsonify({'error': 'No hay observación disponible'}), 400
        except Exception as e:
            print(f"Debug: Error en obtener_estado_entorno - {str(e)}")  # Debug
            return jsonify({'error': f'Error en el servidor: {str(e)}'}), 500

    def controlar_entorno(self, data):
        # Definir estructuras esperadas para cada tipo de acción
        action_structures = {
            "start_batch": {
                "required": [],
                "optional": []
            },
            "execute_steps": {
                "required": ["execution_time", "batch_id", "action_code"],
                "optional": []
            },
            "stop": {
                "required": ["batch_id"],
                "optional": []
            },
            "reset": {
                "required": [],
                "optional": []
            }
        }

        action = data.get("action")
        if action not in action_structures:
            return jsonify({
                "error": "Acción inválida",
                "expected_actions": list(action_structures.keys())
            }), 400

        structure = action_structures[action]
        missing_fields = [key for key in structure["required"] if key not in data]

        if missing_fields:
            return jsonify({
                "error": "Datos incompletos para la acción solicitada.",
                "missing_fields": missing_fields,
                "expected_structure": {
                    "action": "str (e.g., 'execute_steps')",
                    **{key: "field type" for key in structure["required"]}
                }
            }), 400

        if action == "start_batch":
            batch_id = self.env.start_batch()
            return jsonify({"status": "Batch iniciado", "batch_id": batch_id}), 200

        elif action == "execute_steps":
            execution_time = data["execution_time"]
            batch_id = data["batch_id"]
            action_code = data["action_code"]
            return self.ejecutar_steps(batch_id, execution_time, action_code)

        elif action == "stop":
            self.detener_motores()
            batch_id = data["batch_id"]
            pasos_ejecutados = self.env.get_steps_from_batch(batch_id)
            return jsonify({'status': 'Ejecución detenida exitosamente', 'batch_data': pasos_ejecutados}), 200

        elif action == "reset":
            self.env.reset()
            return jsonify({'status': 'Entorno reiniciado con éxito'}), 200

    def ejecutar_steps(self, batch_id, execution_time, action_code):
        start_time = time.time()
        self.env.execution_data = []

        while time.time() - start_time < execution_time:
            obs = self.env.get_observation()
            calculated_action = self.custom_action_code(obs, action_code)
            obs, reward, done, info = self.env.step(calculated_action)
            self.env.store_serial_data(sent_data=str(calculated_action), received_data=str(obs))
            time.sleep(0.3)

        pasos_ejecutados = self.env.get_steps_from_batch(batch_id)
        return jsonify({'status': 'Ejecución completada', 'data': pasos_ejecutados}), 200

    def custom_action_code(self, obs, action_code):
        local_variables = {}
        exec(action_code, {}, local_variables)
        if 'custom_action' in local_variables:
            return local_variables['custom_action'](obs)
        else:
            raise ValueError("El código de acción no contiene una función llamada 'custom_action'")

    def detener_motores(self):
        stop_action = self.env.current_action
        stop_action[0] = 1
        stop_action[1] = 0
        stop_action[2] = 0
        stop_action[3] = 0
        self.env.step(stop_action)

    # ---- Métodos de Control de Base de Datos de Plantas ----
    def crear_planta(self, data):
        mensaje = self.manager.crear_planta(
            id_planta=data.get("id_planta"),
            nombre=data.get("nombre"),
            fecha_plantacion=self.parsear_fecha(data.get("fecha_plantacion")),
            angulo_h=data.get("angulo_h"),
            angulo_y=data.get("angulo_y"),
            longitud_slider=data.get("longitud_slider"),
            velocidad_agua=data.get("velocidad_agua"),
            era=data.get("era")
        )
        return jsonify({"mensaje": mensaje})

    def modificar_planta(self, data):
        mensaje = self.manager.modificar_planta(
            id_planta=data.get("id_planta"),
            era=data.get("era"),
            **{k: v for k, v in data.items() if k not in ["accion", "id_planta", "era"]}
        )
        return jsonify({"mensaje": mensaje})

    def eliminar_planta(self, data):
        mensaje = self.manager.eliminar_planta(
            id_planta=data.get("id_planta"),
            era=data.get("era")
        )
        return jsonify({"mensaje": mensaje})

    def ejecutar_accion_plantas(self, data):
        """Determina y ejecuta la acción solicitada para las plantas."""
        accion = data.get("accion")
        if accion == "crear":
            return self.crear_planta(data)
        elif accion == "modificar":
            return self.modificar_planta(data)
        elif accion == "eliminar":
            return self.eliminar_planta(data)
        else:
            return jsonify({"error": "Acción inválida"}), 400

    def ejecutar_accion_entorno(self, data):
        """Determina y ejecuta la acción solicitada para el entorno."""
        accion = data.get("accion")
        if accion == "actualizar_acciones":
            return self.actualizar_acciones(data)
        elif accion == "obtener_estado":
            return self.obtener_estado_entorno(data)
        elif accion == "controlar_entorno":
            return self.controlar_entorno(data)
        else:
            return jsonify({"error": "Acción inválida"}), 400

    @staticmethod
    def parsear_fecha(fecha_str):
        formatos = ['%Y-%m-%d %H:%M', '%Y-%m-%d']
        for formato in formatos:
            try:
                return datetime.strptime(fecha_str, formato)
            except (ValueError, TypeError):
                continue
        return None

# Instancia del servidor
servidor = ServidorFlask()

# ---- Endpoints ----

# ---- Endpoint de Control del Entorno ----
@app.route('/entorno', methods=['POST'])
def manejar_entorno():
    data = request.json
    if not data:
        print("Debug: No se enviaron datos en la solicitud a /entorno")  # Debug
        return jsonify({"error": "No se enviaron datos."}), 400

    accion = data.get("accion")
    print("Debug: Acción solicitada en /entorno:", accion)  # Debug

    if accion == "actualizar_acciones":
        return servidor.actualizar_acciones(data)
    elif accion == "obtener_estado":
        return servidor.obtener_estado_entorno(data)
    elif accion == "controlar_entorno":
        return servidor.controlar_entorno(data)
    else:
        print("Debug: Acción inválida en /entorno")  # Debug
        return jsonify({"error": "Acción inválida"}), 400

@app.route('/plantas', methods=['POST'])
def manejar_plantas():
    data = request.json
    if not data:
        return jsonify({"error": "No se enviaron datos."}), 400
    return servidor.ejecutar_accion_plantas(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
