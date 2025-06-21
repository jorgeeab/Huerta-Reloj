import tkinter as tk
import threading
import time
import serial

class SerialCommunication:
    def __init__(self, port, baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate)
            print(f"Connected to {self.port}")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to {self.port}: {e}")
            return False

    def disconnect(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print(f"Disconnected from {self.port}")

    def send(self, data):
        if self.ser and self.ser.is_open:
            self.ser.write(data.encode())
            print(f"Sent: {data}")

    def receive(self):
        if self.ser and self.ser.is_open:
            return self.ser.readline().decode().strip()
        return None

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        self.serial_com = SerialCommunication('COM13')

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
        slider = tk.Scale(frame, from_=0, to=400, orient='horizontal', command=lambda value: self.update_slider_command('Setpoint Corredera', value))
        slider.pack(side='left', fill='x', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_slider_command(event, 'Setpoint Corredera', slider))
        self.sliders['Setpoint Corredera'] = slider
        limit_btn = tk.Button(frame, text="Límite", command=lambda: self.set_limit('Setpoint Corredera'))
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
        slider = tk.Scale(frame, from_=0, to=360, orient='horizontal', command=lambda value: self.update_slider_command('Setpoint Ángulo', value))
        slider.pack(side='left', fill='x', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_slider_command(event, 'Setpoint Ángulo', slider))
        self.sliders['Setpoint Ángulo'] = slider
        limit_btn = tk.Button(frame, text="Límite", command=lambda: self.set_limit('Setpoint Ángulo'))
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
        slider = tk.Scale(frame, from_=0, to=100, orient='horizontal', command=lambda value: self.update_slider_command('Setpoint Water', value))
        slider.pack(side='left', fill='x', expand=True)
        slider.bind("<ButtonRelease-1>", lambda event: self.send_slider_command(event, 'Setpoint Water', slider))
        self.sliders['Setpoint Water'] = slider
        limit_btn = tk.Button(frame, text="Límite", command=lambda: self.set_limit('Setpoint Water'))
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
        slider = tk.Scale(frame, from_=-255, to=255, orient='vertical', command=lambda value: self.update_motor_command('corredera', value))
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
        slider = tk.Scale(frame, from_=-255, to=255, orient='vertical', command=lambda value: self.update_motor_command('angulo', value))
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
        slider = tk.Scale(frame, from_=-255, to=255, orient='vertical', command=lambda value: self.update_motor_command('valvula', value))
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

                entry = tk.Entry(frame, width=10)
                entry.pack(side='left', fill='x', expand=True)
                entry.insert(0, '0.0')
                self.entries[label] = entry

                self.labels[label] = tk.Label(frame, text="0")
                self.labels[label].pack(side='left')

            btn = tk.Button(frame, text="Set", command=lambda ls=label_set: self.send_pid_command(ls))
            btn.pack(side='left')
            self.buttons.append(btn)

        self.manual_mode_var = tk.IntVar()
        self.manual_mode_check = tk.Checkbutton(left_frame, text="Modo Manual", variable=self.manual_mode_var, command=self.toggle_manual_mode)
        self.manual_mode_check.pack(pady=5)
        self.buttons.append(self.manual_mode_check)

        self.calibrate_button = tk.Button(left_frame, text="Calibrar Brújula", command=self.calibrate_compass)
        self.calibrate_button.pack(pady=5)
        self.buttons.append(self.calibrate_button)

        self.reset_button = tk.Button(left_frame, text="Reset", command=self.reset_robot)
        self.reset_button.pack(pady=5)
        self.buttons.append(self.reset_button)

        self.comm_label = tk.Label(left_frame, text="Disconnected", bg="black", width=15)
        self.comm_label.pack(pady=2)

        connection_frame = tk.Frame(left_frame)
        connection_frame.pack(fill='x', pady=5)

        tk.Label(connection_frame, text="Port:").pack(side='left')
        self.serial_port = tk.Entry(connection_frame)
        self.serial_port.pack(side='left', padx=5)
        self.serial_port.insert(0, 'COM13')  # Valor predeterminado

        self.connect_button = tk.Button(connection_frame, text="Conectar", command=self.toggle_connection, bg="black", fg="white")
        self.connect_button.pack(side='left', padx=5)

        # Aumentar el tamaño de los cuadros de texto y reducir el tamaño de la fuente
        self.text_font = ("TkFixedFont", 8)  # Configurar fuente con tamaño 8

        self.data_text_sent = tk.Text(self, height=5, width=100, font=self.text_font)
        self.data_text_sent.pack(pady=10)

        self.data_text_received = tk.Text(self, height=5, width=100, font=self.text_font)
        self.data_text_received.pack(pady=10)

    def update_slider_command(self, label, value):
        try:
            self.labels[label].config(text=f"{value:.2f}")
            print(f"Setting {label} to {value}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def send_slider_command(self, event, label, slider):
        try:
            value = slider.get()
            command = f"{label}={value}"
            self.serial_com.send(command)
            print(f"Sent {label} command with value: {value}")
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
            command = f"Motor_{motor}={value}"
            self.serial_com.send(command)
            print(f"Sent {motor} motor command with value: {value}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def send_pid_command(self, label_set):
        try:
            command = {
                'PID_Corredera': [0, 0, 0],
                'PID_Angulo': [0, 0, 0],
                'PID_Valvula': [0, 0, 0]
            }

            for label in label_set:
                value = float(self.entries[label].get())
                if 'Corredera' in label:
                    if 'Kp' in label:
                        command['PID_Corredera'][0] = value
                    elif 'Ki' in label:
                        command['PID_Corredera'][1] = value
                    elif 'Kd' in label:
                        command['PID_Corredera'][2] = value
                elif 'Ángulo' in label:
                    if 'Kp' in label:
                        command['PID_Angulo'][0] = value
                    elif 'Ki' in label:
                        command['PID_Angulo'][1] = value
                    elif 'Kd' in label:
                        command['PID_Angulo'][2] = value
                elif 'Válvula' in label:
                    if 'Kp' in label:
                        command['PID_Valvula'][0] = value
                    elif 'Ki' in label:
                        command['PID_Valvula'][1] = value
                    elif 'Kd' in label:
                        command['PID_Valvula'][2] = value

            pid_command_str = f"PID={command}"
            self.serial_com.send(pid_command_str)
            print(f"Setting PID values: {pid_command_str}")
        except ValueError as e:
            print(f"Invalid input: {e}")

    def toggle_manual_mode(self):
        manual_mode = self.manual_mode_var.get()
        command = f"Manual_Mode={'ON' if manual_mode else 'OFF'}"
        self.serial_com.send(command)
        print(f"Setting manual mode to {'ON' if manual_mode else 'OFF'}")

    def calibrate_compass(self):
        self.serial_com.send("Calibrate_Compass")
        print("Calibrating compass")

    def reset_robot(self):
        self.serial_com.send("Reset")
        print("Resetting robot")

    def toggle_connection(self):
        if self.serial_com.ser is None or not self.serial_com.ser.is_open:
            self.serial_com.port = self.serial_port.get()
            if self.serial_com.connect():
                self.connect_button.config(bg="green", text="Desconectar")
                self.comm_label.config(text="Connected", bg="green")
            else:
                self.connect_button.config(bg="red", text="Conectar")
                self.comm_label.config(text="Disconnected", bg="red")
        else:
            self.serial_com.disconnect()
            self.connect_button.config(bg="black", text="Conectar")
            self.comm_label.config(text="Disconnected", bg="black")

    def update_data(self):
        while True:
            if self.serial_com.ser is not None and self.serial_com.ser.is_open:
                data = self.serial_com.receive()
                if data:
                    self.data_text_received.insert(tk.END, f"{data}\n")
                    self.data_text_received.see(tk.END)
                    self.update_labels(data)
            time.sleep(1)

    def update_labels(self, data):
        try:
            sensor_data = data.split(',')
            if len(sensor_data) >= 18:  # Ensure there are enough data points
                labels_to_update = {
                    'Setpoint Corredera': 0,
                    'Setpoint Ángulo': 1,
                    'Setpoint Water': 2,
                    'PID Kp (Corredera)': 3,
                    'PID Ki (Corredera)': 4,
                    'PID Kd (Corredera)': 5,
                    'PID Kp (Ángulo)': 6,
                    'PID Ki (Ángulo)': 7,
                    'PID Kd (Ángulo)': 8,
                    'PID Kp (Válvula)': 9,
                    'PID Ki (Válvula)': 10,
                    'PID Kd (Válvula)': 11,
                    'Energía Motor Corredera': 12,
                    'Energía Motor Ángulo': 13,
                    'Energía Motor Válvula': 14
                }

                for label, index in labels_to_update.items():
                    value = float(sensor_data[index])
                    self.labels[label].config(text=f"{value:.2f}")
        except ValueError as e:
            print(f"Invalid sensor data: {e}")

    def set_limit(self, label):
        pass

if __name__ == "__main__":
    app = App()
    app.mainloop()

