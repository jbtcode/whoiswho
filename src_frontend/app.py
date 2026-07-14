import os
import sys
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for, flash, send_from_directory

import auth
import config

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import storage
from avatar_storage import AvatarStorage
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))

if config.AUTH_MODE != "mock" and not config.SECRET_KEY:
    raise RuntimeError(
        "WHOISWHO_SECRET_KEY must be set when WHOISWHO_AUTH_MODE is not 'mock'."
    )
app.secret_key = config.SECRET_KEY
app.config["APPLICATION_ROOT"] = "/"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "data" / "avatars")
avatar_storage = AvatarStorage()

DEFAULT_USER = storage.DEFAULT_USER

DEFAULT_EMPLOYEES = [
    {"name": "Ada Lovelace", "role": "Product Designer", "department": "Design"},
    {"name": "Grace Hopper", "role": "Engineering Lead", "department": "Engineering"},
    {"name": "Katherine Johnson", "role": "Data Scientist", "department": "Research"},
    {"name": "Margaret Hamilton", "role": "Software Architect", "department": "Product"},
]


def _user_from_row(row):
    return {
        **DEFAULT_USER,
        **row,
        "first_name": row.get("first_name", DEFAULT_USER["first_name"]),
        "last_name": row.get("last_name", DEFAULT_USER["last_name"]),
        "email": row.get("email", DEFAULT_USER["email"]),
        "avatar": row.get("avatar", f"{row.get('first_name', DEFAULT_USER['first_name'])[0].upper()}{row.get('last_name', DEFAULT_USER['last_name'])[0].upper()}"),
        "avatar_path": row.get("avatar_path"),
    }


def _seed_demo_data():
    storage.initialize_tables()
    users = storage.load_table("Users")
    if not users:
        storage.upsert_row("Users", {
            "PartitionKey": "default",
            "RowKey": DEFAULT_USER["email"],
            **DEFAULT_USER,
        })

    employees = storage.load_table("Employees")
    if not employees:
        for employee in DEFAULT_EMPLOYEES:
            storage.upsert_row(
                "Employees",
                {
                    "PartitionKey": "default",
                    "RowKey": employee["name"].lower().replace(" ", "-"),
                    **employee,
                },
            )


_seed_demo_data()


def get_user():
    if "user" in session:
        user = session["user"]
        email = user.get("email")
        if email:
            rows = storage.load_table("Users")
            for row in rows:
                if row.get("RowKey") == email:
                    refreshed_user = _user_from_row(row)
                    session["user"] = refreshed_user
                    return refreshed_user
        return user

    email = session.get("email")
    if email:
        rows = storage.load_table("Users")
        for row in rows:
            if row.get("RowKey") == email:
                user = _user_from_row(row)
                session["user"] = user
                return user

    return _user_from_row(DEFAULT_USER)


@app.get("/")
def index():
    if session.get("authenticated"):
        return redirect(url_for("home"))
    return redirect(url_for("login"))


@app.get("/login")
@app.post("/login")
def login():
    provider = auth.get_provider()
    if request.method == "POST":
        return provider.login_post(request)
    return provider.login_get()


@app.get("/auth/callback")
def auth_callback():
    return auth.get_provider().callback(request)


@app.get("/avatars/<path:filename>")
def uploaded_file(filename: str):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.get("/home")
def home():
    if not session.get("authenticated"):
        return redirect(url_for("login"))
    employees = [
        {"name": row.get("name"), "role": row.get("role"), "department": row.get("department")}
        for row in storage.load_table("Employees")
    ]
    return render_template("home.html", user=get_user(), employees=employees)


@app.post("/home")
def update_profile():
    if not session.get("authenticated"):
        return redirect(url_for("login"))

    current_user = get_user()
    email = request.form.get("email", current_user["email"])
    uploaded_file = request.files.get("profile_picture")
    avatar_path = current_user.get("avatar_path")
    if uploaded_file and uploaded_file.filename:
        avatar_path = avatar_storage.save(uploaded_file, email)

    updated_user = {
        "PartitionKey": "default",
        "RowKey": email,
        "first_name": request.form.get("first_name", current_user["first_name"]),
        "last_name": request.form.get("last_name", current_user["last_name"]),
        "address": request.form.get("address", current_user.get("address", "")),
        "hobbies": request.form.get("hobbies", current_user.get("hobbies", "")),
        "email": email,
        "role": current_user.get("role", DEFAULT_USER["role"]),
        "avatar": f"{request.form.get('first_name', current_user['first_name'])[0].upper()}{request.form.get('last_name', current_user['last_name'])[0].upper()}",
        "avatar_path": avatar_path,
    }
    storage.upsert_row("Users", updated_user)
    session["email"] = email
    session["user"] = _user_from_row(updated_user)
    flash("Your profile information was updated", "success")
    return redirect(url_for("home"))


@app.get("/employees")
def employees():
    if not session.get("authenticated"):
        return redirect(url_for("login"))
    employees = [
        {"name": row.get("name"), "role": row.get("role"), "department": row.get("department")}
        for row in storage.load_table("Employees")
    ]
    return render_template("employees.html", employees=employees, user=get_user())


@app.get("/logout")
def logout():
    provider = auth.get_provider()
    redirect_url = provider.logout_redirect_url()
    session.clear()
    if redirect_url:
        return redirect(redirect_url)
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
