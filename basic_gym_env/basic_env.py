import matplotlib.pyplot as plt
from nuevo_plantas import PlantasManager
from .tasks_manager import RobotTasksManager
import pygame
import numpy as np
import gym
import serial
import threading
import time
import queue
import csv
import os

class BasicEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, port='COM6', baudrate=115200,
                 archivo_json='data/plants.json',
                 archivo_tareas='data/tasks.json',
                 mode='serial', render=True, logger=None):
        super(BasicEnv, self).__init__()

        self.mode = mode
        self.render = render
        self.logger = logger if logger is not None else print

        # Gestores de datos basados en JSON
        self.plantas_manager = PlantasManager(archivo_json)
        self.tareas_manager = RobotTasksManager(archivo_tareas)

        # Definir espacios de acción y observación
        # Índices de acción alineados con Arduino.procesarComando()
        self.action_space = gym.spaces.Box(
            low=np.array([
                0,      # [0] modoManual
                -255,   # [1] EM_A
                -255,   # [2] EM_X
                -255,   # [3] EM_V
                0,      # [4] X_Requerido
                0,      # [5] A_Requerido
                0,      # [6] Vol_requerido
                0,      # [7] kpX
                0,      # [8] kiX
                0,      # [9] kdX
                0,      # [10] kpA
                0,      # [11] kiA
                0,      # [12] kdA
                0,      # [13] resetVolumen
                0,      # [14] resetMotorXFlag
                0,      # [15] resetMotorAFlag
                0,      # [16] stepsPerMM
                0,      # [17] stepsPerDegree
                0,      # [18] usarLectorVelocidad
                0       # [19] reservado
            ]),
            high=np.array([
                1,       # [0] modoManual
                255,     # [1] EM_A
                255,     # [2] EM_X
                255,     # [3] EM_V
                400,     # [4] X_Requerido
                360,     # [5] A_Requerido
                100000,  # [6] Vol_requerido
                255,     # [7] kpX
                255,     # [8] kiX
                255,     # [9] kdX
                255,     # [10] kpA
                255,     # [11] kiA
                255,     # [12] kdA
                1,       # [13] resetVolumen
                1,       # [14] resetMotorXFlag
                1,       # [15] resetMotorAFlag
                10000,   # [16] stepsPerMM
                10000,   # [17] stepsPerDegree
                1,       # [18] usarLectorVelocidad
                0        # [19] reservado
            ]),
            dtype=np.float32
        )

        self.current_action = np.zeros(20)  # Tamaño ajustado a 20

        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(24,),  # Tamaño ajustado a 24 variables
            dtype=np.float32
        )

        # Inicializar cola de datos y conexión serial
        self.data_queue = queue.Queue()
        self.stop_thread = False
        self.start_time = time.time()

        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.read_thread = None
        # Track attempts to connect to the serial port so we don't spam
        # connection errors when the port is unavailable.
        self.last_serial_attempt = 0
        self.serial_error_logged = False

        if self.mode == 'serial':
            self.connect_serial()
            self.read_thread = threading.Thread(target=self.read_serial)
            self.read_thread.daemon = True
            self.read_thread.start()
        elif self.mode == 'virtual':
            import pybullet as p
            import pybullet_data
            self.p = p
            connection_mode = p.GUI if self.render else p.DIRECT
            p.connect(connection_mode)
            p.setAdditionalSearchPath(pybullet_data.getDataPath())
            p.setGravity(0, 0, -9.8)
            p.loadURDF("plane.urdf")
            robot_path = os.path.join('control_robot',
                                      'Reloj_1_description', 'urdf',
                                      'Reloj_1.xacro')
            self.robotId = p.loadURDF(robot_path, [0, 0, 0.01],
                                      useFixedBase=True)
            self.revolucion_joint_index = 0
            self.corredera_joint_indices = [1, 2, 4, 5]
            self.valve_position = 0.0
            self.last_obs = np.zeros(24, dtype=np.float32)
        else:
            raise ValueError("mode must be 'serial' or 'virtual'")

        self.simulation_time = 0  # Tiempo de simulación
        self.execution_data = []  # Datos de la ejecución actual

        # Nombres de las variables
        self.variable_names = [
            'inputX',           # [0]
            'inputA',           # [1]
            'inputV',           # [2]
            'flowVolume',       # [3]
            'limite_X',         # [4]
            'limite_A',         # [5]
            'calibrando_X',     # [6]
            'calibrando_A',     # [7]
            'manualMotorX',     # [8]
            'manualMotorA',     # [9]
            'manualMotorV',     # [10]
            'modoManual',       # [11]
            'kpX',              # [12]
            'kiX',              # [13]
            'kdX',              # [14]
            'kpA',              # [15]
            'kiA',              # [16]
            'kdA',              # [17]
            'kpV',              # [18]
            'kiV',              # [19]
            'kdV',              # [20]
            'stepsPerMM',       # [21]
            'stepsPerDegree',   # [22]
            'flowCalibFactor'   # [23]
        ]

        # Inicializar pygame y joystick
        pygame.init()
        self.joystick = None
        self.joystick_connected = False
        self.check_joystick_connection()

        # Variable para controlar si el joypad está habilitado
        self.joypad_enabled = False  # Comienza deshabilitado

        # Variable para controlar el modo (0: Automático, 1: Manual)
        self.manual_mode = 0
        self.set_manual_mode(self.manual_mode)

    def connect_serial(self):
        if self.mode != 'serial':
            return False
        if self.ser is not None and self.ser.is_open:
            return True

        # Throttle connection attempts to avoid spamming when the port is busy
        now = time.time()
        if now - self.last_serial_attempt < 2:
            return False
        self.last_serial_attempt = now

        try:
            self.logger(f"Intentando conectar al puerto serial {self.port}")
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.3)
            time.sleep(2)
            self.logger(f"Conectado al puerto serial {self.port}")
            self.serial_error_logged = False
            return True
        except serial.SerialException as e:
            if not self.serial_error_logged:
                self.logger(f"Error al conectar al puerto serial: {e}")
                self.serial_error_logged = True
            self.ser = None
            return False

    def disconnect_serial(self):
        """Cerrar la conexión serial actual si está abierta."""
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
            self.logger("Desconectado del puerto serial")
        self.serial_error_logged = False

    def change_port(self, new_port):
        """Cambiar de puerto y reconectar."""
        self.logger(f"Cambiando puerto serial a {new_port}")
        self.port = new_port
        if self.mode == 'serial':
            self.disconnect_serial()
            self.last_serial_attempt = 0
            self.connect_serial()

    def read_serial(self):
        if self.mode != 'serial':
            return
        buffer = ''
        while not self.stop_thread:
            if self.ser is None or not self.ser.is_open:
                time.sleep(1)
                continue
            try:
                data = self.ser.read(self.ser.in_waiting or 1).decode('utf-8', errors='replace')
                if data:
                    buffer += data
                    while '<' in buffer and '>' in buffer:
                        start = buffer.find('<')
                        end = buffer.find('>', start)
                        if end == -1:
                            break
                        line = buffer[start + 1:end]
                        buffer = buffer[end + 1:]
                        self.process_serial_line(line)
            except serial.SerialException as e:
                self.logger(f"Serial read error: {e}")
                self.ser = None
            except Exception as e:
                self.logger(f"Unexpected error: {e}")

    def process_serial_line(self, line):
        self.logger(f"Arduino: {line}")
        values = line.strip().split(',')

        if len(values) not in (21, 24):
            self.logger(f"Error: expected 21 or 24 values, got {len(values)}")
            return

        try:
            if len(values) == 21:
                inputX = float(values[0])
                inputA = float(values[1])
                flowVolume = float(values[2])
                flowRate = float(values[3])
                limite_X = int(float(values[4]))
                limite_A = int(float(values[5]))
                calibrando_X = int(float(values[6]))
                calibrando_A = int(float(values[7]))
                manualMotorX = float(values[8])
                manualMotorA = float(values[9])
                manualMotorV = float(values[10])
                modoManual = int(float(values[11]))
                kpX = float(values[12])
                kiX = float(values[13])
                kdX = float(values[14])
                kpA = float(values[15])
                kiA = float(values[16])
                kdA = float(values[17])
                stepsPerMM = float(values[18])
                stepsPerDegree = float(values[19])
                flowCalibFactor = float(values[20])

                inputV = manualMotorV
            else:
                raise ValueError("Formato de 24 valores no implementado en Arduino actual")

            obs = np.array([
                inputX,            # [0]
                inputA,            # [1]
                inputV,            # [2]
                flowVolume,        # [3]
                limite_X,          # [4]
                limite_A,          # [5]
                calibrando_X,      # [6]
                calibrando_A,      # [7]
                manualMotorX,      # [8]
                manualMotorA,      # [9]
                manualMotorV,      # [10]
                modoManual,        # [11]
                kpX,               # [12]
                kiX,               # [13]
                kdX,               # [14]
                kpA,               # [15]
                kiA,               # [16]
                kdA,               # [17]
                0.0,               # [18] kpV (no disponible)
                0.0,               # [19] kiV
                0.0,               # [20] kdV
                stepsPerMM,        # [21]
                stepsPerDegree,    # [22]
                flowCalibFactor    # [23]
            ], dtype=np.float32)

            self.data_queue.put(obs)
        except Exception as e:
            self.logger(f"process_serial_line error: {e}")

    def check_joystick_connection(self):
        pygame.joystick.quit()
        pygame.joystick.init()
        joystick_count = pygame.joystick.get_count()
        if joystick_count > 0:
            if not self.joystick_connected:
                self.joystick = pygame.joystick.Joystick(0)
                self.joystick.init()
                self.joystick_connected = True
                print(f"Joystick conectado: {self.joystick.get_name()}")
        else:
            if self.joystick_connected:
                self.joystick.quit()
                self.joystick = None
                self.joystick_connected = False
                print("Joystick desconectado")

    def process_joystick_input(self):
        # Verificar y conectar el joystick si es necesario
        if not self.joystick_connected:
            self.check_joystick_connection()

        # Procesar eventos de pygame
        for event in pygame.event.get():
            if event.type == pygame.JOYAXISMOTION:
                if self.joystick_connected:
                    # Leer valores de los ejes
                    axis0 = self.joystick.get_axis(0)  # Eje horizontal
                    axis1 = self.joystick.get_axis(1)  # Eje vertical

                    if self.manual_mode == 0:
                        # Modo Automático: Control de setpoints
                        delta_corredera = axis1 * 0.5  # Sensibilidad
                        delta_angulo = axis0 * 0.5

                        self.set_corredera(self.current_action[4] + delta_corredera)
                        self.set_angulo(self.current_action[5] + delta_angulo)
                    else:
                        # Modo Manual: Control de energía directamente
                        energia_corredera = int(axis1 * 255)
                        energia_angulo = int(axis0 * 255)

                        self.set_energy_corredera(energia_corredera)
                        self.set_energy_angulo(energia_angulo)
            elif event.type == pygame.JOYBUTTONDOWN:
                if self.joystick_connected:
                    if self.joystick.get_button(0):  # Botón A
                        # Cambiar de modo Automático a Manual y viceversa
                        if self.manual_mode == 1:
                            self.manual_mode = 0
                        else:
                            self.manual_mode = 1

                        self.set_manual_mode(self.manual_mode)

                        print(f"Modo cambiado a {'Manual' if self.manual_mode else 'Automático'}")
            elif event.type == pygame.QUIT:
                pygame.quit()

    def enable_joypad(self):
        """
        Habilita el procesamiento de la entrada del joypad.
        """
        self.joypad_enabled = True
        print("Entrada del joypad habilitada.")

    def disable_joypad(self):
        """
        Deshabilita el procesamiento de la entrada del joypad.
        """
        self.joypad_enabled = False
        print("Entrada del joypad deshabilitada.")

    def step(self, action=None):
        if self.joypad_enabled:
            self.process_joystick_input()

        if action is None:
            action = self.current_action
        else:
            self.current_action = action

        if self.mode == 'serial':
            if self.ser is None or not self.ser.is_open:
                self.connect_serial()

            cmd = [
                int(self.current_action[0]),   # modoManual
                int(self.current_action[1]),   # EMA
                int(self.current_action[2]),   # EMX
                int(self.current_action[3]),   # EMV
                float(self.current_action[4]), # X_Requerido
                float(self.current_action[5]), # A_Requerido
                float(self.current_action[6]), # Vol_requerido
                float(self.current_action[7]), # kpX
                float(self.current_action[8]), # kiX
                float(self.current_action[9]), # kdX
                float(self.current_action[10]),# kpA
                float(self.current_action[11]),# kiA
                float(self.current_action[12]),# kdA
                int(self.current_action[13]),  # resetVolumen
                int(self.current_action[14]),  # resetMotorXFlag
                int(self.current_action[15]),  # resetMotorAFlag
                float(self.current_action[16]),# stepsPerMM
                float(self.current_action[17]),# stepsPerDegree
                int(self.current_action[18]),  # usarLectorVelocidad
                0                              # reservado
            ]
            command_str = ','.join(map(str, cmd)) + '\n'

            try:
                if self.ser:
                    self.ser.write(command_str.encode())
            except serial.SerialException as e:
                self.logger(f"Error al escribir en el puerto serial: {e}")
                self.ser = None

            obs = self.get_observation()
            waited = 0
            while obs is None and waited < 3:
                try:
                    obs = self.data_queue.get(timeout=1)
                except queue.Empty:
                    waited += 1
            if obs is None:
                obs = np.zeros(self.observation_space.shape, dtype=np.float32)

        else:
            angle_rad = np.deg2rad(self.current_action[5])
            slide_pos = -(self.current_action[4] / 1000.0) * 0.2
            for idx in self.corredera_joint_indices:
                self.p.setJointMotorControl2(self.robotId, idx, self.p.POSITION_CONTROL,
                                             targetPosition=slide_pos)
            self.p.setJointMotorControl2(self.robotId, self.revolucion_joint_index,
                                         self.p.POSITION_CONTROL, targetPosition=angle_rad)
            self.valve_position = self.current_action[6]
            self.p.stepSimulation()
            time.sleep(1/240.0)
            angle_state = self.p.getJointState(self.robotId, self.revolucion_joint_index)[0]
            slide_state = self.p.getJointState(self.robotId, self.corredera_joint_indices[0])[0]
            inputA = np.degrees(angle_state)
            inputX = -slide_state * 1000.0 / 0.2
            inputV = self.valve_position
            flowVolume = 0.0
            obs = np.array([
                inputX,
                inputA,
                inputV,
                flowVolume,
                0, 0, 0, 0,
                int(self.current_action[2]),
                int(self.current_action[1]),
                int(self.current_action[3]),
                int(self.current_action[0]),
                self.current_action[7],
                self.current_action[8],
                self.current_action[9],
                self.current_action[10],
                self.current_action[11],
                self.current_action[12],
                0.0,
                0.0,
                0.0,
                self.current_action[16],
                self.current_action[17],
                1.0
            ], dtype=np.float32)
            self.last_obs = obs

        self.simulation_time = round(time.time() - self.start_time, 1)
        reward = round(self.calculate_reward(obs), 1)
        self.store_step(obs, reward)

        self.current_action[13] = 0
        self.current_action[14] = 0
        self.current_action[15] = 0

        return obs, reward, False, {}

    def calculate_reward(self, obs):
        # Implementar la función de recompensa según tus necesidades
        reward = 0
        return reward

    def reset(self):
        if self.mode == 'serial':
            if self.ser is None:
                self.connect_serial()
            if self.ser:
                self.ser.write(b'reset\n')
            time.sleep(2)
        else:
            self.p.resetSimulation()
            self.p.setGravity(0, 0, -9.8)
            self.p.loadURDF("plane.urdf")
            robot_path = os.path.join('control_robot',
                                      'Reloj_1_description', 'urdf',
                                      'Reloj_1.xacro')
            self.robotId = self.p.loadURDF(robot_path, [0, 0, 0.01],
                                           useFixedBase=True)
        self.current_action = np.zeros(20)
        self.execution_data = []
        self.manual_mode = 0
        self.set_manual_mode(self.manual_mode)
        return self.get_observation()

    def render(self, mode='human'):
        pass

    def get_observation(self):
        if self.mode == 'serial':
            try:
                return self.data_queue.get_nowait()
            except queue.Empty:
                return None
        else:
            return self.last_obs

    # Métodos para establecer acciones
    def set_corredera(self, setpoint_corredera):
        setpoint_corredera = np.clip(setpoint_corredera,
                                     self.action_space.low[4],
                                     self.action_space.high[4])
        self.current_action[4] = round(setpoint_corredera, 1)

    def set_angulo(self, setpoint_angle):
        setpoint_angle = np.clip(setpoint_angle,
                                 self.action_space.low[5],
                                 self.action_space.high[5])
        self.current_action[5] = round(setpoint_angle, 2)

    def set_valvula(self, setpoint_water):
        # En el firmware, este índice se usa como volumen objetivo
        setpoint_water = np.clip(setpoint_water,
                                 self.action_space.low[6],
                                 self.action_space.high[6])
        self.current_action[6] = round(setpoint_water, 1)

    # --- Volumen requerido & reset volumen ---
    def set_volumen_requerido(self, volumen):
        self.set_valvula(volumen)

    def reset_volumen(self):
        self.current_action[13] = 1

    def set_steps_per_mm(self, steps):
        self.current_action[16] = float(steps)

    def set_steps_per_degree(self, steps):
        self.current_action[17] = float(steps)

    def set_energy_corredera(self, energia_corredera):
        energia_corredera = np.clip(energia_corredera,
                                    self.action_space.low[2],
                                    self.action_space.high[2])
        self.current_action[2] = int(energia_corredera)

    def set_energy_angulo(self, energia_angulo):
        energia_angulo = np.clip(energia_angulo,
                                 self.action_space.low[1],
                                 self.action_space.high[1])
        self.current_action[1] = int(energia_angulo)

    def set_energy_valvula(self, energia_valvula):
        energia_valvula = np.clip(energia_valvula,
                                  self.action_space.low[3],
                                  self.action_space.high[3])
        self.current_action[3] = int(energia_valvula)

    def set_pid_corredera(self, kp, ki, kd):
        self.current_action[7] = round(kp, 2)
        self.current_action[8] = round(ki, 2)
        self.current_action[9] = round(kd, 2)

    def set_pid_angulo(self, kp, ki, kd):
        self.current_action[10] = round(kp, 2)
        self.current_action[11] = round(ki, 2)
        self.current_action[12] = round(kd, 2)

    def set_pid_valvula(self, kp, ki, kd):
        if self.mode == 'virtual':
            self.current_action[13] = round(kp, 2)
            self.current_action[14] = round(ki, 2)
            self.current_action[15] = round(kd, 2)

    def set_manual_mode(self, manual_mode):
        self.current_action[0] = int(manual_mode)
        self.manual_mode = int(manual_mode)

    def enable_pid(self):
        """Switch to automatic mode using PIDs for control."""
        self.set_manual_mode(0)

    def disable_pid(self):
        """Switch to manual mode bypassing the PIDs."""
        self.set_manual_mode(1)

    def calibrate_X(self, calibrate):
        self.current_action[14] = int(calibrate)

    def calibrate_A(self, calibrate):
        self.current_action[15] = int(calibrate)

    def set_usar_lector_velocidad(self, usar):
        self.current_action[18] = 1 if usar else 0

    def handle_key_press(self, key):
        """Update setpoints or energies based on a keyboard key press."""
        manual = int(self.current_action[0]) == 1
        if manual:
            if key == 'Up':
                self.set_energy_corredera(self.current_action[2] + 1)
            elif key == 'Down':
                self.set_energy_corredera(self.current_action[2] - 1)
            elif key == 'Right':
                self.set_energy_angulo(self.current_action[1] + 1)
            elif key == 'Left':
                self.set_energy_angulo(self.current_action[1] - 1)
            elif key == 'w':
                self.set_energy_valvula(self.current_action[3] + 1)
            elif key == 's':
                self.set_energy_valvula(self.current_action[3] - 1)
        else:
            if key == 'Up':
                self.set_corredera(self.current_action[4] + 10)
            elif key == 'Down':
                self.set_corredera(self.current_action[4] - 10)
            elif key == 'Right':
                self.set_angulo(self.current_action[5] + 10)
            elif key == 'Left':
                self.set_angulo(self.current_action[5] - 10)
            elif key == 'w':
                self.set_valvula(self.current_action[6] + 1)
            elif key == 's':
                self.set_valvula(self.current_action[6] - 1)

        if key == 'm':
            if manual:
                self.enable_pid()
            else:
                self.disable_pid()
            print(f"Modo cambiado a {'Manual' if self.manual_mode else 'Automático'}")

        self.step()

    def store_step(self, obs, reward):
        step_data = np.append(obs, reward)
        self.execution_data.append(step_data)

    def save_execution(self, execution_name):
        with open(f'robot_steps_execution_{execution_name}.csv',
                  'w', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(self.variable_names + ['reward'])
            for row in self.execution_data:
                csv_writer.writerow(row)

    def view_execution(self, execution_name, variable_names):
        try:
            with open(f'robot_steps_execution_{execution_name}.csv',
                      'r') as csvfile:
                csv_reader = csv.reader(csvfile)
                headers = next(csv_reader)
                self.execution_data = []
                for row in csv_reader:
                    self.execution_data.append([float(x) for x in row])

            # Convertir nombres de variables a índices
            indices = [self.variable_names.index(name) for name in variable_names]

            # Graficar las variables especificadas
            self.plot_data(indices, title=f"Ejecución {execution_name} - Variables Seleccionadas en el Tiempo")

        except FileNotFoundError:
            print(f"No se encontraron datos para la ejecución {execution_name}")
        except ValueError as e:
            print(f"Error: {e}")

    def plot_data(self, variable_indices, title="Gráfico de Datos"):
        plt.figure(figsize=(10, 5))
        for index in variable_indices:
            data = [step[index] for step in self.execution_data]
            plt.plot(data, label=self.variable_names[index])
        plt.xlabel('Paso')
        plt.ylabel('Valor')
        plt.title(title)
        plt.legend()
        plt.show()

    def close(self):
        self.stop_thread = True
        if self.mode == 'serial':
            if self.ser is not None:
                self.ser.close()
        else:
            self.p.disconnect()
        if self.joystick is not None:
            self.joystick.quit()
        pygame.quit()
        print("Entorno cerrado")


    # Métodos para gestionar plantas y regímenes
    def agregar_planta(self, planta_details, era):
        self.plantas_manager.agregar_planta(planta_details, era)

    def modificar_planta(self, era, fila, updated_values):
        self.plantas_manager.modificar_planta(era, fila, updated_values)

    def eliminar_planta(self, era, fila):
        self.plantas_manager.eliminar_planta(era, fila)

    def agregar_regimen(self, *args, **kwargs):
        return self.plantas_manager.crear_regimen(*args, **kwargs)

    def modificar_tarea(self, *args, **kwargs):
        return self.plantas_manager.modificar_regimen(*args, **kwargs)

    def eliminar_tarea(self, *args, **kwargs):
        return self.plantas_manager.eliminar_regimen(*args, **kwargs)

    # Gestión de tareas específicas del robot
    def agregar_tarea_robot(self, tarea):
        self.tareas_manager.agregar_tarea(tarea)

    def obtener_tareas_robot(self):
        return self.tareas_manager.obtener_tareas()

    def eliminar_tarea_robot(self, index):
        self.tareas_manager.eliminar_tarea(index)

