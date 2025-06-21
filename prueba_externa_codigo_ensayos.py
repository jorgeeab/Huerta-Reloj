from ensayos_env import EnsayosEnv,  Interfaz
from tkinter import Tk


# Inicializar el entorno
env = EnsayosEnv(archivo_plantas="Plantas.xlsx", archivo_regimenes="Regimenes.xlsx", archivo_ensayos="Ensayos.xlsx")
# 1. Crear una nueva era
env.crear_era("Era_de_pruebaaa")
# 2. Agregar una nueva planta
nueva_planta = {
    "Nombre de la Planta": "OCALOCAe",
    "Regimen": "Regimen 1",
    "Dia Uno": "2024-01-01",
    "Posición X": 2,
    "Posición Y": 3,
    "Posición Z": 1,
    "Velocidad de Agua": 50
}
env.agregar_planta("Era_de_pruebaaa", nueva_planta)
# # 3. Modificar una planta existente

# Archivos de ejemplo para plantas, regímenes, y ensayos
archivo_plantas = "Plantas.xlsx"
archivo_regimenes = "Regimenes.xlsx"
archivo_ensayos = "Ensayos.xlsx"

# Inicializar la ventana principal de Tkinter
root = Tk()

# Crear la instancia de la interfaz gráfica
app = Interfaz(root, archivo_plantas, archivo_regimenes, archivo_ensayos)

# Ejecutar el loop principal de la interfaz
root.mainloop()

# planta_modificada = {
#     "Nombre de la Planta": "Tomate",
#     "Regimen": "Regimen 1",
#     "Dia Uno": "2024-01-01",
#     "Posición X": 5,
#     "Posición Y": 4,
#     "Posición Z": 2,
#     "Velocidad de Agua": 60
# }
# env.modificar_planta("Nueva_Era", "Tomate", planta_modificada)

# # 4. Eliminar una planta
# env.eliminar_planta("Nueva_Era", "Tomate")
#
# # 5. Agregar un nuevo régimen
# nuevo_regimen = [
#     {"Tarea": "Riego", "Numero_Día": 1, "Hora": "08:00", "tiempo_ejecución(s)": 300, "magnitud": 10, "unidades": "litros"},
#     {"Tarea": "Abono", "Numero_Día": 3, "Hora": "12:00", "tiempo_ejecución(s)": 0, "magnitud": 5, "unidades": "gramos"}
# ]
# env.agregar_regimen("Nuevo_Regimen", nuevo_regimen)
#
# # 6. Modificar una tarea en un régimen
# tarea_modificada = {"Tarea": "Riego", "Numero_Día": 1, "Hora": "09:00", "tiempo_ejecución(s)": 200, "magnitud": 15, "unidades": "litros"}
# env.modificar_tarea_regimen("Nuevo_Regimen", 0, tarea_modificada)
#
# # 7. Eliminar una tarea en un régimen
# env.eliminar_tarea_regimen("Nuevo_Regimen", 1)
#
# # 8. Crear un nuevo ensayo basado en plantas y regímenes
# env.crear_ensayo()
#
# # 9. Cargar y mostrar los ensayos
# ensayos = env.cargar_ensayos()
# print(ensayos)
#
# # 10. Guardar los cambios en los archivos Excel
# env.guardar_cambios()
