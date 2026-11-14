"""Fixtures compartidas. Construyen UNA vez, por cada versión de los datos, la base operacional y la analítica (raw -> master -> fs -> ml)
desde los CSV incluidos: v1 = --hasta 2016 y v2 = --hasta 2018. Todo en carpetas temporales: no tocan data/."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cafe_mlops import db, operacional as op, pipeline_ingesta_master, pipeline_ingesta_raw, pipeline_ml  # noqa: E402


def construir(carpeta, hasta):
    """Crea cqi.db y cafe.db en `carpeta` para el --hasta dado, ejecutando los tres pipelines. Devuelve (operacional, analitica)."""
    operacional, analitica = carpeta / 'cqi.db', carpeta / 'cafe.db'
    op.crear_operacional(hasta, operacional, verbose=False)
    pipeline_ingesta_raw.ejecutar(analitica, operacional, verbose=False)
    pipeline_ingesta_master.ejecutar(analitica, verbose=False)
    pipeline_ml.ejecutar(analitica, verbose=False)
    return operacional, analitica


@pytest.fixture(scope='session')
def bases_v1(tmp_path_factory):
    return construir(tmp_path_factory.mktemp('v1'), 2016)


@pytest.fixture(scope='session')
def bases_v2(tmp_path_factory):
    return construir(tmp_path_factory.mktemp('v2'), 2018)


@pytest.fixture(params=[2016, 2018], ids=['hasta2016', 'hasta2018'], scope='session')
def hasta(request):
    return request.param


@pytest.fixture(scope='session')
def bases(hasta, bases_v1, bases_v2):
    """(operacional, analitica) de la versión que toca (las pruebas con esta fixture se ejecutan para --hasta 2016 y 2018)."""
    return bases_v1 if hasta == 2016 else bases_v2


@pytest.fixture()
def con_operacional(bases):
    c = db.conectar(bases[0])
    yield c
    c.close()


@pytest.fixture()
def con(bases):
    c = db.conectar(bases[1])
    yield c
    c.close()
