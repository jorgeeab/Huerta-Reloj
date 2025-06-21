import tkinter as tk

# Función que se ejecuta cuando se mueve cualquiera de los sliders
def print_values():
    val1 = slider1.get()
    val2 = slider2.get()
    val3 = slider3.get()
    print(f"Valor del Slider 1: {val1}, Slider 2: {val2}, Slider 3: {val3}")

# Crear la ventana principal
root = tk.Tk()
root.title("Ejemplo de Varios Sliders en Tkinter")

# Crear sliders
slider1 = tk.Scale(root, from_=0, to=100, orient=tk.HORIZONTAL, label="Slider 1", command=lambda x: print_values())
slider2 = tk.Scale(root, from_=0, to=200, orient=tk.HORIZONTAL, label="Slider 2", command=lambda x: print_values())
slider3 = tk.Scale(root, from_=0, to=300, orient=tk.HORIZONTAL, label="Slider 3", command=lambda x: print_values())

# Empaquetar sliders en la ventana
slider1.pack()
slider2.pack()
slider3.pack()

# Ejecutar el bucle principal de la aplicación
root.mainloop()
