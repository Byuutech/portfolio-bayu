(() => {
    const toggle = document.querySelector("#live-chat-toggle");
    const panel = document.querySelector("#live-chat-panel");
    const close = document.querySelector("#live-chat-close");
    const form = document.querySelector("#live-chat-form");
    const input = document.querySelector("#live-chat-input");
    const messages = document.querySelector("#live-chat-messages");
    const error = document.querySelector("#live-chat-error");

    if (!toggle || !panel || !close || !form || !input || !messages || !error) {
        return;
    }

    let socket;
    let loadedHistory = false;

    function appendMessage(message) {
        const item = document.createElement("article");
        item.className = `live-chat-message ${message.sender === "visitor" ? "is-visitor" : "is-operator"}`;
        const body = document.createElement("p");
        body.textContent = message.body;
        const time = document.createElement("time");
        time.dateTime = message.sent_at;
        time.textContent = new Date(message.sent_at).toLocaleTimeString("id-ID", {
            hour: "2-digit",
            minute: "2-digit"
        });
        item.append(body, time);
        messages.append(item);
        messages.scrollTop = messages.scrollHeight;
    }

    async function loadHistory() {
        try {
            const response = await fetch("/chat/history");
            if (!response.ok) {
                throw new Error("Riwayat chat gagal dimuat.");
            }
            const data = await response.json();
            data.messages.forEach(appendMessage);
            loadedHistory = true;
        } catch (requestError) {
            error.textContent = requestError.message;
        }
    }

    function connect() {
        if (socket) {
            return;
        }
        if (typeof window.io !== "function") {
            error.textContent = "Koneksi live chat tidak tersedia. Muat ulang halaman untuk mencoba lagi.";
            return;
        }
        socket = window.io();
        socket.on("chat:message", appendMessage);
        socket.on("chat:error", (data) => {
            error.textContent = data.message;
        });
        socket.on("connect_error", () => {
            error.textContent = "Tidak dapat terhubung ke live chat. Silakan coba lagi.";
        });
        socket.on("connect", () => {
            error.textContent = "";
        });
    }

    function setOpen(open) {
        toggle.setAttribute("aria-expanded", String(open));
        panel.setAttribute("aria-hidden", String(!open));
        panel.classList.toggle("is-open", open);
        if (open) {
            connect();
            if (!loadedHistory) {
                loadHistory();
            }
            input.focus();
        } else {
            toggle.focus();
        }
    }

    toggle.addEventListener("click", () => setOpen(panel.getAttribute("aria-hidden") === "true"));
    close.addEventListener("click", () => setOpen(false));

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        const body = input.value.trim();
        if (!body || !socket || !socket.connected) {
            if (body) {
                error.textContent = "Sedang menghubungkan ke chat. Coba kirim kembali sebentar lagi.";
            }
            return;
        }
        error.textContent = "";
        socket.emit("chat:send", { body });
        input.value = "";
    });
})();
