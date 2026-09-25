# One-command local dev. AI inference runs on the HOST (Apple Metal); only
# Postgres + Redis run in Docker. See scripts/dev.sh for details.
.PHONY: up down restart status logs

up:        ## Start everything (containers + backend + celery + frontend [+ Ollama])
	@bash scripts/dev.sh up

down:      ## Stop all host processes and containers (volumes preserved)
	@bash scripts/dev.sh down

restart:   ## Restart everything
	@bash scripts/dev.sh down && bash scripts/dev.sh up

status:    ## Show what's running
	@bash scripts/dev.sh status

logs:      ## Tail logs from all host processes
	@bash scripts/dev.sh logs
