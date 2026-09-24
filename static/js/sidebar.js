/* ==========================================================
   Soul AI Premium
   sidebar.js
   User-Aware Chat History
========================================================== */
let currentUser = null;
document.addEventListener("DOMContentLoaded", async () => {

    /* ==========================================
       Elements
    ========================================== */

    const sidebar = document.getElementById("sidebar");
    const toggleBtn = document.getElementById("toggle-btn");
    const historyBox = document.getElementById("history");
    const searchBox = document.getElementById("history-search");


    /* ==========================================
       User State
    ========================================== */

    let conversations = [];

    let activeConversation = null;

    let conversationsKey = null;
    let activeConversationKey = null;
    let hiddenHistoryKey = null;


/* ==========================================
   Get Logged-in User
========================================== */

async function initializeUser() {

    try {

        const response = await fetch("/profile");

        const data = await response.json();


        if (!data.success) {
    window.location.href = "/login-page";
    return false;
}


        /* ======================================
           Logged-in User
        ====================================== */

        currentUser = data.user;

        console.log(
            `👋 Welcome back, ${currentUser.username}`
        );


        /* ======================================
           User-specific Local Storage Keys
        ====================================== */

        conversationsKey =
            `soul_conversations_user_${currentUser.id}`;

        activeConversationKey =
            `active_conversation_user_${currentUser.id}`;

        hiddenHistoryKey =
            `soul_hidden_history_user_${currentUser.id}`;


        /* ======================================
           Update Profile UI
        ====================================== */

        updateUserUI();


        /* ======================================
           Load History From MySQL
        ====================================== */

        const historyResponse =
            await fetch("/chat/history");

        const historyData =
            await historyResponse.json();
console.log("🔥 HISTORY API DATA:", historyData);

if (historyData.success) {

    console.log("🗄️ RAW MYSQL HISTORY:", historyData.history);


    /* ======================================
       Locally Hidden Chats
       DB SE DELETE NAHI HONGE
    ====================================== */

    const hiddenChats = JSON.parse(
        localStorage.getItem(hiddenHistoryKey) || "[]"
    );


    console.log("🙈 Hidden Chats:", hiddenChats);


    /* ======================================
       Convert MySQL → Frontend Conversations
    ====================================== */

    conversations = (historyData.history || [])

        .filter(chat => {

            return !hiddenChats.includes(
                String(chat.dbSessionId)
            );

        })

        .map(chat => {

            return {

                id: chat.id,

                dbSessionId: chat.dbSessionId,

                title: chat.title,

                createdAt: chat.createdAt,

                updatedAt: chat.updatedAt,

                messages: (chat.messages || []).map(msg => ({

                    role: msg.sender,

                    text: msg.message,

                    time: msg.createdAt

                }))

            };

        });


    console.log(
        "✅ FINAL SIDEBAR HISTORY:",
        conversations
    );

    console.log(
        `🗄️ ${conversations.length} chats ready for sidebar`
    );

} else {

            conversations = [];

            console.log(
                "❌ History Error:",
                historyData.message
            );

        }


        /* ==========================================
   Restore Active Conversation
========================================== */

activeConversation =
    localStorage.getItem(
        activeConversationKey
    ) || null;


/* ==========================================
   Validate Active Conversation
========================================== */

if (
    activeConversation &&
    !conversations.some(
        chat => chat.id === activeConversation
    )
) {

    console.log(
        "🧹 Removing old invalid active conversation:",
        activeConversation
    );

    activeConversation = null;

    localStorage.removeItem(
        activeConversationKey
    );
}

        /* ======================================
           Render Sidebar
        ====================================== */

        renderHistory();


        return true;


   } catch (error) {
    console.error(
        "❌ User initialization error:",
        error
    );

    window.location.href = "/login-page";
    return false;
}
}



    /* ==========================================
       Save Data
    ========================================== */

    function saveData() {

        if (!currentUser) return;


        localStorage.setItem(
            conversationsKey,
            JSON.stringify(conversations)
        );


        localStorage.setItem(
            activeConversationKey,
            activeConversation || ""
        );
    }


    /* ==========================================
       Generate ID
    ========================================== */

    function generateID() {

        return (
            "chat_" +
            Date.now() +
            "_" +
            Math.random()
                .toString(36)
                .substring(2, 7)
        );
    }


    /* ==========================================
       Get Conversation
    ========================================== */

    function getConversation(id) {

        return conversations.find(
            chat => chat.id === id
        );
    }


    /* ==========================================
       Sidebar Toggle
    ========================================== */

    function toggleSidebar() {

        if (window.innerWidth <= 900) {

            sidebar.classList.toggle("active");

        } else {

            sidebar.classList.toggle("closed");

        }
    }


    if (toggleBtn) {

        toggleBtn.onclick = toggleSidebar;

    }


    /* ==========================================
       Create Conversation
    ========================================== */

    window.createHistory = function (message) {

        if (!currentUser) {

            console.log("⚠️ Login required");

            return;

        }


        if (activeConversation) return;


        let title = message.trim();


        if (title.length > 40) {

            title =
                title.substring(0, 40) + "...";

        }

const chat = {

    id: generateID(),

    dbSessionId: null,

    title: title,

    createdAt:
        new Date().toISOString(),

    updatedAt:
        new Date().toISOString(),

    messages: []

};


        conversations.unshift(chat);

        activeConversation = chat.id;


        saveData();

        renderHistory();
    };


    /* ==========================================
       Add Message
    ========================================== */

    window.addMessageToConversation =
        function (role, text) {

            if (!currentUser) return;

            if (!activeConversation) return;


            const chat =
                getConversation(activeConversation);


            if (!chat) return;


            chat.messages.push({

                role: role,

                text: text,

                time:
                    new Date().toLocaleTimeString()

            });


            chat.updatedAt =
                new Date().toISOString();


            saveData();
        };


/* ==========================================
   Render History
========================================== */

function renderHistory() {

    if (!historyBox) {

        console.error(
            "❌ History container not found!"
        );

        return;
    }


    console.log(
        "🎨 Rendering sidebar history:",
        conversations
    );


    /* ======================================
       Clear History
    ====================================== */

    historyBox.innerHTML = "";


    /* ======================================
       Empty State
    ====================================== */

    if (!conversations.length) {

        historyBox.innerHTML = `

            <div class="history-empty">

                No conversations yet

            </div>

        `;

        return;
    }


    /* ======================================
       Render Conversations
    ====================================== */

    conversations.forEach(chat => {

        const item =
            document.createElement("div");


        item.className =
            activeConversation === chat.id
                ? "chat-item active-chat"
                : "chat-item";


        item.innerHTML = `

            <span class="chat-title"></span>

            <button
                type="button"
                class="delete-chat"
                title="Remove from history">

                ✖

            </button>

        `;


        /* ==================================
           Chat Title
        ================================== */

        const titleElement =
            item.querySelector(".chat-title");


        titleElement.textContent =
            chat.title || "New Chat";


        /* ==================================
           Select Chat
        ================================== */

        titleElement.onclick = () => {

            selectConversation(chat.id);

        };


        /* ==================================
           Delete Chat
           Sidebar Only
        ================================== */

        item.querySelector(
            ".delete-chat"
        ).onclick = (e) => {

            e.stopPropagation();


            const hiddenChats =
                JSON.parse(
                    localStorage.getItem(
                        hiddenHistoryKey
                    ) || "[]"
                );


            /* ------------------------------
               Save DB ID as hidden
            ------------------------------ */

            if (chat.dbSessionId) {

                const dbId =
                    String(chat.dbSessionId);


                if (
                    !hiddenChats.includes(dbId)
                ) {

                    hiddenChats.push(dbId);

                }

            }


            localStorage.setItem(

                hiddenHistoryKey,

                JSON.stringify(hiddenChats)

            );


            /* ------------------------------
               Remove from sidebar
            ------------------------------ */

            conversations =
                conversations.filter(
                    c => c.id !== chat.id
                );


            /* ------------------------------
               Clear active chat
            ------------------------------ */

            if (
                activeConversation ===
                chat.id
            ) {

                activeConversation = null;

                localStorage.removeItem(
                    activeConversationKey
                );

            }


            saveData();

            renderHistory();


            if (
                typeof clearChat ===
                "function"
            ) {

                clearChat();

            }


            console.log(
                "🗑️ Chat removed from sidebar only"
            );

            console.log(
                "💾 MySQL chat preserved:",
                chat.dbSessionId
            );

        };


        /* ==================================
           Add To Sidebar
        ================================== */

        historyBox.appendChild(item);

    });


    console.log(
        `✅ ${conversations.length} chats rendered in sidebar`
    );

}
    /* ==========================================
       Select Conversation
    ========================================== */

    function selectConversation(id) {

        activeConversation = id;

        saveData();

        renderHistory();


        const conversation =
            getConversation(id);


        if (!conversation) return;


        const chatBox =
            document.getElementById("chat");


        if (!chatBox) return;


        chatBox.innerHTML = "";


        conversation.messages.forEach(
            msg => {

                if (msg.role === "user") {

                    chatBox.insertAdjacentHTML(

                        "beforeend",

                        `
                        <p class="history-user-message">
                            ${msg.text}
                        </p>
                        `

                    );

                }

                else {

                    chatBox.insertAdjacentHTML(

                        "beforeend",

                        `
                        <div class="bot fade-in">

                            <div class="message">

                                ${
                                    marked.parse(
                                        msg.text
                                    )
                                }

                            </div>

                        </div>
                        `

                    );

                }

            }
        );


        if (
            typeof scrollChat ===
            "function"
        ) {

            scrollChat();

        }
    }
    window.getActiveConversationId = function () {

    return activeConversation;

};
/* ==========================================
   MySQL Session Mapping
========================================== */

window.getDatabaseSessionId = function (conversationId) {

    const conversation =
        getConversation(conversationId);

    if (!conversation) {

        return null;

    }

    return conversation.dbSessionId || null;

};


window.setDatabaseSessionId = function (
    conversationId,
    dbSessionId
) {

    const conversation =
        getConversation(conversationId);


    if (!conversation) {

        console.warn(
            "⚠️ Conversation not found:",
            conversationId
        );

        return;

    }


    conversation.dbSessionId =
        dbSessionId;


    console.log(
        "🔗 DB Session mapped:",
        conversation.id,
        "→",
        dbSessionId
    );


    saveData();

};


    /* ==========================================
       Rename Chat
    ========================================== */

    if (historyBox) {

        historyBox.addEventListener(
            "dblclick",
            e => {

                const item =
                    e.target.closest(
                        ".chat-item"
                    );


                if (!item) return;


                const title =
                    item.querySelector(
                        ".chat-title"
                    ).innerText;


                const chat =
                    conversations.find(
                        c => c.title === title
                    );


                if (!chat) return;


                const newTitle =
                    prompt(
                        "Rename Chat",
                        chat.title
                    );


                if (!newTitle) return;


                chat.title =
                    newTitle.trim();


                saveData();

                renderHistory();

            }
        );

    }


    /* ==========================================
       Search
    ========================================== */

    if (searchBox) {

        searchBox.oninput = function () {

            const keyword =
                this.value.toLowerCase();


            document
                .querySelectorAll(".chat-item")
                .forEach(item => {

                    const title =
                        item.innerText
                            .toLowerCase();


                    item.style.display =
                        title.includes(keyword)
                            ? "flex"
                            : "none";

                });

        };
    }


    /* ==========================================
       New Chat
    ========================================== */

    window.clearChat = function () {

        activeConversation = null;

        saveData();


        const chat =
            document.getElementById("chat");


        if (!chat) return;


        chat.innerHTML = `

            <div
                class="welcome-screen"
                id="welcome"
            >

                <div class="welcome-icon">
                    ✨
                </div>

                <h2>
                    How can I help you today?
                </h2>

                <p>
                    Ask me anything.
                    I'm here to help!
                </p>

            </div>

        `;


        renderHistory();
    };


    /* ==========================================
       Clear All History
    ========================================== */

    window.clearAllHistory = function () {

        if (
            !confirm(
                "Delete all conversations?"
            )
        ) {

            return;

        }


        conversations = [];

        activeConversation = null;


        saveData();

        renderHistory();

        clearChat();

    };


    /* ==========================================
       Export History
    ========================================== */

    window.exportHistory = function () {

        const blob = new Blob(

            [
                JSON.stringify(
                    conversations,
                    null,
                    2
                )
            ],

            {
                type:
                    "application/json"
            }

        );


        const url =
            URL.createObjectURL(blob);


        const a =
            document.createElement("a");


        a.href = url;

        a.download =
            "SoulAI-History.json";


        a.click();


        URL.revokeObjectURL(url);

    };


    /* ==========================================
       Mobile Auto Close
    ========================================== */

    document.addEventListener(
        "click",
        function (e) {

            if (window.innerWidth > 900)
                return;


            if (
                !sidebar.contains(e.target) &&
                !toggleBtn.contains(e.target)
            ) {

                sidebar.classList.remove(
                    "active"
                );

            }

        }
    );


    /* ==========================================
       ESC Close
    ========================================== */

    document.addEventListener(
        "keydown",
        function (e) {

            if (e.key === "Escape") {

                sidebar.classList.remove(
                    "active"
                );

            }

        }
    );


    /* ==========================================
       START
    ========================================== */

    await initializeUser();

});

/* ==========================================
   Update User UI
========================================== */

function updateUserUI() {

    const usernameElement =
        document.getElementById("username");

    const emailElement =
        document.getElementById("user-email");

    const loginButton =
        document.getElementById("login-btn");



    // Logged-in user
    const username =
        currentUser.username || "User";

    const email =
        currentUser.email || "";


    if (usernameElement) {

        usernameElement.textContent =
            username;

    }


    if (emailElement) {

        emailElement.textContent =
            email;

    }


if (loginButton) {

    loginButton.textContent = "Logout";

    loginButton.classList.add("logged-in");

    loginButton.onclick = async function () {

        try {
            await window.logout();
        } catch (error) {
            console.error("❌ Logout Error:", error);
        }

    };

}

    console.log(
        `👤 User UI updated: ${username}`
    );
}
