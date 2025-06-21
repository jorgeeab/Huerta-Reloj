import requests

# URL del servidor Flask que transmite la imagen
url = "http://c487-190-113-101-243.ngrok-free.app/capture-image"

# Hacer la solicitud al servidor para obtener la imagen
response = requests.get(url)

# Verificar si la solicitud fue exitosa (código de estado 200)
if response.status_code == 200:
    # Guardar la imagen en un archivo
    with open("imagen_recibida.jpg", "wb") as f:
        f.write(response.content)
    print("Imagen guardada exitosamente como 'imagen_recibida.jpg'")
else:
    print(f"Error al solicitar la imagen. Código de estado: {response.status_code}")
