import numpy as np
import gym
import serial.tools.list_ports
import threading
import time
import json
import queue
import tkinter as tk

class BasicEnv(gym.Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, port='COM4', baudrate=115200, receive_callback=None):
        super(BasicEnv, self).__init__()

        self.action_space = gym.spaces.Box(
            low=np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -255, -255, -255, 0, 0]),
            high=np.array([400, 180, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 1, 255, 255, 255, 1, 1]),
            dtype=np.float32
        )

        self.observation_space = gym.spaces.Box(
            low=0,
            high=400,
            shape=(21,),
            dtype=np.float32
        )

        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.receive_callback = receive_callback

        self.data_queue = queue.Queue()
        self.thread = threading.Thread(target=self.read_serial)
        self.thread.daemon = True
        self.thread.start()

        self.current_action = np.zeros(19)

        self.weights = {
            'flow_rate_weight': 0.5,
            'setpoint_weight': 0.3,
            'angle_horizontal_weight': 0.1,
            'angle_vertical_weight': 0.1
        }

    def connect_serial(self):
        if self.ser is not None and self.ser.is_open:
            self.ser.close()
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)
            print("Connected to serial port")
            return True
        except serial.SerialException as e:
            print(f"Error connecting to serial port: {e}")
            self.ser = None
            return False

    def read_serial(self):
        time.sleep(2)
        while True:
            if self.ser is None or not self.ser.is_open:
                time.sleep(1)
                continue
            try:
                line = self.ser.readline().decode('utf-8').strip()
                if not line:
                    continue
                print(f"Received: {line}")
                if self.receive_callback:
                    self.receive_callback(line)
                parsed_data = self.parse_data(line)
                if parsed_data is not None:
                    self.data_queue.put(parsed_data)
            except serial.SerialException as e:
                print(f"Error reading serial data: {e}")
                self.ser = None
            except Exception as e:
                print(f"Unexpected error: {e}")

    def parse_data(self, line):
        try:
            data = json.loads(line)
            if 'sensores' in data and 'actuadores' in data:
                sensores = data['sensores']
                actuadores = data['actuadores']
                return np.array([
                    sensores.get('inputX', 0),
                    sensores.get('inputA', 0) % 360,
                    sensores.get('inputV', 0),
                    actuadores.get('setpoint_corredera', 0),
                    actuadores.get('setpoint_angle', 0),
                    actuadores.get('setpoint_water', 0),
                    actuadores['pid_corredera'][0],
                    actuadores['pid_corredera'][1],
                    actuadores['pid_corredera'][2],
                    actuadores['pid_angle'][0],
                    actuadores['pid_angle'][1],
                    actuadores['pid_angle'][2],
                    actuadores['pid_valvula'][0],
                    actuadores['pid_valvula'][1],
                    actuadores['pid_valvula'][2],
                    actuadores.get('manual_mode', 0),
                    actuadores.get('energia_motor_corredera', 0),
                    actuadores.get('energia_motor_angulo', 0),
                    actuadores.get('energia_motor_valvula', 0),
                    actuadores.get('calibrating', 0),
                    sensores.get('limite_angulo', 0),
                    sensores.get('limite_corredera', 0),
                    sensores.get('limite_valvula', 0)
                ])
            else:
                print(f"Unexpected data format: {line}")
                return None
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {line} - {e}")
            return None

    def step(self, action):
        if self.ser is None or not self.ser.is_open:
            self.connect_serial()
        self.current_action = action
        command = {
            'actuadores': {
                'setpoint_corredera': float(action[0]),
                'setpoint_angle': float(action[1]),
                'setpoint_water': float(action[2]),
                'pid_corredera': [float(action[3]), float(action[4]), float(action[5])],
                'pid_angle': [float(action[6]), float(action[7]), float(action[8])],
                'pid_valvula': [float(action[9]), float(action[10]), float(action[11])],
                'manual_mode': int(action[12]),
                'energia_motor_corredera': float(action[13]),
                'energia_motor_angulo': float(action[14]),
                'energia_motor_valvula': float(action[15]),
                'calibrating': int(action[16])
            }
        }
        try:
            command_str = json.dumps(command) + '\n'
            print(f"Sent: {command_str}")
            if self.ser:
                self.ser.write(command_str.encode())
            if self.receive_callback:
                self.receive_callback(f"Sent: {command_str}")
        except serial.SerialException as e:
            print(f"Error writing to serial port: {e}")
            self.ser = None

        obs = self.get_observation()
        while obs is None:
            try:
                obs = self.data_queue.get(timeout=1)
            except queue.Empty:
                continue

        reward = self.calculate_reward(obs)
        done = self.is_done(obs)

        return obs, reward, done, {}

    def calculate_reward(self, obs):
        flow_rate = obs[2]
        setpoint = obs[5]
        angle_horizontal = obs[3]
        angle_vertical = obs[4]

        reward = -(self.weights['flow_rate_weight'] * abs(flow_rate - setpoint) +
                   self.weights['setpoint_weight'] * abs(setpoint) +
                   self.weights['angle_horizontal_weight'] * abs(angle_horizontal - 90) +
                   self.weights['angle_vertical_weight'] * abs(angle_vertical - 90))

        return reward

    def is_done(self, obs):
        limite_angulo = obs[20]
        limite_corredera = obs[21]
        limite_valvula = obs[22]
        return limite_angulo or limite_corredera or limite_valvula

    def reset(self):
        if self.ser is None:
            self.connect_serial()
        if self.ser:
            self.ser.write(b'reset\n')
        time.sleep(2)
        self.current_action = np.zeros(19)
        return self.get_observation()

    def render(self, mode='human'):
        pass

    def get_observation(self):
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None

class RobotEnv(BasicEnv):
    def set_servos(self, angle_horizontal, angle_vertical, angle_valve):
        self.current_action[0] = angle_horizontal
        self.current_action[1] = angle_vertical
        self.current_action[2] = angle_valve
        self.step(self.current_action)

    def set_pid_corredera(self, kp, ki, kd):
        self.current_action[3] = kp
        self.current_action[4] = ki
        self.current_action[5] = kd
        self.step(self.current_action)

    def set_pid_angulo(self, kp, ki, kd):
        self.current_action[6] = kp
        self.current_action[7] = ki
        self.current_action[8] = kd
        self.step(self.current_action)

    def set_pid_valvula(self, kp, ki, kd):
        self.current_action[9] = kp
        self.current_action[10] = ki
        self.current_action[11] = kd
        self.step(self.current_action)

    def set_flow_setpoint(self, flow_setpoint):
        self.current_action[2] = flow_setpoint
        self.step(self.current_action)

    def set_motor_energy(self, motor, value):
        if motor == 'corredera':
            self.current_action[13] = value
        elif motor == 'angulo':
            self.current_action[14] = value
        elif motor == 'valvula':
            self.current_action[15] = value
        self.step(self.current_action)

    def set_manual_mode(self, manual):
        self.current_action[12] = 1 if manual else 0
        self.step(self.current_action)

    def calibrate_compass(self):
        self.current_action[16] = 1
        self.step(self.current_action)
        self.current_action[16] = 0

    def set_reward_weights(self, flow_rate_weight, setpoint_weight, angle_horizontal_weight, angle_vertical_weight):
        self.weights['flow_rate_weight'] = flow_rate_weight
        self.weights['setpoint_weight'] = setpoint_weight
        self.weights['angle_horizontal_weight'] = angle_horizontal_weight
        self.weights['angle_vertical_weight'] = angle_vertical_weight

    def send_command(self, command):
        if self.ser is None or not self.ser.is_open:
            self.connect_serial()
        try:
            command_str = json.dumps(command) + '\n'
            print(f"Sent: {command_str}")
            if self.ser:
                self.ser.write(command_str.encode())
            if self.receive_callback:
                self.receive_callback(f"Sent: {command_str}")
        except serial.SerialException as e:
            print(f"Error writing to serial port: {e}")
            self.ser = None

class App(tk.Tk):
    def __init__(self, env_virtual, env_real):
        super().__init__()
        self.env_virtual = env_virtual
        self.env_real = env_real
        self.current_env = self.env_virtual

        self.title("Robot Control Interface")

        self.create_widgets()

        self.update_thread = threading.Thread(target=self.update_data)
        self.update_thread.daemon = True
        self.update_thread.start()

    def create_widgets(self):
        main_frame = tk.Frame(self)
        main_frame.pack(padx=10, pady=10, fill='both', expand=True)

        left_frame = tk.Frame(main_frame)
        left_frame.pack(side='left', fill='both', expand=True)

        right_frame = tk.Frame(main_frame)
        right_frame.pack(side='right', fill='y', expand=True)

        self.sliders = {}
        self.entries = {}
        self.labels = {}
        self.limits = {}

        slider_labels = ['Setpoint Corredera', 'Setpoint Ángulo', 'Setpoint Water']
        slider_ranges = [(0, 400), (0, 360), (0, 100)]

        for i, label in enumerate(slider_labels):
            frame = tk.Frame(left_frame)
            frame.pack(fill='x', pady=5)

            lbl = tk.Label(frame, text=label)
            lbl.pack(side='left')

            slider = tk.Scale(frame, from_=slider_ranges[i][0], to=slider_ranges[i][1], orient='horizontal', command=lambda value, l=label: self.update_slider_command(l, value))
            slider.pack(side='left', fill='x', expand=True)
            slider.bind("<ButtonRelease-1>", lambda event, l=label, s=slider: self.send_slider_command(event, l, s))
            self.sliders[label] = slider

            limit_btn = tk.Button(frame, text="Límite", command=lambda l=label: self.set_limit(l))
            limit_btn.pack(side='left')
            self.limits[label] = limit_btn

            self.labels[label] = tk.Label(frame, text="0")
            self.labels[label].pack(side='left')

        motor_labels = ['Energía Motor Corredera', 'Energía Motor Ángulo', 'Energía Motor Válvula']
        motor_keys = ['corredera', 'angulo', 'valvula']
        motor_ranges = [(-255, 255), (-255, 255), (-255, 255)]

        for i, (label, key) in enumerate(zip(motor_labels, motor_keys)):
            frame = tk.Frame(right_frame)
            frame.pack(fill='y', pady=5)

            lbl = tk.Label(frame, text=label)
            lbl.pack()

            slider = tk.Scale(frame, from_=motor_ranges[i][0], to=motor_ranges[i][1], orient='vertical', command=lambda value, k=key: self.update_motor_command(k, value))
            slider.pack(fill='y', expand=True)
            slider.bind("<ButtonRelease-1>", lambda event, k=key, s=slider: self.send_motor_command(event, k, s))
            self.sliders[label] = slider

            self.labels[label] = tk.Label(frame, text="0")
            self.labels[label].pack()

        pid_labels = [
            ('PID Kp (Corredera)', 'PID Ki (Corredera)', 'PID Kd (Corredera)'),
            ('PID Kp (Ángulo)', 'PID Ki (Ángulo)', 'PID Kd (Ángulo)'),
            ('PID Kp (Válvula)', 'PID Ki (Válvula)', 'PID Kd (Válvula)')
        ]

        for label_set in pid_labels:
            frame = tk.Frame(left_frame)
            frame.pack(fill='x', pady=5)

            for label in label_set:
                lbl = tk.Label(frame, text=label)
                lbl.pack(side='left')

                entry = tk.Entry(frame, width=10)
                entry.pack(side='left', fill='x', expand=True)
                entry.insert(0, '0.0')
                self.entries[label] = entry

                self.labels[label] = tk.Label(frame, text="0")
                self.labels[label].pack(side='left')

            btn = tk.Button(frame, text="Set", command=lambda ls=label_set: self.send_pid_command(ls))
            btn.pack(side='left')

        self.manual_mode_var = tk.IntVar()
        self.manual_mode_check = tk.Checkbutton(left_frame, text="Modo Manual", variable=self.manual_mode_var, command=self.toggle_manual_mode)
        self.manual_mode_check.pack(pady=5)

        self.calibrate_button = tk.Button(left_frame, text="Calibrar Brújula", command=self.calibrate_compass)
        self.calibrate_button.pack(pady=5)

        self.reset_button = tk.Button(left_frame, text="Reset", command=self.reset_robot)
        self.reset_button.pack(pady=5)

        self.comm_label = tk.Label(left_frame, text="Disconnected", bg="black", width=15)
        self.comm_label.pack(pady=2)

        connection_frame = tk.Frame(left_frame)
        connection_frame.pack(fill='x', pady=5)

        tk.Label(connection_frame, text="Virtual Port:").pack(side='left')
        self.virtual_port = tk.Entry(connection_frame)
        self.virtual_port.pack(side='left', padx=5)

        self.virtual_connect_button = tk.Button(connection_frame, text="Conectar Virtual", command=self.connect_virtual, bg="black", fg="white")
        self.virtual_connect_button.pack(side='left', padx=5)

        self.virtual_disconnect_button = tk.Button(connection_frame, text="Desconectar Virtual", command=self.disconnect_virtual, bg="black", fg="white")
        self.virtual_disconnect_button.pack(side='left', padx=5)

        tk.Label(connection_frame, text="Real Port:").pack(side='left')
        self.real_port = tk.Entry(connection_frame)
        self.real_port.pack(side='left', padx=5)

        self.real_connect_button = tk.Button(connection_frame, text="Conectar Real", command=self.connect_real, bg="black", fg="white")
        self.real_connect_button.pack(side='left', padx=5)

        self.real_disconnect_button = tk.Button(connection_frame, text="Desconectar Real", command=self.disconnect_real, bg="black", fg="white")
        self.real_disconnect_button.pack(side='left', padx=5)

        self.switch_button = tk.Button(left_frame, text="Switch Env", command=self.switch_env)
        self.switch_button.pack(pady=5)

        self.data_text_sent = tk.Text(self, height=5, width=50)
        self.data_text_sent.pack(pady=10)

        self.data_text_received = tk.Text(self, height=5, width=50)
        self.data_text_received.pack(pady=10)

    def update_slider_command(self, label, value):
        try:
            action = self.current_env.current_action.copy()
            slider_values = {
                'Setpoint Corredera': 0,
                'Setpoint Ángulo': 1,
                'Setpoint Water': 2
            }
            index = slider_values[label]
            action[index] = float(value)
            self.labels[label].config(text=f"{value:.2f}")
            print(f"Setting {label} to {value}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def send_slider_command(self, event, label, slider):
        try:
            value = slider.get()
            action = self.current_env.current_action.copy()
            slider_values = {
                'Setpoint Corredera': 0,
                'Setpoint Ángulo': 1,
                'Setpoint Water': 2
            }
            index = slider_values[label]
            action[index] = float(value)
            self.current_env.step(action)
            print(f"Sent {label} command with value: {value}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def update_motor_command(self, motor, value):
        try:
            value = float(value)
            self.labels[motor].config(text=f"{value:.2f}")
            print(f"Setting energy for {motor} to {value}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def send_motor_command(self, event, motor, slider):
        try:
            value = slider.get()
            self.current_env.set_motor_energy(motor, value)
            print(f"Sent {motor} motor command with value: {value}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def send_pid_command(self, label_set):
        try:
            command = {
                'actuadores': {
                    'pid_corredera': [0, 0, 0],
                    'pid_angle': [0, 0, 0],
                    'pid_valvula': [0, 0, 0]
                }
            }

            for label in label_set:
                value = float(self.entries[label].get())
                if 'Corredera' in label:
                    if 'Kp' in label:
                        command['actuadores']['pid_corredera'][0] = value
                    elif 'Ki' in label:
                        command['actuadores']['pid_corredera'][1] = value
                    elif 'Kd' in label:
                        command['actuadores']['pid_corredera'][2] = value
                elif 'Ángulo' in label:
                    if 'Kp' in label:
                        command['actuadores']['pid_angle'][0] = value
                    elif 'Ki' in label:
                        command['actuadores']['pid_angle'][1] = value
                    elif 'Kd' in label:
                        command['actuadores']['pid_angle'][2] = value
                elif 'Válvula' in label:
                    if 'Kp' in label:
                        command['actuadores']['pid_valvula'][0] = value
                    elif 'Ki' in label:
                        command['actuadores']['pid_valvula'][1] = value
                    elif 'Kd' in label:
                        command['actuadores']['pid_valvula'][2] = value

            print(f"Setting PID values: {command}")
            self.current_env.send_command(command)
        except ValueError as e:
            print(f"Invalid input: {e}")

    def toggle_manual_mode(self):
        manual_mode = self.manual_mode_var.get()
        print(f"Setting manual mode to {'ON' if manual_mode else 'OFF'}")
        self.current_env.set_manual_mode(manual_mode)

    def calibrate_compass(self):
        self.current_env.calibrate_compass()

    def reset_robot(self):
        self.current_env.reset()

    def connect_virtual(self):
        self.env_virtual.port = self.virtual_port.get()
        if self.env_virtual.connect_serial():
            self.virtual_connect_button.config(bg="green")
        else:
            self.virtual_connect_button.config(bg="red")

    def disconnect_virtual(self):
        if self.env_virtual.ser is not None:
            self.env_virtual.ser.close()
            self.virtual_connect_button.config(bg="black")

    def connect_real(self):
        self.env_real.port = self.real_port.get()
        if self.env_real.connect_serial():
            self.real_connect_button.config(bg="green")
        else:
            self.real_connect_button.config(bg="red")

    def disconnect_real(self):
        if self.env_real.ser is not None:
            self.env_real.ser.close()
            self.real_connect_button.config(bg="black")

    def switch_env(self):
        if self.current_env == self.env_virtual:
            self.current_env = self.env_real
            self.switch_button.config(text="Switch to Virtual")
        else:
            self.current_env = self.env_virtual
            self.switch_button.config(text="Switch to Real")

    def update_data(self):
        while True:
            data = self.current_env.get_observation()
            if data is not None:
                self.update_labels(data)
            time.sleep(1)

    def update_labels(self, data):
        labels_to_update = {
            'Setpoint Corredera': 3,
            'Setpoint Ángulo': 4,
            'Setpoint Water': 5,
            'PID Kp (Corredera)': 6,
            'PID Ki (Corredera)': 7,
            'PID Kd (Corredera)': 8,
            'PID Kp (Ángulo)': 9,
            'PID Ki (Ángulo)': 10,
            'PID Kd (Ángulo)': 11,
            'PID Kp (Válvula)': 12,
            'PID Ki (Válvula)': 13,
            'PID Kd (Válvula)': 14,
            'Energía Motor Corredera': 15,
            'Energía Motor Ángulo': 16,
            'Energía Motor Válvula': 17
        }

        for label, index in labels_to_update.items():
            self.labels[label].config(text=f"{data[index]:.2f}")

    def set_limit(self, label):
        pass

    def receive_callback(self, message):
        if "Sent:" in message:
            self.data_text_sent.insert(tk.END, message + "\n")
            self.data_text_sent.see(tk.END)
        else:
            self.data_text_received.insert(tk.END, message + "\n")
            self.data_text_received.see(tk.END)

class RobotControl:
    def __init__(self, env_virtual, env_real):
        self.env_virtual = env_virtual
        self.env_real = env_real
        self.current_env = self.env_virtual

    def switch_env(self):
        self.current_env = self.env_real if self.current_env == self.env_virtual else self.env_virtual

    def use_interface(self):
        app = App(self.env_virtual, self.env_real)
        self.env_virtual.receive_callback = app.receive_callback
        self.env_real.receive_callback = app.receive_callback
        app.mainloop()

    def set_servos(self, angle_horizontal, angle_vertical, angle_valve):
        self.current_env.set_servos(angle_horizontal, angle_vertical, angle_valve)

    def set_pid_corredera(self, kp, ki, kd):
        self.current_env.set_pid_corredera(kp, ki, kd)

    def set_pid_angulo(self, kp, ki, kd):
        self.current_env.set_pid_angulo(kp, ki, kd)

    def set_pid_valvula(self, kp, ki, kd):
        self.current_env.set_pid_valvula(kp, ki, kd)

    def set_flow_setpoint(self, flow_setpoint):
        self.current_env.set_flow_setpoint(flow_setpoint)

    def set_motor_energy(self, motor, value):
        self.current_env.set_motor_energy(motor, value)

    def set_manual_mode(self, manual):
        self.current_env.set_manual_mode(manual)

    def calibrate_compass(self):
        self.current_env.calibrate_compass()

    def set_reward_weights(self, flow_rate_weight, setpoint_weight, angle_horizontal_weight, angle_vertical_weight):
        self.current_env.set_reward_weights(flow_rate_weight, setpoint_weight, angle_horizontal_weight, angle_vertical_weight)

    def send_command(self, command):
        self.current_env.send_command(command)

def main():
    virtual_env = RobotEnv(port='COM11', baudrate=115200, receive_callback=None)
    real_env = RobotEnv(port='COM12', baudrate=115200, receive_callback=None)
    robot_control = RobotControl(virtual_env, real_env)

    # Use the interface or call methods from RobotControl as needed
    robot_control.use_interface()  # Launch the interface

if __name__ == "__main__":
    main()
