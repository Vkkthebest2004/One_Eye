.PHONY: install run-backend run-frontend run-demo test benchmark clean docker-up docker-down

install:
	/opt/homebrew/bin/python3.11 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r backend/requirements.txt
	cd frontend && npm install

generate-video:
	.venv/bin/python scripts/generate_demo_video.py

seed-db:
	.venv/bin/python scripts/seed_demo.py

run-backend:
	cd backend && ../.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

run-frontend:
	cd frontend && npm run dev

run-demo:
	.venv/bin/python scripts/run_demo.py

test:
	cd backend && ../.venv/bin/pytest tests/ -v

benchmark:
	.venv/bin/python scripts/benchmark.py

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
