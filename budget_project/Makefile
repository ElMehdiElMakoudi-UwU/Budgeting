.PHONY: run kill status logs help
SHELL := /bin/bash

help:
	@echo "Available commands:"
	@echo "  make run    - Start the Django server on port 8010"
	@echo "  make kill   - Stop the Django server"
	@echo "  make status - Check if the server is running"
	@echo "  make logs   - View the server logs"

run:
	cd /home/ubuntu/Budgeting/budget_project && \
	. ../venv/bin/activate && \
	kill $$(lsof -t -i:8010) 2>/dev/null || true && \
	nohup python3 manage.py runserver 0.0.0.0:8010 > django_app.log 2>&1 & \
	echo "Django application started on port 8010. Check django_app.log for output." && \
	sleep 2 && \
	make status && \
	echo "You can view logs with: make logs"

kill:
	@if [ -n "$$(lsof -t -i:8010)" ]; then \
		kill $$(lsof -t -i:8010); \
		echo "Server stopped successfully"; \
	else \
		echo "No server running on port 8010"; \
	fi

status:
	@if [ -n "$$(lsof -t -i:8010)" ]; then \
		echo "Server is running on port 8010"; \
		echo "Process ID: $$(lsof -t -i:8010)"; \
	else \
		echo "Server is not running"; \
	fi

logs:
	@if [ -f django_app.log ]; then \
		tail -f django_app.log; \
	else \
		echo "Log file not found"; \
	fi 