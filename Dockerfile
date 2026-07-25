FROM python:3.12-alpine
ENV PYTHONUNBUFFERED 1

RUN apk update && apk add --no-cache gcc musl-dev bash tzdata \
    openssl-dev libffi-dev make;

RUN cp /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime; \
    echo "America/Sao_Paulo" > /etc/timezone

WORKDIR /code
ADD ./requirements.txt /code
RUN pip install --no-cache-dir -r requirements.txt
COPY . /code

# fabfile.py de provisionamento do servidor fica em server/
WORKDIR /code/server

CMD [ "fab", "--list" ]