import json
import os
import re
from difflib import SequenceMatcher

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = "student-records-project-secret"


# ============================================================
# DATA FILE (persistence)
# ------------------------------------------------------------
# The project still uses Python LISTS as its storage structure
# (no database), but the lists are now saved to a data.json file
# after every change, and loaded again when the server starts.
# So data survives logout AND server restarts.
# ============================================================

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")


# ============================================================
# STATIC CHOICES
# ============================================================

DEFAULT_COURSES = ["Bachelor of Science in Computer Science", "Bachelor of Science in Business Administration", "Bachelor of Science in Education", "Bachelor of Science in Criminology", "Bachelor of Science in Social Work"]
DEFAULT_PROGRAMS = {
    "BSCS": "Bachelor of Science in Computer Science",
    "BSBA": "Bachelor of Science in Business Administration",
    "BSEd": "Bachelor of Science in Education",
    "BSCrim": "Bachelor of Science in Criminology",
    "BSSW": "Bachelor of Science in Social Work"
}

# Courses are now dynamic — the admin can add (and remove) courses.
COURSES = list(DEFAULT_COURSES)
PROGRAMS = dict(DEFAULT_PROGRAMS)

YEAR_LEVELS = ["1st Year", "2nd Year", "3rd Year", "4th Year"]

ACADEMIC_PERIODS = [
    "1st Semester (2026-2027)",
    "2nd Semester (2026-2027)"
]

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
SCHEDULE_DAY_OPTIONS = [
    "Monday - Thursday",
    "Tuesday - Friday",
    "Wednesday",
    "Sunday"
]
TIME_SLOTS = [
    "7:00 AM - 8:30 AM", "8:30 AM - 10:00 AM",
    "10:00 AM - 11:30 AM", "11:30 AM - 1:00 PM",
    "1:00 PM - 2:30 PM", "2:30 PM - 4:00 PM",
    "4:00 PM - 5:30 PM", "5:30 PM - 7:00 PM",
    "7:00 PM - 8:30 PM"
]
GRADE_COMPONENTS = ["Prelim Exam", "Midterm Exam", "Semi-Final Exam", "Final Exam"]

STUDENT_ID_PATTERN = re.compile(r"^\d{6}$")
COURSE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]{2,10}$")


# ============================================================
# STORAGE (Python lists — saved to data.json)
# ============================================================

users = [
    {
        "id": 1,
        "name": "System Administrator",
        "email": "admin@school.com",
        "username": "admin",
        "password": generate_password_hash("admin123"),
        "role": "admin",
        "student_id": "",
        "course": "",
        "year_level": "",
        "teacher_ids": []
    }
]

# Each grade: student_id, subject, grade, semester, year_level, program
grades = []

# Class schedules added by teachers or admin.
# Each schedule: id, student_id, subject, day, time, room
schedules = []

# Subject-teacher assignments (finalized once, shown to the student).
# Each assignment: id, student_id, subject, teacher_id
subject_assignments = []

grade_policy = {
    "Prelim Exam": 25,
    "Midterm Exam": 25,
    "Semi-Final Exam": 25,
    "Final Exam": 25
}

next_user_id = 2
next_schedule_id = 1
next_assignment_id = 1

# Temporary bug/contact reports (visible to the admin).
bug_reports = []

# School announcements. Only the administrator can post or remove these.
announcements = []


# ============================================================
# PERSISTENCE HELPERS
# ============================================================

def save_data():
    """Write all in-memory lists to data.json."""
    payload = {
        "users": users,
        "grades": grades,
        "schedules": schedules,
        "subject_assignments": subject_assignments,
        "grade_policy": grade_policy,
        "bug_reports": bug_reports,
        "announcements": announcements,
        "next_user_id": next_user_id,
        "next_schedule_id": next_schedule_id,
        "next_assignment_id": next_assignment_id,
        "courses": COURSES,
        "programs": PROGRAMS
    }
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        # Never crash the request just because saving failed.
        pass


def load_data():
    """Load saved lists from data.json (if it exists)."""
    global next_user_id, next_schedule_id, next_assignment_id

    if not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data.get("users"), list) and data["users"]:
            users[:] = data["users"]

        if isinstance(data.get("grades"), list):
            grades[:] = data["grades"]

        if isinstance(data.get("schedules"), list):
            schedules[:] = data["schedules"]

        if isinstance(data.get("subject_assignments"), list):
            subject_assignments[:] = data["subject_assignments"]

        if isinstance(data.get("grade_policy"), dict):
            for component in GRADE_COMPONENTS:
                value = data["grade_policy"].get(component)
                if isinstance(value, (int, float)) and value >= 0:
                    grade_policy[component] = value

        if isinstance(data.get("bug_reports"), list):
            bug_reports[:] = data["bug_reports"]

        if isinstance(data.get("announcements"), list):
            announcements[:] = data["announcements"]

        if isinstance(data.get("courses"), list) and data["courses"]:
            COURSES[:] = data["courses"]

        if isinstance(data.get("programs"), dict) and data["programs"]:
            PROGRAMS.clear()
            PROGRAMS.update(data["programs"])

        next_user_id = int(data.get("next_user_id", next_user_id))
        next_schedule_id = int(data.get("next_schedule_id", next_schedule_id))
        next_assignment_id = int(data.get("next_assignment_id", next_assignment_id))

    except Exception:
        # If the file is corrupt, start fresh with defaults.
        pass


# ============================================================
# OOP
# ============================================================

class User:
    """Base class for all users."""

    def __init__(self, name, email, username, role):
        self.name = name
        self.email = email
        self.username = username
        self.role = role

    def dashboard_message(self):
        return "Welcome to the Student Records System."


class Student(User):
    """Student inherits from User."""

    def dashboard_message(self):
        return "View your personal grades and academic records."


class Teacher(User):
    """Teacher inherits from User."""

    def dashboard_message(self):
        return "View students and manage their grades."


class Admin(User):
    """Admin inherits from User."""

    def dashboard_message(self):
        return "View registered users and system information."


def create_user_object(user):
    """Return the correct OOP object based on the user's role."""

    if user is None:
        return None

    classes = {
        "student": Student,
        "teacher": Teacher,
        "admin": Admin
    }

    user_class = classes.get(user["role"], User)

    return user_class(
        user["name"],
        user["email"],
        user["username"],
        user["role"]
    )


# ============================================================
# FUNCTIONS / HELPERS
# ============================================================

def find_user_by_username(username):
    for user in users:
        if user["username"].lower() == username.lower():
            return user
    return None


def find_user_by_login(login):
    """Find a user by username OR email address (used on the login page)."""
    login = login.strip().lower()
    for user in users:
        if user["username"].lower() == login or user["email"].lower() == login:
            return user
    return None


def find_user_by_id(user_id):
    for user in users:
        if user["id"] == user_id:
            return user
    return None


def get_students():
    return [user for user in users if user["role"] == "student"]


def get_teachers():
    return [user for user in users if user["role"] == "teacher"]


def get_user_grades(user_id):
    return [grade for grade in grades if grade["student_id"] == user_id]


def get_user_schedule(user_id):
    student = find_user_by_id(user_id)
    if not student:
        return []

    student_schedules = []
    teacher_groups = student.get("teacher_groups", {})
    for schedule in schedules:
        if schedule.get("student_id") == user_id:
            student_schedules.append(schedule)
            continue

        if (
            schedule.get("course") != student.get("course")
            or schedule.get("year_level") != student.get("year_level")
        ):
            continue

        group = schedule.get("set_group")
        teacher_id = schedule.get("teacher_id")
        assigned_group = teacher_groups.get(str(teacher_id))
        if assigned_group is None and teacher_id in student.get("teacher_ids", []):
            assigned_group = "A"
        if group and assigned_group != group:
            continue

        entry = dict(schedule)
        teacher = find_user_by_id(teacher_id) if teacher_id else None
        entry["teacher_name"] = teacher.get("name", "") if teacher else ""
        student_schedules.append(entry)

    for entry in student_schedules:
        if not entry.get("teacher_name"):
            assignment = next((
                item for item in get_student_assignments(user_id)
                if item.get("subject", "").lower() == entry.get("subject", "").lower()
            ), None)
            teacher_id = assignment.get("teacher_id") if assignment else None
            if not teacher_id and student.get("teacher_ids"):
                teacher_id = student["teacher_ids"][0]
            teacher = find_user_by_id(teacher_id) if teacher_id else None
            entry["teacher_name"] = teacher.get("name", "") if teacher else ""

    return student_schedules


def get_teacher_students(teacher_id):
    """Students the teacher has selected to handle."""
    return [
        s for s in get_students()
        if teacher_id in s.get("teacher_ids", [])
    ]


def get_available_students(teacher_id):
    """Students the teacher has NOT selected yet."""
    return [
        s for s in get_students()
        if teacher_id not in s.get("teacher_ids", [])
    ]


def get_student_assignments(student_id):
    """Finalized subject assignments for a student or their cohort."""
    student = find_user_by_id(student_id)
    if not student:
        return []

    return [
        assignment for assignment in subject_assignments
        if assignment.get("student_id") == student_id
        or (
            assignment.get("course") == student.get("course")
            and assignment.get("year_level") == student.get("year_level")
        )
    ]


def get_teacher_assignments_for_student(teacher_id, student):
    return [
        assignment for assignment in get_student_assignments(student["id"])
        if assignment.get("teacher_id") == teacher_id
    ]


def find_assignment_by_id(assignment_id):
    for a in subject_assignments:
        if a.get("id") == assignment_id:
            return a
    return None


def assignment_exists(student_id, subject, exclude_id=None):
    """True if the student already has this subject assigned."""
    subject = subject.strip().lower()
    for a in subject_assignments:
        if a["student_id"] == student_id and a["subject"].strip().lower() == subject:
            if exclude_id is not None and a.get("id") == exclude_id:
                continue
            return True
    return False


def cohort_assignment_exists(course, year_level, subject, exclude_id=None):
    subject = subject.strip().lower()
    return any(
        assignment.get("course") == course
        and assignment.get("year_level") == year_level
        and assignment.get("subject", "").strip().lower() == subject
        and assignment.get("id") != exclude_id
        for assignment in subject_assignments
    )


def find_schedule_by_id(schedule_id):
    for s in schedules:
        if s.get("id") == schedule_id:
            return s
    return None


def create_schedule_entry(student_id, subject, day, time, room):
    """Add a schedule entry (with a unique id) and persist it."""
    global next_schedule_id

    entry = {
        "id": next_schedule_id,
        "student_id": student_id,
        "subject": subject,
        "day": day,
        "time": time,
        "room": room
    }
    next_schedule_id += 1
    schedules.append(entry)
    return entry


def create_assignment(student_id, subject, teacher_id):
    """Finalized subject-teacher assignment, persisted."""
    global next_assignment_id

    assignment = {
        "id": next_assignment_id,
        "student_id": student_id,
        "subject": subject,
        "teacher_id": teacher_id
    }
    next_assignment_id += 1
    subject_assignments.append(assignment)
    return assignment


def create_cohort_assignment(subject, teacher_id, course, year_level):
    """Assign a subject to every student in a course and year level."""
    global next_assignment_id

    assignment = {
        "id": next_assignment_id,
        "subject": subject,
        "teacher_id": teacher_id,
        "course": course,
        "year_level": year_level
    }
    next_assignment_id += 1
    subject_assignments.append(assignment)
    return assignment


def compute_exam_grade(scores):
    """Return the weighted exam percentage using the configured policy."""
    return sum(
        float(scores[component]) * float(grade_policy[component])
        for component in GRADE_COMPONENTS
    ) / 100


def program_of(course):
    return PROGRAMS.get(course, "")


def student_id_taken(student_id, exclude_user_id=None):
    """Check whether a 6-digit Student ID is already registered."""
    for existing_user in users:
        if existing_user.get("student_id") == student_id:
            if exclude_user_id is not None and existing_user["id"] == exclude_user_id:
                continue
            return True
    return False


def passwords_too_similar(current_password, new_password):
    """
    Returns True if the new password is basically the old password
    wearing a disguise (identical, one contained in the other, or a
    high similarity ratio).
    """
    a = current_password.lower().strip()
    b = new_password.lower().strip()

    if not a or not b:
        return False

    if a == b:
        return True

    if a in b or b in a:
        return True

    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio >= 0.7


def filter_students_for_teacher(teacher, args):
    """
    Applies the teacher's search/filter controls on top of the full
    student list. Defaults to the teacher's own handled course.
    """
    selected_year = args.get("year_level", "all")
    student_id_search = args.get("student_id_search", "").strip()

    result = get_students()

    result = [s for s in result if teacher["id"] not in s.get("teacher_ids", [])]

    if selected_year and selected_year != "all":
        result = [s for s in result if s.get("year_level") == selected_year]

    if student_id_search:
        result = [s for s in result if student_id_search in s.get("student_id", "")]

    return result, selected_year, student_id_search


def build_assignment_rows(assignment_list):
    """Enrich assignments with student/teacher objects for display."""
    rows = []
    for a in assignment_list:
        rows.append({
            "assignment": a,
            "student": find_user_by_id(a["student_id"]) if a.get("student_id") else None,
            "teacher": find_user_by_id(a.get("teacher_id")),
            "course": a.get("course") or (find_user_by_id(a.get("student_id")) or {}).get("course", ""),
            "year_level": a.get("year_level") or (find_user_by_id(a.get("student_id")) or {}).get("year_level", "")
        })
    return rows


def build_schedule_rows(schedule_list):
    """Enrich schedules with student objects for display."""
    rows = []
    for s in schedule_list:
        rows.append({
            "schedule": s,
            "student": find_user_by_id(s["student_id"]) if s.get("student_id") else None,
            "teacher": find_user_by_id(s.get("teacher_id"))
        })
    return rows


def sorted_schedules(schedule_list):
    return sorted(
        schedule_list,
        key=lambda s: (
            SCHEDULE_DAY_OPTIONS.index(s["day"])
            if s.get("day") in SCHEDULE_DAY_OPTIONS
            else (len(SCHEDULE_DAY_OPTIONS) + DAYS.index(s["day"]) if s.get("day") in DAYS else 99),
            s.get("time", "")
        )
    )


# ============================================================
# LOGIN / ROLE PROTECTION
# ============================================================

def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for("login"))

        user = find_user_by_id(session["user_id"])

        if user is None:
            session.clear()
            flash("Your session is no longer valid. Please log in again.", "warning")
            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in first.", "warning")
                return redirect(url_for("login"))

            user = find_user_by_id(session["user_id"])

            if not user:
                session.clear()
                flash("Your session is no longer valid. Please log in again.", "warning")
                return redirect(url_for("login"))

            if user["role"] not in roles:
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("dashboard"))

            return view(*args, **kwargs)

        return wrapped_view

    return decorator


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    current = find_user_by_id(user_id) if user_id else None
    return {
        "current_user": current,
        "COURSES": COURSES,
        "YEAR_LEVELS": YEAR_LEVELS,
        "PROGRAMS": PROGRAMS,
        "ACADEMIC_PERIODS": ACADEMIC_PERIODS,
        "DAYS": DAYS,
        "SCHEDULE_DAY_OPTIONS": SCHEDULE_DAY_OPTIONS,
        "TIME_SLOTS": TIME_SLOTS,
        "GRADE_COMPONENTS": GRADE_COMPONENTS,
        "announcements": announcements
    }


# ============================================================
# MAIN PAGES
# ============================================================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    return render_template("index.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    global next_user_id

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "").strip().lower()
            student_id = request.form.get("student_id", "").strip()
            year_level = request.form.get("year_level", "").strip()
            course = request.form.get("course", "").strip()
            teacher_course = request.form.get("teacher_course", "").strip()

            if not name or not email or not username or not password:
                raise ValueError("Please fill in all required fields.")

            if len(password) < 6:
                raise ValueError("Password must be at least 6 characters.")

            # Public sign-up is only for students and teachers.
            if role not in ("student", "teacher"):
                raise ValueError("Please select Student or Teacher.")

            if find_user_by_username(username):
                raise ValueError("Username is already taken.")

            if role == "student":
                if not student_id:
                    raise ValueError("Student ID is required for students.")

                if not STUDENT_ID_PATTERN.fullmatch(student_id):
                    raise ValueError("Student ID must be exactly 6 digits.")

                if not year_level:
                    raise ValueError("Please select your year level.")

                if course not in COURSES:
                    raise ValueError("Please select a valid course.")

                if student_id_taken(student_id):
                    raise ValueError("Student ID is already registered.")

            else:
                # Teachers register the course they handle, not a student ID.
                if teacher_course not in COURSES:
                    raise ValueError("Please select the course you handle.")

                course = teacher_course
                student_id = ""
                year_level = ""

            new_user = {
                "id": next_user_id,
                "name": name,
                "email": email,
                "username": username,
                "password": generate_password_hash(password),
                "role": role,
                "student_id": student_id,
                "year_level": year_level,
                "course": course,
                "teacher_ids": []
            }

            users.append(new_user)
            next_user_id += 1
            save_data()

            flash("Account created successfully. You can now log in.", "success")
            return redirect(url_for("login"))

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash("Something went wrong while creating the account.", "danger")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_input = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = find_user_by_login(login_input)

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]

            flash("Login successful.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid username/email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out. Your data is saved.", "success")
    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():
    user = find_user_by_id(session["user_id"])

    if user is None:
        session.clear()
        flash("Your session is no longer valid. Please log in again.", "warning")
        return redirect(url_for("login"))

    user_object = create_user_object(user)

    if user["role"] == "student":
        return render_template(
            "student_dashboard.html",
            user=user,
            message=user_object.dashboard_message()
        )

    if user["role"] == "teacher":
        students, selected_year, student_id_search = filter_students_for_teacher(
            user, request.args
        )

        return render_template(
            "teacher_dashboard.html",
            user=user,
            message=user_object.dashboard_message(),
            students=students,
            selected_year=selected_year,
            student_id_search=student_id_search
        )

    # Admin dashboard.
    return render_template(
        "admin_dashboard.html",
        user=user,
        message=user_object.dashboard_message(),
        users=users,
        students=get_students(),
        teachers=get_teachers()
    )


# ============================================================
# STUDENT: ACADEMIC RECORDS (GRADES)
# ============================================================

@app.route("/academic-records")
@role_required("student")
def academic_records():
    user = find_user_by_id(session["user_id"])

    return render_template(
        "academic_records.html",
        user=user,
        my_grades=get_user_grades(user["id"])
    )


# ============================================================
# STUDENT: SCHEDULE
# ============================================================

@app.route("/schedule")
@role_required("student")
def student_schedule():
    user = find_user_by_id(session["user_id"])

    return render_template(
        "schedule.html",
        user=user,
        my_schedule=sorted_schedules(get_user_schedule(user["id"]))
    )


# ============================================================
# STUDENT: MY TEACHERS & SUBJECTS
# ------------------------------------------------------------
# Students see every subject assigned to them, with the teacher
# handling each subject (assignments are finalized once by the
# teacher/admin, so nothing needs to be re-entered).
# ============================================================

@app.route("/my-teachers")
@role_required("student")
def my_teachers():
    user = find_user_by_id(session["user_id"])

    rows = build_assignment_rows(get_student_assignments(user["id"]))

    # Unique list of teachers handling this student.
    seen = set()
    my_teacher_list = []
    for row in rows:
        teacher = row["teacher"]
        if teacher and teacher["id"] not in seen:
            seen.add(teacher["id"])
            my_teacher_list.append(teacher)

    return render_template(
        "student_teachers.html",
        user=user,
        rows=rows,
        my_teacher_list=my_teacher_list
    )


# ============================================================
# TEACHER: MY STUDENTS (selected students, any course)
# ============================================================

@app.route("/teacher/students")
@role_required("teacher")
def teacher_students():
    teacher = find_user_by_id(session["user_id"])

    return render_template(
        "teacher_students.html",
        user=teacher,
        my_students=get_teacher_students(teacher["id"]),
        available_students=get_available_students(teacher["id"]),
        student_groups={
            student["id"]: student.get("teacher_groups", {}).get(str(teacher["id"]), "A")
            for student in get_teacher_students(teacher["id"])
        }
    )


@app.route("/teacher/student/select/<int:student_id>", methods=["POST"])
@role_required("teacher")
def select_student(student_id):
    teacher = find_user_by_id(session["user_id"])
    student = find_user_by_id(student_id)

    if not student or student["role"] != "student":
        flash("Student not found.", "danger")
        return redirect(url_for("teacher_students"))

    teacher_ids = student.setdefault("teacher_ids", [])

    if teacher["id"] in teacher_ids:
        flash(f"{student['name']} is already in your students list.", "warning")
    else:
        teacher_ids.append(teacher["id"])
        student.setdefault("teacher_groups", {})[str(teacher["id"])] = "A"
        save_data()
        flash(f"{student['name']} was added to your students list.", "success")

    return redirect(url_for("teacher_students"))


@app.route("/teacher/student/<int:student_id>/group", methods=["POST"])
@role_required("teacher")
def assign_student_group(student_id):
    teacher = find_user_by_id(session["user_id"])
    student = find_user_by_id(student_id)
    group = request.form.get("group", "").strip()

    if not student or student["role"] != "student" or teacher["id"] not in student.get("teacher_ids", []):
        flash("That student is not assigned to you.", "danger")
    elif group not in ("A", "B"):
        flash("Choose Set A or Set B.", "danger")
    else:
        student.setdefault("teacher_groups", {})[str(teacher["id"])] = group
        save_data()
        flash(f"{student['name']} was placed in Set {group}.", "success")

    return redirect(url_for("teacher_students"))


# ============================================================
# TEACHER: GRADES
# ============================================================

@app.route("/teacher/student/<int:student_id>/grades", methods=["GET", "POST"])
@role_required("teacher")
def manage_grades(student_id):
    teacher = find_user_by_id(session["user_id"])
    student = find_user_by_id(student_id)

    if not student or student["role"] != "student":
        flash("Student not found.", "danger")
        return redirect(url_for("teacher_students"))

    teacher_assignments = get_teacher_assignments_for_student(teacher["id"], student)
    is_selected = teacher["id"] in student.get("teacher_ids", [])
    if not teacher_assignments and not is_selected:
        flash("You can only manage grades for your assigned students and subjects.", "danger")
        return redirect(url_for("teacher_students"))

    if request.method == "POST":
        try:
            assignment_id = request.form.get("assignment_id", type=int)
            assignment = next((
                item for item in teacher_assignments
                if item.get("id") == assignment_id
            ), None)
            semester = request.form.get("semester", "").strip()
            scores = {}

            if not assignment:
                raise ValueError("Choose a subject assigned to you.")

            for component in GRADE_COMPONENTS:
                score = request.form.get(component, "").strip()
                numeric_score = float(score)
                if numeric_score < 1 or numeric_score > 5:
                    raise ValueError("Exam grades must be between 1.00 and 5.00.")
                scores[component] = numeric_score

            if semester not in ACADEMIC_PERIODS:
                raise ValueError("Please select a valid academic period.")

            computed_grade = compute_exam_grade(scores)
            existing_grade = next((
                grade for grade in get_user_grades(student_id)
                if grade.get("subject", "").lower() == assignment["subject"].lower()
                and grade.get("semester") == semester
            ), None)
            grade_record = existing_grade or {
                "student_id": student_id,
                "subject": assignment["subject"],
                "semester": semester,
                "year_level": student["year_level"],
                "program": program_of(student.get("course", ""))
            }
            grade_record.update({
                "grade": f"{computed_grade:.2f}",
                "computed_grade": f"{computed_grade:.2f}",
                "scores": scores,
                "grade_weights": dict(grade_policy),
                "teacher_id": teacher["id"]
            })
            if not existing_grade:
                grades.append(grade_record)
            save_data()

            flash(f"Computed exam grade saved: {computed_grade:.2f}%.", "success")
            return redirect(url_for("manage_grades", student_id=student_id))

        except ValueError as error:
            flash(str(error), "danger")

        except Exception:
            flash("Invalid grade input.", "danger")

    return render_template(
        "manage_grades.html",
        student=student,
        student_grades=get_user_grades(student_id),
        student_program=program_of(student.get("course", "")),
        student_assignments=build_assignment_rows(teacher_assignments)
    )


@app.route(
    "/teacher/grade/update/<int:student_id>/<int:grade_index>",
    methods=["POST"]
)
@role_required("teacher")
def update_grade(student_id, grade_index):
    student_grades = get_user_grades(student_id)

    try:
        target = student_grades[grade_index]

        subject = request.form.get("subject", "").strip()
        grade_value = request.form.get("grade", "").strip()

        if not subject or not grade_value:
            raise ValueError("Subject and grade are required.")

        numeric_grade = float(grade_value)

        if numeric_grade < 1.00 or numeric_grade > 5.00:
            raise ValueError("Grade must be between 1.00 and 5.00.")

        target["subject"] = subject
        target["grade"] = f"{numeric_grade:.2f}"
        save_data()

        flash("Grade updated successfully.", "success")

    except (IndexError, ValueError):
        flash(
            "The grade could not be updated. Use a grade from 1.00 to 5.00.",
            "danger"
        )

    return redirect(url_for("manage_grades", student_id=student_id))


@app.route(
    "/teacher/grade/delete/<int:student_id>/<int:grade_index>",
    methods=["POST"]
)
@role_required("teacher")
def delete_grade(student_id, grade_index):
    student_grades = get_user_grades(student_id)

    try:
        target = student_grades[grade_index]
        grades.remove(target)
        save_data()

        flash("Grade deleted.", "success")

    except (IndexError, ValueError):
        flash("Grade could not be deleted.", "danger")

    return redirect(url_for("manage_grades", student_id=student_id))


# ============================================================
# TEACHER: SCHEDULES
# ============================================================

@app.route("/teacher/schedules", methods=["GET", "POST"])
@role_required("teacher")
def manage_teacher_schedules():
    global next_schedule_id
    teacher = find_user_by_id(session["user_id"])
    teacher_assignments = []
    for assignment in subject_assignments:
        if assignment.get("teacher_id") != teacher["id"]:
            continue
        if assignment.get("course") and assignment.get("year_level"):
            teacher_assignments.append(assignment)
        elif assignment.get("student_id"):
            assigned_student = find_user_by_id(assignment["student_id"])
            if assigned_student:
                cohort_assignment = dict(assignment)
                cohort_assignment["course"] = assigned_student.get("course", "")
                cohort_assignment["year_level"] = assigned_student.get("year_level", "")
                teacher_assignments.append(cohort_assignment)

    if request.method == "POST":
        assignment_id = request.form.get("assignment_id", type=int)
        assignment = next((
            item for item in teacher_assignments
            if item.get("id") == assignment_id
        ), None)
        group = request.form.get("group", "").strip()
        day = request.form.get("day", "").strip()
        time = request.form.get("time", "").strip()
        room = request.form.get("room", "").strip()

        if not assignment:
            flash("Choose a subject assigned to you.", "danger")
        elif group not in ("A", "B"):
            flash("Choose Set A or Set B.", "danger")
        elif day not in SCHEDULE_DAY_OPTIONS:
            flash("Choose one of the available day patterns.", "danger")
        elif time not in TIME_SLOTS:
            flash("Choose an available time slot.", "danger")
        elif not room:
            flash("Room is required.", "danger")
        else:
            schedules.append({
                "id": next_schedule_id,
                "teacher_id": teacher["id"],
                "course": assignment["course"],
                "year_level": assignment["year_level"],
                "subject": assignment["subject"],
                "set_group": group,
                "day": day,
                "time": time,
                "room": room
            })
            next_schedule_id += 1
            save_data()
            flash(f"Schedule added for {assignment['subject']} - Set {group}.", "success")
            return redirect(url_for("manage_teacher_schedules"))

    return render_template(
        "teacher_schedule.html",
        user=teacher,
        teacher_assignments=teacher_assignments,
        teacher_schedules=sorted_schedules([
            schedule for schedule in schedules
            if schedule.get("teacher_id") == teacher["id"]
        ])
    )


@app.route("/teacher/schedule/delete/<int:schedule_id>", methods=["POST"])
@role_required("teacher")
def delete_schedule(schedule_id):
    teacher = find_user_by_id(session["user_id"])
    target = find_schedule_by_id(schedule_id)

    if target and target.get("teacher_id") == teacher["id"]:
        schedules.remove(target)
        save_data()
        flash("Schedule entry deleted.", "success")
    else:
        flash("Schedule entry could not be deleted or belongs to another teacher.", "danger")

    return redirect(url_for("manage_teacher_schedules"))


# ============================================================
# CLASSMATES (STUDENT)
# ============================================================

@app.route("/classmates")
@role_required("student")
def classmates():
    user = find_user_by_id(session["user_id"])

    classmate_list = [
        s for s in get_students()
        if s["id"] != user["id"]
        and s.get("course") == user.get("course")
        and s.get("year_level") == user.get("year_level")
    ]

    my_groups = []
    for teacher_id in user.get("teacher_ids", []):
        teacher = find_user_by_id(teacher_id)
        if teacher:
            my_groups.append({
                "teacher": teacher,
                "set": user.get("teacher_groups", {}).get(str(teacher_id), "A")
            })

    return render_template(
        "classmates.html",
        user=user,
        classmates=classmate_list,
        my_groups=my_groups
    )


# ============================================================
# PROFILE
# ============================================================

@app.route("/profile")
@login_required
def profile():
    user = find_user_by_id(session["user_id"])

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    return render_template("profile.html", user=user)


# ============================================================
# SETTINGS (client-side preferences only, e.g. Dark Mode)
# ============================================================

@app.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


# ============================================================
# CONTACT / BUG REPORT
# ============================================================

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        message = request.form.get("message", "").strip()

        if not name or not email or not message:
            flash("Please complete all fields before submitting.", "danger")

        else:
            bug_reports.append({
                "name": name,
                "email": email,
                "message": message
            })
            save_data()

            flash(
                "Your report has been submitted to the school system administrator.",
                "success"
            )

            return redirect(url_for("contact"))

    return render_template("contact.html")


# ============================================================
# PASSWORD CHANGE
# ============================================================

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    user = find_user_by_id(session["user_id"])

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(user["password"], current_password):
            flash("Current password is incorrect.", "danger")

        elif len(new_password) < 6:
            flash("New password must be at least 6 characters.", "danger")

        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")

        elif passwords_too_similar(current_password, new_password):
            flash(
                "Your new password is too similar to your current password. "
                "Please choose a password that is clearly different.",
                "danger"
            )

        else:
            user["password"] = generate_password_hash(new_password)
            save_data()

            flash("Password changed successfully.", "success")
            return redirect(url_for("dashboard"))

    return render_template("change_password.html")


# ============================================================
# ADMIN: ADD STUDENT / TEACHER ACCOUNTS
# ============================================================

@app.route("/admin/add-account", methods=["GET", "POST"])
@role_required("admin")
def admin_add_account():
    global next_user_id

    if request.method == "POST":
        try:
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "").strip().lower()
            student_id = request.form.get("student_id", "").strip()
            year_level = request.form.get("year_level", "").strip()
            course = request.form.get("course", "").strip()
            teacher_course = request.form.get("teacher_course", "").strip()

            if not name or not email or not username or not password:
                raise ValueError("Please fill in all required fields.")

            if len(password) < 6:
                raise ValueError("Password must be at least 6 characters.")

            if role not in ("student", "teacher"):
                raise ValueError("Please choose Student or Teacher.")

            if find_user_by_username(username):
                raise ValueError("Username is already taken.")

            if role == "student":
                if not STUDENT_ID_PATTERN.fullmatch(student_id or ""):
                    raise ValueError("Student ID must be exactly 6 digits.")

                if not year_level:
                    raise ValueError("Please select a year level.")

                if course not in COURSES:
                    raise ValueError("Please select a valid course.")

                if student_id_taken(student_id):
                    raise ValueError("Student ID is already registered.")
            else:
                if teacher_course not in COURSES:
                    raise ValueError("Please select the course the teacher handles.")

                course = teacher_course
                student_id = ""
                year_level = ""

            new_user = {
                "id": next_user_id,
                "name": name,
                "email": email,
                "username": username,
                "password": generate_password_hash(password),
                "role": role,
                "student_id": student_id,
                "year_level": year_level,
                "course": course,
                "teacher_ids": []
            }

            users.append(new_user)
            next_user_id += 1
            save_data()

            flash(f"Account for {name} ({role}) was created successfully.", "success")
            return redirect(url_for("admin_add_account"))

        except ValueError as error:
            flash(str(error), "danger")
        except Exception:
            flash("Something went wrong while creating the account.", "danger")

    return render_template("admin_add_account.html")


# ============================================================
# ADMIN: COURSES (add new courses dynamically)
# ============================================================

@app.route("/admin/courses", methods=["GET", "POST"])
@role_required("admin")
def admin_courses():
    if request.method == "POST":
        code = request.form.get("code", "").strip().upper()
        program = request.form.get("program", "").strip()

        if not COURSE_CODE_PATTERN.fullmatch(code):
            flash("Course code must be 2-10 letters/numbers (e.g. BSN, BSIT).", "danger")

        elif not program:
            flash("Please enter the full program name.", "danger")

        elif code in COURSES:
            flash("That course code already exists.", "danger")

        else:
            COURSES.append(code)
            PROGRAMS[code] = program
            save_data()
            flash(f"Course {code} was added.", "success")
            return redirect(url_for("admin_courses"))

    return render_template("admin_courses.html")


@app.route("/admin/courses/delete/<code>", methods=["POST"])
@role_required("admin")
def admin_delete_course(code):
    code = code.upper()

    in_use = any(u.get("course") == code for u in users)

    if code not in COURSES:
        flash("Course not found.", "danger")
    elif in_use:
        flash(
            f"Cannot remove {code}: student or teacher accounts are still registered under it.",
            "danger"
        )
    else:
        COURSES.remove(code)
        PROGRAMS.pop(code, None)
        save_data()
        flash(f"Course {code} was removed.", "success")

    return redirect(url_for("admin_courses"))


# ============================================================
# ADMIN: SUBJECT-TEACHER ASSIGNMENTS
# ------------------------------------------------------------
# Admin can add, edit (change the assigned teacher or subject),
# and remove subject assignments for any student.
# ============================================================

@app.route("/admin/assignments")
@role_required("admin")
def admin_assignments():
    rows = build_assignment_rows(subject_assignments)

    return render_template(
        "admin_assignments.html",
        rows=rows,
        teachers=get_teachers()
    )


@app.route("/admin/assignment/add", methods=["POST"])
@role_required("admin")
def admin_add_assignment():
    teacher_id = request.form.get("teacher_id", type=int)
    subject = request.form.get("subject", "").strip()
    year_level = request.form.get("year_level", "").strip()
    teacher = find_user_by_id(teacher_id) if teacher_id else None

    if not teacher or teacher["role"] != "teacher":
        flash("Please choose a valid teacher.", "danger")

    elif not subject:
        flash("Please enter a subject.", "danger")

    elif year_level not in YEAR_LEVELS:
        flash("Please choose a valid year level.", "danger")

    elif cohort_assignment_exists(teacher.get("course", ""), year_level, subject):
        flash(f'"{subject}" is already assigned to that course and year level.', "warning")

    else:
        create_cohort_assignment(subject, teacher_id, teacher.get("course", ""), year_level)
        save_data()
        flash(
            f'"{subject}" assigned to {year_level} students in {teacher["course"]} under {teacher["name"]}.',
            "success"
        )

    return redirect(url_for("admin_assignments"))


@app.route("/admin/assignment/edit/<int:assignment_id>", methods=["GET", "POST"])
@role_required("admin")
def admin_edit_assignment(assignment_id):
    assignment = find_assignment_by_id(assignment_id)

    if not assignment:
        flash("Assignment not found.", "danger")
        return redirect(url_for("admin_assignments"))

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        teacher_id = request.form.get("teacher_id", type=int)
        year_level = request.form.get("year_level", "").strip()
        teacher = find_user_by_id(teacher_id) if teacher_id else None

        if not subject:
            flash("Please enter a subject.", "danger")

        elif not teacher or teacher["role"] != "teacher":
            flash("Please choose a valid teacher.", "danger")

        elif year_level not in YEAR_LEVELS:
            flash("Please choose a valid year level.", "danger")

        elif cohort_assignment_exists(teacher.get("course", ""), year_level, subject, exclude_id=assignment_id):
            flash("That subject is already assigned to the selected course and year level.", "warning")

        else:
            assignment["subject"] = subject
            assignment["teacher_id"] = teacher_id
            assignment["course"] = teacher.get("course", "")
            assignment["year_level"] = year_level
            assignment.pop("student_id", None)
            save_data()
            flash("Cohort subject assignment updated.", "success")
            return redirect(url_for("admin_assignments"))

    legacy_student = find_user_by_id(assignment.get("student_id")) if assignment.get("student_id") else None
    if legacy_student:
        assignment.setdefault("course", legacy_student.get("course", ""))
        assignment.setdefault("year_level", legacy_student.get("year_level", ""))

    return render_template(
        "admin_assignment_edit.html",
        assignment=assignment,
        teachers=get_teachers()
    )


@app.route("/admin/assignment/delete/<int:assignment_id>", methods=["POST"])
@role_required("admin")
def admin_delete_assignment(assignment_id):
    assignment = find_assignment_by_id(assignment_id)

    if assignment:
        subject_assignments.remove(assignment)
        save_data()
        flash("Subject assignment removed.", "success")
    else:
        flash("Assignment not found.", "danger")

    return redirect(url_for("admin_assignments"))


# ============================================================
# ADMIN: SCHEDULES (view / add / edit / remove any entry)
# ============================================================

@app.route("/admin/schedules")
@role_required("admin")
def admin_schedules():
    rows = build_schedule_rows(sorted_schedules(schedules))

    return render_template(
        "admin_schedules.html",
        rows=rows,
        students=get_students()
    )


@app.route("/admin/schedule/edit/<int:schedule_id>", methods=["GET", "POST"])
@role_required("admin")
def admin_edit_schedule(schedule_id):
    schedule = find_schedule_by_id(schedule_id)

    if not schedule:
        flash("Schedule entry not found.", "danger")
        return redirect(url_for("admin_schedules"))

    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        day = request.form.get("day", "").strip()
        time = request.form.get("time", "").strip()
        room = request.form.get("room", "").strip()

        if not subject or not day or not time or not room:
            flash("Subject, day, time, and room are all required.", "danger")

        elif day not in DAYS and day not in SCHEDULE_DAY_OPTIONS:
            flash("Please select a valid day.", "danger")

        else:
            schedule["subject"] = subject
            schedule["day"] = day
            schedule["time"] = time
            schedule["room"] = room
            save_data()
            flash("Schedule entry updated.", "success")
            return redirect(url_for("admin_schedules"))

    return render_template(
        "admin_schedule_edit.html",
        schedule=schedule,
        student=find_user_by_id(schedule.get("student_id")) if schedule.get("student_id") else None
    )


@app.route("/admin/schedule/delete/<int:schedule_id>", methods=["POST"])
@role_required("admin")
def admin_delete_schedule(schedule_id):
    schedule = find_schedule_by_id(schedule_id)

    if schedule:
        schedules.remove(schedule)
        save_data()
        flash("Schedule entry removed.", "success")
    else:
        flash("Schedule entry not found.", "danger")

    return redirect(url_for("admin_schedules"))


# ============================================================
# ADMIN: RESET A STUDENT'S OR TEACHER'S PASSWORD
# ============================================================

@app.route("/admin/reset-password/<int:user_id>", methods=["GET", "POST"])
@role_required("admin")
def admin_reset_password(user_id):
    target = find_user_by_id(user_id)

    if not target or target["role"] not in ("student", "teacher"):
        flash("Only student and teacher accounts can be reset from this page.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if len(new_password) < 6:
            flash("New password must be at least 6 characters.", "danger")

        elif new_password != confirm_password:
            flash("New passwords do not match.", "danger")

        else:
            target["password"] = generate_password_hash(new_password)
            save_data()
            flash(f"Password for {target['name']} has been reset.", "success")
            return redirect(url_for("dashboard"))

    return render_template("admin_reset_password.html", target=target)


# ============================================================
# ADMIN: CHANGE A STUDENT'S ID
# ============================================================

@app.route("/admin/change-id/<int:user_id>", methods=["GET", "POST"])
@role_required("admin")
def admin_change_id(user_id):
    target = find_user_by_id(user_id)

    if not target or target["role"] != "student":
        flash("Only student accounts can have their ID changed here.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        new_student_id = request.form.get("new_student_id", "").strip()

        if not STUDENT_ID_PATTERN.fullmatch(new_student_id):
            flash("Student ID must be exactly 6 digits.", "danger")

        elif student_id_taken(new_student_id, exclude_user_id=target["id"]):
            flash("That Student ID is already registered to another account.", "danger")

        else:
            old_id = target["student_id"]
            target["student_id"] = new_student_id
            save_data()
            flash(
                f"Student ID changed from {old_id} to {new_student_id} "
                f"for {target['name']}.",
                "success"
            )
            return redirect(url_for("dashboard"))

    return render_template("admin_change_id.html", target=target)


# ============================================================
# ADMIN: DELETE A STUDENT OR TEACHER ACCOUNT
# ============================================================

@app.route("/admin/delete-account/<int:user_id>", methods=["POST"])
@role_required("admin")
def admin_delete_account(user_id):
    target = find_user_by_id(user_id)

    # The admin account itself can never be deleted.
    if not target or target["role"] == "admin":
        flash("That account cannot be deleted.", "danger")
        return redirect(url_for("dashboard"))

    users.remove(target)

    # Remove the account's grades, schedules, and assignments too.
    grades[:] = [g for g in grades if g["student_id"] != user_id]
    schedules[:] = [s for s in schedules if s.get("student_id") != user_id and s.get("teacher_id") != user_id]
    subject_assignments[:] = [
        a for a in subject_assignments
        if a.get("student_id") != user_id and a.get("teacher_id") != user_id
    ]
    save_data()

    flash(f"Account for {target['name']} ({target['role']}) was deleted.", "success")
    return redirect(url_for("dashboard"))


# ============================================================
# ADMIN: CHANGE AN ACCOUNT'S ROLE (student <-> teacher)
# ============================================================

@app.route("/admin/change-role/<int:user_id>", methods=["GET", "POST"])
@role_required("admin")
def admin_change_role(user_id):
    target = find_user_by_id(user_id)

    if not target or target["role"] == "admin":
        flash("Only student and teacher accounts can have their role changed.", "danger")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        new_role = request.form.get("role", "").strip().lower()

        if new_role not in ("student", "teacher"):
            flash("Please choose Student or Teacher.", "danger")

        elif new_role == target["role"]:
            flash("This account already has that role.", "warning")

        elif new_role == "teacher":
            # Student -> Teacher: clear student-only fields, keep the course.
            target["role"] = "teacher"
            target["student_id"] = ""
            target["year_level"] = ""
            # Remove assignments where they were the student.
            subject_assignments[:] = [
                a for a in subject_assignments if a.get("student_id") != user_id
            ]
            save_data()
            flash(f"{target['name']} is now a Teacher.", "success")
            return redirect(url_for("dashboard"))

        else:
            # Teacher -> Student: student details are required.
            new_student_id = request.form.get("new_student_id", "").strip()
            year_level = request.form.get("year_level", "").strip()
            course = request.form.get("course", "").strip()

            if not STUDENT_ID_PATTERN.fullmatch(new_student_id):
                flash("Student ID must be exactly 6 digits.", "danger")

            elif student_id_taken(new_student_id, exclude_user_id=target["id"]):
                flash("That Student ID is already registered to another account.", "danger")

            elif year_level not in YEAR_LEVELS:
                flash("Please select a valid year level.", "danger")

            elif course not in COURSES:
                flash("Please select a valid course.", "danger")

            else:
                target["role"] = "student"
                target["student_id"] = new_student_id
                target["year_level"] = year_level
                target["course"] = course
                # Remove assignments where they were the teacher.
                subject_assignments[:] = [
                    a for a in subject_assignments if a.get("teacher_id") != user_id
                ]
                save_data()
                flash(f"{target['name']} is now a Student.", "success")
                return redirect(url_for("dashboard"))

    return render_template("admin_change_role.html", target=target)


# ============================================================
# ADMIN: VIEW / DELETE BUG REPORTS
# ============================================================

@app.route("/admin/report/delete/<int:report_index>", methods=["POST"])
@role_required("admin")
def admin_delete_report(report_index):
    try:
        bug_reports.pop(report_index)
        save_data()
        flash("Report removed.", "success")
    except IndexError:
        flash("Report not found.", "danger")

    return redirect(url_for("dashboard"))


# ============================================================
# ADMIN: ANNOUNCEMENTS
# ============================================================

@app.route("/admin/announcement/add", methods=["POST"])
@role_required("admin")
def admin_add_announcement():
    title = request.form.get("title", "").strip()
    body = request.form.get("body", "").strip()

    if not title or not body:
        flash("Announcement title and message are both required.", "danger")
    else:
        announcements.append({
            "title": title,
            "body": body
        })
        save_data()
        flash("Announcement posted for all users.", "success")

    return redirect(url_for("dashboard"))


@app.route("/admin/announcement/delete/<int:announcement_index>", methods=["POST"])
@role_required("admin")
def admin_delete_announcement(announcement_index):
    try:
        announcements.pop(announcement_index)
        save_data()
        flash("Announcement removed.", "success")
    except IndexError:
        flash("Announcement not found.", "danger")

    return redirect(url_for("dashboard"))


# ============================================================
# RUN
# ============================================================

# Load any previously saved data before serving requests.
load_data()

if __name__ == "__main__":
    app.run(debug=True)
