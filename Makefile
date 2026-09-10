.PHONY: up run test down clean
up:
	docker compose up -d postgres rabbitmq opensearch
run:
	docker compose run --rm demo python -m app.cli run-all
test:
	docker compose run --rm demo pytest -q
down:
	docker compose down
clean:
	docker compose down -v --remove-orphans

