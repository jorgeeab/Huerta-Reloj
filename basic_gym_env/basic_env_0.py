import numpy as np
import gym
import serial
import threading
import time
import json
import queue
import csv
import matplotlib.pyplot as plt
from openpyxl import load_workbook
from .plantas import PlantasManager
from .regimenes import RegimenesManager
from .ensayos import EnsayosEnv
from .utils import crear_archivos_plantas_y_regimenes
import pygame

class BasicEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, port='COM6', baudrate=115200,
                 archivo_plantas='archivo_plantas.xlsx',
                 archivo_regimenes='archivo_regimenes.xlsx',
                 archivo_ensayos='archivo_ensayos.xlsx'):
        super(BasicEnv, self).__init__()

        # Inicializar espacios de acción y observación
        self.action_space = gym.spaces.Box(
            low=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          -255, -255, -255, 0, 0]),
            high=np.array([400, 360, 255, 255, 255, 255, 255, 255,
                           255, 255, 255, 255, 1, 255, 255, 255, 1,
                           1]),
            dtype=np.float32
        )

        self.observation_space = gym.spaces.Box(
            low=0,
            high=400,
            shape=(24,),
            dtype=np.float32
        )

        # Inicializar pesos
        self.weights = {
            'flow_rate_weight': 1.0,
            'setpoint_weight': 1.0,
            'angle_horizontal_weight': 1.0,
            'angle_vertical_weight': 1.0
        }

        # Inicializar conexión serial
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.data_queue = queue.Queue()
        self.stop_thread = False
        self.start_time = time.time()
        self.current_action = np.zeros(19)

        # Inicializar gestores
        self.plantas_manager = PlantasManager(archivo_plantas)
        self.regimenes_manager = RegimenesManager(archivo_regimenes)
        self.ensayos_env = EnsayosEnv(archivo_plantas,
                                      archivo_regimenes,
                                      archivo_ensayos)

        # Conectar y leer del puerto serial
        self.connect_serial()
        self.read_thread = threading.Thread(target=self.read_serial)
        self.read_thread.daemon = True
        self.read_thread.start()

        self.simulation_time = 0  # Tiempo de simulación
        self.execution_data = []  # Datos de la ejecución actual

        # Nombres de variables
        self.variable_names = [
            'inputX', 'inputA', 'inputV',
            'setpoint_corredera', 'setpoint_angle', 'setpoint_water',
            'pid_corredera_Kp', 'pid_corredera_Ki', 'pid_corredera_Kd',
            'pid_angle_Kp', 'pid_angle_Ki', 'pid_angle_Kd',
            'pid_valvula_Kp', 'pid_valvula_Ki', 'pid_valvula_Kd',
            'manual_mode', 'energia_motor_corredera',
            'energia_motor_angulo', 'energia_motor_valvula',
            'calibrating', 'limite_angulo', 'limite_corredera',
            'limite_valvula', 'elapsed_time'
        ]

        # Inicializar pygame y el joystick
        pygame.init()
        self.joystick = None
        self.joystick_connected = False  # Variable para rastrear el estado del joystick
        self.check_joystick_connection()

        # Variable para controlar si el joypad está habilitado
        self.joypad_enabled = False  # Inicia desactivado

        # Variable para controlar el modo (0: Automático, 1: Manual)
        self.manual_mode = 0
        self.set_manual_mode(self.manual_mode)

    def connect_serial(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        try:
            self.ser = serial.Serial(self.port, self.baudrate,
                                     timeout=1)
            time.sleep(2)
            print("Conectado al puerto serial", self.port)
            return True
        except serial.SerialException as e:
            print(f"Error al conectar al puerto serial: {e}")
            self.ser = None
            return False

    def read_serial(self):
        time.sleep(2)
        while not self.stop_thread:
            if self.ser is None or not self.ser.is_open:
                time.sleep(1)
                continue
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if not line:
                    continue
                if line.startswith("{") and line.endswith("}"):
                    parsed_data = self.parse_data(line)
                    if parsed_data is not None:
                        self.data_queue.put(parsed_data)
                else:
                    print(f"JSON recibido incompleto o mal formado: {line}")
            except serial.SerialException as e:
                print(f"Error al leer datos seriales: {e}")
                self.ser = None
            except Exception as e:
                print(f"Error inesperado: {e}")

    def parse_data(self, line):
        try:
            data = json.loads(line)
            sensores = data.get('sensores', {})
            actuadores = data.get('actuadores', {})

            elapsed_time = round(sensores.get('elapsed_time',
                                   time.time() - self.start_time), 1)
            inputX = round(sensores.get('inputX', 0), 1)
            inputA = round(sensores.get('inputA', 0) % 360, 2)
            inputV = round(sensores.get('inputV', 0), 1)

            setpoint_corredera = round(actuadores.get(
                'setpoint_corredera', 0), 1)
            setpoint_angle = round(actuadores.get('setpoint_angle',
                                     0), 2)
            setpoint_water = round(actuadores.get('setpoint_water',
                                     0), 1)

            return np.array([
                inputX, inputA, inputV,
                setpoint_corredera, setpoint_angle, setpoint_water,
                round(actuadores['pid_corredera'][0], 1),
                round(actuadores['pid_corredera'][1], 1),
                round(actuadores['pid_corredera'][2], 1),
                round(actuadores['pid_angle'][0], 1),
                round(actuadores['pid_angle'][1], 1),
                round(actuadores['pid_angle'][2], 1),
                round(actuadores['pid_valvula'][0], 1),
                round(actuadores['pid_valvula'][1], 1),
                round(actuadores['pid_valvula'][2], 1),
                int(actuadores.get('manual_mode', 0)),
                round(actuadores.get('energia_motor_corredera', 0), 1),
                round(actuadores.get('energia_motor_angulo', 0), 1),
                round(actuadores.get('energia_motor_valvula', 0), 1),
                int(actuadores.get('calibrating', 0)),
                int(sensores.get('limite_angulo', 0)),
                int(sensores.get('limite_corredera', 0)),
                int(sensores.get('limite_valvula', 0)),
                elapsed_time
            ])
        except json.JSONDecodeError as e:
            print(f"Error al parsear JSON: {line} - {e}")
            return None
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

    def check_joystick_connection(self):
        """
        Verifica si el joystick está conectado y lo inicializa si es necesario.
        """
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

                        self.set_corredera(self.current_action[0] + delta_corredera)
                        self.set_angulo(self.current_action[1] + delta_angulo)
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

        command = {
            'actuadores': {
                'setpoint_corredera': round(float(action[0]), 1),
                'setpoint_angle': round(float(action[1]), 2),
                'setpoint_water': round(float(action[2]), 1),
                'pid_corredera': [
                    round(float(action[3]), 1),
                    round(float(action[4]), 1),
                    round(float(action[5]), 1)
                ],
                'pid_angle': [
                    round(float(action[6]), 1),
                    round(float(action[7]), 1),
                    round(float(action[8]), 1)
                ],
                'pid_valvula': [
                    round(float(action[9]), 1),
                    round(float(action[10]), 1),
                    round(float(action[11]), 1)
                ],
                'manual_mode': int(action[12]),
                'energia_motor_corredera': round(float(action[13]), 1),
                'energia_motor_angulo': round(float(action[14]), 1),
                'energia_motor_valvula': round(float(action[15]), 1),
                'calibrating': int(action[16])
            }
        }
        try:
            command_str = json.dumps(command) + '\n'
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

        elapsed_sim_time = obs[23]
        while time.time() - start_time < 0.3 and \
                elapsed_sim_time < self.simulation_time + 0.3:
            try:
                obs = self.data_queue.get(timeout=0.01)
                elapsed_sim_time = obs[23]
            except queue.Empty:
                continue

        self.simulation_time = round(time.time() - self.start_time, 1)

        reward = round(self.calculate_reward(obs), 1)
        self.store_step(obs, reward)

        return obs, reward, False, {}

    def calculate_reward(self, obs):
        flow_rate = obs[2]
        setpoint = obs[5]
        angle_horizontal = obs[3]
        angle_vertical = obs[4]

        reward = -(
            self.weights['flow_rate_weight'] * abs(flow_rate - setpoint) +
            self.weights['setpoint_weight'] * abs(setpoint) +
            self.weights['angle_horizontal_weight'] * abs(angle_horizontal - 90) +
            self.weights['angle_vertical_weight'] * abs(angle_vertical - 90)
        )

        return reward

    def reset(self):
        if self.ser is None:
            self.connect_serial()
        if self.ser:
            self.ser.write(b'reset\n')
        time.sleep(2)
        self.current_action = np.zeros(19)
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

    def set_corredera(self, setpoint_corredera):
        setpoint_corredera = np.clip(setpoint_corredera,
                                     self.action_space.low[0],
                                     self.action_space.high[0])
        self.current_action[0] = round(setpoint_corredera, 1)

    def set_angulo(self, setpoint_angle):
        setpoint_angle = np.clip(setpoint_angle,
                                 self.action_space.low[1],
                                 self.action_space.high[1])
        self.current_action[1] = round(setpoint_angle, 2)

    def set_valvula(self, setpoint_water):
        setpoint_water = np.clip(setpoint_water,
                                 self.action_space.low[2],
                                 self.action_space.high[2])
        self.current_action[2] = round(setpoint_water, 1)

    def set_energy_corredera(self, energia_corredera):
        energia_corredera = np.clip(energia_corredera, -255, 255)
        self.current_action[13] = round(energia_corredera, 1)

    def set_energy_angulo(self, energia_angulo):
        energia_angulo = np.clip(energia_angulo, -255, 255)
        self.current_action[14] = round(energia_angulo, 1)

    def set_energy_valvula(self, energia_valvula):
        energia_valvula = np.clip(energia_valvula, -255, 255)
        self.current_action[15] = round(energia_valvula, 1)

    def set_pid_corredera(self, kp, ki, kd):
        self.current_action[3] = round(kp, 1)
        self.current_action[4] = round(ki, 1)
        self.current_action[5] = round(kd, 1)

    def set_pid_angulo(self, kp, ki, kd):
        self.current_action[6] = round(kp, 1)
        self.current_action[7] = round(ki, 1)
        self.current_action[8] = round(kd, 1)

    def set_pid_valvula(self, kp, ki, kd):
        self.current_action[9] = round(kp, 1)
        self.current_action[10] = round(ki, 1)
        self.current_action[11] = round(kd, 1)

    def set_manual_mode(self, manual_mode):
        self.current_action[12] = int(manual_mode)

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

