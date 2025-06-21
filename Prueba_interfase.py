import tkinter as tk
from tkinter import ttk


class ControlInterface(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Interfaz de Control con Teclado")
        self.geometry("400x400")
        self.setup_ui()
        self.bind_keys()

    def setup_ui(self):
        # Crear notebook para pestañas
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(expand=True, fill='both')

        # Crear frame de control
        self.control_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.control_frame, text="Control")

        # Diccionario para almacenar los valores
        self.values = {
            'Valor 1': 0,
            'Valor 2': 0,
            'Valor 3': 0,
            'Valor 4': 0,
            'Valor 5': 0
        }

        # Información de las teclas asignadas
        self.key_bindings = {
            'Valor 1': {'increase': 'Up', 'decrease': 'Down'},
            'Valor 2': {'increase': 'Right', 'decrease': 'Left'},
            'Valor 3': {'increase': 'w', 'decrease': 's'},
            'Valor 4': {'increase': 'Right', 'decrease': 'Left'},
            'Valor 5': {'increase': 'Up', 'decrease': 'Down'}
        }

        # Crear widgets para cada valor
        for idx, (label, value) in enumerate(self.values.items()):
            frame = ttk.Frame(self.control_frame)
            frame.pack(pady=10, padx=10, fill='x')

            # Etiqueta del valor
            ttk.Label(frame, text=label, width=15).pack(side='left')

            # Campo de entrada para mostrar y editar el valor
            entry = ttk.Entry(frame, width=10)
            entry.pack(side='left')
            entry.insert(0, str(value))
            self.values[label] = entry  # Guardar la referencia del Entry widget

            # Desactivar inicialmente los valores 4 y 5
            if label in ['Valor 4', 'Valor 5']:
                entry.config(state='disabled')

            # Etiqueta de instrucciones de teclas
            if label not in ['Valor 4', 'Valor 5']:
                keys = self.key_bindings[label]
                instruction = f"Aumentar: '{keys['increase']}' | Disminuir: '{keys['decrease']}'"
                ttk.Label(frame, text=instruction).pack(side='left', padx=10)
            else:
                ttk.Label(frame, text="Controlado por flechas cuando se activa").pack(side='left', padx=10)

            # Botón de enviar
            send_button = ttk.Button(frame, text="Enviar", command=lambda l=label: self.send_value(l))
            send_button.pack(side='left', padx=5)

        # Checkbox para activar/desactivar los primeros tres valores y activar los valores 4 y 5
        self.checkbox_var = tk.IntVar()
        self.checkbox = ttk.Checkbutton(
            self.control_frame, text="Activar modo alternativo", variable=self.checkbox_var, command=self.toggle_mode
        )
        self.checkbox.pack(pady=10)

        # Crear botones que representan las teclas
        self.key_buttons = {}
        self.create_key_buttons()

    def create_key_buttons(self):
        button_frame = ttk.Frame(self.control_frame)
        button_frame.pack(pady=10)

        # Crear botones en el orden deseado
        self.create_key_button(button_frame, 'Up', '↑', row=0, column=1)
        self.create_key_button(button_frame, 'Down', '↓', row=2, column=1)
        self.create_key_button(button_frame, 'Left', '←', row=1, column=0)
        self.create_key_button(button_frame, 'Right', '→', row=1, column=2)
        self.create_key_button(button_frame, 'w', 'W', row=0, column=0)
        self.create_key_button(button_frame, 's', 'S', row=2, column=0)

    def create_key_button(self, parent_frame, key, text, row, column):
        frame = ttk.Frame(parent_frame)
        frame.pack(side='left', padx=5, pady=5)
        button = ttk.Button(frame, text=text, width=5)
        button.pack()
        self.key_buttons[key] = button

    def bind_keys(self):
        # Asociar eventos de teclado
        self.bind('<Up>', self.handle_key_press)
        self.bind('<Down>', self.handle_key_press)
        self.bind('<Right>', self.handle_key_press)
        self.bind('<Left>', self.handle_key_press)
        self.bind('w', lambda event: self.update_value('Valor 3', 1))
        self.bind('s', lambda event: self.update_value('Valor 3', -1))

        # Asociar eventos de tecla suelta
        self.bind('<KeyRelease-Up>', self.handle_key_release)
        self.bind('<KeyRelease-Down>', self.handle_key_release)
        self.bind('<KeyRelease-Right>', self.handle_key_release)
        self.bind('<KeyRelease-Left>', self.handle_key_release)
        self.bind('<KeyRelease-w>', self.handle_key_release)
        self.bind('<KeyRelease-s>', self.handle_key_release)

    def handle_key_press(self, event):
        if event.keysym in self.key_buttons:
            self.key_buttons[event.keysym].config(style='Pressed.TButton')

        if self.checkbox_var.get():
            if event.keysym in ['Up', 'Down']:
                delta = 1 if event.keysym == 'Up' else -1
                self.update_value('Valor 5', delta)
            elif event.keysym in ['Right', 'Left']:
                delta = 1 if event.keysym == 'Right' else -1
                self.update_value('Valor 4', delta)
        else:
            if event.keysym == 'Up':
                self.update_value('Valor 1', 1)
            elif event.keysym == 'Down':
                self.update_value('Valor 1', -1)
            elif event.keysym == 'Right':
                self.update_value('Valor 2', 1)
            elif event.keysym == 'Left':
                self.update_value('Valor 2', -1)

    def handle_key_release(self, event):
        if event.keysym in self.key_buttons:
            self.key_buttons[event.keysym].config(style='TButton')

    def toggle_mode(self):
        is_active = self.checkbox_var.get()

        # Desactivar/activar los primeros tres valores
        for key in ['Valor 1', 'Valor 2', 'Valor 3']:
            entry = self.values[key]
            entry.config(state='disabled' if is_active else 'normal')

        # Activar/desactivar los valores 4 y 5
        for key in ['Valor 4', 'Valor 5']:
            entry = self.values[key]
            entry.config(state='normal' if is_active else 'disabled')

    def update_value(self, label, delta):
        entry = self.values[label]
        try:
            current_value = int(entry.get())
            new_value = current_value + delta
            entry.delete(0, tk.END)
            entry.insert(0, str(new_value))
            print(f"{label} actualizado a {new_value}")
        except ValueError:
            print(f"Entrada inválida para {label}. Por favor, ingresa un número entero.")

    def send_value(self, label):
        entry = self.values[label]
        try:
            value = int(entry.get())
            print(f"Enviando {label}: {value}")
            # Aquí puedes agregar la lógica para enviar el valor al entorno o dispositivo correspondiente
        except ValueError:
            print(f"Entrada inválida para {label}. Por favor, ingresa un número entero.")


if __name__ == "__main__":
    app = ControlInterface()
    app.mainloop()
