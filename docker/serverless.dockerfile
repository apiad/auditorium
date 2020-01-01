FROM python:3.8-alpine

ARG AUDITORIUM_VERSION
RUN pip install --no-cache-dir fastapi markdown fire pygments jinja2
