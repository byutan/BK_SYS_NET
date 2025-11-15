async function login() {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    const body = `username=${username}&password=${password}`;

    const resp = await fetch("/login", {
        method: "POST",
        headers: {
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body: body
    });

    if (resp.status === 200) {
        window.location.href = "/index.html";
    } else {
        document.getElementById("error").innerText = "Invalid username or password!";
    }
}