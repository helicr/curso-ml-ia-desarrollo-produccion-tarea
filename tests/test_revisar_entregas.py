"""T22: docente/revisar_entregas.py con respuestas simuladas de la API de GitHub (sin red, sin token).

`docente/` es material del docente y se retira de la plantilla al publicar: si no esta, estas pruebas se omiten.
Que prueban: la lectura de enlaces, el limite de 4 llamadas por repositorio, cada comprobacion (publico, nombre, fork de la plantilla,
ultimas ejecuciones, capturas, video, plantilla), los casos «no existe», «no es un fork» y limite de la API agotado, y que el token no se
imprime ni se escribe en el informe. Que NO prueban: la API real (se probo a mano contra el repositorio plantilla).
"""
import base64
import csv
import importlib.util

import pytest

from auxiliar import RAIZ

RUTA = RAIZ / 'docente' / 'revisar_entregas.py'
pytestmark = pytest.mark.skipif(not RUTA.is_file(), reason='docente/ se retira de la plantilla del alumno')


@pytest.fixture(scope='module')
def re_():
    espec = importlib.util.spec_from_file_location('docente_revisar_entregas', RUTA)
    m = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(m)
    return m


class Falso:
    """Cliente simulado: respuestas por ruta; una ErrorDeLaApi/LimiteDeLaApi se lanza si es lo que hay guardado."""

    def __init__(self, re_, respuestas, token=False):
        self.re_, self.respuestas, self.con_token = re_, respuestas, token
        self.llamadas, self.rutas, self.restantes, self.limite = 0, [], 50, 60

    def obtener(self, ruta):
        self.llamadas += 1
        self.rutas.append(ruta)
        r = self.respuestas.get(ruta.split('?')[0])
        if r is None:
            raise self.re_.ErrorDeLaApi(404, 'Not Found')
        if isinstance(r, Exception):
            raise r
        return r


def blob(ruta, tam=10, sha='s'):
    return {'path': ruta, 'type': 'blob', 'size': tam, 'sha': sha}


def repo_json(re_, nombre='taller-ml-ia-dev-production', fork=True, padre=None, usuario='alumno1', privado=False):
    d = {'name': nombre, 'full_name': f'{usuario}/{nombre}', 'private': privado, 'fork': fork, 'default_branch': 'main',
         'owner': {'login': usuario}}
    if fork:
        d['parent'] = {'full_name': padre or 'helicr/curso-ml-ia-desarrollo-produccion-tarea'}
    return d


def runs_json(*pares):
    return {'workflow_runs': [{'name': n, 'conclusion': c, 'status': 'completed' if c else 'in_progress'} for n, c in pares]}


def entrega_completa(re_, plantilla_pendientes=0):
    ce = re_.CE
    arbol = [blob(f'evidencias/capturas/{n}.png') for n in ce.CAPTURAS] + [blob('evidencias/capturas/.gitkeep', 0),
             blob(f'evidencias/video/{ce.NOMBRE_VIDEO}', 5_000_000), blob('evidencias/plantilla-evidencias.md', 100, 'pl')]
    texto = ('relleno\n' + (ce.MARCADOR + '\n') * plantilla_pendientes).encode('utf-8')
    base = '/repos/alumno1/taller-ml-ia-dev-production'
    return {'/repos/alumno1/taller-ml-ia-dev-production': repo_json(re_),
            base + '/actions/runs': runs_json(('Nueva version del modelo', 'success'), ('Validar', 'success'), ('Nueva version del modelo', 'failure')),
            base + '/git/trees/main': {'tree': arbol, 'truncated': False},
            base + '/git/blobs/pl': {'content': base64.b64encode(texto).decode(), 'encoding': 'base64'}}


# ------------------------------------------------------------------------------------------------------------- enlaces
def test_parsea_enlaces_en_varios_formatos(re_):
    for x in ('https://github.com/u1/taller-ml-ia-dev-production', 'github.com/u1/taller-ml-ia-dev-production.git', 'u1/taller-ml-ia-dev-production',
              'https://github.com/u1/taller-ml-ia-dev-production/tree/main', 'https://github.com/u1/taller-ml-ia-dev-production?tab=readme'):
        assert re_.parsear_enlace(x) == ('u1', 'taller-ml-ia-dev-production'), x
    assert re_.parsear_enlace('hola') is None and re_.parsear_enlace('') is None and re_.parsear_enlace('https://github.com/solo') is None


def test_lee_el_archivo_de_enlaces_sin_repetidos_ni_comentarios(re_, tmp_path):
    f = tmp_path / 'enlaces.txt'
    f.write_text('# curso\n\nhttps://github.com/a/r1\nhttps://github.com/A/R1\nb/r2\nnada de esto\n', encoding='utf-8')
    repos, malas = re_.leer_enlaces(f)
    assert repos == [('a', 'r1'), ('b', 'r2')] and malas == ['nada de esto']


# ------------------------------------------------------------------------------------------------------------- una entrega
def test_entrega_completa_usa_cuatro_llamadas_y_cumple_todo(re_):
    c = Falso(re_, entrega_completa(re_))
    f = re_.revisar('alumno1', 'taller-ml-ia-dev-production', c)
    assert c.llamadas == 4 == re_.LLAMADAS_POR_REPOSITORIO
    assert (f['publico'], f['nombre_exacto'], f['es_fork'], f['fork_de_la_plantilla']) == ('si', 'si', 'si', 'si')
    assert f['validar'] == 'success' and f['nueva_version'] == 'success' and f['nueva_version_recuento'] == '1 failure, 1 success'
    assert f['capturas'] == '16/16' and f['capturas_que_faltan'] == '' and f['video'].startswith('OK')
    assert f['plantilla_rellena'] == 'si' and f['observaciones'] == ''
    assert set(f) == set(re_.COLUMNAS)


def test_nombre_mal_no_es_fork_plantilla_sin_rellenar_y_faltan_cosas(re_):
    ce = re_.CE
    base = '/repos/u2/mi-taller'
    arbol = [blob('evidencias/capturas/01-fork-renombrado.png'), blob('evidencias/capturas/02-codespace-abierto.png', 0),
             blob('evidencias/capturas/03-verificar-entorno.gif'), blob('evidencias/video/a.mp4', 60_000_000), blob('evidencias/video/b.mp4', 1),
             blob('evidencias/plantilla-evidencias.md', 9, 'pl')]
    resp = {base: repo_json(re_, 'mi-taller', fork=False, usuario='u2'),
            base + '/actions/runs': {'workflow_runs': []},
            base + '/git/trees/main': {'tree': arbol},
            base + '/git/blobs/pl': {'content': base64.b64encode((ce.MARCADOR * 3).encode()).decode()}}
    f = re_.revisar('u2', 'mi-taller', Falso(re_, resp))
    assert f['nombre_exacto'] == 'no (se llama mi-taller)' and f['es_fork'] == 'no' and f['fork_de_la_plantilla'] == 'no'
    assert 'no es un fork' in f['observaciones']
    assert f['validar'] == 'sin ejecuciones' and f['nueva_version'] == 'sin ejecuciones'
    assert f['capturas'] == '1/16' and '02-codespace-abierto' in f['capturas_que_faltan'] and '03-verificar-entorno' in f['capturas_que_faltan']
    assert f['video'] == '2 MP4 (debe haber uno)'
    assert f['plantilla_rellena'] == 'no (3 marcadores sin rellenar)'


def test_fork_de_otro_repositorio_y_video_grande(re_):
    resp = entrega_completa(re_)
    resp['/repos/alumno1/taller-ml-ia-dev-production'] = repo_json(re_, padre='otro/repositorio')
    resp['/repos/alumno1/taller-ml-ia-dev-production/git/trees/main']['tree'][17] = blob(f'evidencias/video/{re_.CE.NOMBRE_VIDEO}', 60 * 1048576)
    f = re_.revisar('alumno1', 'taller-ml-ia-dev-production', Falso(re_, resp))
    assert f['es_fork'] == 'si' and f['fork_de_la_plantilla'] == 'no' and 'otro/repositorio' in f['observaciones']
    assert f['video'].startswith('pesa 60.0 MB')


def test_el_fork_de_un_fork_cuenta_si_la_fuente_es_la_plantilla(re_):
    resp = entrega_completa(re_)
    d = repo_json(re_, padre='amigo/taller-ml-ia-dev-production')
    d['source'] = {'full_name': 'HeliCR/curso-ml-ia-desarrollo-produccion-tarea'}
    resp['/repos/alumno1/taller-ml-ia-dev-production'] = d
    assert re_.revisar('alumno1', 'taller-ml-ia-dev-production', Falso(re_, resp))['fork_de_la_plantilla'] == 'si'


def test_repositorio_que_no_existe_gasta_una_sola_llamada(re_):
    c = Falso(re_, {})
    f = re_.revisar('nadie', 'nada', c)
    assert c.llamadas == 1 and f['publico'] == 'no existe o no es publico' and '404' in f['observaciones']


def test_ejecuciones_en_curso_y_fallos_de_la_api_no_tumban_la_revision(re_):
    resp = entrega_completa(re_)
    base = '/repos/alumno1/taller-ml-ia-dev-production'
    resp[base + '/actions/runs'] = runs_json(('Validar', None))
    resp[base + '/git/blobs/pl'] = re_.ErrorDeLaApi(500, 'boom')
    f = re_.revisar('alumno1', 'taller-ml-ia-dev-production', Falso(re_, resp))
    assert f['validar'] == 'en curso (in_progress)' and f['nueva_version'] == 'sin ejecuciones'
    assert f['plantilla_rellena'] == 'sin dato (HTTP 500)' and f['capturas'] == '16/16'
    resp[base + '/actions/runs'] = re_.ErrorDeLaApi(403, 'Resource not accessible')
    f = re_.revisar('alumno1', 'taller-ml-ia-dev-production', Falso(re_, resp))
    assert f['validar'].startswith('sin dato') and 'ejecuciones' in f['observaciones']


# ------------------------------------------------------------------------------------------------------------- principal e informe
def test_informe_csv_y_markdown_sin_datos_personales(re_, tmp_path, capsys):
    resp = entrega_completa(re_)
    c = Falso(re_, resp)
    f = tmp_path / 'enlaces.txt'
    f.write_text('https://github.com/alumno1/taller-ml-ia-dev-production\nhttps://github.com/fantasma/nada\n', encoding='utf-8')
    assert re_.principal([str(f), '--salida', str(tmp_path / 'informe')], cliente=c) == 0
    filas = list(csv.DictReader(open(tmp_path / 'informe.csv', encoding='utf-8-sig')))
    assert [x['usuario'] for x in filas] == ['alumno1', 'fantasma'] and filas[0]['capturas'] == '16/16'
    md = (tmp_path / 'informe.md').read_text(encoding='utf-8')
    assert 'alumno1' in md and 'no existe o no es publico' in md and 'No evalua' in md
    assert set(filas[0]) == set(re_.COLUMNAS)
    salida = capsys.readouterr().out
    assert 'Sin GITHUB_TOKEN' in salida and '60 consultas por hora' in salida


def test_con_muchos_repositorios_sin_token_avisa_del_limite(re_, tmp_path, capsys):
    f = tmp_path / 'e.txt'
    f.write_text('\n'.join(f'u{i}/r' for i in range(16)), encoding='utf-8')
    re_.principal([str(f), '--salida', str(tmp_path / 'i')], cliente=Falso(re_, {}))
    assert 'pueden superar el limite' in (tmp_path / 'i.md').read_text(encoding='utf-8')


def test_si_se_agota_el_limite_el_informe_queda_parcial(re_, tmp_path):
    resp = entrega_completa(re_)
    resp['/repos/u9/r'] = re_.LimiteDeLaApi('API rate limit exceeded')
    f = tmp_path / 'e.txt'
    f.write_text('alumno1/taller-ml-ia-dev-production\nu9/r\nu10/r\n', encoding='utf-8')
    assert re_.principal([str(f), '--salida', str(tmp_path / 'i')], cliente=Falso(re_, resp)) == 0
    assert len(list(csv.DictReader(open(tmp_path / 'i.csv', encoding='utf-8-sig')))) == 1
    md = (tmp_path / 'i.md').read_text(encoding='utf-8')
    assert 'Se agoto el limite' in md and 'u9/r' in md and 'u10/r' in md


def test_el_token_no_se_imprime_ni_se_guarda(re_, tmp_path, capsys, monkeypatch):
    secreto = 'ghp_' + 'A' * 36
    cliente = re_.Cliente(secreto)
    assert cliente.con_token and secreto not in repr(vars(cliente).get('llamadas'))
    salida_cli = []

    class Respuesta:
        headers = {'X-RateLimit-Remaining': '4999', 'X-RateLimit-Limit': '5000'}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true}'

    class Abridor:
        def open(self, peticion, timeout=None):
            salida_cli.append(peticion.get_header('Authorization'))
            assert peticion.get_method() == 'GET'
            return Respuesta()

    cliente._abridor = Abridor()
    assert cliente.obtener('/repos/a/b') == {'ok': True} and cliente.restantes == 4999
    assert salida_cli == [f'Bearer {secreto}']            # solo viaja en la cabecera
    resp = entrega_completa(re_)
    f = tmp_path / 'e.txt'
    f.write_text('alumno1/taller-ml-ia-dev-production\n', encoding='utf-8')
    re_.principal([str(f), '--salida', str(tmp_path / 'i')], cliente=Falso(re_, resp, token=True), entorno={'GITHUB_TOKEN': secreto})
    texto = capsys.readouterr().out + (tmp_path / 'i.csv').read_text(encoding='utf-8-sig') + (tmp_path / 'i.md').read_text(encoding='utf-8')
    assert secreto not in texto
    codigo = RUTA.read_text(encoding='utf-8')
    assert 'print(' in codigo and secreto not in codigo
    assert "'GITHUB_TOKEN'" in codigo and '.write_text(self._token' not in codigo


def test_solo_lee_la_api(re_):
    """Ninguna llamada de escritura: el cliente solo hace GET y el codigo no usa POST, PUT, PATCH ni DELETE."""
    codigo = RUTA.read_text(encoding='utf-8')
    assert "method='GET'" in codigo
    for prohibido in ("'POST'", "'PUT'", "'PATCH'", "'DELETE'", 'data=', 'subprocess'):
        assert prohibido not in codigo, prohibido
