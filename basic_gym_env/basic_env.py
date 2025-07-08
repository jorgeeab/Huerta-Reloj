import matplotlib.pyplot as plt
from openpyxl import load_workbook
from .plantas import PlantasManager
from .regimenes import RegimenesManager
from .ensayos import EnsayosEnv
#from .utils import crear_archivos_plantas_y_regimenes
import pygame
import numpy as np
import gym
import serial
import threading
import time
import queue
import csv
import matplotlib.pyplot as plt
from openpyxl import load_workbook
import pygame

class BasicEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, port='COM6', baudrate=115200,
                 archivo_plantas='archivo_plantas.xlsx',
                 archivo_regimenes='archivo_regimenes.xlsx',
                 archivo_ensayos='archivo_ensayos.xlsx'):
        super(BasicEnv, self).__init__()

        # Inicializar gestores de plantas y regímenes
        self.plantas_manager = PlantasManager(archivo_plantas)
        self.regimenes_manager = RegimenesManager(archivo_regimenes)
        self.ensayos_env = EnsayosEnv(archivo_plantas, archivo_regimenes, archivo_ensayos)

        # Definir espacios de acción y observación
        self.action_space = gym.spaces.Box(
            low=np.array([
                0,      # [0] modoManual (0 o 1)
                -255,   # [1] manualMotorA
                -255,   # [2] manualMotorX
                -255,   # [3] manualMotorV
                0,      # [4] X_Requerido
                0,      # [5] A_Requerido
                0,      # [6] Vel_Requerida
                0,      # [7] kpX
                0,      # [8] kiX
                0,      # [9] kdX
                0,      # [10] kpA
                0,      # [11] kiA
                0,      # [12] kdA
                0,      # [13] kpV
                0,      # [14] kiV
                0,      # [15] kdV
                0,      # [16] resetMotorXFlag
                0,      # [17] resetMotorAFlag
                0,      # [18] stepsPerMM
                0       # [19] stepsPerDegree
            ]),
            high=np.array([
                1,      # [0] modoManual
                255,    # [1] manualMotorA
                255,    # [2] manualMotorX
                255,    # [3] manualMotorV
                400,    # [4] X_Requerido
                360,    # [5] A_Requerido
                255,    # [6] Vel_Requerida
                255,    # [7] kpX
                255,    # [8] kiX
                255,    # [9] kdX
                255,    # [10] kpA
                255,    # [11] kiA
                255,    # [12] kdA
                255,    # [13] kpV
                255,    # [14] kiV
                255,    # [15] kdV
                1,      # [16] resetMotorXFlag
                1,      # [17] resetMotorAFlag
                10000,  # [18] stepsPerMM
                10000   # [19] stepsPerDegree
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

        # Conectar al puerto serial y comenzar el hilo de lectura
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connect_serial()
        self.read_thread = threading.Thread(target=self.read_serial)
        self.read_thread.daemon = True
        self.read_thread.start()

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
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.3)
            time.sleep(2)
            print("Conectado al puerto serial", self.port)
            return True
        except serial.SerialException as e:
            print(f"Error al conectar al puerto serial: {e}")
            self.ser = None
            return False

    def read_serial(self):
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
                print(f"Serial read error: {e}")
                self.ser = None
            except Exception as e:
                print(f"Unexpected error: {e}")

    def process_serial_line(self, line):
        # Dividir la línea por comas
        values = line.strip().split(',')

        if len(values) != 24:
            print(f"Error: expected 24 values, got {len(values)}")
            return

        try:
            # Asignar los valores a las variables correspondientes
            inputX = float(values[0])
            inputA = float(values[1])
            inputV = float(values[2])
            flowVolume = float(values[3])
            limite_X = int(values[4])
            limite_A = int(values[5])
            calibrando_X = int(values[6])
            calibrando_A = int(values[7])
            manualMotorX = int(values[8])
            manualMotorA = int(values[9])
            manualMotorV = int(values[10])
            modoManual = int(values[11])
            kpX = float(values[12])
            kiX = float(values[13])
            kdX = float(values[14])
            kpA = float(values[15])
            kiA = float(values[16])
            kdA = float(values[17])
            kpV = float(values[18])
            kiV = float(values[19])
            kdV = float(values[20])
            stepsPerMM = float(values[21])
            stepsPerDegree = float(values[22])
            flowCalibFactor = float(values[23])

            # Crear el array de observación
            obs = np.array([
                inputX,  # [0]
                inputA,  # [1]
                inputV,  # [2]
                flowVolume,  # [3]
                limite_X,  # [4]
                limite_A,  # [5]
                calibrando_X,  # [6]
                calibrando_A,  # [7]
                manualMotorX,  # [8]
                manualMotorA,  # [9]
                manualMotorV,  # [10]
                modoManual,  # [11]
                kpX,  # [12]
                kiX,  # [13]
                kdX,  # [14]
                kpA,  # [15]
                kiA,  # [16]
                kdA,  # [17]
                kpV,  # [18]
                kiV,  # [19]
                kdV,  # [20]
                stepsPerMM,  # [21]
                stepsPerDegree,  # [22]
                flowCalibFactor  # [23]
            ], dtype=np.float32)

            # Colocar la observación en la cola
            self.data_queue.put(obs)
        except ValueError as e:
            print(f"Value error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

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
        # Procesar entrada del joypad solo si está habilitado
        if self.joypad_enabled:
            self.process_joystick_input()

        if self.ser is None or not self.ser.is_open:
            self.connect_serial()

        # Si no se proporciona una acción, usar self.current_action
        if action is None:
            action = self.current_action
        else:
            self.current_action = action

        # Ensamblar la cadena de comando para enviar al Arduino
        command_values = [
            int(self.current_action[0]),   # modoManual
            int(self.current_action[1]),   # manualMotorA
            int(self.current_action[2]),   # manualMotorX
            int(self.current_action[3]),   # manualMotorV
            float(self.current_action[4]), # X_Requerido
            float(self.current_action[5]), # A_Requerido
            float(self.current_action[6]), # Vel_Requerida
            float(self.current_action[7]), # kpX
            float(self.current_action[8]), # kiX
            float(self.current_action[9]), # kdX
            float(self.current_action[10]),# kpA
            float(self.current_action[11]),# kiA
            float(self.current_action[12]),# kdA
            float(self.current_action[13]),# kpV
            float(self.current_action[14]),# kiV
            float(self.current_action[15]),# kdV
            int(self.current_action[16]),  # resetMotorXFlag
            int(self.current_action[17]),  # resetMotorAFlag
            float(self.current_action[18]),# stepsPerMM
            float(self.current_action[19]) # stepsPerDegree
        ]

        # Convertir los valores a strings y unirlos con comas
        command_str = ','.join(map(str, command_values)) + '\n'

        try:
            if self.ser:
                self.ser.write(command_str.encode())
        except serial.SerialException as e:
            print(f"Error al escribir en el puerto serial: {e}")
            self.ser = None

        start_time = time.time()
        obs = self.get_observation()

        while obs is None:
            try:
                obs = self.data_queue.get(timeout=1)
            except queue.Empty:
                continue

        self.simulation_time = round(time.time() - self.start_time, 1)

        reward = round(self.calculate_reward(obs), 1)
        self.store_step(obs, reward)

        return obs, reward, False, {}

    def calculate_reward(self, obs):
        # Implementar la función de recompensa según tus necesidades
        reward = 0
        return reward

    def reset(self):
        if self.ser is None:
            self.connect_serial()
        if self.ser:
            self.ser.write(b'reset\n')
        time.sleep(2)
        self.current_action = np.zeros(20)
        self.execution_data = []
        self.manual_mode = 0
        self.set_manual_mode(self.manual_mode)
        return self.get_observation()

    def render(self, mode='human'):
        pass

    def get_observation(self):
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None

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
        setpoint_water = np.clip(setpoint_water,
                                 self.action_space.low[6],
                                 self.action_space.high[6])
        self.current_action[6] = round(setpoint_water, 1)

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
        self.current_action[7] = round(kp, 1)
        self.current_action[8] = round(ki, 1)
        self.current_action[9] = round(kd, 1)

    def set_pid_angulo(self, kp, ki, kd):
        self.current_action[10] = round(kp, 1)
        self.current_action[11] = round(ki, 1)
        self.current_action[12] = round(kd, 1)

    def set_pid_valvula(self, kp, ki, kd):
        self.current_action[13] = round(kp, 1)
        self.current_action[14] = round(ki, 1)
        self.current_action[15] = round(kd, 1)

    def set_manual_mode(self, manual_mode):
        self.current_action[0] = int(manual_mode)

    def calibrate_X(self, calibrate):
        self.current_action[16] = int(calibrate)

    def calibrate_A(self, calibrate):
        self.current_action[17] = int(calibrate)

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
        if self.ser is not None:
            self.ser.close()
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

    def agregar_regimen(self, regimen_name):
        self.regimenes_manager.agregar_regimen(regimen_name)

    def modificar_tarea(self, regimen, fila, updated_values):
        self.regimenes_manager.modificar_tarea(regimen, fila, updated_values)

    def eliminar_tarea(self, regimen, fila):
        self.regimenes_manager.eliminar_tarea(regimen, fila)

    def crear_ensayo(self):
        self.ensayos_env.crear_ensayo()
