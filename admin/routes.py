from flask import Blueprint, jsonify, session, render_template, request, redirect, url_for
from DB import cursor


admin = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin"
)


# ==========================================================
# ADMIN ACCESS
# ==========================================================

def admin_required():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Admin login required."
        }), 401

    if session.get("role") != "admin":
        return jsonify({
            "success": False,
            "message": "Access denied. Admin privileges required."
        }), 403

    return None


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@admin.route("/", methods=["GET"])
def admin_dashboard():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # -----------------------------
        # Total Users
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM users
        """)

        total_users = cursor.fetchone()["total"]


        # -----------------------------
        # Total AI Providers
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM ai_providers
        """)

        total_providers = cursor.fetchone()["total"]


        # -----------------------------
        # Total API Keys
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM api_keys
        """)

        total_api_keys = cursor.fetchone()["total"]


        return render_template(
            "admin/dashboard.html",
            total_users=total_users,
            total_providers=total_providers,
            total_api_keys=total_api_keys
        )

    except Exception as e:

        print("ADMIN DASHBOARD ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to load dashboard."
        }), 500


# ==========================================================
# USERS PAGE
# ==========================================================

@admin.route("/users", methods=["GET"])
def admin_users():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # -----------------------------
        # Search
        # -----------------------------

        search = request.args.get(
            "search",
            ""
        ).strip()


        # -----------------------------
        # Pagination
        # -----------------------------

        try:
            page = int(
                request.args.get(
                    "page",
                    1
                )
            )
        except ValueError:
            page = 1

        if page < 1:
            page = 1


        per_page = 10

        offset = (page - 1) * per_page


        # -----------------------------
        # Total Matching Users
        # -----------------------------

        if search:

            search_value = f"%{search}%"

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM users
                WHERE
                    username LIKE %s
                    OR full_name LIKE %s
                    OR email LIKE %s
            """, (
                search_value,
                search_value,
                search_value
            ))

        else:

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM users
            """)


        total_users = cursor.fetchone()["total"]


        total_pages = max(
            1,
            (total_users + per_page - 1) // per_page
        )


        if page > total_pages:
            page = total_pages
            offset = (page - 1) * per_page


        # -----------------------------
        # Fetch Users
        # -----------------------------

        if search:

            search_value = f"%{search}%"

            cursor.execute("""
                SELECT
                    id,
                    uuid,
                    username,
                    full_name,
                    email,
                    role,
                    account_status,
                    email_verified,
                    last_login,
                    created_at,
                    updated_at
                FROM users
                WHERE
                    username LIKE %s
                    OR full_name LIKE %s
                    OR email LIKE %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (
                search_value,
                search_value,
                search_value,
                per_page,
                offset
            ))

        else:

            cursor.execute("""
                SELECT
                    id,
                    uuid,
                    username,
                    full_name,
                    email,
                    role,
                    account_status,
                    email_verified,
                    last_login,
                    created_at,
                    updated_at
                FROM users
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (
                per_page,
                offset
            ))


        users = cursor.fetchall()


        return render_template(
            "admin/users.html",
            users=users,
            search=search,
            page=page,
            total_pages=total_pages,
            total_users=total_users,
            admin_id=session.get("user_id")
        )


    except Exception as e:

        print("ADMIN USERS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to load users."
        }), 500


# ==========================================================
# CHANGE USER STATUS
# ==========================================================

@admin.route("/users/<int:user_id>/status", methods=["POST"])
def change_user_status(user_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        data = request.get_json() or {}

        new_status = data.get(
            "status",
            ""
        ).strip().lower()


        allowed_statuses = {
            "active",
            "suspended"
        }


        if new_status not in allowed_statuses:

            return jsonify({
                "success": False,
                "message": "Invalid account status."
            }), 400


        # --------------------------------
        # Prevent self-suspension
        # --------------------------------

        if user_id == session.get("user_id"):

            return jsonify({
                "success": False,
                "message": "You cannot change your own account status."
            }), 403


        # --------------------------------
        # Check User
        # --------------------------------

        cursor.execute("""
            SELECT
                id,
                username,
                role,
                account_status
            FROM users
            WHERE id = %s
        """, (user_id,))

        user = cursor.fetchone()


        if not user:

            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404


        # --------------------------------
        # Prevent modifying another admin
        # --------------------------------

        if user["role"] == "admin":

            return jsonify({
                "success": False,
                "message": "Admin accounts cannot be modified here."
            }), 403


        # --------------------------------
        # Update
        # --------------------------------

        cursor.execute("""
            UPDATE users
            SET account_status = %s
            WHERE id = %s
        """, (
            new_status,
            user_id
        ))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": f"User {new_status} successfully.",
            "status": new_status
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("CHANGE USER STATUS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to update user status."
        }), 500


# ==========================================================
# SOFT DELETE USER
# ==========================================================

@admin.route("/users/<int:user_id>/delete", methods=["POST"])
def delete_user(user_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # --------------------------------
        # Prevent self deletion
        # --------------------------------

        if user_id == session.get("user_id"):

            return jsonify({
                "success": False,
                "message": "You cannot delete your own admin account."
            }), 403


        # --------------------------------
        # Check User
        # --------------------------------

        cursor.execute("""
            SELECT
                id,
                username,
                role,
                account_status
            FROM users
            WHERE id = %s
        """, (user_id,))

        user = cursor.fetchone()


        if not user:

            return jsonify({
                "success": False,
                "message": "User not found."
            }), 404


        # --------------------------------
        # Protect Admin Accounts
        # --------------------------------

        if user["role"] == "admin":

            return jsonify({
                "success": False,
                "message": "Admin accounts cannot be deleted."
            }), 403


        # --------------------------------
        # Soft Delete
        # --------------------------------

        cursor.execute("""
            UPDATE users
            SET account_status = 'deleted'
            WHERE id = %s
        """, (user_id,))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": "User deleted successfully."
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("DELETE USER ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to delete user."
        }), 500

    # ==========================================================
# AI PROVIDERS
# ==========================================================

@admin.route("/providers", methods=["GET"])
def admin_providers():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                p.id,
                p.uuid,
                p.provider_name,
                p.provider_slug,
                p.website,
                p.api_base_url,
                p.description,
                p.is_active,
                p.created_at,
                p.updated_at,

                (
                    SELECT COUNT(*)
                    FROM ai_models m
                    WHERE m.provider_id = p.id
                ) AS model_count,

                (
                    SELECT COUNT(*)
                    FROM api_keys k
                    WHERE k.provider_id = p.id
                ) AS key_count,

                (
                    SELECT COUNT(*)
                    FROM api_keys k
                    WHERE k.provider_id = p.id
                    AND k.health_status = 'healthy'
                    AND k.status = 'active'
                ) AS healthy_keys

            FROM ai_providers p

            ORDER BY p.created_at DESC
        """)

        providers = cursor.fetchall()

        return render_template(
            "admin/providers.html",
            providers=providers
        )

    except Exception as e:

        print("ADMIN PROVIDERS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to load AI providers."
        }), 500


# ==========================================================
# ADD AI PROVIDER
# ==========================================================

@admin.route("/providers/add", methods=["POST"])
def add_provider():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        data = request.get_json() or {}

        provider_name = data.get(
            "provider_name",
            ""
        ).strip()

        provider_slug = data.get(
            "provider_slug",
            ""
        ).strip().lower()

        website = data.get(
            "website",
            ""
        ).strip()

        api_base_url = data.get(
            "api_base_url",
            ""
        ).strip()

        description = data.get(
            "description",
            ""
        ).strip()


        # ------------------------------------------
        # Validation
        # ------------------------------------------

        if not provider_name or not provider_slug:

            return jsonify({
                "success": False,
                "message": "Provider name and slug are required."
            }), 400


        # ------------------------------------------
        # Check duplicate name / slug
        # ------------------------------------------

        cursor.execute("""
            SELECT id
            FROM ai_providers
            WHERE provider_name = %s
               OR provider_slug = %s
        """, (
            provider_name,
            provider_slug
        ))

        if cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "Provider name or slug already exists."
            }), 409


        # ------------------------------------------
        # UUID
        # ------------------------------------------

        import uuid

        provider_uuid = str(
            uuid.uuid4()
        )


        # ------------------------------------------
        # Insert
        # ------------------------------------------

        cursor.execute("""
            INSERT INTO ai_providers
            (
                uuid,
                provider_name,
                provider_slug,
                website,
                api_base_url,
                description,
                is_active
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                1
            )
        """, (
            provider_uuid,
            provider_name,
            provider_slug,
            website or None,
            api_base_url or None,
            description or None
        ))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": "AI Provider added successfully."
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("ADD PROVIDER ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to add provider."
        }), 500


# ==========================================================
# TOGGLE AI PROVIDER
# ==========================================================

@admin.route(
    "/providers/<int:provider_id>/toggle",
    methods=["POST"]
)
def toggle_provider(provider_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                provider_name,
                is_active
            FROM ai_providers
            WHERE id = %s
        """, (provider_id,))

        provider = cursor.fetchone()


        if not provider:

            return jsonify({
                "success": False,
                "message": "Provider not found."
            }), 404


        new_status = (
            0
            if provider["is_active"]
            else 1
        )


        cursor.execute("""
            UPDATE ai_providers
            SET is_active = %s
            WHERE id = %s
        """, (
            new_status,
            provider_id
        ))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": (
                "Provider enabled."
                if new_status
                else "Provider disabled."
            ),
            "is_active": new_status
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("TOGGLE PROVIDER ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to change provider status."
        }), 500


# ==========================================================
# REMOVE AI PROVIDER
# ==========================================================

@admin.route(
    "/providers/<int:provider_id>/delete",
    methods=["POST"]
)
def delete_provider(provider_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                provider_name
            FROM ai_providers
            WHERE id = %s
        """, (provider_id,))

        provider = cursor.fetchone()


        if not provider:

            return jsonify({
                "success": False,
                "message": "Provider not found."
            }), 404


        # ------------------------------------------
        # Check Models
        # ------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM ai_models
            WHERE provider_id = %s
        """, (provider_id,))

        model_count = cursor.fetchone()["total"]


        # ------------------------------------------
        # Check API Keys
        # ------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM api_keys
            WHERE provider_id = %s
        """, (provider_id,))

        key_count = cursor.fetchone()["total"]


        # ------------------------------------------
        # Protect dependencies
        # ------------------------------------------

        if model_count > 0 or key_count > 0:

            return jsonify({
                "success": False,
                "message": (
                    "Provider cannot be removed while "
                    f"{model_count} model(s) and "
                    f"{key_count} API key(s) are attached. "
                    "Disable it instead."
                )
            }), 409


        # ------------------------------------------
        # Delete
        # ------------------------------------------

        cursor.execute("""
            DELETE FROM ai_providers
            WHERE id = %s
        """, (provider_id,))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": "Provider removed successfully."
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("DELETE PROVIDER ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to remove provider."
        }), 500

# ==========================================================
# AI MODELS
# ==========================================================

@admin.route("/models", methods=["GET"])
def admin_models():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                m.id,
                m.provider_id,
                m.uuid,
                m.model_name,
                m.model_slug,
                m.model_version,
                m.context_window,
                m.max_output_tokens,
                m.supports_images,
                m.supports_files,
                m.supports_web_search,
                m.is_default,
                m.is_active,
                m.supports_streaming,
                m.supports_function_calling,
                m.supports_json_mode,
                p.provider_name,
                p.provider_slug
            FROM ai_models m
            INNER JOIN ai_providers p
                ON m.provider_id = p.id
            ORDER BY p.provider_name ASC, m.created_at DESC
        """)

        models = cursor.fetchall()

        cursor.execute("""
            SELECT
                id,
                provider_name,
                provider_slug
            FROM ai_providers
            WHERE is_active = 1
            ORDER BY provider_name ASC
        """)

        providers = cursor.fetchall()

        return render_template(
            "admin/models.html",
            models=models,
            providers=providers
        )

    except Exception as e:

        print("ADMIN MODELS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to load AI models."
        }), 500


# ==========================================================
# ADD AI MODEL
# ==========================================================

@admin.route("/models/add", methods=["POST"])
def add_model():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        data = request.get_json() or {}

        provider_id = data.get("provider_id")
        model_name = data.get("model_name", "").strip()
        model_slug = data.get("model_slug", "").strip()
        model_version = data.get("model_version", "").strip()

        context_window = data.get("context_window")
        max_output_tokens = data.get("max_output_tokens")

        supports_images = int(bool(data.get("supports_images")))
        supports_files = int(bool(data.get("supports_files")))
        supports_web_search = int(bool(data.get("supports_web_search")))
        supports_streaming = int(bool(data.get("supports_streaming", True)))
        supports_function_calling = int(bool(data.get("supports_function_calling")))
        supports_json_mode = int(bool(data.get("supports_json_mode")))

        if not provider_id or not model_name or not model_slug:

            return jsonify({
                "success": False,
                "message": "Provider, model name and model slug are required."
            }), 400

        try:
            provider_id = int(provider_id)
        except (ValueError, TypeError):

            return jsonify({
                "success": False,
                "message": "Invalid provider."
            }), 400

        context_window = (
            int(context_window)
            if context_window not in ("", None)
            else None
        )

        max_output_tokens = (
            int(max_output_tokens)
            if max_output_tokens not in ("", None)
            else None
        )

        # --------------------------------------------------
        # Provider Check
        # --------------------------------------------------

        cursor.execute("""
            SELECT id
            FROM ai_providers
            WHERE id = %s
              AND is_active = 1
        """, (provider_id,))

        if not cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "Provider not found or disabled."
            }), 404

        # --------------------------------------------------
        # Duplicate Model
        # --------------------------------------------------

        cursor.execute("""
            SELECT id
            FROM ai_models
            WHERE provider_id = %s
              AND model_slug = %s
        """, (
            provider_id,
            model_slug
        ))

        if cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "This model already exists for the provider."
            }), 409

        # --------------------------------------------------
        # UUID
        # --------------------------------------------------

        import uuid

        model_uuid = str(uuid.uuid4())

        # --------------------------------------------------
        # Insert
        # --------------------------------------------------

        cursor.execute("""
            INSERT INTO ai_models
            (
                provider_id,
                uuid,
                model_name,
                model_slug,
                model_version,
                context_window,
                max_output_tokens,
                supports_images,
                supports_files,
                supports_web_search,
                is_default,
                is_active,
                supports_streaming,
                supports_function_calling,
                supports_json_mode
            )
            VALUES
            (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                0, 1,
                %s, %s, %s
            )
        """, (
            provider_id,
            model_uuid,
            model_name,
            model_slug,
            model_version or None,
            context_window,
            max_output_tokens,
            supports_images,
            supports_files,
            supports_web_search,
            supports_streaming,
            supports_function_calling,
            supports_json_mode
        ))

        from DB import db
        db.commit()

        return jsonify({
            "success": True,
            "message": "AI Model added successfully."
        })

    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("ADD MODEL ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to add AI model."
        }), 500


# ==========================================================
# TOGGLE MODEL
# ==========================================================

@admin.route("/models/<int:model_id>/toggle", methods=["POST"])
def toggle_model(model_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                model_name,
                is_active
            FROM ai_models
            WHERE id = %s
        """, (model_id,))

        model = cursor.fetchone()

        if not model:

            return jsonify({
                "success": False,
                "message": "Model not found."
            }), 404

        new_status = 0 if model["is_active"] else 1

        cursor.execute("""
            UPDATE ai_models
            SET is_active = %s
            WHERE id = %s
        """, (
            new_status,
            model_id
        ))

        from DB import db
        db.commit()

        return jsonify({
            "success": True,
            "message": (
                "Model enabled."
                if new_status
                else "Model disabled."
            ),
            "is_active": new_status
        })

    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("TOGGLE MODEL ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to change model status."
        }), 500


# ==========================================================
# SET DEFAULT MODEL
# ==========================================================

@admin.route("/models/<int:model_id>/default", methods=["POST"])
def set_default_model(model_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                provider_id,
                model_name,
                is_active
            FROM ai_models
            WHERE id = %s
        """, (model_id,))

        model = cursor.fetchone()

        if not model:

            return jsonify({
                "success": False,
                "message": "Model not found."
            }), 404

        if not model["is_active"]:

            return jsonify({
                "success": False,
                "message": "Enable the model before setting it as default."
            }), 400

        # Only one default model per provider
        cursor.execute("""
            UPDATE ai_models
            SET is_default = 0
            WHERE provider_id = %s
        """, (model["provider_id"],))

        cursor.execute("""
            UPDATE ai_models
            SET is_default = 1
            WHERE id = %s
        """, (model_id,))

        from DB import db
        db.commit()

        return jsonify({
            "success": True,
            "message": f"{model['model_name']} is now the default model."
        })

    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("SET DEFAULT MODEL ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to set default model."
        }), 500


# ==========================================================
# REMOVE MODEL
# ==========================================================

@admin.route("/models/<int:model_id>/delete", methods=["POST"])
def delete_model(model_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                model_name
            FROM ai_models
            WHERE id = %s
        """, (model_id,))

        model = cursor.fetchone()

        if not model:

            return jsonify({
                "success": False,
                "message": "Model not found."
            }), 404

        # --------------------------------------------------
        # Check API Keys
        # --------------------------------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM api_keys
            WHERE model_id = %s
        """, (model_id,))

        key_count = cursor.fetchone()["total"]

        if key_count > 0:

            return jsonify({
                "success": False,
                "message": (
                    f"Cannot remove this model because "
                    f"{key_count} API key(s) are attached. "
                    "Disable it instead."
                )
            }), 409

        cursor.execute("""
            DELETE FROM ai_models
            WHERE id = %s
        """, (model_id,))

        from DB import db
        db.commit()

        return jsonify({
            "success": True,
            "message": "AI Model removed successfully."
        })

    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("DELETE MODEL ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to remove model."
        }), 500

    # ==========================================================
# API KEYS
# ==========================================================

@admin.route("/api-keys", methods=["GET"])
def admin_api_keys():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # --------------------------------------------------
        # API Keys
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                k.id,
                k.uuid,
                k.provider_id,
                k.model_id,
                k.api_key,
                k.key_name,
                k.priority,
                k.status,
                k.daily_limit,
                k.used_today,
                k.total_requests,
                k.total_errors,
                k.average_response_ms,
                k.last_used,
                k.last_error,
                k.created_at,
                k.updated_at,
                k.encrypted,
                k.expires_at,
                k.health_status,

                p.provider_name,

                m.model_name

            FROM api_keys k

            INNER JOIN ai_providers p
                ON p.id = k.provider_id

            LEFT JOIN ai_models m
                ON m.id = k.model_id

            ORDER BY
                k.priority ASC,
                k.created_at DESC
        """)

        api_keys = cursor.fetchall()


        # --------------------------------------------------
        # Mask API Keys
        # --------------------------------------------------

        for key in api_keys:

            raw_key = key.get("api_key") or ""

            if len(raw_key) <= 8:

                key["masked_key"] = "••••••••"

            else:

                key["masked_key"] = (
                    "••••••••••••"
                    + raw_key[-6:]
                )


        # --------------------------------------------------
        # Providers
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                provider_name
            FROM ai_providers
            WHERE is_active = 1
            ORDER BY provider_name ASC
        """)

        providers = cursor.fetchall()


        # --------------------------------------------------
        # Models
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                provider_id,
                model_name
            FROM ai_models
            WHERE is_active = 1
            ORDER BY model_name ASC
        """)

        models = cursor.fetchall()


        return render_template(
            "admin/api_keys.html",
            api_keys=api_keys,
            providers=providers,
            models=models
        )


    except Exception as e:

        print("ADMIN API KEYS ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to load API keys."
        }), 500


# ==========================================================
# ADD API KEY
# ==========================================================

@admin.route("/api-keys/add", methods=["POST"])
def add_api_key():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        data = request.get_json() or {}


        provider_id = data.get("provider_id")
        model_id = data.get("model_id")
        api_key = data.get("api_key", "").strip()
        key_name = data.get("key_name", "").strip()

        priority = data.get("priority", 1)
        daily_limit = data.get("daily_limit", 0)
        expires_at = data.get("expires_at")


        # --------------------------------------------------
        # Validation
        # --------------------------------------------------

        if not provider_id or not api_key:

            return jsonify({
                "success": False,
                "message": "Provider and API key are required."
            }), 400


        try:

            provider_id = int(provider_id)

        except (TypeError, ValueError):

            return jsonify({
                "success": False,
                "message": "Invalid provider."
            }), 400


        if model_id:

            try:
                model_id = int(model_id)

            except (TypeError, ValueError):

                return jsonify({
                    "success": False,
                    "message": "Invalid model."
                }), 400

        else:

            model_id = None


        try:
            priority = max(1, int(priority))

        except (TypeError, ValueError):

            priority = 1


        try:
            daily_limit = max(0, int(daily_limit))

        except (TypeError, ValueError):

            daily_limit = 0


        # --------------------------------------------------
        # Provider Check
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                provider_name
            FROM ai_providers
            WHERE id = %s
              AND is_active = 1
        """, (provider_id,))

        provider = cursor.fetchone()


        if not provider:

            return jsonify({
                "success": False,
                "message": "Provider not found or disabled."
            }), 404


        # --------------------------------------------------
        # Model Check
        # --------------------------------------------------

        if model_id:

            cursor.execute("""
                SELECT
                    id,
                    provider_id
                FROM ai_models
                WHERE id = %s
                  AND is_active = 1
            """, (model_id,))

            model = cursor.fetchone()


            if not model:

                return jsonify({
                    "success": False,
                    "message": "Model not found or disabled."
                }), 404


            if model["provider_id"] != provider_id:

                return jsonify({
                    "success": False,
                    "message": "Selected model does not belong to this provider."
                }), 400


        # --------------------------------------------------
        # Duplicate Key Check
        # --------------------------------------------------

        cursor.execute("""
            SELECT id
            FROM api_keys
            WHERE api_key = %s
        """, (api_key,))

        if cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "This API key already exists."
            }), 409


        # --------------------------------------------------
        # UUID
        # --------------------------------------------------

        import uuid

        key_uuid = str(uuid.uuid4())


        # --------------------------------------------------
        # Insert
        # --------------------------------------------------

        cursor.execute("""
            INSERT INTO api_keys
            (
                uuid,
                provider_id,
                model_id,
                api_key,
                key_name,
                priority,
                status,
                daily_limit,
                used_today,
                total_requests,
                total_errors,
                average_response_ms,
                encrypted,
                expires_at,
                health_status
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'active',
                %s,
                0,
                0,
                0,
                0,
                1,
                %s,
                'healthy'
            )
        """, (
            key_uuid,
            provider_id,
            model_id,
            api_key,
            key_name or None,
            priority,
            daily_limit,
            expires_at or None
        ))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": "API key added successfully."
        })


    except Exception as e:

        try:

            from DB import db
            db.rollback()

        except Exception:
            pass


        print("ADD API KEY ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to add API key."
        }), 500


# ==========================================================
# TOGGLE API KEY
# ==========================================================

@admin.route(
    "/api-keys/<int:key_id>/toggle",
    methods=["POST"]
)
def toggle_api_key(key_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                status
            FROM api_keys
            WHERE id = %s
        """, (key_id,))

        key = cursor.fetchone()


        if not key:

            return jsonify({
                "success": False,
                "message": "API key not found."
            }), 404


        if key["status"] == "active":

            new_status = "disabled"

        else:

            new_status = "active"


        cursor.execute("""
            UPDATE api_keys
            SET
                status = %s,
                health_status =
                    CASE
                        WHEN %s = 'disabled'
                        THEN 'disabled'
                        ELSE 'healthy'
                    END
            WHERE id = %s
        """, (
            new_status,
            new_status,
            key_id
        ))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": (
                "API key enabled."
                if new_status == "active"
                else "API key disabled."
            ),
            "status": new_status
        })


    except Exception as e:

        try:

            from DB import db
            db.rollback()

        except Exception:
            pass


        print("TOGGLE API KEY ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to change API key status."
        }), 500


# ==========================================================
# DELETE API KEY
# ==========================================================

@admin.route(
    "/api-keys/<int:key_id>/delete",
    methods=["POST"]
)
def delete_api_key(key_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                key_name
            FROM api_keys
            WHERE id = %s
        """, (key_id,))

        key = cursor.fetchone()


        if not key:

            return jsonify({
                "success": False,
                "message": "API key not found."
            }), 404


        cursor.execute("""
            DELETE FROM api_keys
            WHERE id = %s
        """, (key_id,))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": "API key removed successfully."
        })


    except Exception as e:

        try:

            from DB import db
            db.rollback()

        except Exception:
            pass


        print("DELETE API KEY ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to remove API key."
        }), 500

# ==========================================================
# ROUTING RULES
# ==========================================================

@admin.route("/routing", methods=["GET"])
def admin_routing():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # --------------------------------------------------
        # Routing Rules
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                r.id,
                r.capability_id,
                r.primary_provider_id,
                r.fallback_provider_id,
                r.priority,
                r.is_active,
                r.created_at,

               c.capability_name AS capability_name,

                p.provider_name AS primary_provider_name,

                f.provider_name AS fallback_provider_name

            FROM provider_routing_rules r

            INNER JOIN ai_capabilities c
                ON c.id = r.capability_id

            INNER JOIN ai_providers p
                ON p.id = r.primary_provider_id

            LEFT JOIN ai_providers f
                ON f.id = r.fallback_provider_id

            ORDER BY
                r.priority ASC,
                r.created_at DESC
        """)

        rules = cursor.fetchall()


        # --------------------------------------------------
        # Capabilities
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                 capability_name
            FROM ai_capabilities
            ORDER BY capability_name ASC
        """)

        capabilities = cursor.fetchall()


        # --------------------------------------------------
        # Active Providers
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                provider_name
            FROM ai_providers
            WHERE is_active = 1
            ORDER BY provider_name ASC
        """)

        providers = cursor.fetchall()


        return render_template(
            "admin/routing.html",
            rules=rules,
            capabilities=capabilities,
            providers=providers
        )


    except Exception as e:

        print("ADMIN ROUTING ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to load routing rules."
        }), 500


# ==========================================================
# ADD ROUTING RULE
# ==========================================================

@admin.route("/routing/add", methods=["POST"])
def add_routing_rule():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        data = request.get_json() or {}

        capability_id = data.get("capability_id")
        primary_provider_id = data.get("primary_provider_id")
        fallback_provider_id = data.get("fallback_provider_id")
        priority = data.get("priority", 1)


        if not capability_id or not primary_provider_id:

            return jsonify({
                "success": False,
                "message": "Capability and primary provider are required."
            }), 400


        capability_id = int(capability_id)
        primary_provider_id = int(primary_provider_id)

        if fallback_provider_id:
            fallback_provider_id = int(fallback_provider_id)
        else:
            fallback_provider_id = None

        priority = max(1, int(priority))


        # --------------------------------------------------
        # Check Capability
        # --------------------------------------------------

        cursor.execute("""
            SELECT id
            FROM ai_capabilities
            WHERE id = %s
        """, (capability_id,))

        if not cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "Capability not found."
            }), 404


        # --------------------------------------------------
        # Check Primary Provider
        # --------------------------------------------------

        cursor.execute("""
            SELECT id
            FROM ai_providers
            WHERE id = %s
              AND is_active = 1
        """, (primary_provider_id,))

        if not cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "Primary provider not found or disabled."
            }), 404


        # --------------------------------------------------
        # Check Fallback Provider
        # --------------------------------------------------

        if fallback_provider_id:

            if fallback_provider_id == primary_provider_id:

                return jsonify({
                    "success": False,
                    "message": "Fallback provider cannot be the same as primary provider."
                }), 400


            cursor.execute("""
                SELECT id
                FROM ai_providers
                WHERE id = %s
                  AND is_active = 1
            """, (fallback_provider_id,))

            if not cursor.fetchone():

                return jsonify({
                    "success": False,
                    "message": "Fallback provider not found or disabled."
                }), 404


        # --------------------------------------------------
        # Duplicate Rule
        # --------------------------------------------------

        cursor.execute("""
            SELECT id
            FROM provider_routing_rules
            WHERE capability_id = %s
              AND primary_provider_id = %s
              AND is_active = 1
        """, (
            capability_id,
            primary_provider_id
        ))

        if cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "An active routing rule already exists for this capability and provider."
            }), 409


        # --------------------------------------------------
        # Insert
        # --------------------------------------------------

        cursor.execute("""
            INSERT INTO provider_routing_rules
            (
                capability_id,
                primary_provider_id,
                fallback_provider_id,
                priority,
                is_active
            )
            VALUES
            (
                %s,
                %s,
                %s,
                %s,
                1
            )
        """, (
            capability_id,
            primary_provider_id,
            fallback_provider_id,
            priority
        ))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": "Routing rule added successfully."
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("ADD ROUTING ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to add routing rule."
        }), 500


# ==========================================================
# TOGGLE ROUTING RULE
# ==========================================================

@admin.route(
    "/routing/<int:rule_id>/toggle",
    methods=["POST"]
)
def toggle_routing_rule(rule_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT
                id,
                is_active
            FROM provider_routing_rules
            WHERE id = %s
        """, (rule_id,))

        rule = cursor.fetchone()


        if not rule:

            return jsonify({
                "success": False,
                "message": "Routing rule not found."
            }), 404


        new_status = 0 if rule["is_active"] else 1


        cursor.execute("""
            UPDATE provider_routing_rules
            SET is_active = %s
            WHERE id = %s
        """, (
            new_status,
            rule_id
        ))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": (
                "Routing rule enabled."
                if new_status
                else "Routing rule disabled."
            ),
            "is_active": new_status
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("TOGGLE ROUTING ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to change routing rule."
        }), 500


# ==========================================================
# DELETE ROUTING RULE
# ==========================================================

@admin.route(
    "/routing/<int:rule_id>/delete",
    methods=["POST"]
)
def delete_routing_rule(rule_id):

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        cursor.execute("""
            SELECT id
            FROM provider_routing_rules
            WHERE id = %s
        """, (rule_id,))

        if not cursor.fetchone():

            return jsonify({
                "success": False,
                "message": "Routing rule not found."
            }), 404


        cursor.execute("""
            DELETE FROM provider_routing_rules
            WHERE id = %s
        """, (rule_id,))


        from DB import db

        db.commit()


        return jsonify({
            "success": True,
            "message": "Routing rule removed successfully."
        })


    except Exception as e:

        try:
            from DB import db
            db.rollback()
        except Exception:
            pass

        print("DELETE ROUTING ERROR:", e)

        return jsonify({
            "success": False,
            "message": "Unable to remove routing rule."
        }), 500
    # ==========================================================
# HEALTH
# ==========================================================

@admin.route("/health", methods=["GET"])
def admin_health():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # --------------------------------------------------
        # Provider health information
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                p.id,
                p.provider_name,
                p.provider_slug,

                COUNT(k.id) AS key_count,

                COALESCE(
                    SUM(
                        CASE
                            WHEN k.health_status = 'healthy'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS healthy_keys,

                COALESCE(
                    ROUND(
                        AVG(
                            NULLIF(k.average_response_ms, 0)
                        )
                    ),
                    0
                ) AS average_response_ms,

                MAX(k.last_used) AS last_used,

                CASE

                    WHEN COUNT(k.id) = 0
                        THEN 'disabled'

                    WHEN SUM(
                        CASE
                            WHEN k.health_status = 'healthy'
                            THEN 1
                            ELSE 0
                        END
                    ) > 0
                        THEN 'healthy'

                    WHEN SUM(
                        CASE
                            WHEN k.health_status = 'slow'
                            THEN 1
                            ELSE 0
                        END
                    ) > 0
                        THEN 'slow'

                    ELSE 'invalid'

                END AS health_status

            FROM ai_providers p

            LEFT JOIN api_keys k
                ON k.provider_id = p.id

            GROUP BY
                p.id,
                p.provider_name,
                p.provider_slug

            ORDER BY
                p.provider_name ASC
        """)

        providers = cursor.fetchall()


        # --------------------------------------------------
        # Summary
        # --------------------------------------------------

        summary = {

            "total": len(providers),

            "healthy": sum(
                1
                for p in providers
                if p["health_status"] == "healthy"
            ),

            "slow": sum(
                1
                for p in providers
                if p["health_status"] == "slow"
            ),

            "issues": sum(
                1
                for p in providers
                if p["health_status"]
                not in ("healthy", "slow")
            )

        }


        return render_template(
            "admin/health.html",
            providers=providers,
            summary=summary
        )


    except Exception as e:

        print(
            "ADMIN HEALTH ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to load health."
        }), 500


# ==========================================================
# HEALTH CHECK
# ==========================================================

@admin.route(
    "/health/check",
    methods=["POST"]
)
def admin_health_check():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # --------------------------------------------------
        # Basic DB health refresh
        #
        # Real provider API testing will be connected
        # after the provider/API routing layer is ready.
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                id,
                provider_id,
                status
            FROM api_keys
            WHERE status = 'active'
        """)

        keys = cursor.fetchall()


        checked = 0


        for key in keys:

            cursor.execute("""
                UPDATE api_keys

                SET
                    health_status = 'healthy',
                    updated_at = CURRENT_TIMESTAMP

                WHERE id = %s
            """, (
                key["id"],
            ))

            checked += 1


        from DB import db

        db.commit()


        return jsonify({

            "success": True,

            "message":
                f"Health check completed for {checked} API keys.",

            "checked":
                checked

        })


    except Exception as e:

        try:

            from DB import db

            db.rollback()

        except Exception:
            pass


        print(
            "HEALTH CHECK ERROR:",
            e
        )


        return jsonify({

            "success": False,

            "message":
                "Unable to perform health check."

        }), 500

# ==========================================================
# ANALYTICS
# ==========================================================

@admin.route("/analytics", methods=["GET"])
def admin_analytics():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # --------------------------------------------------
        # PERIOD
        # --------------------------------------------------

        period = request.args.get("period", 30, type=int)

        if period not in [7, 30, 90]:
            period = 30


        # --------------------------------------------------
        # SUMMARY
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                COUNT(*) AS total_requests,

                SUM(
                    CASE
                        WHEN request_status = 'success'
                        THEN 1 ELSE 0
                    END
                ) AS successful_requests,

                SUM(
                    CASE
                        WHEN request_status = 'failed'
                        THEN 1 ELSE 0
                    END
                ) AS failed_requests,

                COALESCE(
                    ROUND(AVG(response_time_ms), 0),
                    0
                ) AS avg_response_ms,

                COALESCE(
                    SUM(request_tokens),
                    0
                )
                +
                COALESCE(
                    SUM(response_tokens),
                    0
                ) AS total_tokens

            FROM api_usage_logs

            WHERE created_at >= DATE_SUB(
                NOW(),
                INTERVAL %s DAY
            )
        """, (period,))

        summary = cursor.fetchone() or {}


        total_requests = summary.get("total_requests") or 0
        successful_requests = summary.get("successful_requests") or 0
        failed_requests = summary.get("failed_requests") or 0

        if total_requests > 0:
            success_rate = round(
                (successful_requests / total_requests) * 100,
                1
            )
        else:
            success_rate = 0

        summary["total_requests"] = total_requests
        summary["successful_requests"] = successful_requests
        summary["failed_requests"] = failed_requests
        summary["avg_response_ms"] = summary.get(
            "avg_response_ms"
        ) or 0
        summary["total_tokens"] = summary.get(
            "total_tokens"
        ) or 0
        summary["success_rate"] = success_rate


        # --------------------------------------------------
        # DAILY USAGE
        # --------------------------------------------------

        cursor.execute("""
            SELECT
                DATE(created_at) AS usage_date,

                COUNT(*) AS requests,

                SUM(
                    CASE
                        WHEN request_status = 'success'
                        THEN 1 ELSE 0
                    END
                ) AS successes,

                SUM(
                    CASE
                        WHEN request_status = 'failed'
                        THEN 1 ELSE 0
                    END
                ) AS failures,

                COALESCE(
                    SUM(request_tokens),
                    0
                )
                +
                COALESCE(
                    SUM(response_tokens),
                    0
                ) AS tokens

            FROM api_usage_logs

            WHERE created_at >= DATE_SUB(
                NOW(),
                INTERVAL %s DAY
            )

            GROUP BY DATE(created_at)

            ORDER BY usage_date ASC
        """, (period,))

        daily_rows = cursor.fetchall()


        daily_usage = []

        for row in daily_rows:

            daily_usage.append({
                "date": str(row["usage_date"]),
                "requests": row["requests"] or 0,
                "successes": row["successes"] or 0,
                "failures": row["failures"] or 0,
                "tokens": row["tokens"] or 0
            })


        # --------------------------------------------------
        # PROVIDER USAGE
        # --------------------------------------------------

        cursor.execute("""
            SELECT

                COALESCE(
                    p.provider_name,
                    'Unknown'
                ) AS provider_name,

                COUNT(*) AS requests,

                SUM(
                    CASE
                        WHEN a.request_status = 'success'
                        THEN 1 ELSE 0
                    END
                ) AS successes,

                SUM(
                    CASE
                        WHEN a.request_status = 'failed'
                        THEN 1 ELSE 0
                    END
                ) AS failures,

                COALESCE(
                    ROUND(
                        AVG(a.response_time_ms),
                        0
                    ),
                    0
                ) AS avg_response_ms

            FROM api_usage_logs a

            LEFT JOIN ai_providers p
                ON a.provider_id = p.id

            WHERE a.created_at >= DATE_SUB(
                NOW(),
                INTERVAL %s DAY
            )

            GROUP BY
                a.provider_id,
                p.provider_name

            ORDER BY requests DESC
        """, (period,))

        provider_usage = cursor.fetchall()


        # --------------------------------------------------
        # MODEL USAGE
        # --------------------------------------------------

        cursor.execute("""
            SELECT

                COALESCE(
                    m.model_name,
                    'Unknown'
                ) AS model_name,

                COALESCE(
                    p.provider_name,
                    'Unknown'
                ) AS provider_name,

                COUNT(*) AS requests,

                SUM(
                    CASE
                        WHEN a.request_status = 'success'
                        THEN 1 ELSE 0
                    END
                ) AS successes,

                COALESCE(
                    ROUND(
                        AVG(a.response_time_ms),
                        0
                    ),
                    0
                ) AS avg_response_ms

            FROM api_usage_logs a

            LEFT JOIN ai_models m
                ON a.model_id = m.id

            LEFT JOIN ai_providers p
                ON a.provider_id = p.id

            WHERE a.created_at >= DATE_SUB(
                NOW(),
                INTERVAL %s DAY
            )

            GROUP BY
                a.model_id,
                m.model_name,
                p.provider_name

            ORDER BY requests DESC
        """, (period,))

        model_usage = cursor.fetchall()


        # --------------------------------------------------
        # RECENT ACTIVITY
        # --------------------------------------------------

        cursor.execute("""
            SELECT

                a.created_at,

                COALESCE(
                    p.provider_name,
                    'Unknown'
                ) AS provider_name,

                COALESCE(
                    m.model_name,
                    'Unknown'
                ) AS model_name,

                a.request_status,

                COALESCE(
                    a.response_time_ms,
                    0
                ) AS response_time_ms,

                COALESCE(
                    a.request_tokens,
                    0
                ) AS request_tokens,

                COALESCE(
                    a.response_tokens,
                    0
                ) AS response_tokens,

                a.error_message

            FROM api_usage_logs a

            LEFT JOIN ai_providers p
                ON a.provider_id = p.id

            LEFT JOIN ai_models m
                ON a.model_id = m.id

            ORDER BY
                a.created_at DESC

            LIMIT 20
        """)

        recent_activity = cursor.fetchall()


        # --------------------------------------------------
        # RENDER
        # --------------------------------------------------

        return render_template(
            "admin/analytics.html",
            summary=summary,
            daily_usage=daily_usage,
            provider_usage=provider_usage,
            model_usage=model_usage,
            recent_activity=recent_activity,
            period=period
        )


    except Exception as e:

        print("❌ Analytics Error:", e)

        return jsonify({
            "error": "Failed to load analytics",
            "details": str(e)
        }), 500

    # ==========================================================
# ACTIVITY LOGS
# ==========================================================

@admin.route("/logs", methods=["GET"])
def admin_logs():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # --------------------------------------------------
        # Filters
        # --------------------------------------------------

        search = request.args.get("search", "").strip()
        severity = request.args.get("severity", "").strip().lower()
        module = request.args.get("module", "").strip()

        page = request.args.get("page", 1, type=int)

        if page < 1:
            page = 1

        per_page = 50
        offset = (page - 1) * per_page

        # --------------------------------------------------
        # Allowed severity values
        # --------------------------------------------------

        allowed_severity = [
            "info",
            "warning",
            "error",
            "critical"
        ]

        if severity not in allowed_severity:
            severity = ""

        # --------------------------------------------------
        # Build WHERE
        # --------------------------------------------------

        conditions = []
        params = []

        if severity:
            conditions.append("al.severity = %s")
            params.append(severity)

        if module:
            conditions.append("al.module = %s")
            params.append(module)

        if search:

            conditions.append("""
                (
                    al.action LIKE %s
                    OR al.module LIKE %s
                    OR al.description LIKE %s
                    OR al.ip_address LIKE %s
                )
            """)

            search_value = f"%{search}%"

            params.extend([
                search_value,
                search_value,
                search_value,
                search_value
            ])

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # --------------------------------------------------
        # Logs
        # --------------------------------------------------

        cursor.execute(
            f"""
            SELECT
                al.id,
                al.user_id,
                al.action,
                al.module,
                al.description,
                al.ip_address,
                al.created_at,
                al.severity,

                u.username,
                u.full_name

            FROM activity_logs al

            LEFT JOIN users u
                ON al.user_id = u.id

            {where_clause}

            ORDER BY al.created_at DESC

            LIMIT %s OFFSET %s
            """,
            params + [per_page + 1, offset]
        )

        logs = cursor.fetchall()

        # --------------------------------------------------
        # Pagination
        # --------------------------------------------------

        has_next = len(logs) > per_page

        if has_next:
            logs = logs[:per_page]

        # --------------------------------------------------
        # Statistics
        # --------------------------------------------------

        cursor.execute(
    """
    SELECT
        COUNT(*) AS total,

        COALESCE(
            SUM(
                CASE
                    WHEN severity = 'info'
                    THEN 1 ELSE 0
                END
            ), 0
        ) AS info,

        COALESCE(
            SUM(
                CASE
                    WHEN severity = 'warning'
                    THEN 1 ELSE 0
                END
            ), 0
        ) AS warning,

        COALESCE(
            SUM(
                CASE
                    WHEN severity = 'error'
                    THEN 1 ELSE 0
                END
            ), 0
        ) AS error,

        COALESCE(
            SUM(
                CASE
                    WHEN severity = 'critical'
                    THEN 1 ELSE 0
                END
            ), 0
        ) AS critical

    FROM activity_logs
    """
)

        stats = cursor.fetchone()

        if not stats:
            stats = {
                "total": 0,
                "info": 0,
                "warning": 0,
                "error": 0,
                "critical": 0
            }

        # --------------------------------------------------
        # Modules for filter
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT DISTINCT module
            FROM activity_logs
            WHERE module IS NOT NULL
              AND module != ''
            ORDER BY module ASC
            """
        )

        modules = cursor.fetchall()

        # --------------------------------------------------
        # Render
        # --------------------------------------------------

        return render_template(
            "admin/logs.html",

            logs=logs,
            stats=stats,
            modules=modules,

            search=search,
            severity=severity,
            module=module,

            page=page,
            has_next=has_next
        )

    except Exception as e:

        print("❌ ADMIN LOGS ERROR:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

    # ==========================================================
# ADMIN SETTINGS
# ==========================================================

@admin.route("/settings", methods=["GET", "POST"])
def admin_settings():

    access_error = admin_required()

    if access_error:
        return access_error

    try:

        # ==================================================
        # POST ACTIONS
        # ==================================================

        if request.method == "POST":

            action = request.form.get("action", "").strip()

            # --------------------------------------------------
            # ADD SETTING
            # --------------------------------------------------

            if action == "add":

                setting_key = request.form.get(
                    "setting_key",
                    ""
                ).strip()

                setting_value = request.form.get(
                    "setting_value",
                    ""
                )

                description = request.form.get(
                    "description",
                    ""
                ).strip()

                if not setting_key:

                    return jsonify({
                        "success": False,
                        "error": "Setting key is required."
                    }), 400

                cursor.execute(
                    """
                    INSERT INTO system_settings
                    (
                        setting_key,
                        setting_value,
                        description,
                        updated_by
                    )
                    VALUES (%s, %s, %s, %s)

                    ON DUPLICATE KEY UPDATE
                        setting_value = VALUES(setting_value),
                        description = VALUES(description),
                        updated_by = VALUES(updated_by)
                    """,
                    (
                        setting_key,
                        setting_value,
                        description,
                        session.get("user_id")
                    )
                )

                return redirect("/admin/settings")

            # --------------------------------------------------
            # UPDATE SETTING
            # --------------------------------------------------

            elif action == "update":

                setting_id = request.form.get(
                    "setting_id",
                    type=int
                )

                setting_value = request.form.get(
                    "setting_value",
                    ""
                )

                if not setting_id:

                    return jsonify({
                        "success": False,
                        "error": "Invalid setting ID."
                    }), 400

                cursor.execute(
                    """
                    UPDATE system_settings

                    SET
                        setting_value = %s,
                        updated_by = %s

                    WHERE id = %s
                    """,
                    (
                        setting_value,
                        session.get("user_id"),
                        setting_id
                    )
                )

                return redirect("/admin/settings")

            # --------------------------------------------------
            # DELETE SETTING
            # --------------------------------------------------

            elif action == "delete":

                setting_id = request.form.get(
                    "setting_id",
                    type=int
                )

                if not setting_id:

                    return jsonify({
                        "success": False,
                        "error": "Invalid setting ID."
                    }), 400

                cursor.execute(
                    """
                    DELETE FROM system_settings
                    WHERE id = %s
                    """,
                    (setting_id,)
                )

                return redirect("/admin/settings")

        # ==================================================
        # GET SETTINGS
        # ==================================================

        cursor.execute(
            """
            SELECT
                id,
                setting_key,
                setting_value,
                description,
                updated_by,
                updated_at

            FROM system_settings

            ORDER BY setting_key ASC
            """
        )

        settings = cursor.fetchall()

        # ==================================================
        # RENDER
        # ==================================================

        return render_template(
            "admin/settings.html",
            settings=settings
        )

    except Exception as e:

        print("❌ ADMIN SETTINGS ERROR:", e)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500