# Datos de calidad del café (CQI): copia sin modificar

## Qué hay aquí

| Archivo | Filas de datos | Columnas | Contenido |
|---|---|---|---|
| `arabica_data_cleaned.csv` | 1 311 | 44 | Cafés arábica, versión limpia |
| `robusta_data_cleaned.csv` | 28 | 44 | Cafés robusta, versión limpia |
| `SHA256SUMS` | | | Huellas SHA-256 de los dos archivos |

Los dos CSV son una copia byte a byte de los originales. No se ha quitado ninguna columna, ninguna fila ni ningún valor.

## De dónde sale

Copia de los archivos `data/arabica_data_cleaned.csv` y `data/robusta_data_cleaned.csv` del repositorio <https://github.com/jldbc/coffee-quality-database> (licencia MIT, «Copyright (c) 2018 James LeDoux»; texto en `references/LICENSE-jldbc.txt`).

Según el README de ese repositorio, las reseñas proceden de las páginas de catas del Coffee Quality Institute (CQI), recogidas en enero de 2018.

Atribución: el dato es de CQI, recopilado y publicado en GitHub por James LeDoux (jldbc). Detalles de la fuente, huellas de los originales y estado de las condiciones de uso en `references/fuente.md`.

## Datos personales: qué contiene y por qué no se han retirado

Las columnas `Owner`, `Owner.1`, `Producer`, `Farm.Name`, `Certification.Contact` y `Certification.Address` contienen nombres de personas y empresas, de fincas, y datos de contacto y dirección de certificadoras, tal como aparecen en el repositorio de origen.

Por decisión del instructor (el taller es un laboratorio), **no se han retirado ni seudonimizado**: el archivo es idéntico al original. Si el uso del repositorio fuera público y se quisiera limitar esa información, habría que revisar esta decisión antes de publicarlo.

## Condiciones de uso

- Licencia del repositorio de origen: MIT.
- Condiciones de uso de los datos de CQI (`database.coffeeinstitute.org`): **sin verificar**.

## Comprobar la copia

Huellas en `SHA256SUMS`. Desde la raíz del repositorio, con PowerShell:

```
Get-FileHash -Algorithm SHA256 data\raw\cqi\*.csv
```

Las pruebas que lo vigilan: `python -m pytest -q tests\test_dato.py`.
