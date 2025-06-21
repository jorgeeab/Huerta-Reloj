import time
import numpy as np
import serial
import threading
from simple_pid import PID
import pybullet as p
import pybullet_data
import math

# Conexión a PyBullet
p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)

# Cargar el plano y el modelo URDF del robot
planeId = p.loadURDF("plane.urdf")
robotId = p.loadURDF("Reloj_1_description/urdf/Reloj_1.xacro", [0, 0, 0.01], useFixedBase=True)


# Crear sliders para controlar los joints
slider_revolucion = p.addUserDebugParameter("Revolución", 0, 360, 0)
slider_corredera = p.addUserDebugParameter("Corredera", 0, 1000, 0)

# Índices de los joints
revolucion_joint_index = 0
corredera_joint_indices = [1, 2, 4, 5]

def move_joints(robot_id, joint_indices, target_positions, max_force=10.0):
    """ Mover múltiples joints a posiciones objetivo simultáneamente """
    for joint_index, target_position in zip(joint_indices, target_positions):
        p.setJointMotorControl2(
            bodyIndex=robot_id,
            jointIndex=joint_index,
            controlMode=p.POSITION_CONTROL,
            targetPosition=target_position,
            force=max_force
        )

class WaterFlowSensor:
    def __init__(self, relationship_factor):
        self.relationship_factor = relationship_factor

    def read_flow_rate(self, valve_position):
        return valve_position * self.relationship_factor

class SimulatedDCMotor:
    def __init__(self, motor_name):
        self.motor_name = motor_name
        self.speed = 0
        self.position = 0

    def set_speed(self, speed):
        self.speed = speed

    def run(self, speed):
        self.position += speed

    def stop(self):
        self.speed = 0

    def get_position(self):
        return self.position

class PyBulletDCMotor:
    def __init__(self, robot_id, joint_index):
        self.robot_id = robot_id
        self.joint_index = joint_index

    def set_speed(self, speed):
        p.setJointMotorControl2(self.robot_id, self.joint_index, p.VELOCITY_CONTROL, targetVelocity=speed)

    def set_position(self, position):
        p.setJointMotorControl2(self.robot_id, self.joint_index, p.POSITION_CONTROL, targetPosition=position)

    def get_position(self):
        joint_state = p.getJointState(self.robot_id, self.joint_index)
        return joint_state[0]

class RobotController:
    def __init__(self):
        self.pid_angle = PID(1, 1, 0.2, setpoint=0)
        self.pid_corredera = PID(1, 1, 0.2, setpoint=0)
        self.pid_valvula = PID(15, 0, 0, setpoint=0)
        self.water_sensor = WaterFlowSensor(relationship_factor=1.0)

        self.motor_angle = PyBulletDCMotor(robotId, revolucion_joint_index)
        self.motores_corredera = [PyBulletDCMotor(robotId, i) for i in corredera_joint_indices]
        self.motor_valvula = SimulatedDCMotor("MotorV")

        self.servoH = SimulatedDCMotor("ServoH")
        self.servoV = SimulatedDCMotor("ServoV")

        self.lastUpdateTimeDatos = 0
        self.updateIntervalDatos = 300

        self.A_Requerido = 0
        self.X_Requerido = 0
        self.Vel_Requerida = 0

        self.modoManual = False
        self.manualMotorA = 0
        self.manualMotorX = 0
        self.manualMotorV = 0

    def recibir_datos(self, comando):
        try:
            params = comando.split(',')
            if params[0] == 'reset':
                self.setup()
                return

            anguloH = int(params[0])
            anguloV = int(params[1])
            self.servoH.set_speed(anguloH)
            self.servoV.set_speed(anguloV)

            self.Vel_Requerida = float(params[2])
            self.A_Requerido = float(params[3])
            self.X_Requerido = float(params[4])

            self.pid_valvula.tunings = (float(params[5]), float(params[6]), float(params[7]))
            self.pid_angle.tunings = (float(params[8]), float(params[9]), float(params[10]))
            self.pid_corredera.tunings = (float(params[11]), float(params[12]), float(params[13]))

            calibrar = int(params[14])
            if calibrar == 1:
                self.calibrate_compass()

            self.modoManual = params[15] == "1"
            if self.modoManual:
                self.manualMotorA = int(params[16])
                self.manualMotorX = int(params[17])
                self.manualMotorV = int(params[18])
                self.controlar_motores_manual()

            if len(params) > 19:
                self.water_sensor.relationship_factor = float(params[19])
        except ValueError as e:
            print(f"Error processing command: {comando} - {e}")

    def enviar_datos(self):
        current_time = time.time()
        if current_time - self.lastUpdateTimeDatos >= self.updateIntervalDatos / 1000.0:
            self.lastUpdateTimeDatos = current_time

            anguloHActual = self.servoH.get_position()
            anguloVActual = self.servoV.get_position()
            inputAActual = self.motor_angle.get_position()
            inputXActual = self.motores_corredera[0].get_position()
            inputVActual = self.water_sensor.read_flow_rate(self.motor_valvula.get_position())

            datos = f"V,{anguloHActual},{anguloVActual},{inputVActual},{inputAActual},{inputXActual},{self.Vel_Requerida},{self.A_Requerido},{self.X_Requerido},{self.pid_valvula.Kp},{self.pid_valvula.Ki},{self.pid_valvula.Kd},{self.pid_angle.Kp},{self.pid_angle.Ki},{self.pid_angle.Kd},{self.pid_corredera.Kp},{self.pid_corredera.Ki},{self.pid_corredera.Kd},{self.water_sensor.relationship_factor}"

            print(datos)
            if self.serial_connection and self.serial_connection.ser:
                self.serial_connection.ser.write(f"{datos}\n".encode())

    def read_encoder(self, motor):
        return motor.get_position()

    def calibrate_compass(self):
        print("Calibrating compass...")
        time.sleep(2)
        print("Compass calibrated.")

    def controlar_motores_manual(self):
        self.motor_angle.set_speed(self.manualMotorA)
        for motor in self.motores_corredera:
            motor.set_speed(self.manualMotorX)
        self.motor_valvula.set_speed(self.manualMotorV)

    def actualizar_controladores(self, dt):
        if not self.modoManual:
            inputA = self.read_encoder(self.motor_angle)
            self.pid_angle.setpoint = self.A_Requerido
            outputA = self.pid_angle(inputA)
            self.motor_angle.set_speed(self.map_output(outputA))

            inputX = self.read_encoder(self.motores_corredera[0])
            self.pid_corredera.setpoint = self.X_Requerido
            outputX = self.pid_corredera(inputX)
            for motor in self.motores_corredera:
                motor.set_speed(self.map_output(outputX))

            inputV = self.water_sensor.read_flow_rate(self.motor_valvula.get_position())
            self.pid_valvula.setpoint = self.Vel_Requerida
            outputV = self.pid_valvula(inputV)
            self.motor_valvula.set_speed(self.map_output(outputV))

        self.enviar_datos()

    def map_output(self, output):
        if output > 0:
            return np.clip(output, 70, 255)
        elif output < 0:
            return np.clip(output, -255, -70)
        return 0

    def setup(self):
        self.calibrate_compass()
        print("Setup complete.")

    def controlar_desde_sliders(self):
        # Leer y convertir valores de sliders a posiciones o velocidades
        target_position_revolucion = math.radians(p.readUserDebugParameter(slider_revolucion))
        target_position_corredera = -(p.readUserDebugParameter(slider_corredera) / 1000.0) * 0.2

        # Usar los métodos de PyBulletDCMotor para aplicar estas posiciones
        self.motor_angle.set_position(target_position_revolucion)
        for motor in self.motores_corredera:
            motor.set_position(target_position_corredera)

class VirtualSerialRobot:
    def __init__(self, port='COM1', baudrate=115200):
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

    def loop(self):
        dt = 1.0 / 240.0  # Tiempo de paso en segundos
        while True:
            if self.ser.in_waiting > 0:
                comando = self.ser.readline().decode().strip()
                print(f"Comando recibido: {comando}")
                self.robot_controller.recibir_datos(comando)

            self.robot_controller.actualizar_controladores(dt)
            self.robot_controller.controlar_desde_sliders()
            p.stepSimulation()
            time.sleep(dt)

    def start(self):
        self.robot_controller.setup()
        loop_thread = threading.Thread(target=self.loop)
        loop_thread.start()

# Instanciar el robot virtual y ejecutar el bucle principal en un hilo
virtual_robot = VirtualSerialRobot()
virtual_robot.start()
