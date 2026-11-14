"""Capa ML: arma el dataset de entrenamiento = variables (FS) + objetivo (y) + partición temporal.

Es la traducción a Python de  notebooks/03_pipeline_fs_a_ml.ipynb.

OBJETIVO (y)
    y = 1 si Total.Cup.Points >= config.UMBRAL_ESPECIALIDAD (el lote es café de especialidad); 0 si no.
    Es lo único que mira el resultado de la cata, y es correcto: es la respuesta que el modelo debe anticipar.

PARTICIÓN TEMPORAL DESLIZANTE (config.particiones_de), por el año de la cata
    train  el modelo aprende       valid  se comparan modelos y se elige       test  se mide el elegido, una sola vez
    Es por TIEMPO, nunca aleatoria ni por orden de fila (el archivo viene ordenado por puntuación): en producción se entrena
    con el pasado y se predice lo que llega después. Los intervalos de años no se solapan y no dejan huecos.
    Desliza con la versión de los datos (la versión sale del año de cata máximo de MASTER, no de un parámetro aparte):
    versión 1 train <= 2014, valid 2015, test 2016;  versión 2 train <= 2015, valid 2016, test 2017-2018.

Antes de construir comprueba que los intervalos son consecutivos y que ningún lote queda sin partición.

Uso:  python -m cafe_mlops.modeling.ml_dataset
"""
from .. import config, db


class ParticionInvalidaError(RuntimeError):
    pass


def particiones_de_los_datos(con):
    """(versión, particiones) que corresponden a los datos de MASTER: la versión es la que cubre su año de cata máximo."""
    anio = db.escalar(con, 'SELECT MAX(anio_cata) FROM master_lotes')
    version = config.version_por_anio(anio) if anio is not None else None
    if version is None:
        raise ParticionInvalidaError(f'El año de cata máximo de MASTER ({anio}) no corresponde a ninguna versión de los datos '
                                     f'(config.VERSIONES_DATOS: {config.VERSIONES_DATOS}).')
    return version, config.particiones_de(version)


def comprobar_particiones(particiones):
    """Los intervalos de años deben ser train < valid < test, consecutivos, sin solaparse ni dejar huecos."""
    if list(particiones) != ['train', 'valid', 'test']:
        raise ParticionInvalidaError(f'Se esperan las particiones train, valid y test, en ese orden (hay: {list(particiones)})')
    anterior = None
    for nombre, (desde, hasta) in particiones.items():
        if desde > hasta:
            raise ParticionInvalidaError(f'{nombre}: el año inicial {desde} es posterior al final {hasta}')
        if anterior is not None and desde != anterior + 1:
            raise ParticionInvalidaError(f'{nombre} empieza en {desde} pero la anterior termina en {anterior}: deben ser consecutivas')
        anterior = hasta


def construir_ml(con=None, verbose=True):
    """Registra las particiones de la versión de los datos y el umbral, y llena ml_dataset con sql/ml/02_poblar_ml.sql."""
    cierre = con is None
    con = con or db.conectar()
    _, particiones = particiones_de_los_datos(con)
    comprobar_particiones(particiones)
    db.ejecutar_script(con, config.SQL / 'ml' / '01_crear_ml.sql')
    con.execute('INSERT INTO ml_parametros (clave, valor) VALUES (?, ?)', ('umbral_especialidad', config.UMBRAL_ESPECIALIDAD))
    con.executemany('INSERT INTO ml_particiones (particion, anio_desde, anio_hasta) VALUES (?,?,?)',
                    [(p, d, h) for p, (d, h) in particiones.items()])
    con.commit()
    db.ejecutar_script(con, config.SQL / 'ml' / '02_poblar_ml.sql')
    en_fs, en_ml = db.escalar(con, 'SELECT COUNT(*) FROM fs_lote'), db.escalar(con, 'SELECT COUNT(*) FROM ml_dataset')
    if en_fs != en_ml:
        anios = [r[0] for r in con.execute('SELECT DISTINCT m.anio_cata FROM fs_lote f JOIN master_lotes m USING (lote_id) '
                                           'WHERE f.lote_id NOT IN (SELECT lote_id FROM ml_dataset) ORDER BY 1')]
        raise ParticionInvalidaError(f'{en_fs - en_ml} lotes de FS no caen en ninguna partición (años de cata: {anios}). Revisa config.particiones_de.')
    if verbose:
        filas = con.execute('SELECT particion, COUNT(*), SUM(y), MIN(anio_cata), MAX(anio_cata) FROM ml_dataset '
                            'GROUP BY particion ORDER BY MIN(anio_cata)').fetchall()
        for particion, n, positivos, desde, hasta in filas:
            print(f'  ML: {particion:5s} {n:>6,} lotes ({desde}-{hasta}) | especialidad {positivos:,} ({100 * positivos / n:.1f} %) | no {n - positivos:,}')
    if cierre:
        con.close()


if __name__ == '__main__':
    construir_ml()
