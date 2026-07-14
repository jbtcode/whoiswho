from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, session, url_for

from .. import storage
from ..avatar_storage import AvatarStorage
from ..users import _user_from_row, get_user, login_required

bp = Blueprint("profile", __name__)
avatar_storage = AvatarStorage()


@bp.get("/")
def index():
    if session.get("authenticated"):
        return redirect(url_for("profile.home"))
    return redirect(url_for("auth.login"))


@bp.get("/avatars/<path:filename>")
@login_required
def uploaded_file(filename: str):
    return send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)


@bp.get("/home")
@login_required
def home():
    employees = [
        {"name": row.get("name"), "role": row.get("role"), "department": row.get("department")}
        for row in storage.load_table("Employees")
    ]
    return render_template("profile/home.html", user=get_user(), employees=employees)


@bp.post("/home")
@login_required
def update_profile():
    current_user = get_user()
    email = request.form.get("email", current_user["email"])
    uploaded_picture = request.files.get("profile_picture")
    avatar_path = current_user.get("avatar_path")
    if uploaded_picture and uploaded_picture.filename:
        avatar_path = avatar_storage.save(uploaded_picture, email)

    updated_user = {
        "PartitionKey": "default",
        "RowKey": email,
        "first_name": request.form.get("first_name", current_user["first_name"]),
        "last_name": request.form.get("last_name", current_user["last_name"]),
        "address": request.form.get("address", current_user.get("address", "")),
        "hobbies": request.form.get("hobbies", current_user.get("hobbies", "")),
        "email": email,
        "role": current_user.get("role", storage.DEFAULT_USER["role"]),
        "avatar": f"{request.form.get('first_name', current_user['first_name'])[0].upper()}{request.form.get('last_name', current_user['last_name'])[0].upper()}",
        "avatar_path": avatar_path,
    }
    storage.upsert_row("Users", updated_user)
    session["email"] = email
    session["user"] = _user_from_row(updated_user)
    flash("Your profile information was updated", "success")
    return redirect(url_for("profile.home"))
