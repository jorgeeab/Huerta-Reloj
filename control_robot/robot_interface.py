import tkinter as tk
import threading
import time

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
        self.buttons = []

        # Slider for Setpoint Corredera
        frame = tk.Frame(left_frame)
        frame.pack(fill='x', pady=5)
        lbl = tk.Label(frame, text='Setpoint Corredera')
        lbl.pack(side='left')
        slider = tk.Scale(frame, from_=0, to=400, orient='horizontal', command=lambda value: self.update_slider_command('Setpoint Corredera', value), state=tk.DISABLED)
        slider.pack(side='left', fill='x', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_slider_command(event, 'Setpoint Corredera', slider))
        self.sliders['Setpoint Corredera'] = slider
        limit_btn = tk.Button(frame, text="Límite", command=lambda: self.set_limit('Setpoint Corredera'), state=tk.DISABLED)
        limit_btn.pack(side='left')
        self.limits['Setpoint Corredera'] = limit_btn
        self.buttons.append(limit_btn)
        self.labels['Setpoint Corredera'] = tk.Label(frame, text="0")
        self.labels['Setpoint Corredera'].pack(side='left')

        # Slider for Setpoint Ángulo
        frame = tk.Frame(left_frame)
        frame.pack(fill='x', pady=5)
        lbl = tk.Label(frame, text='Setpoint Ángulo')
        lbl.pack(side='left')
        slider = tk.Scale(frame, from_=0, to=360, orient='horizontal', command=lambda value: self.update_slider_command('Setpoint Ángulo', value), state=tk.DISABLED)
        slider.pack(side='left', fill='x', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_slider_command(event, 'Setpoint Ángulo', slider))
        self.sliders['Setpoint Ángulo'] = slider
        limit_btn = tk.Button(frame, text="Límite", command=lambda: self.set_limit('Setpoint Ángulo'), state=tk.DISABLED)
        limit_btn.pack(side='left')
        self.limits['Setpoint Ángulo'] = limit_btn
        self.buttons.append(limit_btn)
        self.labels['Setpoint Ángulo'] = tk.Label(frame, text="0")
        self.labels['Setpoint Ángulo'].pack(side='left')

        # Slider for Setpoint Water
        frame = tk.Frame(left_frame)
        frame.pack(fill='x', pady=5)
        lbl = tk.Label(frame, text='Setpoint Water')
        lbl.pack(side='left')
        slider = tk.Scale(frame, from_=0, to=100, orient='horizontal', command=lambda value: self.update_slider_command('Setpoint Water', value), state=tk.DISABLED)
        slider.pack(side='left', fill='x', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_slider_command(event, 'Setpoint Water', slider))
        self.sliders['Setpoint Water'] = slider
        limit_btn = tk.Button(frame, text="Límite", command=lambda: self.set_limit('Setpoint Water'), state=tk.DISABLED)
        limit_btn.pack(side='left')
        self.limits['Setpoint Water'] = limit_btn
        self.buttons.append(limit_btn)
        self.labels['Setpoint Water'] = tk.Label(frame, text="0")
        self.labels['Setpoint Water'].pack(side='left')

        # Slider for Energía Motor Corredera
        frame = tk.Frame(right_frame)
        frame.pack(fill='y', pady=5)
        lbl = tk.Label(frame, text='Energía Motor Corredera')
        lbl.pack()
        slider = tk.Scale(frame, from_=-255, to=255, orient='vertical', command=lambda value: self.update_motor_command('corredera', value), state=tk.DISABLED)
        slider.pack(fill='y', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_motor_command(event, 'corredera', slider))
        self.sliders['Energía Motor Corredera'] = slider
        self.labels['Energía Motor Corredera'] = tk.Label(frame, text="0")
        self.labels['Energía Motor Corredera'].pack()

        # Slider for Energía Motor Ángulo
        frame = tk.Frame(right_frame)
        frame.pack(fill='y', pady=5)
        lbl = tk.Label(frame, text='Energía Motor Ángulo')
        lbl.pack()
        slider = tk.Scale(frame, from_=-255, to=255, orient='vertical', command=lambda value: self.update_motor_command('angulo', value), state=tk.DISABLED)
        slider.pack(fill='y', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_motor_command(event, 'angulo', slider))
        self.sliders['Energía Motor Ángulo'] = slider
        self.labels['Energía Motor Ángulo'] = tk.Label(frame, text="0")
        self.labels['Energía Motor Ángulo'].pack()

        # Slider for Energía Motor Válvula
        frame = tk.Frame(right_frame)
        frame.pack(fill='y', pady=5)
        lbl = tk.Label(frame, text='Energía Motor Válvula')
        lbl.pack()
        slider = tk.Scale(frame, from_=-255, to=255, orient='vertical', command=lambda value: self.update_motor_command('valvula', value), state=tk.DISABLED)
        slider.pack(fill='y', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_motor_command(event, 'valvula', slider))
        self.sliders['Energía Motor Válvula'] = slider
        self.labels['Energía Motor Válvula'] = tk.Label(frame, text="0")
        self.labels['Energía Motor Válvula'].pack()

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

                entry = tk.Entry(frame, width=10, state=tk.DISABLED)
                entry.pack(side='left', fill='x', expand=True)
                entry.insert(0, '0.0')
                self.entries[label] = entry

                self.labels[label] = tk.Label(frame, text="0")
                self.labels[label].pack(side='left')

            btn = tk.Button(frame, text="Set", command=lambda ls=label_set: self.send_pid_command(ls), state=tk.DISABLED)
            btn.pack(side='left')
            self.buttons.append(btn)

        self.manual_mode_var = tk.IntVar()
        self.manual_mode_check = tk.Checkbutton(left_frame, text="Modo Manual", variable=self.manual_mode_var, command=self.toggle_manual_mode, state=tk.DISABLED)
        self.manual_mode_check.pack(pady=5)
        self.buttons.append(self.manual_mode_check)

        self.calibrate_button = tk.Button(left_frame, text="Calibrar Brújula", command=self.calibrate_compass, state=tk.DISABLED)
        self.calibrate_button.pack(pady=5)
        self.buttons.append(self.calibrate_button)

        self.reset_button = tk.Button(left_frame, text="Reset", command=self.reset_robot, state=tk.DISABLED)
        self.reset_button.pack(pady=5)
        self.buttons.append(self.reset_button)

        self.comm_label = tk.Label(left_frame, text="Disconnected", bg="black", width=15)
        self.comm_label.pack(pady=2)

        connection_frame = tk.Frame(left_frame)
        connection_frame.pack(fill='x', pady=5)

        tk.Label(connection_frame, text="Virtual Port:").pack(side='left')
        self.virtual_port = tk.Entry(connection_frame)
        self.virtual_port.pack(side='left', padx=5)
        self.virtual_port.insert(0, 'COM12')  # Valor predeterminado

        self.virtual_connect_button = tk.Button(connection_frame, text="Conectar Virtual", command=self.toggle_virtual_connection, bg="black", fg="white")
        self.virtual_connect_button.pack(side='left', padx=5)

        tk.Label(connection_frame, text="Real Port:").pack(side='left')
        self.real_port = tk.Entry(connection_frame)
        self.real_port.pack(side='left', padx=5)
        self.real_port.insert(0, 'COM4')  # Valor predeterminado

        self.real_connect_button = tk.Button(connection_frame, text="Conectar Real", command=self.toggle_real_connection, bg="black", fg="white")
        self.real_connect_button.pack(side='left', padx=5)

        self.switch_button = tk.Button(left_frame, text="Switch Env", command=self.switch_env, state=tk.DISABLED)
        self.switch_button.pack(pady=5)
        self.buttons.append(self.switch_button)

        # Aumentar el tamaño de los cuadros de texto y reducir el tamaño de la fuente
        self.text_font = ("TkFixedFont", 8)  # Configurar fuente con tamaño 8

        self.data_text_sent = tk.Text(self, height=5, width=100, font=self.text_font)
        self.data_text_sent.pack(pady=10)

        self.data_text_received = tk.Text(self, height=5, width=100, font=self.text_font)
        self.data_text_received.pack(pady=10)

        self.update_button_states()

    def update_slider_command(self, label, value):
        try:
            action = self.env.current_action.copy()  # Copiar la acción actual del entorno
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
            action = self.env.current_action.copy()  # Copiar la acción actual del entorno
            slider_values = {
                'Setpoint Corredera': 0,
                'Setpoint Ángulo': 1,
                'Setpoint Water': 2
            }
            index = slider_values[label]
            action[index] = float(value)
            self.env.step(action)  # Ejecutar un paso en el entorno con la acción modificada
            command_str = f"Sent {label} command with value: {value}\n"
            self.data_text_sent.insert(tk.END, command_str)
            self.data_text_sent.see(tk.END)
            print(command_str.strip())  # Imprimir en la consola también
        except ValueError as e:
            print(f"Invalid input: {e}")
    def update_motor_command(self, motor, value):
        try:
            value = float(value)
            self.labels[f'Energía Motor {motor.capitalize()}'].config(text=f"{value:.2f}")
            print(f"Setting energy for {motor} to {value}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def send_motor_command(self, event, motor, slider):
        try:
            value = slider.get()
            self.current_env.set_motor_energy(motor, value)
            msg = f"Sent {motor} motor command with value: {value}\n"
            self.data_text_sent.insert(tk.END, msg)
            self.data_text_sent.see(tk.END)
            print(msg.strip())
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
        msg = f"Set manual mode to {'ON' if manual_mode else 'OFF'}\n"
        self.current_env.set_manual_mode(manual_mode)
        self.data_text_sent.insert(tk.END, msg)
        self.data_text_sent.see(tk.END)
        print(msg.strip())

    def calibrate_compass(self):
        self.current_env.calibrate_compass()
        msg = "Sent compass calibration command\n"
        self.data_text_sent.insert(tk.END, msg)
        self.data_text_sent.see(tk.END)
        print(msg.strip())

    def reset_robot(self):
        self.current_env.reset()
        msg = "Sent reset command\n"
        self.data_text_sent.insert(tk.END, msg)
        self.data_text_sent.see(tk.END)
        print(msg.strip())

    def toggle_virtual_connection(self):
        if self.env_virtual.ser is None or not self.env_virtual.ser.is_open:
            self.env_virtual.port = self.virtual_port.get()
            if self.env_virtual.connect_serial():
                self.virtual_connect_button.config(bg="green", text="Desconectar Virtual")
                msg = "Connected Virtual\n"
            else:
                self.virtual_connect_button.config(bg="red", text="Conectar Virtual")
                msg = "Failed Virtual connection\n"
        else:
            self.env_virtual.disconnect_serial()
            self.virtual_connect_button.config(bg="black", text="Conectar Virtual")
            msg = "Disconnected Virtual\n"
        self.update_button_states()
        self.data_text_sent.insert(tk.END, msg)
        self.data_text_sent.see(tk.END)
        print(msg.strip())

    def toggle_real_connection(self):
        if self.env_real.ser is None or not self.env_real.ser.is_open:
            self.env_real.port = self.real_port.get()
            if self.env_real.connect_serial():
                self.real_connect_button.config(bg="green", text="Desconectar Real")
                msg = "Connected Real\n"
            else:
                self.real_connect_button.config(bg="red", text="Conectar Real")
                msg = "Failed Real connection\n"
        else:
            self.env_real.disconnect_serial()
            self.real_connect_button.config(bg="black", text="Conectar Real")
            msg = "Disconnected Real\n"
        self.update_button_states()
        self.data_text_sent.insert(tk.END, msg)
        self.data_text_sent.see(tk.END)
        print(msg.strip())

    def switch_env(self):
        if self.current_env.ser is None or not self.current_env.ser.is_open:
            print("No se puede cambiar de entorno: el entorno actual no está conectado.")
            return
        if self.current_env == self.env_virtual:
            if self.env_real.ser is not None and self.env_real.ser.is_open:
                self.current_env = self.env_real
                self.switch_button.config(text="Switch to Virtual")
            else:
                print("No se puede cambiar de entorno: el entorno real no está conectado.")
        else:
            if self.env_virtual.ser is not None and self.env_virtual.ser.is_open:
                self.current_env = self.env_virtual
                self.switch_button.config(text="Switch to Real")
            else:
                print("No se puede cambiar de entorno: el entorno virtual no está conectado.")
        self.update_button_states()

    def update_button_states(self):
        connected = (self.env_virtual.ser is not None and self.env_virtual.ser.is_open) or (self.env_real.ser is not None and self.env_real.ser.is_open)
        for button in self.buttons:
            button.config(state=tk.NORMAL if connected else tk.DISABLED)
        for slider in self.sliders.values():
            slider.config(state=tk.NORMAL if connected else tk.DISABLED)
        for entry in self.entries.values():
            entry.config(state=tk.NORMAL if connected else tk.DISABLED)
        self.switch_button.config(state=tk.NORMAL if connected else tk.DISABLED)

    def update_data(self):
        while True:
            if (self.env_virtual.ser is not None and self.env_virtual.ser.is_open) or (self.env_real.ser is not None and self.env_real.ser.is_open):
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
            if isinstance(data[index], (int, float)):  # Verificar si el valor es numérico
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
