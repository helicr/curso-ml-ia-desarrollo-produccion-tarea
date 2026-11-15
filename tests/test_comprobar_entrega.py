"""T21/T22: el comprobador de la entrega (taller/comprobar_entrega.py), con carpetas temporales y sin red.

Que prueban: entrega completa -> sin fallos; faltan capturas, MP4 grande, dos MP4, nombre mal, marcador sin rellenar -> fallo con un
mensaje claro; la plantilla de evidencias VACIA (la real del repositorio) hace fallar al comprobador; las 16 capturas del comprobador son
las de la plantilla. Que NO prueban: el workflow en GitHub (lo prueba quien coordina en un fork real) ni la duracion ni la voz del video.
"""
import importlib.util
import re
from pathlib import Path

import pytest

from auxiliar import RAIZ

RUTA = RAIZ / 'taller' / 'comprobar_entrega.py'
PLANTILLA = RAIZ / 'evidencias' / 'plantilla-evidencias.md'


@pytest.fixture(scope='module')
def ce():
    espec = importlib.util.spec_from_file_location('taller_comprobar_entrega', RUTA)
    m = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(m)
    return m


@pytest.fixture
def entrega(tmp_path, ce):
    """Una entrega completa: 16 capturas (mezclando extensiones), un MP4 pequeno y la plantilla rellena."""
    capturas = tmp_path / 'evidencias' / 'capturas'
    video = tmp_path / 'evidencias' / 'video'
    capturas.mkdir(parents=True)
    video.mkdir()
    (capturas / '.gitkeep').write_bytes(b'')
    for i, nombre in enumerate(ce.CAPTURAS):
        (capturas / f'{nombre}{(".png", ".jpg", ".jpeg", ".webp")[i % 4]}').write_bytes(b'x' * 10)
    (video / '.gitkeep').write_bytes(b'')
    (video / ce.NOMBRE_VIDEO).write_bytes(b'0' * 2048)
    (tmp_path / 'evidencias' / 'plantilla-evidencias.md').write_text(
        PLANTILLA.read_text(encoding='utf-8').replace(ce.MARCADOR, 'texto del alumno'), encoding='utf-8')
    return tmp_path


def fallos(ce, raiz, nombre=None):
    return {r.clave: r for r in ce.comprobar(raiz, nombre or ce.NOMBRE_REPOSITORIO) if not r.cumple}


# ------------------------------------------------------------------------------------------------------------- lo esperado en la plantilla
def test_las_16_capturas_del_comprobador_son_las_de_la_plantilla(ce):
    plantilla = re.findall(r'^## \d+\. `(\d\d-[a-z0-9-]+)` \(paso \d+\)', PLANTILLA.read_text(encoding='utf-8'), flags=re.M)
    assert list(ce.CAPTURAS) == plantilla and len(plantilla) == 16


def test_la_plantilla_tiene_marcadores_y_el_video_tiene_el_nombre_que_pide(ce):
    t = PLANTILLA.read_text(encoding='utf-8')
    assert t.count(ce.MARCADOR) == 44          # 5 datos + 16 x 2 por captura + 3 del video + 4 respuestas
    assert f'evidencias/video/{ce.NOMBRE_VIDEO}' in t


def test_la_plantilla_vacia_hace_fallar_al_comprobador(ce, entrega):
    (entrega / 'evidencias' / 'plantilla-evidencias.md').write_text(PLANTILLA.read_text(encoding='utf-8'), encoding='utf-8')
    f = fallos(ce, entrega)
    assert set(f) == {'plantilla'}
    assert '44 marcadores' in f['plantilla'].mensaje and ce.MARCADOR in f['plantilla'].mensaje


def test_sin_nada_subido_el_comprobador_falla_en_capturas_video_y_plantilla(ce, tmp_path):
    (tmp_path / 'evidencias').mkdir()
    (tmp_path / 'evidencias' / 'plantilla-evidencias.md').write_text(PLANTILLA.read_text(encoding='utf-8'), encoding='utf-8')
    assert set(fallos(ce, tmp_path)) == {'capturas', 'video', 'plantilla'}
    assert ce.main(['--raiz', str(tmp_path), '--repo', ce.NOMBRE_REPOSITORIO]) == 1


# ------------------------------------------------------------------------------------------------------------- entrega completa
def test_entrega_completa_cumple_todo(ce, entrega):
    assert fallos(ce, entrega) == {}
    assert ce.main(['--raiz', str(entrega), '--repo', ce.NOMBRE_REPOSITORIO]) == 0


def test_la_entrega_completa_publica_notices_y_una_tabla_de_cumple(ce, entrega, capsys, tmp_path):
    resumen = tmp_path / 'resumen.md'
    assert ce.main(['--raiz', str(entrega), '--repo', ce.NOMBRE_REPOSITORIO, '--resumen', str(resumen)]) == 0
    salida = capsys.readouterr().out.splitlines()
    assert salida and all(l.startswith('::notice title=') for l in salida)
    md = resumen.read_text(encoding='utf-8')
    assert '| Comprobacion | Resultado | Detalle |' in md and md.count('| Cumple |') >= 4 + 16 and '| Falta |' not in md
    assert 'duracion del video' in md           # dice lo que no puede comprobar


def test_acepta_las_cuatro_extensiones_aunque_vengan_en_mayusculas(ce, entrega):
    capturas = entrega / 'evidencias' / 'capturas'
    for p in capturas.glob('04-pipeline.*'):
        p.unlink()
    (capturas / '04-pipeline.PNG').write_bytes(b'x')
    assert fallos(ce, entrega) == {}


# ------------------------------------------------------------------------------------------------------------- fallos con mensaje claro
def test_nombre_del_repositorio_mal(ce, entrega):
    f = fallos(ce, entrega, 'mi-taller')
    assert set(f) == {'nombre'} and 'mi-taller' in f['nombre'].mensaje and ce.NOMBRE_REPOSITORIO in f['nombre'].mensaje
    assert 'taller-ml-ia-dev-production-1' in fallos(ce, entrega, 'taller-ml-ia-dev-production-1')['nombre'].mensaje
    assert 'Taller-ML-IA-Dev-Production' in fallos(ce, entrega, 'Taller-ML-IA-Dev-Production')['nombre'].mensaje     # distingue mayusculas
    assert ce.main(['--raiz', str(entrega), '--repo', 'mi-taller']) == 1


def test_faltan_capturas_y_dice_cuales(ce, entrega):
    capturas = entrega / 'evidencias' / 'capturas'
    for nombre in ('03-verificar-entorno', '16-paquetes-y-pr'):
        for p in capturas.glob(nombre + '.*'):
            p.unlink()
    f = fallos(ce, entrega)
    assert set(f) == {'capturas'}
    assert 'Faltan 2 de 16' in f['capturas'].mensaje and '`03-verificar-entorno`' in f['capturas'].mensaje and '`16-paquetes-y-pr`' in f['capturas'].mensaje
    assert '14 de 16' in f['capturas'].titulo


def test_captura_vacia_o_con_extension_no_admitida(ce, entrega):
    capturas = entrega / 'evidencias' / 'capturas'
    for p in capturas.glob('05-pipeline-sin-cambios.*'):
        p.write_bytes(b'')
    for p in capturas.glob('06-modelo-version.*'):
        p.rename(capturas / '06-modelo-version.gif')
    m = fallos(ce, entrega)['capturas'].mensaje
    assert '`05-pipeline-sin-cambios`' in m and '0 bytes' in m
    assert '`06-modelo-version`' in m and '06-modelo-version.gif' in m          # cita el archivo sobrante


def test_nombre_de_captura_casi_igual_da_una_pista(ce, entrega):
    capturas = entrega / 'evidencias' / 'capturas'
    for p in capturas.glob('10-ui-cabecera.*'):
        p.rename(capturas / '10-ui-cabezera.png')
    m = fallos(ce, entrega)['capturas'].mensaje
    assert '10-ui-cabezera.png' in m and 'se parece a `10-ui-cabecera`' in m


def test_no_hay_carpeta_de_capturas(ce, entrega):
    import shutil
    shutil.rmtree(entrega / 'evidencias' / 'capturas')
    assert 'No existe la carpeta' in fallos(ce, entrega)['capturas'].mensaje


def test_mp4_demasiado_grande(ce, entrega):
    with open(entrega / 'evidencias' / 'video' / ce.NOMBRE_VIDEO, 'wb') as f:
        f.truncate(ce.LIMITE_VIDEO)               # exactamente 50 MB: no es «menos de 50 MB»
    m = fallos(ce, entrega)['video'].mensaje
    assert 'menos de 50 MB' in m and '50.0 MB' in m
    with open(entrega / 'evidencias' / 'video' / ce.NOMBRE_VIDEO, 'wb') as f:
        f.truncate(ce.LIMITE_VIDEO - 1)
    assert fallos(ce, entrega) == {}


def test_dos_mp4(ce, entrega):
    (entrega / 'evidencias' / 'video' / 'otro.MP4').write_bytes(b'0' * 10)
    m = fallos(ce, entrega)['video'].mensaje
    assert 'Hay 2 MP4' in m and 'exactamente uno' in m and 'otro.MP4' in m


def test_ningun_mp4_y_otros_formatos(ce, entrega):
    carpeta = entrega / 'evidencias' / 'video'
    (carpeta / ce.NOMBRE_VIDEO).rename(carpeta / 'grabacion.mov')
    m = fallos(ce, entrega)['video'].mensaje
    assert 'No hay ningun MP4' in m and 'grabacion.mov' in m


def test_mp4_con_otro_nombre_o_vacio(ce, entrega):
    carpeta = entrega / 'evidencias' / 'video'
    (carpeta / ce.NOMBRE_VIDEO).rename(carpeta / 'mi-video.mp4')
    assert 'debe llamarse exactamente `servicio-en-produccion.mp4`' in fallos(ce, entrega)['video'].mensaje
    (carpeta / 'mi-video.mp4').rename(carpeta / ce.NOMBRE_VIDEO)
    (carpeta / ce.NOMBRE_VIDEO).write_bytes(b'')
    assert 'vacio' in fallos(ce, entrega)['video'].mensaje


def test_marcador_sin_rellenar(ce, entrega):
    ruta = entrega / 'evidencias' / 'plantilla-evidencias.md'
    ruta.write_text(ruta.read_text(encoding='utf-8') + f'\n- Respuesta: {ce.MARCADOR}\n', encoding='utf-8')
    m = fallos(ce, entrega)['plantilla'].mensaje
    assert 'Quedan 1 marcadores' in m and 'lineas' in m


def test_plantilla_borrada(ce, entrega):
    (entrega / 'evidencias' / 'plantilla-evidencias.md').unlink()
    assert 'No existe' in fallos(ce, entrega)['plantilla'].mensaje


# ------------------------------------------------------------------------------------------------------------- salida
def test_los_fallos_salen_como_error_y_en_el_resumen(ce, entrega, capsys, tmp_path):
    for p in (entrega / 'evidencias' / 'capturas').glob('01-*'):
        p.unlink()
    resumen = tmp_path / 'r.md'
    assert ce.main(['--raiz', str(entrega), '--repo', ce.NOMBRE_REPOSITORIO, '--resumen', str(resumen)]) == 1
    salida = capsys.readouterr().out.splitlines()
    errores = [l for l in salida if l.startswith('::error title=')]
    assert len(errores) == 2                     # la captura y el aviso final
    assert any('01-fork-renombrado' in l for l in errores)
    assert not any('\n' in l for l in salida)
    md = resumen.read_text(encoding='utf-8')
    assert '| Falta |' in md and '`01-fork-renombrado` | Falta' in md


def test_los_comandos_de_workflow_escapan_porcentajes_y_saltos(ce):
    r = ce.Resultado('x', 'a: b, c', False, '100% mal\nsegunda')
    linea = ce.anotaciones([r])[0]
    assert linea == '::error title=a%3A b%2C c::100%25 mal%0Asegunda'


def test_el_nombre_sale_del_argumento_del_entorno_o_de_github_repository(ce):
    assert ce.nombre_del_repositorio('x', {}) == 'x'
    assert ce.nombre_del_repositorio(None, {'NOMBRE_REPOSITORIO': 'y', 'GITHUB_REPOSITORY': 'u/z'}) == 'y'
    assert ce.nombre_del_repositorio(None, {'NOMBRE_REPOSITORIO': '', 'GITHUB_REPOSITORY': 'u/z'}) == 'z'
    assert ce.nombre_del_repositorio(None, {}) == ''
    assert ce.comprobar_nombre('').cumple is False


def test_en_el_repositorio_plantilla_no_comprueba_nada_y_termina_bien(ce, tmp_path, capsys):
    assert ce.main(['--raiz', str(tmp_path), '--repo', ce.NOMBRE_PLANTILLA]) == 0
    assert 'plantilla' in capsys.readouterr().out


def test_el_script_no_usa_red_ni_escribe_en_el_repositorio():
    codigo = RUTA.read_text(encoding='utf-8')
    for prohibido in ('urllib', 'socket', 'requests', 'subprocess', 'os.system', '.write_text(', '.unlink('):
        assert prohibido not in codigo, prohibido
    assert not re.search(r'[A-Za-z]:\\\\|/Users/|/home/', codigo)


def test_ejecucion_como_script_desde_otra_carpeta(entrega, tmp_path):
    import subprocess
    import sys
    r = subprocess.run([sys.executable, '-I', str(RUTA), '--raiz', str(entrega), '--repo', 'taller-ml-ia-dev-production'],
                       capture_output=True, text=True, encoding='utf-8', cwd=str(tmp_path), timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert '::notice title=Entrega completa' in r.stdout
