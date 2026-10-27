# Servicio PDF -> imagenes para n8n (Imatecnica).
# Recibe un PDF en base64 y devuelve cada pagina en DOS mitades PNG a 200 ppp
# (con solape del 8% para no cortar ninguna linea), listas para un extractor de vision.
# Sin estado, sin disco persistente, sin datos guardados.
import base64, io, os, subprocess, tempfile

from flask import Flask, jsonify, request
from PIL import Image

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 40 * 1024 * 1024  # 40 MB

TOKEN = os.environ.get('AUTH_TOKEN', '')          # si se define, exige cabecera X-Token
DPI = int(os.environ.get('DPI', '200'))
MAX_PAGINAS = int(os.environ.get('MAX_PAGINAS', '6'))
SOLAPE = 0.08


@app.get('/salud')
def salud():
    return jsonify(ok=True)


@app.post('/paginas')
def paginas():
    if TOKEN and request.headers.get('X-Token') != TOKEN:
        return jsonify(error='token invalido'), 401
    datos = request.get_json(silent=True) or {}
    try:
        pdf = base64.b64decode(datos.get('pdf', ''), validate=False)
        if not pdf.startswith(b'%PDF'):
            return jsonify(error='no es un PDF'), 400
    except Exception:
        return jsonify(error='base64 invalido'), 400
    with tempfile.TemporaryDirectory() as d:
        ruta = os.path.join(d, 'doc.pdf')
        with open(ruta, 'wb') as f:
            f.write(pdf)
        try:
            subprocess.run(['pdftoppm', '-r', str(DPI), '-png', '-l', str(MAX_PAGINAS),
                            ruta, os.path.join(d, 'pag')], check=True, timeout=120)
        except Exception:
            return jsonify(error='no se pudo convertir'), 422
        salida = []
        for nombre in sorted(a for a in os.listdir(d) if a.endswith('.png')):
            im = Image.open(os.path.join(d, nombre))
            w, h = im.size
            mitad, solape = h // 2, int(h * SOLAPE)
            for caja in ((0, 0, w, min(h, mitad + solape)), (0, max(0, mitad - solape), w, h)):
                buf = io.BytesIO()
                im.crop(caja).save(buf, format='PNG')
                salida.append(base64.b64encode(buf.getvalue()).decode())
        return jsonify(paginas=salida, n=len(salida))
