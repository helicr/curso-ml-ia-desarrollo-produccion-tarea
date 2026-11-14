"""Capa FS: variables reutilizables por lote.

Es la traducción a Python de  notebooks/02_pipeline_master_a_fs.ipynb.

QUÉ ES FS
    De «feature store», almacén de variables: las variables (datos que describen a cada lote) se calculan una vez,
    se documentan (fs_catalogo: descripción, origen y CUÁNDO SE CONOCEN) y se reutilizan. Granularidad de fs_lote: una fila por lote.
    Es una capa didáctica, no una plataforma completa. Es más sencilla que la del curso (clientes con ventanas temporales).

REGLA DE ORO
    Cada variable se conoce AL RECIBIR EL LOTE, antes de catarlo. FS nunca lee las notas de cata ni el total de puntos:
    las diez notas SUMAN el total, así que usarlas sería FUGA de información (un modelo que «suma», no que predice).
    La prueba tests/test_fs_y_ml.py lo verifica (columnas, catálogo y texto del SQL).

Las variables están en config.FEATURES.

Uso:  python -m cafe_mlops.features
"""
from . import config, db


def construir_fs(con=None, verbose=True):
    """Crea fs_catalogo y fs_lote y las llena ejecutando sql/fs/01_crear_fs.sql y 02_poblar_fs.sql."""
    cierre = con is None
    con = con or db.conectar()
    db.ejecutar_script(con, config.SQL / 'fs' / '01_crear_fs.sql')
    db.ejecutar_script(con, config.SQL / 'fs' / '02_poblar_fs.sql')
    if verbose:
        n = db.escalar(con, 'SELECT COUNT(*) FROM fs_lote')
        print(f'  FS: fs_lote {n:,} lotes, {len(config.FEATURES)} variables (catálogo: {db.escalar(con, "SELECT COUNT(*) FROM fs_catalogo")})')
    if cierre:
        con.close()


if __name__ == '__main__':
    construir_fs()
