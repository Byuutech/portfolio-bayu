(() => {
    const list = document.querySelector("#operator-conversations");
    const messages = document.querySelector("#operator-messages");
    const empty = document.querySelector("#operator-empty");
    const form = document.querySelector("#operator-chat-form");
    const input = document.querySelector("#operator-chat-input");
    const error = document.querySelector("#operator-chat-error");

    if (!list || !messages || !empty || !form || !input || !error) {
        return;
    }

    let socket;
    let selectedConversation = null;

    function appendMessage(message) {
        const item = document.createElement("article");
        item.className = `live-chat-message ${message.sender === "operator" ? "is-visitor" : "is-operator"}`;
        const body = document.createElement("p");
        body.textContent = message.body;
        const time = document.createElement("time");
        time.dateTime = message.sent_at;
        time.textContent = new Date(message.sent_at).toLocaleString("id-ID", {
            dateStyle: "short",
            timeStyle: "short"
        });
        item.append(body, time);
        messages.append(item);
        messages.scrollTop = messages.scrollHeight;
    }

    async function loadConversations() {
        const response = await fetch("/operator/conversations");
        if (!response.ok) {
            throw new Error("Daftar percakapan gagal dimuat.");
        }
        const data = await response.json();
        list.replaceChildren();
        data.conversations.forEach((conversation) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "operator-conversation";
            button.classList.toggle("is-selected", conversation.id === selectedConversation);
            const title = document.createElement("strong");
            title.textContent = `Pengunjung ${conversation.id.slice(0, 8)}`;
            const preview = document.createElement("span");
            preview.textContent = conversation.last_message || "Belum ada pesan";
            button.append(title, preview);
            button.addEventListener("click", () => selectConversation(conversation.id));
            list.append(button);
        });
    }

    function selectConversation(conversationId) {
        selectedConversation = conversationId;
        messages.replaceChildren();
        empty.hidden = true;
        input.disabled = false;
        form.querySelector("button").disabled = false;
        error.textContent = "";
        socket.emit("chat:select", { conversation_id: conversationId });
        loadConversations().catch((requestError) => {
            error.textContent = requestError.message;
        });
    }

    if (typeof window.io !== "function") {
        error.textContent = "Koneksi live chat tidak tersedia. Muat ulang halaman untuk mencoba lagi.";
        return;
    }
    socket = window.io();
    socket.on("connect_error", () => {
        error.textContent = "Tidak dapat terhubung ke live chat. Silakan muat ulang halaman.";
    });
    socket.on("chat:error", (data) => {
        error.textContent = data.message;
    });
    socket.on("chat:history", (data) => {
        if (data.conversation_id !== selectedConversation) {
            return;
        }
        messages.replaceChildren();
        data.messages.forEach(appendMessage);
    });
    socket.on("chat:message", (message) => {
        if (message.conversation_id === selectedConversation) {
            appendMessage(message);
        }
        loadConversations().catch((requestError) => {
            error.textContent = requestError.message;
        });
    });
    socket.on("chat:conversation", (message) => {
        if (message.conversation_id !== selectedConversation) {
            loadConversations().catch((requestError) => {
                error.textContent = requestError.message;
            });
        }
    });

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const body = input.value.trim();
        if (!body || !selectedConversation || !socket.connected) {
            return;
        }
        socket.emit("chat:send", {
            conversation_id: selectedConversation,
            body
        });
        input.value = "";
    });

    loadConversations().catch((requestError) => {
        error.textContent = requestError.message;
    });
})();
