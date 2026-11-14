# Imagen del Codespace del taller: Python 3.11 de Microsoft (la misma versión que las imágenes y el CI).
# Por qué hay un Dockerfile y no solo «image»: esta imagen trae un repositorio apt de yarn cuya clave GPG ha caducado
# (NO_PUBKEY 62D54FD4003F6525). La característica Docker-in-Docker hace «apt-get update» al instalarse y falla con
# ese repositorio. El taller no usa yarn: se quita antes de que se instale Docker-in-Docker.
# (Medido el 14/11/2026 al crear el Codespace del repositorio de prueba: «Container creation failed».)
FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

RUN rm -f /etc/apt/sources.list.d/yarn.list \
    && sed -i '/dl.yarnpkg.com/d' /etc/apt/sources.list 2>/dev/null || true
