"""Pruebas de config.py (T03): importa, las variables no incluyen notas de cata, y el resto de constantes son coherentes."""
import csv
import os
import subprocess
import sys

import pytest

from auxiliar import ARCHIVOS, NOTAS, RAIZ
from cafe_mlops import config


def _normalizar(nombre):
    return nombre.lower().replace('.', '_').replace(' ', '_')


def test_importa_y_define_lo_esencial():
    for nombre in ('RAIZ', 'DB_OPERACIONAL', 'DB', 'FUENTES', 'VERSIONES_DATOS', 'UMBRAL_ESPECIALIDAD', 'ANIO_VALID_POR_VERSION', 'VENTANA_COMUN', 'particiones_de', 'SEMILLA',
                   'FEATURES', 'SEGMENTOS', 'TOLERANCIA_COMPARACION', 'NOTAS_CATA'):
        assert hasattr(config, nombre), nombre


def test_las_bases_se_llaman_cqi_y_cafe():
    assert config.DB_OPERACIONAL.name == 'cqi.db'
    assert config.DB.name == 'cafe.db'


def test_las_variables_no_incluyen_notas_de_cata():
    """LA PRUEBA DE LA FUGA: las diez notas suman Total.Cup.Points; ninguna puede ser variable."""
    notas = {_normalizar(n) for lista in NOTAS.values() for n in lista}
    variables = {_normalizar(v) for v in config.FEATURES}
    assert not variables & notas
    assert not variables & {_normalizar(n) for n in config.TODAS_LAS_NOTAS}
    # tampoco el total ni nada que lo nombre
    for v in config.FEATURES:
        assert 'total' not in v.lower() and 'cup' not in v.lower() and 'puntos' not in v.lower() and 'cata' not in v.lower(), v


def test_las_notas_de_config_son_las_del_csv():
    assert {k: list(v) for k, v in config.NOTAS_CATA.items()} == NOTAS
    for especie, ruta in ARCHIVOS.items():
        with open(ruta, encoding='utf-8', newline='') as f:
            cabecera = next(csv.reader(f))
        assert set(NOTAS[especie]) <= set(cabecera)
        assert config.COLUMNA_TOTAL in cabecera
    assert len(config.TODAS_LAS_NOTAS) == 15


def test_las_variables_no_son_datos_de_personas_ni_columnas_excluidas():
    prohibidas = {_normalizar(c) for c in config.COLUMNAS_PERSONALES + config.COLUMNAS_FUERA_DEL_MODELO}
    assert not {_normalizar(v) for v in config.FEATURES} & prohibidas
    for origen in config.ORIGEN_DE_LAS_VARIABLES.values():
        assert origen not in config.COLUMNAS_PERSONALES + config.COLUMNAS_FUERA_DEL_MODELO + config.TODAS_LAS_NOTAS + [config.COLUMNA_TOTAL]


def test_las_columnas_personales_existen_en_el_csv():
    """Se declaran porque están: si el CSV cambiara, la lista de lo prohibido tendría que revisarse."""
    with open(ARCHIVOS['Arabica'], encoding='utf-8', newline='') as f:
        cabecera = next(csv.reader(f))
    assert set(config.COLUMNAS_PERSONALES) <= set(cabecera)


def test_variables_son_categoricas_mas_numericas_sin_repetidas():
    assert config.FEATURES == config.CATEGORICAS + config.NUMERICAS
    assert len(set(config.FEATURES)) == len(config.FEATURES) == 10
    assert set(config.ORIGEN_DE_LAS_VARIABLES) == set(config.FEATURES)
    assert 'especie' in config.CATEGORICAS and config.OBJETIVO not in config.FEATURES


def test_objetivo_y_umbral():
    assert config.OBJETIVO == 'y'
    assert config.UMBRAL_ESPECIALIDAD == 80.0


@pytest.mark.parametrize('version', sorted(config.VERSIONES_DATOS.values()))
def test_particion_temporal_consecutiva_y_sin_solapes(version):
    particiones = config.particiones_de(version)
    assert list(particiones) == ['train', 'valid', 'test']
    anterior = None
    for desde, hasta in particiones.values():
        assert desde <= hasta
        if anterior is not None:
            assert desde == anterior + 1
        anterior = hasta
    assert particiones['train'][0] == config.ANIO_PRIMERA_CATA
    assert particiones['test'][1] == {v: h for h, v in config.VERSIONES_DATOS.items()}[version]   # cubre hasta el --hasta de su versión


def test_particion_deslizante_exacta_de_cada_version():
    assert config.particiones_de(1) == {'train': (2009, 2014), 'valid': (2015, 2015), 'test': (2016, 2016)}
    assert config.particiones_de(2) == {'train': (2009, 2015), 'valid': (2016, 2016), 'test': (2017, 2018)}
    with pytest.raises(ValueError):
        config.particiones_de(3)
    assert [config.version_por_anio(a) for a in (2009, 2016, 2017, 2018, 2019)] == [1, 1, 2, 2, None]


def test_la_ventana_comun_queda_fuera_del_entrenamiento_de_todas_las_versiones():
    desde, hasta = config.VENTANA_COMUN
    assert desde <= hasta
    for version in config.VERSIONES_DATOS.values():
        assert config.particiones_de(version)['train'][1] < desde     # nadie entrena con ella
    assert config.METRICA_COMPARACION == 'auc_comun'


def test_versiones_de_los_datos():
    assert config.VERSIONES_DATOS == {2016: 1, 2018: 2}
    assert config.HASTA_INICIAL == 2016
    assert config.version_de_datos(2016) == 1 and config.version_de_datos(2018) == 2
    with pytest.raises(ValueError):
        config.version_de_datos(2017)


def test_segmentos_de_negocio_ordenados_y_con_cierre_en_cero():
    desdes = [s['desde'] for s in config.SEGMENTOS]
    assert desdes == sorted(desdes, reverse=True)
    assert desdes[-1] == 0.0
    assert all(s['segmento'] and s['recomendacion'] for s in config.SEGMENTOS)


def test_tolerancia_de_la_comparacion():
    assert 0 < config.TOLERANCIA_COMPARACION < 1
    assert config.METRICA_COMPARACION


def test_las_fuentes_existen():
    for ruta in config.FUENTES.values():
        assert ruta.is_file()


def test_las_variables_de_entorno_llevan_el_prefijo_taller(tmp_path):
    entorno = dict(os.environ, TALLER_DB=str(tmp_path / 'otra.db'), TALLER_MODELOS=str(tmp_path / 'm'), TALLER_URL_API='http://api:8080')
    for antiguo in ('CURSO_DB', 'CURSO_MODELOS'):
        entorno.pop(antiguo, None)
    salida = subprocess.run([sys.executable, '-c', 'from cafe_mlops import config; print(config.DB, config.MODELOS, config.URL_API)'],
                            cwd=RAIZ, env=entorno, capture_output=True, text=True, check=True).stdout.split()
    assert salida == [str(tmp_path / 'otra.db'), str(tmp_path / 'm'), 'http://api:8080']


def test_ninguna_ruta_personal_en_el_codigo_ni_en_el_sql():
    prohibidos = ['C:' + '\\Users', 'C:' + '/Users', 'BK' + '70827', '/home/' + 'he']
    for carpeta in ('cafe_mlops', 'sql'):
        for ruta in (RAIZ / carpeta).rglob('*'):
            if ruta.suffix in ('.py', '.sql'):
                texto = ruta.read_text(encoding='utf-8')
                for p in prohibidos:
                    assert p not in texto, f'{ruta}: {p}'
    assert 'C:' + '\\Users' not in (RAIZ / 'Makefile').read_text(encoding='utf-8')
