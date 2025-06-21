
import pygame
import numpy as np
import gym
import serial
import threading
import time
import sqlite3
import json

class BasicEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, port='COM6', baudrate=115200):
        super(BasicEnv, self).__init__()
        self.start_time = time.time()


        # Inicializar current_batch como None
        self.current_batch = None  # Inicializado como None
        self.stop_thread = False  # Nueva variable de control para detener el hilo


        self.action_space = gym.spaces.Box(
            low=np.array([
                0,      # [0] modoManual (0 o 1)
                -255,   # [1] EMA (control manual del motor angular)
                -255,   # [2] EMX (control manual del motor lineal)
                -255,   # [3] EMV (control manual de la bomba)
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
                0,      # [18] (valor no utilizado)
                0       # [19] (valor no utilizado)
            ]),
            high=np.array([
                1,      # [0] modoManual
                255,    # [1] EMA
                255,    # [2] EMX
                255,    # [3] EMV
                400,    # [4] X_Requerido
                360,    # [5] A_Requerido
                1000,   # [6] Vol_requerido
                255,    # [7] kpX
                255,    # [8] kiX
                255,    # [9] kdX
                255,    # [10] kpA
                255,    # [11] kiA
                255,    # [12] kdA
                1,      # [13] resetVolumen
                1,      # [14] resetMotorXFlag
                1,      # [15] resetMotorAFlag
                10000,  # [16] stepsPerMM
                10000,  # [17] stepsPerDegree
                0,      # [18] (valor no utilizado)
                0       # [19] (valor no utilizado)
            ]),
            dtype=np.float32
        )

        self.current_action = np.zeros(20)  # Tamaño ajustado a 20 variables

        self.variable_names = [
            'inputX',           # [0]
            'inputA',           # [1]
            'volumen',          # [2]
            'flow',             # [3]
            'XLimit_State',     # [4]
            'ALimit_State',     # [5]
            'calibrandoX',      # [6]
            'calibrandoA',      # [7]
            'EMX',              # [8]
            'EMA',              # [9]
            'EMV',              # [10]
            'modoManual',       # [11]
            'kpX',              # [12]
            'kiX',              # [13]
            'kdX',              # [14]
            'kpA',              # [15]
            'kiA',              # [16]
            'kdA',              # [17]
            'stepsPerMM',       # [18]
            'stepsPerDegree',   # [19]
            'flowCalibFactor',   # [20]
            #'execution_time'  # [21] <-- Nuevo valor
        ]

        self.observation_space = gym.spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(22,),  # Tamaño ajustado a 22 variables
            dtype=np.float32
        )

        # Conectar al puerto serial y comenzar el hilo de lectura
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.connect_serial()
        self.read_thread = threading.Thread(target=self.read_serial)
        self.read_thread.daemon = True
        self.read_thread.start()


        # Inicializar pygame y joystick
        pygame.init()
        self.joystick = None
        self.joystick_connected = False
        self.check_joystick_connection()
        self.joypad_enabled = False  # Comienza deshabilitado

        # Variable para controlar el modo (0: Automático, 1: Manual)
        self.manual_mode = 0
        self.set_manual_mode(self.manual_mode)

        # Cargar las configuraciones de PID y calibraciones
        self.config_file = 'configuracion_pid.json'
        self.load_configurations()

    def save_configurations(self):
        """
        Guarda las configuraciones actuales de PID y calibraciones en el archivo JSON.
        """
        config = {
            'kpX': float(self.current_action[7]),  # Convertir a float estándar
            'kiX': float(self.current_action[8]),
            'kdX': float(self.current_action[9]),
            'kpA': float(self.current_action[10]),
            'kiA': float(self.current_action[11]),
            'kdA': float(self.current_action[12]),
            'stepsPerMM': float(self.current_action[16]),
            'stepsPerDegree': float(self.current_action[17])
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
                print("Configuraciones guardadas en el archivo:", self.config_file)
        except Exception as e:
            print(f"Error al guardar las configuraciones: {e}")

    def load_configurations(self):
        """
        Carga las configuraciones de PID y calibraciones desde el archivo JSON.
        Si el archivo no existe, utiliza valores predeterminados.
        """
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)

                # Cargar configuraciones de PID
                self.current_action[7:10] = [
                    config.get('kpX', 1.0),  # kpX
                    config.get('kiX', 0.1),  # kiX
                    config.get('kdX', 0.05)  # kdX
                ]
                self.current_action[10:13] = [
                    config.get('kpA', 1.5),  # kpA
                    config.get('kiA', 0.3),  # kiA
                    config.get('kdA', 0.2)  # kdA
                ]

                # Cargar calibraciones
                self.current_action[16] = config.get('stepsPerMM', 1000.0)
                self.current_action[17] = config.get('stepsPerDegree', 1000.0)

                print("Configuraciones cargadas desde el archivo:", self.config_file)
        except FileNotFoundError:
            print("Archivo de configuración no encontrado. Usando valores predeterminados.")
            # Establecer valores predeterminados
            self.current_action[7:10] = [1.0, 0.1, 0.05]  # PID para corredera
            self.current_action[10:13] = [1.5, 0.3, 0.2]  # PID para ángulo
            self.current_action[16] = 1000.0  # stepsPerMM
            self.current_action[17] = 1000.0  # stepsPerDegree
        except Exception as e:
            print(f"Error al cargar las configuraciones: {e}")

    ###... Funciones relacionadas con la gestion de la base de datos
    def create_table(self):
        conn = sqlite3.connect('execution_data.db')
        cursor = conn.cursor()
        # Define the columns, including 'execution_time' separately
        columns = ', '.join([f'"{name}" REAL' for name in self.variable_names] + [
            '"execution_time" REAL',
            '"sent_data" TEXT',
            '"received_data" TEXT'
        ])

        sql = f'''
        CREATE TABLE IF NOT EXISTS execution_data (
            batch_id TEXT,
            {columns}
        )
        '''
        cursor.execute(sql)
        conn.commit()
        conn.close()

    def start_batch(self, batch_id=None):
        if batch_id is None:
            batch_id = f'batch_{int(time.time())}'
        self.current_batch = batch_id
        self.last_batch = batch_id  # Actualiza el último batch
        self.start_time = time.time()
        print(f"Batch '{batch_id}' iniciado.")
        return batch_id

    def store_serial_data(self, obs_data=None, sent_data=None, received_data=None, execution_time=None):
        """
        Stores sent and received serial data in the database.
        """
        # Create a new database connection
        conn = sqlite3.connect('execution_data.db')
        cursor = conn.cursor()

        if obs_data is not None:
            obs_values = obs_data.tolist()
        else:
            obs_values = [None] * len(self.variable_names)

        # Verificar que execution_time no sea None
        if execution_time is None:
            execution_time = time.time()

        # Prepare the values for insertion
        values = [self.current_batch] + obs_values + [execution_time, sent_data, received_data]
        placeholders = ', '.join(['?'] * len(values))
        columns = 'batch_id, ' + ', '.join(
            [f'"{name}"' for name in self.variable_names]) + ', "execution_time", "sent_data", "received_data"'
        sql = f'INSERT INTO execution_data ({columns}) VALUES ({placeholders})'

        try:
            cursor.execute(sql, values)
            conn.commit()
        except Exception as e:
            print(f"Error al insertar datos en la base de datos: {e}")
        finally:
            conn.close()

    def get_steps_from_batch(self, batch_id=None, tiempo=None, intervalo=1.0):
        """Obtiene los pasos del batch específico y filtra por el rango de tiempo proporcionado.
           Si se encuentra un execution_time nulo, se usa el valor anterior o 0 si tampoco hay uno anterior.
        """
        # Si no se proporciona un batch_id, usamos el último batch disponible
        batch_id = batch_id or self.current_batch or self.last_batch
        if batch_id is None:
            print("No hay batch_id disponible para recuperar datos.")
            return {"error": "No hay batch_id disponible para recuperar datos."}

        conn = sqlite3.connect('execution_data.db')
        cursor = conn.cursor()
        print("batch_id:", batch_id)
        print("tiempo solicitado:", tiempo)

        try:
            # Contar el número total de pasos en la base de datos para este batch
            cursor.execute('SELECT COUNT(*) FROM execution_data WHERE batch_id = ?', (batch_id,))
            total_steps = cursor.fetchone()[0]
            print(f"Total de pasos registrados en el batch '{batch_id}': {total_steps}")

            # Obtener el rango de tiempos (mínimo y máximo execution_time) en el batch
            cursor.execute(
                'SELECT MIN(execution_time), MAX(execution_time) FROM execution_data WHERE batch_id = ?',
                (batch_id,)
            )
            time_range = cursor.fetchone()
            print(f"Rango de tiempo del batch '{batch_id}': {time_range[0]} (mínimo), {time_range[1]} (máximo)")

            # Recuperar todos los datos del batch ordenados por tiempo
            cursor.execute('SELECT * FROM execution_data WHERE batch_id = ? ORDER BY execution_time ASC', (batch_id,))
            rows = cursor.fetchall()

            if not rows:
                print("No se encontraron datos para este batch.")
                return {}

            print(f"Cantidad de filas recuperadas del batch: {len(rows)}")

            filtered_rows = []
            previous_time = None
            last_valid_time = 0  # Inicializamos con un tiempo predeterminado
            step_count = 0

            current_time = time.time()

            # Ajuste en el cálculo de time_limit
            if tiempo is not None:
                time_limit = current_time - tiempo
                print(f"Filtrando datos desde el tiempo {time_limit} hasta {current_time} (últimos {tiempo} segundos)")
            else:
                time_limit = 0  # Si tiempo es None, no limitamos por tiempo
                print("No se aplicará filtrado por tiempo; se incluirán todos los datos disponibles.")

            for row_index, row in enumerate(rows):
                # Aquí puedes ajustar según la estructura de tus filas y columnas
                print(f"Procesando fila {row_index + 1}/{len(rows)}: {row}")
                if len(row) < len(self.variable_names) + 4:
                    print(f"Advertencia: Fila incompleta o inesperada -> {row}")
                    continue

                execution_time = row[-3]

                # Si el tiempo de ejecución es nulo, usa el último tiempo válido
                if execution_time is None:
                    print(
                        f"Advertencia: execution_time es None en la fila {row_index + 1}. Usando último tiempo válido ({last_valid_time}).")
                    execution_time = last_valid_time
                else:
                    last_valid_time = execution_time

                # Filtrar por límite de tiempo si es aplicable
                if tiempo is not None and execution_time < time_limit:
                    print(
                        f"Fila {row_index + 1}: execution_time ({execution_time}) fuera del límite de tiempo ({time_limit}).")
                    continue

                # Filtrar por intervalo
                if previous_time is None or (execution_time - previous_time) >= intervalo:
                    filtered_row = [
                        round(float(val), 2) if isinstance(val, (float, int)) else val
                        for val in row[1:]
                    ]
                    filtered_rows.append(filtered_row)
                    previous_time = execution_time
                    step_count += 1

            columns = self.variable_names + ['execution_time', 'sent_data', 'received_data']

            if step_count > 0:
                data = {col: [row[idx] for row in filtered_rows] for idx, col in enumerate(columns)}
                print(f"Datos filtrados: {data}")
                print(f"Total de pasos seleccionados tras filtrar: {step_count}")
                return data
            else:
                print("No se encontraron pasos en el intervalo especificado o dentro del tiempo solicitado.")
                return {
                    "error": "No se han encontrado pasos en el intervalo especificado o dentro del tiempo solicitado"
                }

        except Exception as e:
            print(f"Error al obtener los datos del batch: {e}")
            return {}
        finally:
            cursor.close()
            conn.close()

    ###...Funciones relacionadads con la conexion serial con arduino
    def connect_serial(self):
        if self.ser is not None and self.ser.is_open:
            try:
                self.ser.close()  # Cerrar el puerto si ya está abierto
                print("Puerto serial cerrado correctamente.")
            except Exception as e:
                print(f"Error al cerrar el puerto serial: {e}")

        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=0.3)
            time.sleep(2)
            print("Conectado al puerto serial", self.port)
            self.store_serial_data(sent_data="Conexión establecida en puerto: " + self.port)
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
                        # Guardar los datos recibidos
                        self.store_serial_data(received_data=line)

            except serial.SerialException as e:
                print(f"Serial read error: {e}")
                self.ser = None
            except Exception as e:
                print(f"Unexpected error: {e}")

    def process_serial_line(self, line):
        import time

        # Procesar la línea serial recibida
        values = line.strip().split(',')

        # Convertir los valores a float y manejar posibles errores
        try:
            obs_data = np.array([float(v) if v else 0.0 for v in values], dtype=np.float32)
        except ValueError as e:
            print(f"Error al convertir los valores de la línea serial a float: {e}")
            return

        # Actualizar la observación actual
        self.current_observation = obs_data

        # Obtener el tiempo de ejecución
        execution_time = time.time()

        # Crear un diccionario para depuración (opcional)
        obs_dict = dict(zip(self.variable_names, obs_data))
       # print(f"Datos a insertar: {obs_dict}")

        # Almacenar los datos en la base de datos
        self.store_serial_data(obs_data=obs_data, received_data=line, execution_time=execution_time)

    ##...funciones generales que concuerdan con la metodología Gym
    def custom_action(self, obs):

        obs = np.nan_to_num(obs, nan=0.0)
        # Definir setpoints y parámetros PID para X y A únicamente
        setpoint_x = 0
        setpoint_a = 0
        kp_x, ki_x, kd_x = 1.0, 0.1, 0.05
        kp_a, ki_a, kd_a = 1.5, 0.3, 0.2


        action = [
            0,  # modoManual
            0,  # EMA no sirve estando el modo manual desactivado
            0,  # EMX no sirve estando el modo manual desactivado
            0,  # EMV no sirve estando el modo manual desactivado
            setpoint_x,  # X_Requerido
            setpoint_a,  # A_Requerido
            0,  # Vol_requerido
            kp_x, ki_x, kd_x,  # PID para corredera (X)
            kp_a, ki_a, kd_a,  # PID para ángulo (A)
            0,  # resetVolumen
            0,  # resetMotorXFlag
            0,  # resetMotorAFlag
            obs[18],  # stepsPerMM
            obs[19],  # stepsPerDegree
            0,  # valor no utilizado
            0  # valor no utilizado
        ]

        return np.array(action, dtype=np.float32)

    def step(self, action=None):
        # Procesar entrada del joypad solo si está habilitado
        if self.joypad_enabled:
            self.process_joystick_input()
        if self.ser is None or not self.ser.is_open:
            self.connect_serial()
        # Obtener la observación actual
        obs = self.get_observation()
        # Si se proporciona una acción, actualizar 'self.current_action'
        if action is not None:
            self.current_action = action
        # Si 'action' es 'None', mantenemos 'self.current_action' sin cambios

        # Verificar que 'self.current_action' no sea 'None'
        if self.current_action is None:
            print("Advertencia: 'self.current_action' es 'None'. Usando acción por defecto.")
            self.current_action = np.zeros(20)  # O establece valores predeterminados apropiados

        # Ensamblar la cadena de comando para enviar al Arduino
        command_values = [
            int(self.current_action[0]),  # modoManual
            int(self.current_action[1]),  # EMA
            int(self.current_action[2]),  # EMX
            int(self.current_action[3]),  # EMV
            float(self.current_action[4]),  # X_Requerido
            float(self.current_action[5]),  # A_Requerido
            float(self.current_action[6]),  # Vol_requerido
            float(self.current_action[7]),  # kpX
            float(self.current_action[8]),  # kiX
            float(self.current_action[9]),  # kdX
            float(self.current_action[10]),  # kpA
            float(self.current_action[11]),  # kiA
            float(self.current_action[12]),  # kdA
            int(self.current_action[13]),  # resetVolumen
            int(self.current_action[14]),  # resetMotorXFlag
            int(self.current_action[15]),  # resetMotorAFlag
            float(self.current_action[16]),  # stepsPerMM
            float(self.current_action[17]),  # stepsPerDegree
            0,  # Valor no utilizado
            0  # Valor no utilizado
        ]

        # Convertir los valores a strings y unirlos con comas
        command_str = ','.join(map(str, command_values)) + '\n'
        try:
            if self.ser:
                self.ser.write(command_str.encode())
        except serial.SerialException as e:
            print(f"Error al escribir en el puerto serial: {e}")
            self.ser = None
        reward = round(self.calculate_reward(obs), 1)
        # Almacenar cada observación en la base de datos asociada al batch actual
        self.store_serial_data(obs_data=obs, sent_data=str(command_values), received_data=str(obs))
        time.sleep(0.3)
        return obs, reward, False, {}

    def calculate_reward(self, obs):
        # Implementar la función de recompensa según tus necesidades
        reward = 0
        return reward

    def reset(self):
        # Reconectar al puerto serial si es necesario
        if self.ser is None:
            self.connect_serial()
        if self.ser:
            # Enviar un comando de reinicio al dispositivo
            self.ser.write(b'reset\n')
        time.sleep(2)  # Pausa para asegurar que el dispositivo esté reiniciado

        # Reiniciar las variables de acción a sus valores predeterminados
        self.current_action = np.zeros(20)

        # Cargar la configuración guardada para PID y calibraciones
        self.load_configurations()

        # Reiniciar cualquier otra configuración necesaria
        self.manual_mode = 1
        # Si es necesario, enviar comandos específicos para restablecer los motores
        # (esto dependerá del comportamiento de tu hardware)
        self.set_manual_mode(self.manual_mode)

        # Reiniciar el tiempo de inicio para c
        # Restablecer energías y setpoints
        self.set_energy_corredera(0)  # Restablecer energía de corredera
        self.set_energy_angulo(0)  # Restablecer energía de ángulo
        self.set_energy_valvula(0)  # Restablecer energía de la válvula

        #cálculos de tiempo de ejecución
        self.start_time = time.time()

        # Retornar la observación inicial
        return self.get_observation()

    def render(self, mode='human'):
        pass

    def get_observation(self):
        """
        Retrieves the most recent observation from the database.
        """
        conn = sqlite3.connect('execution_data.db')
        cursor = conn.cursor()
        try:
            cursor.execute(
                'SELECT * FROM execution_data WHERE batch_id = ? AND inputX IS NOT NULL ORDER BY execution_time DESC LIMIT 1',
                (self.current_batch,))
            row = cursor.fetchone()

            if row is None:
                print("No se encontraron datos en la base de datos.")
                return np.zeros(len(self.variable_names), dtype=np.float32)

            # Extract observation data (excluding batch_id and sent/received data)
            observation = np.array(row[1:1 + len(self.variable_names)], dtype=np.float32)

            return observation
        except sqlite3.Error as e:
            print(f"Error al obtener la observación de la base de datos: {e}")
            return None
        finally:
            conn.close()


## .. funciones relacionadas con el Uso del control joypad

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

    def set_steps_per_mm(self, steps_per_mm):
        self.current_action[16] = float(steps_per_mm)
        self.save_configurations()  # Guardar las configuraciones

    def set_steps_per_degree(self, steps_per_degree):
        self.current_action[17] = float(steps_per_degree)
        self.save_configurations()  # Guardar las configuraciones


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

    def set_volumen_requerido(self, volumen_requerido):
        volumen_requerido = np.clip(volumen_requerido,
                                    self.action_space.low[6],
                                    self.action_space.high[6])
        self.current_action[6] = round(volumen_requerido, 1)

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

    def set_pid_corredera(self, kp, ki, kd, save=True):
        self.current_action[7] = round(kp, 1)
        self.current_action[8] = round(ki, 1)
        self.current_action[9] = round(kd, 1)
        if save:
            self.save_configurations()  # Guardar solo si save=True

    def set_pid_angulo(self, kp, ki, kd, save=True):
        self.current_action[10] = round(kp, 1)
        self.current_action[11] = round(ki, 1)
        self.current_action[12] = round(kd, 1)
        if save:
            self.save_configurations()

    def set_manual_mode(self, manual_mode):
        self.current_action[0] = int(manual_mode)

    def reset_volumen(self):
        self.current_action[13] = 1  # Establecer la bandera para reiniciar el volumen

    def reset_X(self, calibrate):
        self.current_action[14] = int(calibrate)

    def reset_A(self, calibrate):
        self.current_action[15] = int(calibrate)

    def calibrate_StepsPerMM(self, calibrate):
        self.current_action[16] = int(calibrate)

    def calibrate_stepsPerDegree(self, calibrate):
        self.current_action[17] = int(calibrate)

    def detener_motores(self):
        stop_action = self.current_action.copy()
        stop_action[0] = 1
        stop_action[1] = 0
        stop_action[2] = 0
        stop_action[3] = 0
        self.step(stop_action)
        return "Motores detenidos."

    def update_requirements(self, **kwargs):
        if 'X_Requerido' in kwargs:
            self.set_corredera(kwargs['X_Requerido'])
        if 'A_Requerido' in kwargs:
            self.set_angulo(kwargs['A_Requerido'])
        if 'Vol_requerido' in kwargs:
            self.set_volumen_requerido(kwargs['Vol_requerido'])
        return "Requerimientos actualizados."

    def start_observing(self, batch_id=None):
        new_batch_id = self.start_batch(batch_id)
        return f"Observación iniciada con batch_id: {new_batch_id}"

    def stop_observing(self):
        if self.current_batch is None:
            return {"error": "No hay una observación activa."}
        data = self.get_steps_from_batch(batch_id=self.current_batch, tiempo=None, intervalo=0.01)
        # Opcional: self.current_batch = None
        return data

    def get_latest_observations(self, tiempo=10.0, intervalo=1.0):
        if self.current_batch is None and not hasattr(self, 'last_batch'):
            return {"error": "No se han registrado batchs ni observaciones."}
        batch_id = self.current_batch if self.current_batch is not None else getattr(self, 'last_batch', None)
        if batch_id is None:
            return {"error": "No hay batch disponible."}
        data = self.get_steps_from_batch(batch_id=batch_id, tiempo=tiempo, intervalo=intervalo)
        return data

    def close(self):
        self.stop_thread = True
        if hasattr(self, 'conn'):
            self.conn.close()
        if self.ser is not None:
            self.ser.close()
        if self.joystick is not None:
            self.joystick.quit()
        pygame.quit()
        print("Entorno cerrado")

