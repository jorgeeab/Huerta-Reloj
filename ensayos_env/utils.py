import os
import pandas as pd

import os
import pandas as pd

def crear_archivos_plantas_y_regimenes(archivo_plantas, archivo_regimenes):
    datos_plantas = pd.DataFrame({
        'Nombre de la Planta': ['Planta1', 'Planta2'],
        'Regimen': ['Regimen 1', 'Regimen 2'],
        'Dia Uno': ['2024-01-01', '2024-02-01'],
        'Posición X': [1, 4],
        'Posición Y': [2, 5],
        'Posición Z': [3, 6],
        'Velocidad de Agua': [0, 0],
        'Detalles': ['Detalle 1', 'Detalle 2']  # Agregar la columna Detalles
    })

    datos_regimenes = pd.DataFrame({
        'Numero_Día': [1, 3],
        'Hora': ['08:00', '14:00'],
        'Tarea': ['Riego', 'Abonado'],
        'magnitud': [5, 10],
        'unidades': ['litros', 'gramos'],
        'Detalles': ['Riego ligero', 'Abono orgánico']  # Asegurarse de incluir Detalles aquí también
    })

    if not os.path.exists(archivo_plantas):
        with pd.ExcelWriter(archivo_plantas, engine='openpyxl') as writer:
            for era in ['Era1', 'Era2']:
                datos_plantas.to_excel(writer, sheet_name=era, index=False)

    if not os.path.exists(archivo_regimenes):
        with pd.ExcelWriter(archivo_regimenes, engine='openpyxl') as writer:
            for regimen in ['Regimen 1', 'Regimen 2']:
                datos_regimenes.to_excel(writer, sheet_name=regimen, index=False)
