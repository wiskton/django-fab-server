# -*- coding: utf-8 -*-
# Copie este arquivo para "local_settings.py" (na raiz do projeto, ao lado do
# fabfile.py) e ajuste os valores abaixo para apontar para o servidor do seu
# projeto. Esse arquivo é ignorado pelo git (veja .gitignore) e é importado
# automaticamente pelo fabfile.py, sobrescrevendo os valores padrão definidos
# lá -- assim todos os comandos (fab newserver, fab newaccount, fab login...)
# passam a mirar no seu servidor sem precisar editar o fabfile.py em si.
#
#   cp local_settings-template.py local_settings.py
#
# Isso permite reaproveitar este mesmo repositório (django-fab-server) para
# provisionar servidores de outros projetos: cada um com seu próprio
# local_settings.py local, nunca commitado.

user = "root"
host = "192.168.0.1"
chave = ""  # caminho da chave privada ssh, ex: "~/.ssh/meu_projeto.pem"
