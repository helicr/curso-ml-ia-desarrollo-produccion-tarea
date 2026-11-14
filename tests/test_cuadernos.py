"""Pruebas de los cuadernos (T09): notebooks/00 a 04.

Los cuadernos son para ejecutar («dar al play»): el alumno no escribe ni edita nada. Se vigila que lleguen EJECUTADOS, con las salidas
reales guardadas y sin errores, que no cuelen rutas ni datos personales, que las cifras guardadas sean las del paquete y que, ejecutados
de nuevo desde cero en una carpeta temporal, den las mismas salidas (prueba lenta, marcada con `lento`).

    rapidas ... leen los .ipynb guardados (estructura, errores, rutas y nombres personales, cifras)
    lenta ..... los ejecuta de arriba abajo con nbclient en carpetas temporales y compara con lo guardado
"""
import copy
import json
import re

import nbformat
import pytest

from auxiliar import RAIZ
from test_higiene import _nombres_de_personas, _tokens_personales

CARPETA = RAIZ / 'notebooks'
NOMBRES = ['00_pipeline_operacional', '01_pipeline_raw_a_master', '02_pipeline_master_a_fs', '03_pipeline_fs_a_ml',
           '04_entrenamiento_y_seguimiento']
TOPE_BYTES = 2_000_000


def _leer(nombre):
    return nbformat.read(CARPETA / f'{nombre}.ipynb', as_version=4)


def _salidas(celda):
    """Texto de todas las salidas de una celda de código (streams y text/plain), sin imágenes."""
    trozos = []
    for o in celda.get('outputs', []):
        if o.output_type == 'stream':
            trozos.append(o.text)
        elif o.output_type in ('execute_result', 'display_data'):
            trozos.append(o.data.get('text/plain', ''))
        elif o.output_type == 'error':
            trozos.append(f'ERROR {o.ename}: {o.evalue}')
    return '\n'.join(trozos)


def _todo_el_texto(nb):
    """Fuente de todas las celdas y todas las salidas (también el HTML y los metadatos), para buscar lo que no debe estar."""
    return json.dumps({k: v for k, v in nb.items() if k != 'cells'}, ensure_ascii=False) + '\n' + '\n'.join(
        ''.join(c['source']) + '\n' + json.dumps(c.get('outputs', []), ensure_ascii=False) for c in nb.cells)


@pytest.fixture(scope='module', params=NOMBRES)
def nb(request):
    return request.param, _leer(request.param)


# --------------------------------------------------------------------------------------------------- estructura
def test_estan_los_cinco_cuadernos_y_nada_mas():
    assert sorted(p.name for p in CARPETA.glob('*.ipynb')) == [f'{n}.ipynb' for n in NOMBRES]


def test_el_formato_es_valido_y_cada_celda_tiene_su_identificador(nb):
    nombre, cuaderno = nb
    nbformat.validate(cuaderno)
    ids = [c['id'] for c in cuaderno.cells]
    assert len(set(ids)) == len(ids)
    assert (CARPETA / f'{nombre}.ipynb').stat().st_size < TOPE_BYTES


def test_empieza_con_un_titulo_y_explica_al_alumno_que_no_programa(nb):
    nombre, cuaderno = nb
    primera = cuaderno.cells[0]
    assert primera.cell_type == 'markdown' and primera.source.startswith(f'# {nombre[:2]} ·')
    assert 'No hay código que escribir' in primera.source or 'No hay código que escribir' in ' '.join(c.source for c in cuaderno.cells[:3])
    markdown = [c for c in cuaderno.cells if c.cell_type == 'markdown']
    codigo = [c for c in cuaderno.cells if c.cell_type == 'code']
    assert len(markdown) >= 6 and len(codigo) >= 5
    assert any(c.source.lstrip().startswith(('## Resumen', '## Para practicar')) or '## Resumen' in c.source for c in markdown)


def test_no_hay_nada_que_completar_ni_editar(nb):
    """Ni huecos para rellenar ni entradas del teclado: el alumno solo ejecuta."""
    _, cuaderno = nb
    for c in cuaderno.cells:
        if c.cell_type != 'code':
            continue
        assert not re.search(r'\binput\(|NotImplementedError|\bTODO\b|\bFIXME\b|<COMPLETA|\.\.\.\s*#\s*escribe', c.source), c.source[:80]


def test_solo_el_cuaderno_00_tiene_parametros_y_son_los_previstos():
    for nombre in NOMBRES:
        etiquetadas = [c for c in _leer(nombre).cells if 'parameters' in c.get('metadata', {}).get('tags', [])]
        assert len(etiquetadas) == (1 if nombre.startswith('00') else 0), nombre
    celda = next(c for c in _leer(NOMBRES[0]).cells if 'parameters' in c.get('metadata', {}).get('tags', []))
    assert 'HASTA = 2016' in celda.source


def test_cada_cuaderno_usa_el_paquete_en_vez_de_copiar_su_logica(nb):
    _, cuaderno = nb
    codigo = '\n'.join(c.source for c in cuaderno.cells if c.cell_type == 'code')
    assert 'from cafe_mlops import' in codigo


# --------------------------------------------------------------------------------------------------- ejecutados, sin errores
def test_estan_ejecutados_de_arriba_abajo_sin_errores_guardados(nb):
    nombre, cuaderno = nb
    codigo = [c for c in cuaderno.cells if c.cell_type == 'code']
    assert [c['execution_count'] for c in codigo] == list(range(1, len(codigo) + 1)), f'{nombre}: no se ejecutó en orden de arriba abajo'
    for c in codigo:
        assert not any(o.output_type == 'error' for o in c.outputs), f'{nombre}: error guardado en una celda'
    salidas = '\n'.join(json.dumps(c.outputs, ensure_ascii=False) for c in codigo)
    for marca in ('Traceback', 'Error:', 'FileNotFoundError', 'No such file', 'Exception'):
        assert marca not in salidas, f'{nombre}: «{marca}» en las salidas'


def test_toda_celda_que_debe_mostrar_algo_tiene_su_salida(nb):
    """Las celdas que dibujan, imprimen o terminan en una tabla dejan salida guardada (el alumno ve lo mismo que aquí)."""
    nombre, cuaderno = nb
    vacias = []
    for c in cuaderno.cells:
        if c.cell_type != 'code' or c.outputs:
            continue
        if 'print(' in c.source or 'plt.show()' in c.source or 'display(' in c.source or 'ejecutar(' in c.source:
            vacias.append(c.source.splitlines()[0][:60])
    assert not vacias, f'{nombre}: celdas sin salida: {vacias}'


# --------------------------------------------------------------------------------------------------- sin rutas ni nombres personales
def test_ninguna_ruta_ni_dato_personal_en_el_codigo_ni_en_las_salidas(nb):
    nombre, cuaderno = nb
    texto = _todo_el_texto(cuaderno)
    for motivo, patron in _tokens_personales():
        assert not patron.search(texto), f'{nombre}: {motivo}'
    # tampoco rutas absolutas de ningun tipo en lo que se ve
    visibles = '\n'.join(_salidas(c) for c in cuaderno.cells if c.cell_type == 'code')
    assert not re.search(r'[A-Za-z]:[\\/]', visibles), f'{nombre}: ruta absoluta de Windows en una salida'
    assert not re.search(r'(?<![\w.:])/(?:home|Users|tmp|var|private|workspaces)/', visibles), f'{nombre}: ruta absoluta en una salida'


def test_ningun_nombre_de_persona_en_los_cuadernos(nb):
    nombre, cuaderno = nb
    texto = _todo_el_texto(cuaderno).lower()
    encontrados = [n for n in _nombres_de_personas() if n in texto]
    assert not encontrados, f'{nombre}: {encontrados[:3]}'


def test_no_hay_marcas_de_tiempo_ni_duraciones_que_cambien_en_cada_ejecucion(nb):
    nombre, cuaderno = nb
    for c in cuaderno.cells:
        assert 'execution' not in c.get('metadata', {}), f'{nombre}: tiempos de ejecución guardados'
    visibles = '\n'.join(_salidas(c) for c in cuaderno.cells if c.cell_type == 'code')
    assert not re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', visibles), f'{nombre}: fecha y hora en una salida'
    assert not re.search(r'\(\d+\.\d s\)', visibles), f'{nombre}: duración en una salida'


# --------------------------------------------------------------------------------------------------- las cifras son las del paquete
def test_las_cifras_del_cuaderno_04_son_las_de_la_referencia_y_las_de_la_particion():
    from cafe_mlops import config
    ref = json.loads((RAIZ / 'models' / 'referencia.json').read_text(encoding='utf-8'))
    texto = '\n'.join(_salidas(c) for c in _leer(NOMBRES[4]).cells if c.cell_type == 'code')
    assert f'{ref[config.METRICA_COMPARACION]:.4f}' in texto            # la candidata del cuaderno es la referencia (versión 1)
    assert ref['huella_datos'] in texto and 'versión 1 de los datos' in texto
    n = ref['filas']
    assert f'train {n["train"]:>5} lotes' in texto and f'test  {n["test"]:>5} lotes' in texto
    assert 'APROBADA' in texto and 'DIFIERE' not in texto and 'RECHAZADA' not in texto


def test_el_cuaderno_03_muestra_la_particion_deslizante_y_la_fuga():
    from cafe_mlops import config
    cuaderno = _leer(NOMBRES[3])
    texto = '\n'.join(_salidas(c) for c in cuaderno.cells if c.cell_type == 'code')
    for version in config.VERSIONES_DATOS.values():
        for _, (desde, hasta) in config.particiones_de(version).items():
            assert str(desde) in texto and str(hasta) in texto
    assert 'FUGA' in texto and 'AUC valid' in texto
    fuga = re.search(r'B · las diez notas de cata \(FUGA\)\s+\d+\s+([\d.]+)\s+([\d.]+)', texto)
    honesto = re.search(r'A · variables al recibir el lote \(honesto\)\s+\d+\s+([\d.]+)\s+([\d.]+)', texto)
    assert fuga and honesto
    assert float(fuga.group(2)) > 0.95 > float(honesto.group(2))        # con las notas «acierta» casi todo; sin ellas, no


def test_los_cuadernos_no_dicen_cifras_que_no_se_pueden_comprobar():
    """Las cifras que cita el texto de los cuadernos (lotes, años) coinciden con las del proyecto."""
    from cafe_mlops import config
    texto = '\n'.join(c.source for n in NOMBRES for c in _leer(n).cells if c.cell_type == 'markdown')
    assert f'>= {config.UMBRAL_ESPECIALIDAD:g}' in texto or f'>= {int(config.UMBRAL_ESPECIALIDAD)}' in texto
    assert '2016' in texto and '2018' in texto


# --------------------------------------------------------------------------------------------------- ejecución real (lenta)
def _normalizado(cuaderno):
    """Salidas de cada celda de código, sin huellas (hexadecimales largos: dependen del código fuente tal como esté en disco)."""
    return [re.sub(r'\b[0-9a-f]{12,16}\b', '<huella>', _salidas(c)) for c in cuaderno.cells if c.cell_type == 'code']


@pytest.mark.lento
def test_los_cuadernos_se_ejecutan_de_arriba_abajo_y_dan_lo_mismo_que_lo_guardado(tmp_path, monkeypatch):
    """Los cinco, en orden, en carpetas temporales (rutas por TALLER_*): sin errores y con las mismas salidas que las guardadas."""
    nbclient = pytest.importorskip('nbclient')
    pytest.importorskip('ipykernel')
    for variable, valor in (('TALLER_DB_OPERACIONAL', tmp_path / 'cqi.db'), ('TALLER_DB', tmp_path / 'cafe.db'),
                            ('TALLER_MODELOS', tmp_path / 'models'), ('TALLER_REPORTES', tmp_path / 'reports')):
        monkeypatch.setenv(variable, str(valor))
    monkeypatch.setenv('PYTHONIOENCODING', 'utf-8')
    for nombre in NOMBRES:
        guardado = _leer(nombre)
        nuevo = copy.deepcopy(guardado)
        for c in nuevo.cells:
            if c.cell_type == 'code':
                c.outputs, c.execution_count = [], None
        cliente = nbclient.NotebookClient(nuevo, timeout=900, kernel_name='python3', record_timing=False,
                                          resources={'metadata': {'path': str(CARPETA)}})
        cliente.execute()          # CellExecutionError si una celda falla
        assert _normalizado(nuevo) == _normalizado(guardado), f'{nombre}: las salidas ya no coinciden con las guardadas'
    # lo que dejaron los cuadernos es lo mismo que deja la orden de la terminal: modelo guardado, informe y una versión registrada
    assert (tmp_path / 'models' / 'modelo.joblib').exists() and (tmp_path / 'reports' / 'metricas.json').exists()
    metricas = json.loads((tmp_path / 'reports' / 'metricas.json').read_text(encoding='utf-8'))
    ref = json.loads((RAIZ / 'models' / 'referencia.json').read_text(encoding='utf-8'))
    assert metricas['modelos'][metricas['mejor']]['comun']['auc'] == pytest.approx(ref['auc_comun'], abs=1e-12)
