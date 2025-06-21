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
p.connect(p.GUI)
p.configureDebugVisualizer(p.COV_ENABLE_GUI, 0)  # Ocultar las pestañas de Explorer, Test y Params
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)

# Cargar el plano y el modelo URDF del robot
planeId = p.loadURDF("plane.urdf")
robot_orientation = p.getQuaternionFromEuler([0, 0, np.pi / 6])
robotId = p.loadURDF("Reloj_1_description/urdf/Reloj_1.xacro", [0, 0, 0.01], useFixedBase=True)

# Configurar la cámara para que esté más cerca del robot
camera_distance = 0.5  # Distancia de la cámara al robot
camera_yaw = 50  # Ángulo horizontal de la cámara
camera_pitch = -30  # Ángulo vertical de la cámara
camera_target_position = [0, 0, 0]  # Posición objetivo de la cámara (puede ajustar según la posición del robot)
p.resetDebugVisualizerCamera(camera_distance, camera_yaw, camera_pitch, camera_target_position)

# Colores en formato RGBA
silver_color = [192/255, 192/255, 192/255, 1]
light_beige_color = [245/255, 245/255, 220/255, 1]  # Beige claro
dark_gray_color = [50/255, 50/255, 50/255, 1]  # Gris oscuro

# Índices de las partes del robot
arm_indices = [0, 1, 2, 3, 4, 5]  # Índices de los brazos
motor_box_index = 6  # Índice de la caja del motor
base_index = 0  # índice 0 (Revolución 8)

# Función para cambiar el color de las partes del robot
def change_joint_color(robot_id, joint_indices, color):
    for joint_index in joint_indices:
        p.changeVisualShape(robot_id, joint_index, rgbaColor=color)

# Cambiar el color de los brazos a plateado
change_joint_color(robotId, arm_indices, silver_color)
# motor a beige claro
change_joint_color(robotId, [motor_box_index], light_beige_color)
# base a gris oscuro
p.changeVisualShape(robotId, -1, rgbaColor=dark_gray_color)  # Usamos -1 para cambiar el color del cuerpo base

# Índices de los joints
revolucion_joint_index = 0
corredera_joint_indices = [1, 2, 4, 5]

# Coeficientes de conversión
rad_to_deg = 180 / math.pi
deg_to_rad = math.pi / 180

# Mapeo de posición de la corredera a centímetros
def map_position_to_cm(position):
    min_position = 0.0
    max_position = -0.2
    min_cm = 0
    max_cm = 400
    return ((position - min_position) / (max_position - min_position)) * (max_cm - min_cm) + min_cm

# Mapeo de ángulo de revoluciones a grados
def map_position_to_deg(position):
    return position * rad_to_deg

class PyBulletDCMotor:
    def __init__(self, robot_id, joint_index):
        self.robot_id = robot_id
        self.joint_index = joint_index

        self.lower_limit = 0
        self.upper_limit = 2 * np.pi  # 360 grados = 2*PI radianes, 180 grados = PI radianes

    def set_speed(self, speed):
        max_speed = 0.5
        speed = np.clip(speed, -255, 255) * max_speed / 255
        p.setJointMotorControl2(self.robot_id, self.joint_index, p.VELOCITY_CONTROL, targetVelocity=speed)

    def get_position(self):
        joint_state = p.getJointState(self.robot_id, self.joint_index)
        return joint_state[0]

    def reset_position(self):
        p.resetJointState(self.robot_id, self.joint_index, targetValue=0)

    def set_position_limits(self, lower, upper):
        self.lower_limit = lower
        self.upper_limit = upper
        p.changeDynamics(self.robot_id, self.joint_index, jointLowerLimit=lower, jointUpperLimit=upper)

    def set_position(self, position, max_force=10):
        position = np.clip(position, self.lower_limit, self.upper_limit)
        p.setJointMotorControl2(self.robot_id, self.joint_index, p.POSITION_CONTROL, targetPosition=position, force=max_force)

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
        self.last_sphere_time = time.time()

    def generate_spheres(self, rate):
        interval = 1.0 / rate
        current_time = time.time()
        if current_time - self.last_sphere_time >= interval:
            self.last_sphere_time = current_time
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

    def set_speed(self, speed):
        max_rate = 10.0  # Esferas por segundo
        min_rate = 1.0   # Esferas por segundo
        rate = np.clip(speed, -255, 255) * (max_rate - min_rate) / 255 + min_rate
        self.generate_spheres(rate)

class WaterFlowSensor:
    def __init__(self, relationship_factor):
        self.relationship_factor = relationship_factor
        self.max_flow_rate = 1718071988.3403404  # Valor máximo del flujo de agua

    def read_flow_rate(self, valve_position):
        raw_flow_rate = valve_position * self.relationship_factor
        return self.map_flow_to_100(raw_flow_rate)

    def map_flow_to_100(self, flow_rate):
        return (flow_rate / self.max_flow_rate) * 100

class RobotController:
    def __init__(self):
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

        # Variables para los límites del ángulo
        self.angle_lower_limit = 0
        self.angle_upper_limit = 300 * deg_to_rad  # Convertir a radianes

        self.motor_angle = PyBulletDCMotor(robotId, revolucion_joint_index)
        self.motor_angle.set_position_limits(lower=self.angle_lower_limit, upper=self.angle_upper_limit)  # Limitar el ángulo entre 0 y 300 grados
        self.motores_corredera = [PyBulletDCMotor(robotId, i) for i in corredera_joint_indices]
        self.motor_valvula = ValveActuator(robotId, corredera_joint_indices[-1], max_spheres=100)

        self.lastUpdateTimeDatos = 0
        self.updateIntervalDatos = 300  # Intervalo de 300 milisegundos

        self.A_Requerido = 0
        self.X_Requerido = 0
        self.Vel_Requerida = 0

        self.modoManual = False
        self.manualMotorA = 0
        self.manualMotorX = 0
        self.manualMotorV = 0

        self.calibrating = False

        # Variables de estado actuales
        self.anguloHActual = 0
        self.anguloVActual = 0
        self.inputAActual = 0
        self.inputXActual = 0
        self.inputVActual = 0

    def actualizar_controladores(self, dt):
        if self.calibrating:
            return

        if self.modoManual:
            for motor in self.motores_corredera:
                motor.set_speed(self.manualMotorX)
            self.motor_angle.set_speed(self.manualMotorA)
            self.motor_valvula.set_speed(self.manualMotorV)
        else:
            inputX = map_position_to_cm(self.motores_corredera[0].get_position())
            self.pid_corredera.setpoint = self.X_Requerido
            outputX = self.pid_corredera(inputX)
            for motor in self.motores_corredera:
                motor.set_speed(-outputX)

            inputA = (map_position_to_deg(self.motor_angle.get_position())) % 360
            self.pid_angle.setpoint = self.A_Requerido
            outputA = self.pid_angle(inputA)
            self.motor_angle.set_position(self.motor_angle.get_position() + outputA * dt)

            self.motor_valvula.set_speed(self.Vel_Requerida)

        self.inputXActual = map_position_to_cm(self.motores_corredera[0].get_position())
        self.inputAActual = map_position_to_deg(self.motor_angle.get_position()) % 360
        self.inputVActual = self.water_sensor.read_flow_rate(self.motor_valvula.last_sphere_time)

    def enviar_datos(self):
        sensores = {
            'inputX': self.inputXActual,
            'inputA': self.inputAActual,
            'inputV': self.inputVActual,
            'limite_angulo': int(self.inputAActual <= 0 or self.inputAActual >= 300),
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

        if self.serial_connection and self.serial_connection.ser:
            data_str = json.dumps(datos)
           # print(f"Sending: {data_str}")  # Imprimir lo que se envía
            self.serial_connection.ser.write(data_str.encode() + b'\n')

    def recibir_datos(self, comando):
        try:
            data = json.loads(comando)
            print(f"Received: {comando}")  # Imprimir lo que se recibe
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

                # Actualizar los valores PID en las variables de instancia
                self.pid_angle_Kp, self.pid_angle_Ki, self.pid_angle_Kd = self.pid_angle.tunings
                self.pid_corredera_Kp, self.pid_corredera_Ki, self.pid_corredera_Kd = self.pid_corredera.tunings
                self.pid_valvula_Kp, self.pid_valvula_Ki, self.pid_valvula_Kd = self.pid_valvula.tunings

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {comando} - {e}")

    def simular_calibracion(self):
        # Simular movimiento del actuador del ángulo hasta su máximo y devolverlo al inicio
        max_angle = self.angle_upper_limit  # Valor máximo del ángulo en radianes
        current_angle = self.motor_angle.get_position()

        # Mover al ángulo máximo
        while current_angle < max_angle:
            self.motor_angle.set_speed(50)  # Ajusta la velocidad según sea necesario
            p.stepSimulation()
            time.sleep(0.01)
            current_angle = self.motor_angle.get_position()

        # Devolver al ángulo inicial
        while current_angle > 0:
            self.motor_angle.set_speed(-50)  # Ajusta la velocidad según sea necesario
            p.stepSimulation()
            time.sleep(0.01)
            current_angle = self.motor_angle.get_position()

        self.motor_angle.set_speed(0)
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
    def __init__(self, port='COM11', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            print(f"Serial port {port} opened successfully")
        except serial.SerialException as e:
            print(f"Error opening serial port: {e}")
            raise

        self.robot_controller = RobotController()
        self.robot_controller.serial_connection = self

        self.start_sending_data()

    def start_sending_data(self):
        threading.Thread(target=self.send_data_loop).start()

    def send_data_loop(self):
        while True:
            self.robot_controller.enviar_datos()
            time.sleep(self.robot_controller.updateIntervalDatos / 1000.0)

    def loop(self):
        dt = 1.0 / 240.0
        while True:
            if self.ser.in_waiting > 0:
                comando = self.ser.readline().decode().strip()
                self.robot_controller.recibir_datos(comando)

            self.robot_controller.actualizar_controladores(dt)
            p.stepSimulation()
            time.sleep(dt)

    def start(self):
        self.robot_controller.setup()
        loop_thread = threading.Thread(target=self.loop)
        loop_thread.start()

# Instanciar el robot virtual y ejecutar el bucle principal en un hilo
virtual_robot = VirtualSerialRobot()
virtual_robot.start()
