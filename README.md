# QueueFlow - Full Stack Queue Management System

A clean, responsive full-stack Queue Management Application built with **Python (Flask)**, **SQLite**, **Bootstrap 5**, and **Chart.js**.

## Features Implemented
1. **Manager Authentication:** Secure session-based login (`admin` / `admin123`).
2. **Multi-Queue Management:** Create and switch between multiple named queues dynamically.
3. **Token Lifecycle Operations:**
   - Issue new tokens (`T-101`, `T-102`, etc.) for incoming persons.
   - Real-time waiting list display with the next-in-line token highlighted.
   - Reorder tokens (**Move Up** / **Move Down**) dynamically in the queue.
   - **Assign Top Token** for service with a single click.
   - **Cancel** tokens cleanly from the waiting list.
4. **Analytics Dashboard:** Real-time KPI cards (Active Queues, Waiting Count, Served Count, Average Wait Time) and interactive Chart.js visualizations for queue length breakdown and wait-time trends.

## Tech Stack
- **Backend:** Python 3, Flask, RESTful JSON APIs
- **Database:** SQLite3 (auto-initialized with sample data on first run)
- **Frontend:** HTML5, CSS3, Bootstrap 5, Vanilla JavaScript (Fetch API), Chart.js

## How to Run Locally
1. Install Flask:
   ```bash
   pip install flask
   ```
2. Run the application:
   ```bash
   python app.py
   ```
3. Open `http://127.0.0.1:5000` in your browser and log in with `admin` / `admin123`.
