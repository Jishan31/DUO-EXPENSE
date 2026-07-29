import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user

from extensions import db
from models import User, Category, DEFAULT_CATEGORIES
from utils.oauth import oauth, google_configured, apple_configured
from utils.validators import validate_email_format, validate_phone_for_region, is_password_strong_enough, REGIONS

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        region = request.form.get("region", "IN").strip().upper()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not username or len(username) < 3:
            errors.append("Username must be at least 3 characters.")

        email_ok, email_result = validate_email_format(email)
        if not email_ok:
            errors.append(f"Email address: {email_result}")
        else:
            email = email_result

        formatted_phone = None
        if phone:
            phone_ok, phone_result = validate_phone_for_region(phone, region)
            if not phone_ok:
                errors.append(f"Phone number: {phone_result}")
            elif session.get("otp_verified_phone") != phone_result:
                errors.append("Please verify your phone number with the OTP code first.")
            else:
                formatted_phone = phone_result

        if not is_password_strong_enough(password):
            errors.append("Password is too weak — use at least 8 characters with a mix of uppercase, "
                           "lowercase, and a number or symbol.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        if User.query.filter_by(username=username).first():
            errors.append("That username is already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("An account with that email already exists.")
        if formatted_phone and User.query.filter_by(phone=formatted_phone).first():
            errors.append("An account with that phone number already exists.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", form_data=request.form, regions=REGIONS)

        user = User(username=username, email=email, phone=formatted_phone, region=region)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()  # get user.id before commit

        # Seed default categories for the new user so the wheel isn't empty
        for i, cat in enumerate(DEFAULT_CATEGORIES):
            db.session.add(Category(
                user_id=user.id, name=cat["name"], icon=cat["icon"],
                color=cat["color"], is_default=True, sort_order=i
            ))

        db.session.commit()
        session.pop("otp_code", None)
        session.pop("otp_phone", None)
        session.pop("otp_expires", None)
        session.pop("otp_verified_phone", None)
        login_user(user)
        flash("Welcome to your new account!", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("register.html", form_data={}, regions=REGIONS)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auditor.auditor_dashboard") if current_user.role == "auditor" else url_for("main.dashboard"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter(
            (db.func.lower(User.email) == identifier) | (db.func.lower(User.username) == identifier)
        ).first()

        if not user or not user.check_password(password):
            flash("Invalid username/email or password.", "error")
        elif user.role == "auditor":
            flash("That's an auditor account — use the Auditor Login page instead.", "error")
        else:
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("main.dashboard"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You've been logged out.", "info")
    return redirect(url_for("main.landing"))


@auth_bp.route("/send-otp", methods=["POST"])
def send_otp():
    import random
    import time

    phone = request.form.get("phone", "").strip()
    region = request.form.get("region", "IN").strip().upper()
    if not phone:
        return jsonify({"error": "Enter a phone number first."}), 400

    ok, result = validate_phone_for_region(phone, region)
    if not ok:
        return jsonify({"error": result}), 400

    code = f"{random.randint(0, 999999):06d}"
    session["otp_code"] = code
    session["otp_phone"] = result
    session["otp_expires"] = time.time() + 300  # 5 minutes

    # No SMS provider is wired up — set SMS_API_KEY (and add the real send
    # call here) to actually deliver codes. Until then, the code is returned
    # directly so registration can still be tested end-to-end without one.
    if os.environ.get("SMS_API_KEY"):
        # send_sms(result, f"Your Duo Expense verification code is {code}")
        return jsonify({"message": f"Code sent to {result}."})
    return jsonify({"message": f"Demo mode (no SMS provider configured) \u2014 your code is {code}", "demo_code": code})


@auth_bp.route("/verify-otp", methods=["POST"])
def verify_otp():
    import time

    submitted = request.form.get("otp", "").strip()
    if not session.get("otp_code") or time.time() > session.get("otp_expires", 0):
        return jsonify({"verified": False, "error": "Code expired \u2014 send a new one."}), 400
    if submitted != session.get("otp_code"):
        return jsonify({"verified": False, "error": "Incorrect code."}), 400

    session["otp_verified_phone"] = session.get("otp_phone")
    return jsonify({"verified": True})


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")

        user = User.query.filter(db.func.lower(User.username) == username, db.func.lower(User.email) == email).first()

        if not user:
            flash("No account matches that username and email together — double check both.", "error")
        elif not is_password_strong_enough(new_password):
            flash("New password is too weak — use at least 8 characters with a mix of uppercase, lowercase, and a number or symbol.", "error")
        elif new_password != confirm:
            flash("Passwords don't match.", "error")
        else:
            user.set_password(new_password)
            db.session.commit()
            flash("Password reset — you can log in with your new password now.", "success")
            return redirect(url_for("auditor.auditor_login") if user.role == "auditor" else url_for("auth.login"))

    return render_template("forgot_password.html")


@auth_bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_username":
            new_username = request.form.get("username", "").strip()
            if not new_username or len(new_username) < 3:
                flash("Username must be at least 3 characters.", "error")
            elif User.query.filter(User.username == new_username, User.id != current_user.id).first():
                flash("That username is already taken.", "error")
            else:
                current_user.username = new_username
                db.session.commit()
                flash("Username updated.", "success")

        elif action == "update_password":
            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm = request.form.get("confirm_password", "")
            if not current_user.check_password(current_password):
                flash("Current password is incorrect.", "error")
            elif not is_password_strong_enough(new_password):
                flash("New password is too weak — use at least 8 characters with a mix of uppercase, lowercase, and a number or symbol.", "error")
            elif new_password != confirm:
                flash("New passwords don't match.", "error")
            else:
                current_user.set_password(new_password)
                db.session.commit()
                flash("Password updated.", "success")

        return redirect(url_for("auth.account"))

    return render_template("account.html")


def _unique_username(base):
    base = "".join(c for c in base.lower() if c.isalnum()) or "user"
    candidate = base
    n = 1
    while User.query.filter_by(username=candidate).first():
        n += 1
        candidate = f"{base}{n}"
    return candidate


def _login_or_create_oauth_user(provider, oauth_id, email, name):
    """Shared by Google and Apple: find a matching account, link one if the
    email already exists from a password signup, or create a brand new one."""
    user = User.query.filter_by(oauth_provider=provider, oauth_id=oauth_id).first()
    if not user and email:
        user = User.query.filter_by(email=email).first()
        if user:
            user.oauth_provider = provider
            user.oauth_id = oauth_id

    if not user:
        user = User(
            username=_unique_username((name or email or provider).split("@")[0]),
            email=email or f"{provider}_{oauth_id}@no-email.duoexpense",
            oauth_provider=provider, oauth_id=oauth_id,
        )
        db.session.add(user)
        db.session.flush()
        for i, cat in enumerate(DEFAULT_CATEGORIES):
            db.session.add(Category(
                user_id=user.id, name=cat["name"], icon=cat["icon"],
                color=cat["color"], is_default=True, sort_order=i,
            ))

    db.session.commit()
    login_user(user)
    return user


@auth_bp.route("/auth/google/login")
def google_login():
    if not google_configured():
        flash("Google sign-in isn't set up for this deployment yet.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.google_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google/callback")
def google_callback():
    if not google_configured():
        return redirect(url_for("auth.login"))
    try:
        token = oauth.google.authorize_access_token()
        info = token.get("userinfo") or oauth.google.userinfo()
    except Exception:
        flash("Google sign-in didn't complete — please try again.", "error")
        return redirect(url_for("auth.login"))

    _login_or_create_oauth_user("google", info["sub"], info.get("email", "").lower(), info.get("name", ""))
    flash("Signed in with Google.", "success")
    return redirect(url_for("main.dashboard"))


@auth_bp.route("/auth/apple/login")
def apple_login():
    if not apple_configured():
        flash("Apple sign-in isn't set up for this deployment yet.", "error")
        return redirect(url_for("auth.login"))
    redirect_uri = url_for("auth.apple_callback", _external=True)
    return oauth.apple.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/apple/callback", methods=["GET", "POST"])
def apple_callback():
    if not apple_configured():
        return redirect(url_for("auth.login"))
    try:
        token = oauth.apple.authorize_access_token()
        info = token.get("userinfo") or {}
    except Exception:
        flash("Apple sign-in didn't complete — please try again.", "error")
        return redirect(url_for("auth.login"))

    # Apple only sends the user's name on the very first authorization ever —
    # request.form carries it as a JSON string under "user" on that first call.
    name = ""
    user_blob = request.form.get("user")
    if user_blob:
        import json
        try:
            parsed = json.loads(user_blob)
            name = " ".join([parsed.get("name", {}).get("firstName", ""), parsed.get("name", {}).get("lastName", "")]).strip()
        except (ValueError, KeyError):
            pass

    _login_or_create_oauth_user("apple", info.get("sub"), (info.get("email") or "").lower(), name)
    flash("Signed in with Apple.", "success")
    return redirect(url_for("main.dashboard"))
