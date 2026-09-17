from flask import Blueprint, request, jsonify, session
from DB import db, cursor
import bcrypt
import uuid


auth = Blueprint("auth", __name__)


# ==========================================================
# REGISTER
# ==========================================================

@auth.route("/register", methods=["POST"])
def register():

    try:
        data = request.get_json() or {}

        username = data.get("username", "").strip()
        full_name = data.get("full_name", "").strip()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not username or not email or not password:
            return jsonify({
                "success": False,
                "message": "Username, email and password are required."
            }), 400

        if len(password) < 6:
            return jsonify({
                "success": False,
                "message": "Password must be at least 6 characters."
            }), 400

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Email already registered."
            }), 409

        cursor.execute(
            """
            SELECT id
            FROM users
            WHERE username = %s
            """,
            (username,)
        )

        if cursor.fetchone():
            return jsonify({
                "success": False,
                "message": "Username already exists."
            }), 409

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        user_uuid = str(uuid.uuid4())

        # New registrations are explicitly normal users.
        cursor.execute(
            """
            INSERT INTO users
            (
                uuid,
                username,
                full_name,
                email,
                password_hash,
                role
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                'user'
            )
            """,
            (
                user_uuid,
                username,
                full_name,
                email,
                hashed_password
            )
        )

        db.commit()

        return jsonify({
            "success": True,
            "message": "Registration Successful 🎉"
        }), 201

    except Exception as e:
        db.rollback()
        print("REGISTER ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Registration failed."
        }), 500


# ==========================================================
# LOGIN
# ==========================================================

@auth.route("/login", methods=["POST"])
def login():

    try:
        data = request.get_json() or {}

        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Email and password are required."
            }), 400

        cursor.execute(
            """
            SELECT
                id,
                uuid,
                username,
                full_name,
                email,
                password_hash,
                role,
                account_status
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "message": "Invalid email or password."
            }), 401

        if user["account_status"] != "active":
            return jsonify({
                "success": False,
                "message": f"Account is {user['account_status']}."
            }), 403

        password_valid = bcrypt.checkpw(
            password.encode("utf-8"),
            user["password_hash"].encode("utf-8")
        )

        if not password_valid:
            return jsonify({
                "success": False,
                "message": "Invalid email or password."
            }), 401

        # --------------------------------------------------
        # Create role-aware session
        # --------------------------------------------------
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["email"] = user["email"]
        session["role"] = user["role"]

        # Keep last-login information current.
        cursor.execute(
            """
            UPDATE users
            SET last_login = NOW()
            WHERE id = %s
            """,
            (user["id"],)
        )
        db.commit()

        return jsonify({
            "success": True,
            "message": "Login Successful 🎉",
            "user": {
                "id": user["id"],
                "uuid": user["uuid"],
                "username": user["username"],
                "full_name": user["full_name"],
                "email": user["email"],
                "role": user["role"]
            }
        })

    except Exception as e:
        db.rollback()
        print("LOGIN ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Login failed."
        }), 500


# ==========================================================
# LOGOUT
# ==========================================================

@auth.route("/logout", methods=["POST"])
def logout():
    session.clear()

    return jsonify({
        "success": True,
        "message": "Logged out successfully."
    })


# ==========================================================
# PROFILE
# ==========================================================

@auth.route("/profile", methods=["GET"])
def profile():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Not logged in."
        }), 401

    try:
        cursor.execute(
            """
            SELECT
                id,
                uuid,
                username,
                full_name,
                email,
                role,
                account_status
            FROM users
            WHERE id = %s
            """,
            (session["user_id"],)
        )

        user = cursor.fetchone()

        if not user:
            session.clear()
            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404

        session["role"] = user["role"]

        return jsonify({
            "success": True,
            "user": user
        })

    except Exception as e:
        print("PROFILE ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to load profile."
        }), 500


# ==========================================================
# CHECK LOGIN
# ==========================================================

@auth.route("/check-login", methods=["GET"])
def check_login():

    if "user_id" not in session:
        return jsonify({
            "logged_in": False
        })

    try:
        cursor.execute(
            """
            SELECT
                id,
                username,
                email,
                role,
                account_status
            FROM users
            WHERE id = %s
            """,
            (session["user_id"],)
        )

        user = cursor.fetchone()

        if not user or user["account_status"] != "active":
            session.clear()
            return jsonify({
                "logged_in": False
            })

        # Always refresh the session role from MySQL.
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["email"] = user["email"]
        session["role"] = user["role"]

        return jsonify({
            "logged_in": True,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "role": user["role"]
            }
        })

    except Exception as e:
        print("CHECK LOGIN ERROR:", e)

        return jsonify({
            "logged_in": False,
            "message": "Unable to verify login."
        }), 500
