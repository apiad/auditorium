FROM python:3.8-alpine

ARG AUDITORIUM_VERSION
COPY dist/auditorium-${AUDITORIUM_VERSION}-py3-none-any.whl /dist/auditorium-${AUDITORIUM_VERSION}-py3-none-any.whl
RUN pip install --no-cache-dir /dist/auditorium-${AUDITORIUM_VERSION}-py3-none-any.whl
