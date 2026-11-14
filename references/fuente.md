# Fuente de los datos de calidad del café (CQI)

## Fuente

- **Repositorio:** `jldbc/coffee-quality-database` en GitHub: https://github.com/jldbc/coffee-quality-database
- **Ruta en el repositorio:** `data/arabica_data_cleaned.csv` y `data/robusta_data_cleaned.csv` (versiones limpias).
- **Origen de los datos:** páginas de reseñas de catas del Coffee Quality Institute (CQI), https://database.coffeeinstitute.org/ . Según el README del repositorio, recogidas en **enero de 2018**.
- **Último commit del repositorio:** 16/06/2018 (comprobado el 14/11/2026).
- **Fecha de descarga:** sin dato (no consta en la carpeta de exploración).

## Cómo se obtuvo

Descarga directa de los archivos crudos de la rama `master` desde `raw.githubusercontent.com`, sin credenciales. Las catas no se volvieron a recoger.

## Huellas SHA-256 de los originales

| Archivo original | Bytes | Filas × columnas | SHA-256 |
|---|---|---|---|
| `data/arabica_data_cleaned.csv` | 649 689 | 1 311 × 44 | `f99e588fcdd564e43a779a4b0f3870760018b1ffec7eab7f43db7bedf8f6d670` |
| `data/robusta_data_cleaned.csv` | 13 921 | 28 × 44 | `bde9e70dc9e6d1529d4bb690c80a227766a8f747582144a30754a7d4713753bf` |
| `data/arabica_ratings_raw.csv` | 684 741 | 1 312 × 53 | `90e4d5e0e805f8d86dda5e4259a2e9077c90375be2a4e44928741aac75f8f65c` |
| `data/robusta_ratings_raw.csv` | 14 610 | sin inspeccionar | `eeedaba933ce18944588ee8d8f26184ddf70e5d0d3652d0ead25173e44400736` |
| `LICENSE` | 1 069 | | `0eeab284c6ecdf40da37d099a27811a039e6adccdda1a2d465a7964e03d619cb` |

Solo los dos CSV limpios están en la plantilla (`data/raw/cqi/`). Los crudos no se usan.

## Qué se ha modificado

**Nada.** Los dos CSV de `data/raw/cqi/` son copias byte a byte de los originales (mismo SHA-256). Se conservan todas las columnas, incluidas las que contienen nombres de personas y datos de contacto (`Owner`, `Owner.1`, `Producer`, `Farm.Name`, `Certification.Contact`, `Certification.Address`), por decisión del instructor. La limpieza del dato es responsabilidad de la capa MASTER.

## Licencia y condiciones

- **Repositorio de origen:** MIT (`LICENSE`, «Copyright (c) 2018 James LeDoux»). Copia en `references/LICENSE-jldbc.txt`.
- **Derechos sobre el dato de CQI:** la licencia la declara quien redistribuye, no CQI. Condiciones de uso de `database.coffeeinstitute.org`: **sin verificar**.
- **Atribución:** Coffee Quality Institute (datos); James LeDoux, `jldbc/coffee-quality-database` (recopilación y limpieza, MIT).
- **Descripción en Kaggle** (copia alternativa, no usada): «I'm not the Owner of the Datasets, nor scrapping was performed by me».
