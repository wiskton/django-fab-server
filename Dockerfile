FROM python:2-alpine
ENV PYTHONUNBUFFERED 1

RUN apk update && apk add --no-cache gcc python-dev musl-dev bash tzdata \
    libressl-dev musl-dev libffi-dev make;

RUN cp /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime; \
    echo "America/Sao_Paulo" > /etc/timezone

WORKDIR /code
ADD ./requirements.txt /code
RUN pip install --no-cache-dir -r requirements.txt
COPY . /code

CMD [ "fab", "list" ]