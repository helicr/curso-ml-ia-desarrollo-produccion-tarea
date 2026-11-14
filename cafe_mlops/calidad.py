"""Reglas de calidad de la capa MASTER.

Una regla de calidad es una consulta SQL que devuelve UN número, más un criterio que dice si ese número es aceptable.
Hay tres tipos:
  duro    -> si falla, el pipeline se detiene (estado ERROR): seguir produciría resultados falsos.
             Ej.: R01, conciliación: lotes de RAW = lotes de MASTER + descartes.
  alerta  -> se registra y se avisa, pero el pipeline sigue (estado ALERTA). MASTER ya corrigió o apartó esos datos.
             Ej.: R07, altitudes fuera de 100–4 000 m (MASTER las deja nulas).
  info    -> solo informa (estado OK). Ej.: R13, porcentaje de lotes sin variedad.
El resultado queda en la tabla master_calidad, con fecha: es la evidencia de que el dato se reviso.
La misma lista esta en el cuaderno 01; las pruebas exigen que ambos produzcan la misma tabla.
"""
from datetime import datetime

from . import config


class CalidadError(RuntimeError):
    pass


def _reglas():
    cero = lambda v: v == 0  # noqa: E731
    n_notas = len(config.NOTAS_CATA['Arabica'])
    return [
        ('R01_conciliacion', 'Lotes de RAW menos (lotes de MASTER + descartes). Debe ser 0.',
         "SELECT (SELECT COUNT(*) FROM raw_lotes) - (SELECT COUNT(*) FROM master_lotes) - (SELECT COUNT(*) FROM master_descartes)",
         'duro', '= 0', cero),
        ('R02_lotes_sin_las_diez_notas', f'Lotes de MASTER que no tienen exactamente {n_notas} notas de cata en RAW.',
         f"SELECT COUNT(*) FROM master_lotes m WHERE (SELECT COUNT(*) FROM raw_notas_cata n WHERE n.cata_id = m.lote_id) <> {n_notas}",
         'duro', '= 0', cero),
        ('R03_lotes_con_varias_catas', 'Lotes de RAW con más de una cata (MASTER espera una por lote).',
         "SELECT COUNT(*) FROM (SELECT lote_id FROM raw_catas GROUP BY lote_id HAVING COUNT(*) > 1)",
         'duro', '= 0', cero),
        ('R04_diferencia_total_menos_notas', 'Mayor diferencia absoluta entre Total.Cup.Points y la suma de las diez notas (la fuga: el total ES esa suma).',
         "SELECT ROUND(MAX(ABS(m.total_puntos - (SELECT SUM(n.valor) FROM raw_notas_cata n WHERE n.cata_id = m.lote_id))), 2) FROM master_lotes m",
         'info', 'informativo', None),
        ('R05_fechas_de_cata_en_rango', f'Fechas de cata de MASTER fuera de {config.FECHA_CATA_MINIMA} a {config.FECHA_CATA_LIMITE} (exclusivo) o mal formadas.',
         f"SELECT COUNT(*) FROM master_lotes WHERE fecha_cata NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
         f"OR fecha_cata < '{config.FECHA_CATA_MINIMA}' OR fecha_cata >= '{config.FECHA_CATA_LIMITE}'",
         'duro', '= 0', cero),
        ('R06_fechas_con_espacios_o_saltos', 'Fechas de cata de RAW con espacios, tabuladores o saltos de línea sobrantes (MASTER los quita).',
         "SELECT COUNT(*) FROM raw_catas WHERE fecha_cata_texto <> TRIM(fecha_cata_texto, char(32, 9, 10, 13))",
         'alerta', '= 0', cero),
        ('R07_altitud_fuera_de_rango', f'Lotes con altitud media fuera de {config.ALTITUD_MIN_M}–{config.ALTITUD_MAX_M} m (MASTER la deja nula).',
         f"SELECT COUNT(*) FROM raw_lotes WHERE altitud_media_m IS NOT NULL "
         f"AND (altitud_media_m < {config.ALTITUD_MIN_M} OR altitud_media_m > {config.ALTITUD_MAX_M})",
         'alerta', '= 0', cero),
        ('R08_pct_altitud_nula_en_master', 'Porcentaje de lotes de MASTER sin altitud utilizable.',
         "SELECT ROUND(100.0 * SUM(CASE WHEN altitud_media_m IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) FROM master_lotes",
         'info', 'informativo', None),
        ('R09_catas_con_total_cero', 'Catas de RAW con total 0 (cata incompleta; MASTER las descarta).',
         "SELECT COUNT(*) FROM raw_catas WHERE total_puntos IS NULL OR total_puntos <= 0",
         'alerta', '= 0', cero),
        ('R10_humedad_cero', 'Lotes con humedad 0 en RAW (parece «no medido»; MASTER la deja nula).',
         f"SELECT COUNT(*) FROM raw_analisis_verde WHERE humedad = {config.HUMEDAD_NO_MEDIDA}",
         'alerta', '= 0', cero),
        ('R11_humedad_fuera_de_0_a_1', 'Lotes de RAW con humedad menor que 0 o mayor que 1 (es una fracción).',
         "SELECT COUNT(*) FROM raw_analisis_verde WHERE humedad < 0 OR humedad > 1",
         'duro', '= 0', cero),
        ('R12_defectos_negativos', 'Lotes de RAW con defectos o quakers negativos.',
         "SELECT COUNT(*) FROM raw_analisis_verde WHERE defectos_cat1 < 0 OR defectos_cat2 < 0 OR quakers < 0",
         'duro', '= 0', cero),
        ('R13_pct_sin_variedad', 'Porcentaje de lotes de MASTER sin variedad.',
         "SELECT ROUND(100.0 * SUM(CASE WHEN variedad IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) FROM master_lotes",
         'info', 'informativo', None),
        ('R14_pct_sin_metodo_proceso', 'Porcentaje de lotes de MASTER sin método de proceso.',
         "SELECT ROUND(100.0 * SUM(CASE WHEN metodo_proceso IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) FROM master_lotes",
         'info', 'informativo', None),
        ('R15_pct_sin_color', 'Porcentaje de lotes de MASTER sin color.',
         "SELECT ROUND(100.0 * SUM(CASE WHEN color IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) FROM master_lotes",
         'info', 'informativo', None),
        ('R16_lotes_en_master', 'Lotes catados en MASTER.',
         "SELECT COUNT(*) FROM master_lotes", 'info', 'informativo', None),
        ('R17_pct_especialidad', f'Porcentaje de lotes de MASTER con total >= {config.UMBRAL_ESPECIALIDAD:g} (el positivo del objetivo).',
         f"SELECT ROUND(100.0 * SUM(CASE WHEN total_puntos >= {config.UMBRAL_ESPECIALIDAD} THEN 1 ELSE 0 END) / COUNT(*), 2) FROM master_lotes",
         'info', 'informativo', None),
    ]


def evaluar(con, lanzar=True):
    """Ejecuta todas las reglas, las guarda en master_calidad y devuelve la lista de resultados."""
    ahora = datetime.now().isoformat(timespec='seconds')
    resultados, errores = [], []
    con.execute('DELETE FROM master_calidad')
    for regla, descripcion, sql, tipo, umbral, cumple in _reglas():
        valor = con.execute(sql).fetchone()[0]
        if tipo == 'info':
            estado = 'OK'
        else:
            ok = cumple(valor)
            estado = 'OK' if ok else ('ERROR' if tipo == 'duro' else 'ALERTA')
        if estado == 'ERROR':
            errores.append(f'{regla}: {descripcion} -> {valor}')
        con.execute('INSERT INTO master_calidad (regla, descripcion, valor, umbral, estado, evaluado_en) VALUES (?,?,?,?,?,?)',
                    (regla, descripcion, valor, umbral, estado, ahora))
        resultados.append({'regla': regla, 'descripcion': descripcion, 'valor': valor, 'umbral': umbral, 'estado': estado})
    con.commit()
    if errores and lanzar:
        raise CalidadError('Fallaron reglas de calidad duras:\n  ' + '\n  '.join(errores))
    return resultados
