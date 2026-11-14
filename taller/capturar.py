"""Captura las salidas REALES de los pasos del alumno SIN Docker y las guarda en taller/salidas-reales.json.

Todo ocurre en una carpeta temporal limpia (variables TALLER_*): no toca el repositorio, ni data/, ni models/, ni reports/.
Pasos, en orden: verificar entorno (si existe cafe_mlops/verificar.py) -> operacional -> raw -> master -> fs/ml -> train
(--hasta 2016) -> segunda ejecucion («sin cambios») -> --hasta 2018 (version 2) -> comparar con la referencia (tolerancia
por defecto y 0,10) -> API local (/salud, /listo, /predecir, 422, aviso) -> interfaz local (/recomendar).
Cierra los procesos que abre. Las rutas se sustituyen por <taller> y se quitan duraciones y fechas.

Las cifras de Docker y GitHub Actions no se pueden medir aqui: se copian de «Notas de T15» (TAREAS.md) y se marcan con
origen «github-actions».

Uso (desde la raiz del repositorio, con el entorno activado):   python -m taller.capturar [--salida RUTA]
"""
import argparse
import json
import os
import platform
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = Path(__file__).resolve().parent / 'salidas-reales.json'
DATOS = RAIZ / 'tests' / 'datos'
PUERTO_API_VISIBLE, PUERTO_INTERFAZ_VISIBLE = 8080, 8090   # los de la documentacion; se ejecuta en puertos libres

# Cifras medidas en GitHub Actions (T15), copiadas de «Notas de T15» en TAREAS.md. No se añade nada mas.
GITHUB_ACTIONS = {
    'origen': 'github-actions',
    'fuente': 'TAREAS.md, «Notas de T15» (prueba real en GitHub, 14/11/2026), repositorio de prueba del taller',
    'validar': {
        'origen': 'github-actions', 'run': 43634940765, 'resultado': 'verde', 'duracion': '7 min 42 s',
        'pruebas_que_pasan': 422,
        'pipeline_segunda_ejecucion': 'sin cambios',
        'imagen_cafe_api': {'tamano': '826 MB', 'comprimida': '183 MB', 'usuario': 10001},
        'imagen_cafe_interfaz': {'tamano': '213 MB', 'comprimida': '51 MB', 'usuario': 10001, 'scikit_learn': 'no'},
        'compose': 'sano', 'api_publicada_fuera': 'no', 'prediccion_por_la_interfaz': 'correcta',
    },
    'nueva_version_rechazada': {
        'origen': 'github-actions', 'run': 43640636319, 'duracion': '1 min 34 s', 'hasta': 2018, 'tolerancia': 0.02,
        'auc_ventana_comun_candidata': 0.7951, 'auc_ventana_comun_referencia': 0.8525, 'diferencia': -0.0574,
        'resultado': 'RECHAZADA', 'construye_o_publica': 'no',
    },
    'nueva_version_aprobada': {
        'origen': 'github-actions', 'run': 43641866374, 'duracion': '4 min 30 s', 'hasta': 2018, 'tolerancia': 0.10,
        'huella_datos': 'bebc87b9eddf0199', 'aprobacion_manual': 'environment produccion',
        'imagenes_publicadas': ['ghcr.io/<usuario>/cafe-api:v2-bebc87b9eddf0199',
                                'ghcr.io/<usuario>/cafe-interfaz:v2-bebc87b9eddf0199'],
        'visibilidad_paquetes': 'privados', 'pull_request': 1,
    },
}


def puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def esperar(url, segundos=90):
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            urllib.request.urlopen(url, timeout=2).read()
            return True
        except Exception:     # noqa: BLE001 - aun no escucha
            time.sleep(0.5)
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--salida', type=Path, default=SALIDA, help='donde guardar el JSON (por defecto taller/salidas-reales.json)')
    a = ap.parse_args(argv)

    tmp = Path(tempfile.mkdtemp(prefix='taller-capturar-')).resolve()
    p_api, p_ui = puerto_libre(), puerto_libre()
    entorno = dict(os.environ, TALLER_DB_OPERACIONAL=str(tmp / 'cqi.db'), TALLER_DB=str(tmp / 'cafe.db'),
                   TALLER_MODELOS=str(tmp / 'models'), TALLER_REPORTES=str(tmp / 'reports'),
                   TALLER_REFERENCIA=str(RAIZ / 'models' / 'referencia.json'),
                   PYTHONIOENCODING='utf-8', NO_PROXY='127.0.0.1,localhost', no_proxy='127.0.0.1,localhost',
                   MLFLOW_DISABLE_AGENT_HINT='1', PYTHONDONTWRITEBYTECODE='1')
    for k in ('HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'TALLER_URL_API', 'TALLER_PUERTO_API',
              'TALLER_PUERTO_INTERFAZ', 'TALLER_DB_SOLO_LECTURA'):
        entorno.pop(k, None)

    def limpiar(texto):
        for ruta in sorted({str(tmp), str(RAIZ), RAIZ.as_posix(), tmp.as_posix(), str(Path.home()), Path.home().as_posix()},
                           key=len, reverse=True):
            texto = texto.replace(ruta, '<taller>')
        texto = texto.replace(f'127.0.0.1:{p_api}', f'127.0.0.1:{PUERTO_API_VISIBLE}')
        texto = texto.replace(f'127.0.0.1:{p_ui}', f'127.0.0.1:{PUERTO_INTERFAZ_VISIBLE}')
        texto = texto.replace('<taller>\\', '<taller>/')
        return texto

    def lineas(texto):
        res = []
        for l in limpiar(texto).splitlines():
            l = re.sub(r'\s*\(\d+(\.\d+)? ?s\)\s*$', '', l).rstrip()     # duraciones: "  (1.2 s)"
            if l.strip():
                res.append(l)
        return res

    pasos, procesos = {}, []

    def registrar(clave, comando, codigo, salida, **extra):
        pasos[clave] = {'orden': len(pasos) + 1, 'comando': comando, 'codigo': codigo, 'salida': salida, **extra}
        print(f'[{codigo}] {clave}: {comando}')

    def orden(clave, *args, comando=None, esperado=0):
        r = subprocess.run([sys.executable, *args], cwd=RAIZ, env=entorno, capture_output=True, text=True, encoding='utf-8',
                           errors='replace', timeout=900)
        salida = lineas(r.stdout + (('\n' + r.stderr) if r.stderr.strip() and r.returncode else ''))
        registrar(clave, comando or 'python ' + ' '.join(args), r.returncode, salida, tipo='terminal')
        if esperado is not None and r.returncode != esperado:
            raise SystemExit(f'fallo en {clave} (codigo {r.returncode}):\n' + '\n'.join(salida[-30:]))

    def servidor(clave_ruta, *args, url, comando):
        log = open(tmp / f'{clave_ruta}.log', 'w', encoding='utf-8')
        p = subprocess.Popen([sys.executable, *args], cwd=RAIZ, env=entorno, stdout=log, stderr=subprocess.STDOUT)
        procesos.append((p, log))
        if not esperar(url):
            raise SystemExit(f'no arranco: {comando}')
        return p

    def http(clave, metodo, base, ruta, cuerpo_archivo=None, comando=None):
        datos = (DATOS / cuerpo_archivo).read_bytes() if cuerpo_archivo else None
        return _http(clave, metodo, base, ruta, datos, comando, cuerpo_archivo)
    def _http(clave, metodo, base, ruta, datos, comando, archivo):
        req = urllib.request.Request(base + ruta, data=datos, method=metodo,
                                     headers={'Content-Type': 'application/json'} if datos else {})
        try:
            r = urllib.request.urlopen(req, timeout=60)
            codigo, cuerpo = r.status, r.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            codigo, cuerpo = e.code, e.read().decode('utf-8')
        try:
            salida = json.loads(cuerpo)
        except ValueError:
            salida = lineas(cuerpo) if '\n' in cuerpo else limpiar(cuerpo)
        if isinstance(salida, dict) and 'id_peticion' in salida:
            salida['id_peticion'] = '<id-peticion>'      # aleatorio en cada peticion
        extra = {'tipo': 'http', 'metodo': metodo, 'ruta': ruta}
        if archivo:
            extra['cuerpo'] = f'tests/datos/{archivo}'
        registrar(clave, comando, codigo, json.loads(limpiar(json.dumps(salida, ensure_ascii=False))), **extra)
        return codigo, salida

    try:
        # ------------------------------------------------------------------ verificar el entorno
        if (RAIZ / 'cafe_mlops' / 'verificar.py').exists():
            r = subprocess.run([sys.executable, '-m', 'cafe_mlops.verificar'], cwd=RAIZ, env=entorno, capture_output=True,
                               text=True, encoding='utf-8', errors='replace', timeout=300)
            registrar('verificar_entorno', 'python -m cafe_mlops.verificar', r.returncode, lineas(r.stdout + r.stderr),
                      tipo='terminal')
        else:
            registrar('verificar_entorno', 'python -m cafe_mlops.verificar', None,
                      ['OMITIDO: cafe_mlops/verificar.py todavia no existe; no se ejecuto y no hay salida real.'],
                      tipo='terminal', omitido=True)

        # ------------------------------------------------------------------ pipelines: version 1, segunda ejecucion, version 2
        # El orquestador crea la operacional y lanza raw -> master -> fs/ml -> train en un solo comando.
        orden('pipeline_hasta_2016', '-m', 'cafe_mlops.pipeline', '--hasta', '2016')
        orden('pipeline_segunda_ejecucion', '-m', 'cafe_mlops.pipeline', '--hasta', '2016')
        orden('pipeline_hasta_2018', '-m', 'cafe_mlops.pipeline', '--hasta', '2018')
        # tolerancia por defecto: la version 2 sale RECHAZADA (codigo distinto de 0, es lo esperado); con 0,10 sale APROBADA
        orden('comparar_tolerancia_por_defecto', '-m', 'cafe_mlops.modeling.comparar', esperado=None)
        orden('comparar_tolerancia_010', '-m', 'cafe_mlops.modeling.comparar', '--tolerancia-referencia', '0.10', esperado=None)
        # ------------------------------------------------------------------ API y interfaz de la version 1 (la que se despliega)
        base_api, base_ui = f'http://127.0.0.1:{p_api}', f'http://127.0.0.1:{p_ui}'
        comando_api = 'python -m cafe_mlops.api'
        entorno['TALLER_PUERTO_API'] = str(p_api)
        servidor('api', '-m', 'cafe_mlops.api', url=base_api + '/listo', comando=comando_api)
        pasos['arranque_api'] = {'orden': len(pasos) + 1, 'comando': comando_api, 'codigo': 0, 'tipo': 'proceso',
                                 'salida': [f'API escuchando en http://127.0.0.1:{PUERTO_API_VISIBLE} (puerto libre real: se muestra el de la guia); '
                                            '/listo respondio 200']}
        http('api_salud', 'GET', base_api, '/salud', comando='GET /salud')
        http('api_listo', 'GET', base_api, '/listo', comando='GET /listo')
        http('api_predecir', 'POST', base_api, '/predecir', 'lote_ejemplo.json', comando='POST /predecir  (tests/datos/lote_ejemplo.json)')
        http('api_predecir_422', 'POST', base_api, '/predecir', 'lote_imposible.json',
             comando='POST /predecir  (tests/datos/lote_imposible.json)')
        http('api_predecir_aviso', 'POST', base_api, '/predecir', 'lote_categoria_nueva.json',
             comando='POST /predecir  (tests/datos/lote_categoria_nueva.json)')

        comando_ui = 'python -m cafe_mlops.interfaz'
        servidor('interfaz', '-m', 'cafe_mlops.interfaz', '--url', base_api, '--puerto', str(p_ui), url=base_ui + '/salud',
                 comando=comando_ui)
        pasos['arranque_interfaz'] = {'orden': len(pasos) + 1, 'comando': comando_ui, 'codigo': 0, 'tipo': 'proceso',
                                      'salida': [f'Interfaz escuchando en http://127.0.0.1:{PUERTO_INTERFAZ_VISIBLE} (puerto libre real: se muestra el de la guia); '
                                                 '/salud respondio 200']}
        _http('interfaz_recomendar', 'POST', base_ui, '/recomendar', json.dumps({'lote_ids': [1, 2, 3]}).encode(),
              'POST /recomendar  {"lote_ids": [1, 2, 3]}', None)
        pasos['interfaz_recomendar']['cuerpo'] = {'lote_ids': [1, 2, 3]}

    finally:
        cerrar(procesos)
        meta = {
            'nota': 'Salidas reales de los pasos del alumno SIN Docker, ejecutadas en una carpeta temporal limpia (<taller> = raiz del '
                    'proyecto). Se quitaron duraciones y fechas. API e interfaz se ejecutaron en puertos libres; se muestran '
                    f'como {PUERTO_API_VISIBLE} y {PUERTO_INTERFAZ_VISIBLE}. Las comparaciones usan la referencia models/referencia.json '
                    'sin modificarla (la tolerancia 0,10 se pasa por parametro). Las variables TALLER_* apuntan a la carpeta temporal.',
            'python': platform.python_version(),
            'sistema': platform.system(),
            'orden_de_los_pasos': 'ver el campo «orden» de cada paso',
        }
        resultado = {'meta': meta, 'pasos': pasos, 'github_actions': GITHUB_ACTIONS}
        texto = limpiar(json.dumps(resultado, ensure_ascii=False, indent=1))
        a.salida.write_text(texto + '\n', encoding='utf-8')
        print('guardado en', a.salida.name)
    return 0


def cerrar(procesos):
    while procesos:
        p, log = procesos.pop()
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=10)
        log.close()


if __name__ == '__main__':
    raise SystemExit(main())

