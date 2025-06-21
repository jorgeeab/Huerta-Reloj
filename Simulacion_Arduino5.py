import threading
from simple_pid import PID
import math
import json
import time
import numpy as np
import pybullet as p
import pybullet_data
import serial

# Conectar a PyBullet
physicsClient = p.connect(p.GUI)
p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)

planeId = p.loadURDF("plane.urdf")
robot_orientation = p.getQuaternionFromEuler([0, 0, np.pi / 6])
robotId = p.loadURDF("Reloj_1_description/urdf/Reloj_1.xacro", [0, 0, 0.01], useFixedBase=True)

camera_distance = 0.5
camera_yaw = 50
camera_pitch = -30
camera_target_position = [0, 0, 0]
p.resetDebugVisualizerCamera(camera_distance, camera_yaw, camera_pitch, camera_target_position)

silver_color = [192 / 255, 192 / 255, 192 / 255, 1]
light_beige_color = [245 / 255, 245 / 255, 220 / 255, 1]
dark_gray_color = [50 / 255, 50 / 255, 50 / 255, 1]

arm_indices = [ 1, 2, 3, 4, 5]
motor_box_index = 6
base_index = 0

def change_joint_color(robot_id, joint_indices, color):
    for joint_index in joint_indices:
        p.changeVisualShape(robot_id, joint_index, rgbaColor=color)

change_joint_color(robotId, arm_indices, silver_color)
change_joint_color(robotId, [motor_box_index], light_beige_color)
p.changeVisualShape(robotId, -1, rgbaColor=dark_gray_color)

revolucion_joint_index = 0
corredera_joint_indices = [1, 2, 4, 5]
p.changeDynamics(robotId, 0,
                 lateralFriction=10.0,  # Aumentar la fricción
                 jointDamping=10.0)    # Aumentar el damping aún más
for joint in corredera_joint_indices:
    p.changeDynamics(robotId, joint,
                     lateralFriction=10.0,  # Aumentar la fricción
                     jointDamping=10.0)  # Aumentar el damping aún más

rad_to_deg = 180 / math.pi
deg_to_rad = math.pi / 180

def map_position_to_cm(position):
    min_position = 0.0
    max_position = -0.2
    min_cm = 0
    max_cm = 400
    return round(((position - min_position) / (max_position - min_position)) * (max_cm - min_cm) + min_cm, 2)

def map_position_to_deg(position):
    return round(position * rad_to_deg, 2)

class PyBulletDCMotor:
    def __init__(self, robot_id, joint_index):
        self.robot_id = robot_id
        self.joint_index = joint_index
        self.lower_limit_deg = 0
        self.upper_limit_deg = 300

    def set_torque(self, torque):
        p.setJointMotorControl2(self.robot_id, self.joint_index, p.TORQUE_CONTROL, force=round(torque, 2))

    def get_position(self):
        joint_state = p.getJointState(self.robot_id, self.joint_index)
        return joint_state[0]

    def reset_position(self):
        p.resetJointState(self.robot_id, self.joint_index, targetValue=0)

    def set_position_limits(self, lower_deg, upper_deg):
        self.lower_limit_deg = lower_deg
        self.upper_limit_deg = upper_deg
        lower_rad = lower_deg * deg_to_rad
        upper_rad = upper_deg * deg_to_rad
        p.changeDynamics(self.robot_id, self.joint_index, jointLowerLimit=lower_rad, jointUpperLimit=upper_rad)

    def enforce_limits(self):
        current_position = self.get_position()
        if current_position < self.lower_limit_deg * deg_to_rad:
            p.resetJointState(self.robot_id, self.joint_index, self.lower_limit_deg * deg_to_rad)
        elif current_position > self.upper_limit_deg * deg_to_rad:
            p.resetJointState(self.robot_id, self.joint_index, self.upper_limit_deg * deg_to_rad)

class ValveActuator:
    def __init__(self, robot_id, joint_index, max_spheres=100):
        self.robot_id = robot_id
        self.joint_index = joint_index
        self.max_spheres = max_spheres
        self.sphere_radius = 0.001
        self.sphere_mass = 0.001
        self.sphere_collision = p.createCollisionShape(p.GEOM_SPHERE, radius=self.sphere_radius)
        self.sphere_visual = p.createVisualShape(p.GEOM_SPHERE, radius=self.sphere_radius, rgbaColor=[0, 0, 1, 1])
        self.generated_spheres = []
        self.last_sphere_time = 0

    def generate_spheres(self, rate, simulation_time):
        interval = 1.0 / rate
        if simulation_time - self.last_sphere_time >= interval:
            self.last_sphere_time = simulation_time
            joint_state = p.getLinkState(self.robot_id, self.joint_index, computeForwardKinematics=True)
            pos = joint_state[0]
            ori = joint_state[1]
            rot_matrix = p.getMatrixFromQuaternion(ori)
            rot_matrix = np.array(rot_matrix).reshape(3, 3)
            yaw_matrix = np.array([
                [np.cos(np.pi / 6), -np.sin(np.pi / 6), 0],
                [np.sin(np.pi / 6), np.cos(np.pi / 6), 0],
                [0, 0, 1]
            ])
            combined_rot_matrix = np.dot(rot_matrix, yaw_matrix)
            distance_from_center = -0.2
            relative_pos = np.array([0.0, distance_from_center, -0.03])
            global_pos = np.dot(combined_rot_matrix, relative_pos) + np.array(pos)

            if len(self.generated_spheres) < self.max_spheres:
                sphere_id = p.createMultiBody(baseMass=self.sphere_mass, baseCollisionShapeIndex=self.sphere_collision,
                                              baseVisualShapeIndex=self.sphere_visual, basePosition=global_pos)
                self.generated_spheres.append(sphere_id)
            else:
                sphere_id = self.generated_spheres.pop(0)
                p.resetBasePositionAndOrientation(sphere_id, global_pos, [0, 0, 0, 1])
                self.generated_spheres.append(sphere_id)

        for sphere_id in self.generated_spheres:
            contact_points = p.getContactPoints(bodyA=sphere_id, bodyB=planeId)
            if contact_points:
                p.removeBody(sphere_id)
                self.generated_spheres.remove(sphere_id)

    def set_speed(self, speed, simulation_time):
        max_rate = 10.0
        min_rate = 1.0
        rate = np.clip(speed, -255, 255) * (max_rate - min_rate) / 255 + min_rate
        self.generate_spheres(round(rate, 2), simulation_time)

class WaterFlowSensor:
    def __init__(self, relationship_factor):
        self.relationship_factor = relationship_factor
        self.max_flow_rate = 1718071988.34

    def read_flow_rate(self, valve_position):
        raw_flow_rate = valve_position * self.relationship_factor
        return round(self.map_flow_to_100(raw_flow_rate), 2)

    def map_flow_to_100(self, flow_rate):
        return (flow_rate / self.max_flow_rate) * 100

class RobotController:
    def __init__(self):
        # PID
        self.pid_angle_Kp = 1
        self.pid_angle_Ki = 1
        self.pid_angle_Kd = 0.2
        self.pid_corredera_Kp = 1
        self.pid_corredera_Ki = 1
        self.pid_corredera_Kd = 0.2
        self.pid_valvula_Kp = 15
        self.pid_valvula_Ki = 0
        self.pid_valvula_Kd = 0

        self.pid_angle = PID(self.pid_angle_Kp, self.pid_angle_Ki, self.pid_angle_Kd, setpoint=0)
        self.pid_corredera = PID(self.pid_corredera_Kp, self.pid_corredera_Ki, self.pid_corredera_Kd, setpoint=0)
        self.pid_valvula = PID(self.pid_valvula_Kp, self.pid_valvula_Ki, self.pid_valvula_Kd, setpoint=0)

        self.water_sensor = WaterFlowSensor(relationship_factor=1.0)

        self.angle_lower_limit_deg = 0
        self.angle_upper_limit_deg = 300

        self.motor_angle = PyBulletDCMotor(robotId, revolucion_joint_index)
        self.motor_angle.set_position_limits(self.angle_lower_limit_deg, self.angle_upper_limit_deg)
        self.motores_corredera = [PyBulletDCMotor(robotId, i) for i in corredera_joint_indices]
        self.motor_valvula = ValveActuator(robotId, corredera_joint_indices[-1], max_spheres=100)

        self.simulation_time = 0
        self.lastUpdateTimeDatos = 0
        self.updateIntervalDatos = 300

        self.A_Requerido = 0
        self.X_Requerido = 0
        self.Vel_Requerida = 0

        self.modoManual = False
        self.manualMotorA = 0
        self.manualMotorX = 0
        self.manualMotorV = 0

        self.calibrating = False

        self.anguloHActual = 0
        self.anguloVActual = 0
        self.inputAActual = 0
        self.inputXActual = 0
        self.inputVActual = 0

        # Variables globales similares al Arduino
        self.stepsPerMM = 1   # Escala para convertir mm a pasos (ejemplo)
        self.stepsPerDegree = 1# Escala para convertir grados a pasos (ejemplo)
        self.flowCalibFactor = 1.0   # Factor de calibración de flujo

        # Variables para reset
        self.resetX = False
        self.resetA = False
        self.XLimit_State = 0
        self.ALimit_State = 0
        self.volumen = 0.0
        self.flow = 0.0

    def actualizar_controladores(self, dt, simulation_time):
        self.simulation_time = simulation_time

        if self.resetX or self.resetA:
            self.controlar_motores_reset()
            return

        if self.calibrating:
            return

        if self.modoManual:
            for motor in self.motores_corredera:
                motor.set_torque(self.manualMotorX)
            self.motor_angle.set_torque(self.manualMotorA)
            self.motor_valvula.set_speed(self.manualMotorV, self.simulation_time)
        else:
            # Lecturas base
            inputX_medido = map_position_to_cm(self.motores_corredera[0].get_position())
            inputA_medido = map_position_to_deg(self.motor_angle.get_position()) % 360

            # Aplicar stepsPerMM y stepsPerDegree para simular lógica Arduino
            # Por ejemplo, podemos convertir la medición a "pasos"
            # inputX en pasos = inputX_medido (en cm) * stepsPerMM
            # inputA en pasos = inputA_medido (en grados) * stepsPerDegree
            # Si prefieres mantener cm y grados, puedes no multiplicar, pero la idea es ejemplificar
            inputX = (inputX_medido * self.stepsPerMM) # convierte cm a pasos
            inputA = (inputA_medido * self.stepsPerDegree) # convierte grados a pasos

            self.pid_corredera.setpoint = self.X_Requerido * self.stepsPerMM
            outputX = self.pid_corredera(inputX)
            for motor in self.motores_corredera:
                motor.set_torque(-outputX)

            self.pid_angle.setpoint = self.A_Requerido * self.stepsPerDegree
            outputA = self.pid_angle(inputA)
            self.motor_angle.set_torque(outputA)

            self.motor_angle.enforce_limits()

            self.motor_valvula.set_speed(self.Vel_Requerida, self.simulation_time)

        # Actualizar lecturas finales
        # inputXActual e inputAActual las guardamos en cm y grados reales, no en pasos
        self.inputXActual = map_position_to_cm(self.motores_corredera[0].get_position())
        self.inputAActual = map_position_to_deg(self.motor_angle.get_position()) % 360

        # Lectura del flujo calibrado
        # si tuviéramos un valor raw_flow, podríamos multiplicar por flowCalibFactor
        # aquí simplemente usaremos el sensor actual
        raw_flow = self.water_sensor.read_flow_rate(self.motor_valvula.last_sphere_time)
        self.inputVActual = raw_flow * self.flowCalibFactor

    def controlar_motores_reset(self):
        # Modo manual al hacer reset
        self.modoManual = True

        # Simular movimiento hacia el límite
        if self.resetX:
            if self.XLimit_State == 0:
                self.manualMotorX = -100
            else:
                self.manualMotorX = 0
                self.resetX = False
            for motor in self.motores_corredera:
                motor.set_torque(self.manualMotorX)

        if self.resetA:
            if self.ALimit_State == 0:
                self.manualMotorA = -100
            else:
                self.manualMotorA = 0
                self.resetA = False
            self.motor_angle.set_torque(self.manualMotorA)

        self.motor_valvula.set_speed(self.manualMotorV, self.simulation_time)

    def enviar_datos(self):
        """
        Envía los datos al entorno en el formato exacto esperado, encapsulados en '<>' (21 valores).
        inputX, inputA, volumen, flow, XLimit_State, ALimit_State, calibrandoX, calibrandoA,
        EMX, EMA, EMV, modoManual, kpX, kiX, kdX, kpA, kiA, kdA, stepsPerMM, stepsPerDegree, flowCalibFactor
        """
        if hasattr(self, 'serial_connection') and self.serial_connection.ser and self.serial_connection.ser.is_open:
            try:
                inputX = self.inputXActual
                inputA = self.inputAActual
                # volumen y flow pueden mantenerse en 0 o calcularse
                volumen = self.volumen
                flow = self.flow
                XLimit_State = self.XLimit_State
                ALimit_State = self.ALimit_State
                calibrandoX = 0
                calibrandoA = 0
                EMX = 0.0
                EMA = 0.0
                EMV = 0.0
                modoManual = 1 if self.modoManual else 0
                kpX = self.pid_corredera_Kp
                kiX = self.pid_corredera_Ki
                kdX = self.pid_corredera_Kd
                kpA = self.pid_angle_Kp
                kiA = self.pid_angle_Ki
                kdA = self.pid_angle_Kd

                datos = [
                    round(inputX, 2),
                    round(inputA, 2),
                    round(volumen, 2),
                    round(flow, 2),
                    int(XLimit_State),
                    int(ALimit_State),
                    int(calibrandoX),
                    int(calibrandoA),
                    round(EMX, 2),
                    round(EMA, 2),
                    round(EMV, 2),
                    int(modoManual),
                    round(kpX, 2),
                    round(kiX, 2),
                    round(kdX, 2),
                    round(kpA, 2),
                    round(kiA, 2),
                    round(kdA, 2),
                    round(self.stepsPerMM, 2),
                    round(self.stepsPerDegree, 2),
                    round(self.flowCalibFactor, 2)
                ]

                data_str = '<' + ','.join(map(str, datos)) + '>\n'
                self.serial_connection.write_with_retries(data_str.encode())
                print(f"Datos enviados: {data_str}")
            except Exception as e:
                print(f"Error al enviar datos: {e}")
        else:
            print("Error: Conexión serial no disponible.")

    def recibir_datos(self, comando):
        """
        Procesa los datos recibidos del entorno, sin encapsulación '<>'.
        """
        try:
            valores = comando.strip().split(',')

            if len(valores) != 20:
                print(f"Error: Número incorrecto de valores recibidos: {comando}")
                return

            self.modoManual = int(np.clip(int(valores[0]), 0, 1))
            self.manualMotorA = int(np.clip(int(valores[1]), -255, 255))
            self.manualMotorX = int(np.clip(int(valores[2]), -255, 255))
            self.manualMotorV = int(np.clip(int(valores[3]), -255, 255))
            self.X_Requerido = round(np.clip(float(valores[4]), 0, 400), 2)
            self.A_Requerido = round(np.clip(float(valores[5]), 0, 360), 2)
            self.Vel_Requerida = round(np.clip(float(valores[6]), 0, 1000), 2)
            self.pid_corredera_Kp = round(np.clip(float(valores[7]), 0, 255), 2)
            self.pid_corredera_Ki = round(np.clip(float(valores[8]), 0, 255), 2)
            self.pid_corredera_Kd = round(np.clip(float(valores[9]), 0, 255), 2)
            self.pid_angle_Kp = round(np.clip(float(valores[10]), 0, 255), 2)
            self.pid_angle_Ki = round(np.clip(float(valores[11]), 0, 255), 2)
            self.pid_angle_Kd = round(np.clip(float(valores[12]), 0, 255), 2)

            reset_volumen = int(np.clip(int(valores[13]), 0, 1))
            reset_motor_x_flag = int(np.clip(int(valores[14]), 0, 1))
            reset_motor_a_flag = int(np.clip(int(valores[15]), 0, 1))

            newStepsPerMM = float(valores[16])
            newStepsPerDegree = float(valores[17])
            newFlowCalibFactor = float(valores[18]) if len(valores) > 18 else 1.0

            # Actualizar calibraciones si no son cero
            if newStepsPerMM != 0:
                self.stepsPerMM = newStepsPerMM
            if newStepsPerDegree != 0:
                self.stepsPerDegree = newStepsPerDegree
            self.flowCalibFactor = newFlowCalibFactor

            # Aplicar nuevos tunings
            self.pid_corredera.SetTunings(self.pid_corredera_Kp, self.pid_corredera_Ki, self.pid_corredera_Kd)
            self.pid_angle.SetTunings(self.pid_angle_Kp, self.pid_angle_Ki, self.pid_angle_Kd)

            if reset_volumen:
                print("Reiniciando volumen.")
                self.reset_volumen()
            if reset_motor_x_flag:
                print("Reiniciando motor X.")
                self.reset_X()
            if reset_motor_a_flag:
                print("Reiniciando motor A.")
                self.reset_A()

            print(f"Datos recibidos correctamente: {comando}")
        except Exception as e:
            print(f"Error al procesar los datos recibidos: {comando} - {e}")

    def simular_calibracion(self):
        max_angle_rad = self.angle_upper_limit_deg * deg_to_rad
        current_angle = self.motor_angle.get_position()

        while current_angle < max_angle_rad:
            self.motor_angle.set_torque(200)
            p.stepSimulation()
            time.sleep(0.01)
            current_angle = self.motor_angle.get_position()

        while current_angle > 0:
            self.motor_angle.set_torque(-200)
            p.stepSimulation()
            time.sleep(0.01)
            current_angle = self.motor_angle.get_position()

        self.motor_angle.set_torque(0)
        self.calibrating = 0

    def reset_volumen(self):
        self.volumen = 0.0
        self.flow = 0.0

    def reset_X(self):
        self.resetX = True

    def reset_A(self):
        self.resetA = True

    def reset_robot(self):
        self.X_Requerido = 0
        self.A_Requerido = 0
        self.Vel_Requerida = 0
        self.manualMotorA = 0
        self.manualMotorX = 0
        self.manualMotorV = 0
        self.modoManual = False
        self.calibrating = False
        self.resetX = False
        self.resetA = False
        self.motor_angle.reset_position()
        for motor in self.motores_corredera:
            motor.reset_position()

    def setup(self):
        print("Setup complete.")


class VirtualSerialRobot:
    def __init__(self, port='COM14', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

        self.simulation_time = 0
        self.start_time = time.time()

        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            print(f"Serial port {port} opened successfully")
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            raise

        # Crear el controlador del robot
        self.robot_controller = RobotController()
        self.robot_controller.serial_connection = self  # Asignar la conexión serial

        self.start_sending_data()

    def start_sending_data(self):
        threading.Thread(target=self.send_data_loop).start()

    def send_data_loop(self):
        interval = 0.3  # 300 ms
        next_time = time.perf_counter() + interval

        while True:
            try:
                self.robot_controller.enviar_datos()
            except Exception as e:
                print(f"Error al enviar datos: {e}")

            now = time.perf_counter()
            sleep_time = max(0, next_time - now)
            time.sleep(sleep_time)
            next_time += interval

    def loop(self):
        """
        Activa el modo de tiempo real para la simulación.
        """
        # Activar simulación en tiempo real
        p.setRealTimeSimulation(1)

        # Mantener el programa activo para recibir datos y enviar acciones
        while True:
            if self.ser.in_waiting > 0:
                # Procesar comandos entrantes
                comando = self.ser.readline().decode().strip()
                print(f"Comando recibido: {comando}")
                self.robot_controller.recibir_datos(comando)

            # Actualizar los controladores según las acciones recibidas
            self.robot_controller.actualizar_controladores(0, self.simulation_time)

            # Enviar los datos al entorno
            self.robot_controller.enviar_datos()

            # Opcional: Agregar un pequeño retraso para evitar un uso excesivo de CPU
            time.sleep(0.1)

    def step(self, dt):
        # Procesar comandos entrantes
        if self.ser.in_waiting > 0:
            comando = self.ser.readline().decode().strip()
            print(f"Comando recibido: {comando}")
            self.robot_controller.recibir_datos(comando)

        # Actualizar controladores
        self.robot_controller.actualizar_controladores(dt, self.simulation_time)

        # Enviar datos al entorno
        self.robot_controller.enviar_datos()

        # Paso de simulación
        p.stepSimulation()

    def start(self):
        self.robot_controller.setup()
        loop_thread = threading.Thread(target=self.loop)
        loop_thread.start()

    def write_with_retries(self, data, retries=3, delay=0.1):
        for attempt in range(retries):
            try:
                self.ser.write(data)
                break
            except serial.serialutil.SerialTimeoutException as e:
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    print(f"Failed to write data after {retries} attempts: {e}")

def test_torque_on_joint(motor=None, initial_torque=1, max_torque=100, step=1):
    """
    Prueba aplicar diferentes niveles de torque a una junta hasta que comience a moverse.
    """
    current_torque = initial_torque

    while current_torque <= max_torque:
        motor.set_torque(current_torque)
        p.stepSimulation()

        joint_position = motor.get_position()

        print(f"Torque: {current_torque}, Position: {joint_position}")

        if abs(joint_position) > 1:
            print(f"Movement started at torque: {current_torque}")
            #break

        current_torque += step
        time.sleep(0.1)
    motor.set_torque(0)

# Creación del robot virtual y arranque del sistema
virtual_robot = VirtualSerialRobot()

# Probar el torque en el motor de rotación (ángulo)
#test_torque_on_joint(virtual_robot.robot_controller.motor_angle, initial_torque=100, max_torque=300, step=1)

virtual_robot.start()
