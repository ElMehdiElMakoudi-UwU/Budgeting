#!/bin/bash

# Change to the project directory
cd /home/ubuntu/Budgeting/budget_project

# Activate virtual environment
source ../venv/bin/activate

# Kill any existing process running on port 8010
kill $(lsof -t -i:8010) 2>/dev/null || true

# Start the Django application with nohup
nohup python3 manage.py runserver 0.0.0.0:8010 > django_app.log 2>&1 &

echo "Django application started on port 8010. Check django_app.log for output."
echo "To stop the application, run: kill \$(lsof -t -i:8010)" 