from functools import wraps

from flask import redirect, session, url_for

from . import storage


def _user_from_row(row):
    default_user = storage.DEFAULT_USER
    return {
        **default_user,
        **row,
        "first_name": row.get("first_name", default_user["first_name"]),
        "last_name": row.get("last_name", default_user["last_name"]),
        "email": row.get("email", default_user["email"]),
        "avatar": row.get("avatar", f"{row.get('first_name', default_user['first_name'])[0].upper()}{row.get('last_name', default_user['last_name'])[0].upper()}"),
        "avatar_path": row.get("avatar_path"),
    }


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

    return _user_from_row(storage.DEFAULT_USER)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped
