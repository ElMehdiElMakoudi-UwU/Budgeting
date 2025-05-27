# Personal Budget Management Application

A comprehensive Django-based budgeting application that helps users manage their personal finances effectively.

## Features

- **Transaction Management**: Track income and expenses with detailed categorization
- **Budget Planning**: Set and monitor monthly budgets by category
- **Recurring Transactions**: Automate regular income and expense entries
- **Category Management**: Organize transactions with custom categories
- **Dark Mode Support**: Toggle between light and dark themes for comfortable viewing
- **Analytics**: Visualize spending patterns and budget progress
- **Responsive Design**: Works seamlessly on desktop and mobile devices

## Technology Stack

- Python 3.x
- Django 4.x
- Bootstrap 5
- Chart.js
- SQLite (default database)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/ElMehdiElMakoudi-UwU/Budgeting.git
cd Budgeting
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create a superuser (admin):
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

7. Visit http://localhost:8000 in your browser

## Usage

1. Register a new account or login
2. Set up your income and expense categories
3. Add your transactions
4. Create budgets for different categories
5. Set up recurring transactions for regular income/expenses
6. View analytics to track your spending patterns

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 