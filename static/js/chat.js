/* ==========================================================
   SOUL AI 💫
   chat.js — STREAMING VERSION
   ========================================================== */

let isGenerating = false;


/* ==========================================================
   SCROLL
========================================================== */

function scrollChat() {

    const chat = document.getElementById("chat");

    if (!chat) return;

    chat.scrollTo({
        top: chat.scrollHeight,
        behavior: "smooth"
    });
}


/* ==========================================================
   WELCOME
========================================================== */

function hideWelcome() {

    const welcome = document.getElementById("welcome");

    if (welcome) {
        welcome.remove();
    }
}


/* ==========================================================
   TIME
========================================================== */

function getTime() {

    return new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit"
    });
}


/* ==========================================================
   ADD USER MESSAGE SAFELY
========================================================== */

function addUserMessage(message) {

    const chat = document.getElementById("chat");

    if (!chat) return;

    const wrapper = document.createElement("div");

    wrapper.className = "user fade-in";

    const paragraph = document.createElement("p");

    paragraph.textContent = message;

    wrapper.appendChild(paragraph);

    chat.appendChild(wrapper);
}


/* ==========================================================
   ADD TYPING INDICATOR
========================================================== */

function showTyping() {

    const chat = document.getElementById("chat");

    if (!chat) return;

    const typing = document.createElement("div");

    typing.className = "bot fade-in";
    typing.id = "typing";

    typing.innerHTML = `
        <div class="typing-box">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;

    chat.appendChild(typing);

    scrollChat();
}


/* ==========================================================
   REMOVE TYPING
========================================================== */

function removeTyping() {

    const typing = document.getElementById("typing");

    if (typing) {
        typing.remove();
    }
}


/* ==========================================================
   CREATE BOT MESSAGE
========================================================== */

function createBotMessage() {

    const chat = document.getElementById("chat");

    if (!chat) return null;

    const wrapper = document.createElement("div");

    wrapper.className = "bot fade-in";

    const message = document.createElement("div");

    message.className = "message";

    wrapper.appendChild(message);

    chat.appendChild(wrapper);

    return message;
}


/* ==========================================================
   UPDATE BOT MESSAGE
========================================================== */

function updateBotMessage(element, text) {

    if (!element) return;

    try {

        if (typeof marked !== "undefined") {

            element.innerHTML = marked.parse(text);

        } else {

            element.textContent = text;

        }

    } catch (error) {

        console.warn("Markdown rendering error:", error);

        element.textContent = text;
    }

    scrollChat();
}


/* ==========================================================
   ERROR MESSAGE
========================================================== */

function showError(message) {

    const chat = document.getElementById("chat");

    if (!chat) return;

    const wrapper = document.createElement("div");

    wrapper.className = "bot fade-in";

    const box = document.createElement("div");

    box.className = "message";

    const title = document.createElement("strong");

    title.textContent = "⚠️ Connection Error";

    const paragraph = document.createElement("p");

    paragraph.textContent =
        message || "Unable to connect to Soul AI.";

    const time = document.createElement("div");

    time.className = "message-time";

    time.textContent = getTime();

    box.appendChild(title);
    box.appendChild(paragraph);
    box.appendChild(time);

    wrapper.appendChild(box);

    chat.appendChild(wrapper);

    scrollChat();
}


/* ==========================================================
   SERVER ERROR HANDLER
========================================================== */

async function getServerError(response) {

    try {

        const text = await response.text();

        try {

            const data = JSON.parse(text);

            return (
                data.message ||
                data.error ||
                "Server error occurred."
            );

        } catch {

            return text || "Server error occurred.";
        }

    } catch {

        return "Unable to read server response.";
    }
}


/* ==========================================================
   SEND MESSAGE — STREAMING
========================================================== */

async function sendMessage() {

    if (isGenerating) return;

    const input = document.getElementById("msg");
    const chat = document.getElementById("chat");

    if (!input || !chat) return;

    const message = input.value.trim();

    if (!message) return;


    /* ------------------------------------------------------
       LOCK GENERATION
    ------------------------------------------------------ */

    isGenerating = true;


    /* ------------------------------------------------------
       UI
    ------------------------------------------------------ */

    hideWelcome();


    /* ------------------------------------------------------
       CREATE FRONTEND HISTORY
    ------------------------------------------------------ */

    if (!window.getActiveConversationId()) {

        createHistory(message);
    }


    /* ------------------------------------------------------
       SAVE USER MESSAGE LOCALLY
    ------------------------------------------------------ */

    addMessageToConversation("user", message);

    addUserMessage(message);


    /* ------------------------------------------------------
       CLEAR INPUT
    ------------------------------------------------------ */

    input.value = "";

    input.style.height = "auto";


    scrollChat();


    /* ------------------------------------------------------
       TYPING
    ------------------------------------------------------ */

    showTyping();


    try {

        /* ==================================================
           GET ACTIVE CONVERSATION
        ================================================== */

        const activeConversationId =
            window.getActiveConversationId
                ? window.getActiveConversationId()
                : null;


        /* ==================================================
           GET DATABASE SESSION
        ================================================== */

        let dbSessionId = null;

        if (window.getDatabaseSessionId) {

            dbSessionId =
                window.getDatabaseSessionId(
                    activeConversationId
                );
        }


        /* ==================================================
           REQUEST
        ================================================== */

        const response = await fetch("/chat", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({

                message: message,

                session_id: dbSessionId
            })
        });


        /* ==================================================
           SERVER ERROR
        ================================================== */

        if (!response.ok) {

            const errorMessage =
                await getServerError(response);

            throw new Error(errorMessage);
        }


        /* ==================================================
           SESSION ID
        ================================================== */

        const newSessionId =
            response.headers.get("X-Session-ID");


        if (
            newSessionId &&
            window.setDatabaseSessionId
        ) {

            window.setDatabaseSessionId(
                activeConversationId,
                newSessionId
            );
        }


        /* ==================================================
           REMOVE TYPING
        ================================================== */

        removeTyping();


        /* ==================================================
           STREAM CHECK
        ================================================== */

        if (!response.body) {

            throw new Error(
                "Streaming is not supported by this browser."
            );
        }


        /* ==================================================
           CREATE BOT MESSAGE
        ================================================== */

        const botMessage =
            createBotMessage();


        if (!botMessage) {

            throw new Error(
                "Unable to create chat message."
            );
        }


        /* ==================================================
           STREAM READER
        ================================================== */

        const reader =
            response.body.getReader();


        const decoder =
            new TextDecoder("utf-8");


        let fullResponse = "";


        /* ==================================================
           READ STREAM
        ================================================== */

        while (true) {

            const {
                value,
                done
            } = await reader.read();


            if (done) break;


            const chunk =
                decoder.decode(
                    value,
                    {
                        stream: true
                    }
                );


            if (!chunk) continue;


            fullResponse += chunk;


            /* ----------------------------------------------
               LIVE UPDATE
            ---------------------------------------------- */

            updateBotMessage(
                botMessage,
                fullResponse
            );
        }


        /* ==================================================
           FINAL DECODER FLUSH
        ================================================== */

        const finalChunk =
            decoder.decode();


        if (finalChunk) {

            fullResponse += finalChunk;

            updateBotMessage(
                botMessage,
                fullResponse
            );
        }


        /* ==================================================
           SAVE ASSISTANT MESSAGE
        ================================================== */

        if (fullResponse.trim()) {

            addMessageToConversation(
                "assistant",
                fullResponse
            );
        }


        /* ==================================================
           FINAL SCROLL
        ================================================== */

        scrollChat();


    } catch (error) {

        console.error(
            "❌ Soul AI Chat Error:",
            error
        );


        removeTyping();


        showError(
            error.message ||
            "Unable to connect to Soul AI."
        );


    } finally {

        /* ==================================================
           UNLOCK
        ================================================== */

        isGenerating = false;

        scrollChat();
    }
}


/* ==========================================================
   ENTER KEY
========================================================== */

function handleEnter(event) {

    if (
        event.key === "Enter" &&
        !event.shiftKey
    ) {

        event.preventDefault();

        sendMessage();
    }
}


/* ==========================================================
   AUTO RESIZE
========================================================== */

function autoResize(textarea) {

    if (!textarea) return;

    textarea.style.height = "auto";

    textarea.style.height =
        textarea.scrollHeight + "px";
}


/* ==========================================================
   INPUT AUTO RESIZE
========================================================== */

function initializeInput() {

    const input =
        document.getElementById("msg");

    if (!input) return;

    input.addEventListener(
        "input",
        function () {

            autoResize(this);
        }
    );
}


/* ==========================================================
   QUICK PROMPT
========================================================== */

function quickPrompt(text) {

    const input =
        document.getElementById("msg");

    if (!input) return;

    input.value = text;

    autoResize(input);

    input.focus();
}


/* ==========================================================
   INITIALIZE
========================================================== */

window.addEventListener(
    "load",
    function () {

        initializeInput();

        const input =
            document.getElementById("msg");

        if (input) {

            input.focus();
        }
    }
);


/* ==========================================================
   GLOBAL FUNCTIONS
========================================================== */

window.sendMessage = sendMessage;

window.scrollChat = scrollChat;

window.quickPrompt = quickPrompt;

window.handleEnter = handleEnter;

window.autoResize = autoResize;