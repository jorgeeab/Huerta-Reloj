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

arm_indices = [0, 1, 2, 3, 4, 5]
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

rad_to_deg = 180 / math.pi
deg_to_rad = math.pi / 180

def map_position_to_cm(position):
    min_position = 0.0
    max_position = -0.2
    min_cm = 0
    max_cm = 400
    return round(((position - min_position) / (max_position - min_position)) * (max_cm - min_cm) + min_cm, 1)

def map_position_to_deg(position):
    return round(position * rad_to_deg, 2)

def map_torque_to_motor(torque, max_torque):
    return np.clip(round((torque / max_torque) * 255, 1), -255, 255)

class PyBulletDCMotor:
    def __init__(self, robot_id, joint_index, torque_relation=1.0):
        self.robot_id = robot_id
        self.joint_index = joint_index
        self.lower_limit_deg = 0
        self.upper_limit_deg = 300
        self.max_torque = 10 * torque_relation
        p.changeDynamics(self.robot_id, self.joint_index, jointDamping=10.0, lateralFriction=1.0)

    def set_torque(self, torque):
        motor_torque = map_torque_to_motor(torque, self.max_torque)
        p.setJointMotorControl2(self.robot_id, self.joint_index, p.TORQUE_CONTROL, force=motor_torque)

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
        self.generate_spheres(rate, simulation_time)

class WaterFlowSensor:
    def __init__(self, relationship_factor):
        self.relationship_factor = relationship_factor
        self.max_flow_rate = 1718071988.34

    def read_flow_rate(self, valve_position):
        raw_flow_rate = valve_position * self.relationship_factor
        return round(self.map_flow_to_100(raw_flow_rate), 1)

    def map_flow_to_100(self, flow_rate):
        return (flow_rate / self.max_flow_rate) * 100

class RobotController:
    def __init__(self, torque_relation=1.0):
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

        self.motor_angle = PyBulletDCMotor(robotId, revolucion_joint_index, torque_relation=torque_relation)
        self.motor_angle.set_position_limits(self.angle_lower_limit_deg, self.angle_upper_limit_deg)
        self.motores_corredera = [PyBulletDCMotor(robotId, i, torque_relation=torque_relation) for i in corredera_joint_indices]
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

    def actualizar_controladores(self, dt, simulation_time):
        self.simulation_time = simulation_time

        if self.calibrating:
            return

        if self.modoManual:
            for motor in self.motores_corredera:
                motor.set_torque(self.manualMotorX)
            self.motor_angle.set_torque(self.manualMotorA)
            self.motor_valvula.set_speed(self.manualMotorV, self.simulation_time)
        else:
            inputX = map_position_to_cm(self.motores_corredera[0].get_position())
            self.pid_corredera.setpoint = self.X_Requerido
            outputX = self.pid_corredera(inputX)
            for motor in self.motores_corredera:
                motor.set_torque(-outputX)

            inputA = map_position_to_deg(self.motor_angle.get_position()) % 360
            self.pid_angle.setpoint = self.A_Requerido
            outputA = self.pid_angle(inputA)
            self.motor_angle.set_torque(outputA)

            self.motor_angle.enforce_limits()

            self.motor_valvula.set_speed(self.Vel_Requerida, self.simulation_time)

        self.inputXActual = map_position_to_cm(self.motores_corredera[0].get_position())
        self.inputAActual = map_position_to_deg(self.motor_angle.get_position()) % 360
        self.inputVActual = self.water_sensor.read_flow_rate(self.motor_valvula.last_sphere_time)

    def enviar_datos(self):
        if self.serial_connection and self.serial_connection.ser and self.serial_connection.ser.is_open:
            try:
                sensores = {
                    'inputX': self.inputXActual,
                    'inputA': self.inputAActual,
                    'inputV': self.inputVActual,
                    'limite_angulo': int(
                        self.inputAActual <= self.angle_lower_limit_deg or self.inputAActual >= self.angle_upper_limit_deg),
                    'limite_corredera': int(self.inputXActual <= 0),
                    'limite_valvula': int(self.inputVActual <= 0)
                }
                actuadores = {
                    'setpoint_corredera': self.X_Requerido,
                    'setpoint_angle': self.A_Requerido,
                    'setpoint_water': self.Vel_Requerida,
                    'pid_corredera': list(self.pid_corredera.tunings),
                    'pid_angle': list(self.pid_angle.tunings),
                    'pid_valvula': list(self.pid_valvula.tunings),
                    'manual_mode': self.modoManual,
                    'energia_motor_corredera': self.manualMotorX,
                    'energia_motor_angulo': self.manualMotorA,
                    'energia_motor_valvula': self.manualMotorV,
                    'calibrating': self.calibrating
                }
                datos = {'sensores': sensores, 'actuadores': actuadores}

                data_str = json.dumps(datos)
                self.serial_connection.write_with_retries(data_str.encode() + b'\n')
            except Exception as e:
                print(f"Error al enviar datos: {e}")
        else:
            print("Error: Conexión serial no disponible.")

    def recibir_datos(self, comando):
        try:
            if comando.strip() == "reset":
                print("Received reset command.")
                self.reset_robot()
                return

            data = json.loads(comando)
            if 'actuadores' in data:
                actuadores = data['actuadores']
                if 'setpoint_corredera' in actuadores:
                    self.X_Requerido = actuadores['setpoint_corredera']
                if 'setpoint_angle' in actuadores:
                    self.A_Requerido = actuadores['setpoint_angle']
                if 'pid_corredera' in actuadores:
                    self.pid_corredera.tunings = tuple(actuadores['pid_corredera'])
                if 'pid_angle' in actuadores:
                    self.pid_angle.tunings = tuple(actuadores['pid_angle'])
                if 'setpoint_water' in actuadores:
                    self.Vel_Requerida = actuadores['setpoint_water']
                if 'pid_valvula' in actuadores:
                    self.pid_valvula.tunings = tuple(actuadores['pid_valvula'])
                if 'manual_mode' in actuadores:
                    self.modoManual = actuadores['manual_mode']
                if 'energia_motor_corredera' in actuadores:
                    self.manualMotorX = actuadores['energia_motor_corredera']
                if 'energia_motor_angulo' in actuadores:
                    self.manualMotorA = actuadores['energia_motor_angulo']
                if 'energia_motor_valvula' in actuadores:
                    self.manualMotorV = actuadores['energia_motor_valvula']
                if 'calibrating' in actuadores:
                    self.calibrating = actuadores['calibrating']
                    if self.calibrating == 1:
                        self.simular_calibracion()

                self.pid_angle_Kp, self.pid_angle_Ki, self.pid_angle_Kd = self.pid_angle.tunings
                self.pid_corredera_Kp, self.pid_corredera_Ki, self.pid_corredera_Kd = self.pid_corredera.tunings
                self.pid_valvula_Kp, self.pid_valvula_Ki, self.pid_valvula_Kd = self.pid_valvula.tunings

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {comando} - {e}")

    def simular_calibracion(self):
        max_angle_rad = self.angle_upper_limit_deg * deg_to_rad
        current_angle = self.motor_angle.get_position()

        while current_angle < max_angle_rad:
            self.motor_angle.set_torque(50)
            p.stepSimulation()
            time.sleep(0.01)
            current_angle = self.motor_angle.get_position()

        while current_angle > 0:
            self.motor_angle.set_torque(-50)
            p.stepSimulation()
            time.sleep(0.01)
            current_angle = self.motor_angle.get_position()

        self.motor_angle.set_torque(0)
        self.calibrating = 0

    def reset_robot(self):
        self.X_Requerido = 0
        self.A_Requerido = 0
        self.Vel_Requerida = 0
        self.manualMotorA = 0
        self.manualMotorX = 0
        self.manualMotorV = 0
        self.modoManual = False
        self.calibrating = False

        self.motor_angle.reset_position()
        for motor in self.motores_corredera:
            motor.reset_position()

    def setup(self):
        print("Setup complete.")

class VirtualSerialRobot:
    def __init__(self, port='COM11', baudrate=115200, torque_relation=1.0):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.torque_relation = torque_relation
        self.simulation_time = 0
        self.start_time = time.time()

        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            print(f"Serial port {port} opened successfully")
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            raise

        self.robot_controller = RobotController(torque_relation=self.torque_relation)
        self.robot_controller.serial_connection = self

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

            # Espera hasta el siguiente ciclo
            now = time.perf_counter()
            sleep_time = max(0, next_time - now)
            time.sleep(sleep_time)
            next_time += interval

    def loop(self):
        dt = 1.0 / 240.0
        p.setTimeStep(dt)  # Asegurar que el tiempo de paso de la simulación se mantenga constante
        while True:
            real_time_start = time.time()  # Tiempo real al inicio del paso
            self.simulation_time += dt
            self.step(dt)
            real_time_end = time.time()  # Tiempo real al final del paso

            elapsed_real_time = real_time_end - real_time_start  # Tiempo real transcurrido
            if elapsed_real_time < dt:
                time.sleep(dt - elapsed_real_time)  # Pausa para sincronizar el tiempo de simulación con el tiempo real

    def step(self, dt):
        if self.ser.in_waiting > 0:
            comando = self.ser.readline().decode().strip()
            self.robot_controller.recibir_datos(comando)

        self.robot_controller.actualizar_controladores(dt, self.simulation_time)
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

# Creación del robot virtual y arranque del sistema
virtual_robot = VirtualSerialRobot(torque_relation=1.5)
virtual_robot.start()
