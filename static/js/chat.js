async function loginChat() {
    const name = document.getElementById("chatUser").value;

    await fetch("/login", {
        method: "PUT",
        headers: { "Content-Type": "text/plain" },
        body: name
    });

    alert("Logged in to chat server.");
}

async function submitInfo() {
    const ip = document.getElementById("peerIP").value;
    const port = document.getElementById("peerPort").value;

    await fetch("/submit-info", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip, port })
    });

    alert("Peer info submitted.");
}

async function getList() {
    const resp = await fetch("/get-list");
    const peers = await resp.json();

    const list = document.getElementById("peerList");
    list.innerHTML = "";

    peers.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.port;
        opt.textContent = `${p.ip}:${p.port}`;
        list.appendChild(opt);
    });
}

async function broadcast() {
    const msg = document.getElementById("msgInput").value;

    await fetch("/broadcast-peer", {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: msg
    });

    addMessage("You (broadcast): " + msg);
}

async function sendPeer() {
    const msg = document.getElementById("msgInput").value;
    const port = document.getElementById("peerList").value;

    await fetch(`/send-peer?port=${port}`, {
        method: "POST",
        headers: { "Content-Type": "text/plain" },
        body: msg
    });

    addMessage(`You → ${port}: ${msg}`);
}

function addMessage(text) {
    const box = document.getElementById("messages");
    const p = document.createElement("p");
    p.textContent = text;
    box.appendChild(p);
    box.scrollTop = box.scrollHeight;
}
