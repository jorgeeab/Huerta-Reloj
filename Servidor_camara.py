from flask import Flask, jsonify, request
import cv2
import base64

app = Flask(__name__)

# Función para capturar una imagen de la cámara y devolverla como base64
def gen_frame(camera_id=0):
    # Abrir la cámara usando el ID proporcionado
    camera = cv2.VideoCapture(camera_id)  # Usar la cámara especificada por ID

    success, frame = camera.read()  # Capturar una imagen

    if not success:
        return None

    # Codificar la imagen como JPEG
    ret, buffer = cv2.imencode('.jpg', frame)

    if not ret:
        return None

    # Convertir el buffer en una cadena de base64
    frame_base64 = base64.b64encode(buffer).decode('utf-8')

    camera.release()  # Liberar la cámara

    return frame_base64

@app.route('/capture-image')
def servir_imagen_archivo():
    # Obtener el ID de la cámara desde los parámetros de la solicitud
    camera_id = request.args.get('cameraId', default=0, type=int)

    frame_base64 = gen_frame(camera_id)  # Obtener la imagen de la cámara en base64

    if frame_base64 is None:
        return "Error al capturar la imagen", 500

    return

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)