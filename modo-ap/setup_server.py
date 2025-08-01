# setup_server.py
# Servidor de configuración inicial para SHPD (modo hotspot)

from flask import Flask, request, render_template_string
import os

app = Flask(__name__)

HTML_FORM = """
<!DOCTYPE html>
<html>
<head>
  <title>Configuración SHPD</title>
  <style>
    body { font-family: sans-serif; margin: 2em; }
    label { display: block; margin-top: 1em; }
    input { padding: 0.5em; width: 100%; max-width: 400px; }
    button { margin-top: 2em; padding: 1em; background: #2c3e50; color: white; border: none; }
  </style>
</head>
<body>
  <h1>🛠️ Configuración de SHPD</h1>
  <form method="POST">
    <label>Nombre de Red WiFi (SSID):</label>
    <input name="ssid" required />

    <label>Contraseña WiFi:</label>
    <input name="password" type="password" required />

    <label>Código de Cliente (ej. cliente123):</label>
    <input name="cliente_id" required />

    <button type="submit">Conectar y comenzar</button>
  </form>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        ssid = request.form['ssid']
        password = request.form['password']
        cliente_id = request.form['cliente_id']

        # Guardar archivo de configuración del cliente
        with open("/home/rodo/shpd.conf", "w") as f:
            f.write(cliente_id.strip())

        # Guardar configuración de red WiFi para wpa_supplicant
        wpa_conf = f'''
network={{
    ssid="{ssid}"
    psk="{password}"
}}
'''
        #with open("sudo /etc/wpa_supplicant/wpa_supplicant.conf", "a") as wifi:
        #    wifi.write(wpa_conf)

        # Ejecutar script de finalización para apagar hotspot y reiniciar
        os.system("nohup bash -c 'sleep 3 && /home/rodo/finalize_config.sh' &")
        return "<h2>✅ Dispositivo configurado. Reiniciando...</h2>"

    return render_template_string(HTML_FORM)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
