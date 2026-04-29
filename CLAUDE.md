# CLAUDE.md — CN334 Room Booking System

## Project Overview
Django web app for booking meeting/classroom rooms in the Electrical & Computer Engineering (ECE) department at Thammasat University. Authentication via TU REST API (no passwords stored locally). UI in Thai language.

## Tech Stack
- **Backend**: Django 4.2, Python 3.11
- **Database**: SQLite (dev) / PostgreSQL 15 (Docker)
- **Auth**: TU REST API — `POST https://restapi.tu.ac.th/api/v1/auth/Ad/verify`
- **Deploy**: Docker + docker-compose
- **Frontend**: Django Templates + CSS Grid (Thai language UI, Sarabun font)
- **Static CSS**: modular files in `src/bookings/static/bookings/css/` (variables, base, components, layout, pages → compiled into main.css)

## Project Structure
```
src/
├── bookings/          # Main app — auth, booking form, calendar
│   ├── models.py      # User (AbstractUser+role), Room, Booking
│   ├── views.py       # tu_login_view, logout_view, create_booking_view, calendar_view, api endpoints
│   ├── urls.py
│   ├── static/bookings/css/   # main.css + source partials
│   └── templates/bookings/
│       ├── login.html         # Two-panel login (uses main.css)
│       ├── booking_form.html  # Sidebar shell + time-slot picker (uses main.css)
│       └── calendar.html      # FullCalendar weekly/monthly view
├── dashboard/         # Admin & user dashboard views
│   └── templates/dashboard/
│       ├── admin_dashboard.html
│       ├── user_dashboard.html
│       └── manage_rooms.html
├── reports/           # Admin report/statistics views
│   └── templates/reports/
│       └── report_dashboard.html
└── core/              # Django project config (settings, urls)
```

## Key Models
- **User**: extends AbstractUser; `role` = `Lecturer` | `Admin`
- **Room**: `room_id` (PK), `name`, `room_type`, `capacity`, `is_active`
- **Booking**: links User+Room; fields: `purpose_type` (Teaching/Training), `course_code`, `course_name`, `program`, `training_topic`, `start_time`, `end_time`, `status` (Pending/Approved/Rejected/Cancelled); has conflict detection in `clean()`

## Rooms (seed data)
| ID | Name | Type | Capacity |
|----|------|------|----------|
| 406-3 | ห้องประชุม 1 | Meeting | 60 |
| 406-5 | ห้องประชุม 2 | Meeting | 15 |
| 408-1 | ห้องประชุม 3 | Meeting | 10 |
| 408-2/1 | ห้องบรรยาย 1 | Classroom | 20 |
| 408-2/2 | ห้องบรรยาย 2 | Classroom | 20 |

## User Roles
- **Lecturer**: book rooms, view own bookings, cancel own upcoming bookings
- **Admin**: approve/reject bookings, manage rooms, view reports, assign roles

## Booking Purpose Types (FR-BOOK-02)
1. **สอนปกติ/ชดเชย/เสริม** — requires: course_code, course_name, program (Bachelor / Master / TEP-TEPE / TU-PINE)
2. **จัดอบรม/จัดติว** — requires: training_topic

## Environment Variables
- `TU_API_KEY` — Application-Key for TU REST API (required for login)
- `SECRET_KEY`, `DEBUG`, `DATABASE_URL` (see settings.py / .env)

## Running the Project
```bash
# Docker (recommended)
docker-compose up --build

# Local dev
cd src && python manage.py runserver
```

## Commands
```bash
python src/manage.py migrate
python src/manage.py createsuperuser
python src/manage.py shell
```

## Current State
- [x] TU REST API login/logout (`login.html` — two-panel branded UI)
- [x] Booking form with room select, purpose type, time-slot picker, conflict detection (`booking_form.html`)
- [x] Calendar view — FullCalendar weekly/monthly, room filter, click-to-book (`calendar.html`)
- [x] Admin dashboard + report dashboard
- [x] User model with role
- [ ] Approval workflow (Admin approve/reject + email notification)
- [ ] Email notifications (SMTP) — FR-NOTI-01/02
- [ ] Recurring bookings UI — FR-BOOK-09
- [ ] My bookings + cancel — FR-BOOK-08
- [ ] Utilization rate reports — FR-RPT-02
- [ ] Room management by Admin — FR-ADM-01

## SRS Priority Reference
- **Must**: Login, booking+conflict detection, approval workflow, calendar, email notifications
- **Should**: Recurring bookings, my bookings/cancel, utilization reports, room management
- **Could**: Click-to-book on calendar, email reminders (D-1), CSV export, blackout periods
