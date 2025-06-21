# protocolos.py
import os

class Protocolo:
    def __init__(self, nombre_protocolo):
        self.nombre_protocolo = nombre_protocolo
        self.protocolo_path = os.path.join('protocolos', f"{self.nombre_protocolo}.py")
        self.funcion = None
        if os.path.exists(self.protocolo_path):
            self.cargar_protocolo()
        else:
            print(f"Protocolo '{self.nombre_protocolo}' no encontrado.")

    def cargar_protocolo(self):
        with open(self.protocolo_path, 'r') as f:
            codigo = f.read()
        local_variables = {}
        exec(codigo, {}, local_variables)
        if 'custom_action' in local_variables and callable(local_variables['custom_action']):
            self.funcion = local_variables['custom_action']
            print(f"Protocolo '{self.nombre_protocolo}' cargado exitosamente.")
        else:
            raise ValueError("El protocolo debe contener una función llamada 'custom_action'.")

    def ejecutar(self, observacion):
        if self.funcion:
            return self.funcion(observacion)
        else:
            raise ValueError("El protocolo no ha sido cargado o no contiene la función 'custom_action'.")

    @staticmethod
    def listar_protocolos():
        protocolos = []
        if os.path.exists('protocolos'):
            for file in os.listdir('protocolos'):
                if file.endswith('.py'):
                    protocolos.append(file[:-3])  # Remover la extensión '.py'
        return protocolos

    @staticmethod
    def guardar_protocolo(nombre_protocolo, codigo):
        if not os.path.exists('protocolos'):
            os.makedirs('protocolos')
        protocolo_path = os.path.join('protocolos', f"{nombre_protocolo}.py")
        with open(protocolo_path, 'w') as f:
            f.write(codigo)
        print(f"Protocolo '{nombre_protocolo}' guardado exitosamente.")

    @staticmethod
    def eliminar_protocolo(nombre_protocolo):
        protocolo_path = os.path.join('protocolos', f"{nombre_protocolo}.py")
        if os.path.exists(protocolo_path):
            os.remove(protocolo_path)
            print(f"Protocolo '{nombre_protocolo}' eliminado exitosamente.")
        else:
            print(f"Protocolo '{nombre_protocolo}' no existe.")