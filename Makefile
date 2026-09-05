.DEFAULT_GOAL := help

COMPOSE := docker compose

.PHONY: help build up down restart logs shell selftest certs clean

help: ## Показать список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

build: ## Собрать образ
	$(COMPOSE) build

up: ## Поднять сервис
	$(COMPOSE) up -d

down: ## Остановить и удалить контейнер
	$(COMPOSE) down

restart: ## Перезапустить сервис
	$(COMPOSE) restart

logs: ## Смотреть логи
	$(COMPOSE) logs -f

shell: ## Bash внутри контейнера
	$(COMPOSE) exec pycades bash

selftest: ## Смоук-тест: подпись и проверка
	$(COMPOSE) exec pycades python selftest.py

certs: ## Показать сертификаты, видимые КриптоПро
	$(COMPOSE) exec pycades certmgr -list

clean: ## Удалить контейнеры и образы проекта
	$(COMPOSE) down --rmi local
