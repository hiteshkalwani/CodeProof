.PHONY: install test lint up down logs dev-api dev-web

install:  ## Backend + frontend dependencies
	pip install -r backend/requirements-dev.txt
	cd frontend && npm ci

test:  ## All tests. Docker sandbox tests run when Docker is reachable.
	cd backend && pytest
	cd frontend && npm test

lint:
	cd backend && ruff check .

up:  ## Full stack on http://localhost:8080 (demo mode unless .env says otherwise)
	test -f .env || cp .env.example .env
	docker pull -q python:3.12-alpine && docker pull -q node:22-alpine
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

dev-api:  ## Django on :8000 with SQLite and the scripted model
	cd backend && DJANGO_DEBUG=1 LLM_PROVIDER=fake python manage.py migrate && DJANGO_DEBUG=1 LLM_PROVIDER=fake python manage.py runserver

dev-web:  ## Vite on :5173, proxies /api to :8000
	cd frontend && npm run dev
