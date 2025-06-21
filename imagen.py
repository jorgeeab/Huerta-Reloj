from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/get_image_markdown', methods=['GET'])
def get_image_markdown():
    # El texto en Markdown con la URL de la imagen
    markdown_text = "![Descripción de la imagen](http://localhost:5000/static/'Captura de pantalla 2023-12-01 100940.png')"
    
    # Devolverlo como respuesta JSON
    return jsonify({"markdown": markdown_text})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
