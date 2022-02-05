FROM python:3.9-alpine
ENV PYTHONUNBUFFERED 1

RUN apk update && \
    apk add --no-cache gcc musl-dev bash tzdata \
    libressl-dev musl-dev libffi-dev make openssh-keygen openssh-client;

RUN cp /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime; \
    echo "America/Sao_Paulo" > /etc/timezone

RUN python -m pip install --upgrade pip

WORKDIR /code
ADD ./requirements.txt /code
RUN pip install --no-cache-dir -r requirements.txt
COPY . /code