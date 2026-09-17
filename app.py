# ==========================================================
# Soul AI 💫
# Flask Application
# Streaming + MySQL Chat System
# ==========================================================

from config import Config

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    Response,
    stream_with_context,
    url_for
)

from DB import db, cursor
from auth import auth

from api_manager import (
    generate,
    generate_stream
)

import time
import uuid

from admin.routes import admin


# ==========================================================
# Flask App
# ==========================================================

app = Flask(__name__)

app.secret_key = Config.SECRET_KEY

app.register_blueprint(auth)
app.register_blueprint(admin)


# ==========================================================
# 🧠 SOUL AI SYSTEM PROMPT
# ==========================================================

SYSTEM_PROMPT = """
You are Soul AI 💫 — smart, warm, curious, practical, and easy to talk to.

Your goal is to make every answer feel clear, useful, natural, intelligent,
and a little delightful.

VOICE
- Sound human and conversational, never robotic.
- Be confident, friendly, and intelligent.
- Start with an interesting insight or "aha" moment when it genuinely fits.
- Never force excitement, jokes, emojis, or the word "wow".
- Match the user's language and tone naturally.
- If the user uses Hinglish, reply naturally in Hinglish.
- Keep explanations simple without making them childish.

READABILITY
- Use short paragraphs.
- Use headings, bullets, and numbered steps when useful.
- Use **bold** for important points when appropriate.
- Use examples when they make something easier to understand.
- Never create unnecessary walls of text.

ADAPT TO THE QUESTION
- Simple question → give a short, direct answer.
- Complex question → break it into easy sections.
- Coding question → give clean code first, then explain briefly.
- How-to question → give clear step-by-step instructions.
- Academic question → prioritize correctness and easy understanding.
- Casual conversation → be natural and conversational.
- Technical question → be precise and practical.

PERSONALITY
- Give useful insights, analogies, or interesting facts when they add value.
- Light humor is welcome when appropriate.
- Be encouraging without sounding fake.
- Do not repeat the user's question unnecessarily.
- Do not sound like a textbook unless the situation requires it.

RESPONSE STYLE
- Do NOT force a fixed format on every answer.
- Do NOT always include a title, tip, or emoji.
- Use Markdown naturally.
- Keep responses concise unless the user asks for detail.
- Prefer useful information over unnecessary words.

ACCURACY
- Never invent facts.
- If uncertain, clearly say so.
- Never pretend to have performed an action you did not perform.

You are Soul AI 💫.

Be useful first.
Be interesting second.
Never be robotic.
"""


# ==========================================================
# Login Page
# ==========================================================

@app.route("/login-page")
def login_page():

    return render_template(
        "login.html"
    )


# ==========================================================
# Register Page
# ==========================================================

@app.route("/register-page")
def register_page():

    return render_template(
        "register.html"
    )


# ==========================================================
# Home
# ==========================================================

@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login_page"))

    return render_template("index.html")

# ==========================================================
# 💬 CHAT
# ==========================================================

@app.route(
    "/chat",
    methods=["POST"]
)
def chat():

    try:

        # --------------------------------------------------
        # Login Check
        # --------------------------------------------------

        if "user_id" not in session:

            return jsonify({
                "success": False,
                "message": "Please login first."
            }), 401


        # --------------------------------------------------
        # Request Data
        # --------------------------------------------------

        data = request.get_json() or {}

        user_message = (
            data.get("message", "")
            .strip()
        )

        session_id = data.get(
            "session_id"
        )

        # Optional explicit capability. If omitted, the Smart Routing
        # Engine automatically infers the best capability from the prompt.
        capability = data.get("capability")


        # --------------------------------------------------
        # Empty Message
        # --------------------------------------------------

        if not user_message:

            return jsonify({
                "success": False,
                "message": "Message cannot be empty."
            }), 400


        user_id = session["user_id"]


        # --------------------------------------------------
        # Create Chat Session
        # --------------------------------------------------

        if not session_id:

            chat_uuid = str(
                uuid.uuid4()
            )

            cursor.execute(
                """
                INSERT INTO chat_sessions
                (
                    uuid,
                    user_id,
                    title
                )
                VALUES
                (
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    chat_uuid,
                    user_id,
                    user_message[:50]
                )
            )

            db.commit()

            session_id = cursor.lastrowid


        else:

            # --------------------------------------------------
            # Security Check
            # --------------------------------------------------

            cursor.execute(
                """
                SELECT id
                FROM chat_sessions
                WHERE id = %s
                AND user_id = %s
                AND is_deleted = 0
                """,
                (
                    session_id,
                    user_id
                )
            )

            chat_session = (
                cursor.fetchone()
            )


            if not chat_session:

                return jsonify({
                    "success": False,
                    "message": "Invalid chat session."
                }), 403


        # --------------------------------------------------
        # Save User Message
        # --------------------------------------------------

        cursor.execute(
            """
            INSERT INTO chat_messages
            (
                session_id,
                sender,
                message,
                message_type,
                tokens_used,
                response_time_ms
            )
            VALUES
            (
                %s,
                'user',
                %s,
                'text',
                0,
                0
            )
            """,
            (
                session_id,
                user_message
            )
        )

        db.commit()


        # --------------------------------------------------
        # Prompt
        # --------------------------------------------------

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"User: {user_message}"
        )


        # --------------------------------------------------
        # Start Timer
        # --------------------------------------------------

        start_time = time.perf_counter()


        # ==================================================
        # 🚀 STREAMING RESPONSE
        # ==================================================

        def generate_response():

            full_response = ""

            try:

                for chunk in generate_stream(
                    prompt,
                    capability=capability
                ):

                    if not chunk:
                        continue

                    full_response += chunk

                    yield chunk


                # --------------------------------------------------
                # Response Complete
                # --------------------------------------------------

                response_time_ms = int(
                    (
                        time.perf_counter()
                        - start_time
                    ) * 1000
                )


                # --------------------------------------------------
                # Save Complete AI Response
                # --------------------------------------------------

                save_cursor = db.cursor()

                save_cursor.execute(
                    """
                    INSERT INTO chat_messages
                    (
                        session_id,
                        sender,
                        message,
                        message_type,
                        tokens_used,
                        response_time_ms
                    )
                    VALUES
                    (
                        %s,
                        'assistant',
                        %s,
                        'text',
                        0,
                        %s
                    )
                    """,
                    (
                        session_id,
                        full_response,
                        response_time_ms
                    )
                )


                # --------------------------------------------------
                # Update Chat Session
                # --------------------------------------------------

                save_cursor.execute(
                    """
                    UPDATE chat_sessions
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (
                        session_id,
                    )
                )


                db.commit()

                save_cursor.close()


                print(
                    f"⚡ Streaming response completed "
                    f"| {response_time_ms} ms "
                    f"| session {session_id}"
                )


            except Exception as e:

                print(
                    f"❌ STREAM RESPONSE ERROR: {e}"
                )


        # --------------------------------------------------
        # Streaming Headers
        # --------------------------------------------------

        response = Response(
            stream_with_context(
                generate_response()
            ),
            mimetype="text/plain"
        )


        response.headers[
            "X-Session-ID"
        ] = str(session_id)

        response.headers[
            "Cache-Control"
        ] = "no-cache"

        response.headers[
            "X-Accel-Buffering"
        ] = "no"


        return response


    except Exception as e:

        print(
            "❌ CHAT ERROR:",
            e
        )

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


# ==========================================================
# 💾 CHAT HISTORY
# ==========================================================

@app.route(
    "/chat/history",
    methods=["GET"]
)
def chat_history():

    try:

        # --------------------------------------------------
        # Login Check
        # --------------------------------------------------

        if "user_id" not in session:

            return jsonify({
                "success": False,
                "message": "Please login first."
            }), 401


        user_id = session["user_id"]


        # --------------------------------------------------
        # Get User Chat Sessions
        # --------------------------------------------------

        cursor.execute(
            """
            SELECT
                id,
                uuid,
                title,
                created_at,
                updated_at

            FROM chat_sessions

            WHERE user_id = %s
            AND is_deleted = 0

            ORDER BY updated_at DESC
            """,
            (
                user_id,
            )
        )

        sessions = cursor.fetchall()


        history = []


        # --------------------------------------------------
        # Get Messages
        # --------------------------------------------------

        for chat_session in sessions:

            current_session_id = (
                chat_session["id"]
            )


            cursor.execute(
                """
                SELECT
                    id,
                    sender,
                    message,
                    message_type,
                    tokens_used,
                    response_time_ms,
                    created_at

                FROM chat_messages

                WHERE session_id = %s

                ORDER BY created_at ASC
                """,
                (
                    current_session_id,
                )
            )

            messages = cursor.fetchall()


            history.append({

                "id":
                    chat_session["uuid"],

                "dbSessionId":
                    current_session_id,

                "title":
                    chat_session["title"],

                "createdAt":
                    (
                        chat_session[
                            "created_at"
                        ].isoformat()
                        if chat_session[
                            "created_at"
                        ]
                        else None
                    ),

                "updatedAt":
                    (
                        chat_session[
                            "updated_at"
                        ].isoformat()
                        if chat_session[
                            "updated_at"
                        ]
                        else None
                    ),

                "messages": [

                    {

                        "id":
                            msg["id"],

                        "sender":
                            msg["sender"],

                        "message":
                            msg["message"],

                        "message_type":
                            msg["message_type"],

                        "tokens_used":
                            msg["tokens_used"],

                        "response_time_ms":
                            msg[
                                "response_time_ms"
                            ],

                        "createdAt":
                            (
                                msg[
                                    "created_at"
                                ].isoformat()
                                if msg[
                                    "created_at"
                                ]
                                else None
                            )

                    }

                    for msg in messages

                ]

            })


        # --------------------------------------------------
        # Return History
        # --------------------------------------------------

        return jsonify({

            "success": True,

            "history":
                history

        })


    except Exception as e:

        print(
            "❌ HISTORY ERROR:",
            e
        )

        return jsonify({

            "success": False,

            "message":
                str(e)

        }), 500


# ==========================================================
# Run
# ==========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        threaded=True
    )