# Student Records Management System

A school-style **Python Flask + HTML/CSS** project.

## Storage Requirement

This project uses **Python Lists only** (no database). All lists are now
**saved to a `data.json` file** after every change and reloaded when the
server starts, so accounts, grades, schedules, subject assignments,
courses, announcements, and reports are **kept even after logging out or
restarting the server**.

## Default administrative account

Username: `admin`
Password: `admin123`

## How to run

```bash
python -m venv venv
venv\Scripts\activate        (Windows)
source venv/bin/activate       (Mac/Linux)
pip install -r requirements.txt
python app.py
```

Open: `http://127.0.0.1:5000`

## What each role can do

### Admin
- View registered users (Students table + Teachers table)
- **Add Student / Teacher accounts** directly (no signup needed)
- **Manage Courses**: add new courses (code + full program name); they
  instantly appear in signup, registration, and grade entry
- **Subjects & Teachers**: assign a subject to a teacher and year level;
  every student in the teacher's course and selected year level sees it
- **All Schedules**: view, add, edit, or remove any student's schedule
  entries (day, time, subject, room)
- Reset passwords, change Student IDs, change roles, delete accounts
- Configure exam grade weights

### Teacher
- Search and select students in their course; already-selected students
  disappear from that teacher's search results
- Divide selected students into Set A and Set B
- Enter Prelim, Midterm, Semi-Final, and Final exam scores; computed
  weighted grades are saved to the student's academic records
- Schedule assigned subjects for Set A or Set B using the available day
  patterns and time slots
- Profile, change password, and settings

### Student
- View personal academic records (grades)
- View classmates (same course + year level)
- **My Teachers & Subjects**: see every finalized subject with the teacher
  handling it, plus a list of their teachers
- View personal schedule, including the assigned teacher
- Profile, change password, and settings

## OOP requirements demonstrated

- Functions, Lists, Encapsulation through classes, Inheritance,
  Polymorphism, Exception Handling, Flask, HTML/CSS,
  Role-based access control
