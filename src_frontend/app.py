import os
from pathlib import Path

from flask import Flask, redirect, render_template, request, session, url_for, flash

import storage

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))
app.secret_key = "whoiswho-dev-secret"
app.config["APPLICATION_ROOT"] = "/"

DEFAULT_USER = {
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada.lovelace@whoiswho.dev",
    "address": "10 Downing Street, London",
    "hobbies": "Reading, Hiking, Tech",
    "role": "Product Designer",
    "avatar": "AL",
}

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
        return session["user"]

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
    if request.method == "POST":
        email = request.form.get("email", DEFAULT_USER["email"])
        user_row = {
            "PartitionKey": "default",
            "RowKey": email,
            "first_name": request.form.get("first_name", DEFAULT_USER["first_name"]),
            "last_name": request.form.get("last_name", DEFAULT_USER["last_name"]),
            "email": email,
            "address": "",
            "hobbies": "",
            "role": DEFAULT_USER["role"],
            "avatar": f"{request.form.get('first_name', DEFAULT_USER['first_name'])[0].upper()}{request.form.get('last_name', DEFAULT_USER['last_name'])[0].upper()}",
        }
        storage.upsert_row("Users", user_row)
        session["authenticated"] = True
        session["email"] = email
        session["user"] = _user_from_row(user_row)
        flash("Signed in successfully through SSO", "success")
        return redirect(url_for("home"))

    return render_template("login.html")


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
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
