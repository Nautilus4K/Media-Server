// For phone enter key and shits
document.addEventListener("DOMContentLoaded", () => {
    const usernameInput = document.getElementById("username_input");
    const passwordInput = document.getElementById("password_input");

    // Pressing Enter on Username shifts focus to Password
    usernameInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault(); // Prevents default form submit/behavior
            passwordInput.focus();
        }
    });

    // Pressing Enter on Password calls login()
    passwordInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            login();
        }
    });
});

if (getCookie("token") != "") {
    fetch('/check-auth', {
        headers: {
            "Token": getCookie("token")
        },
        credentials: 'omit'
    })
    .then(response => response.json())
    .then(data => {
        console.log(data)
        if (!data) {
            // FAILURE
            // YESSIR
            // right now theres no token like this, so YESSIR
            setCookie("token", "", 0);
        } else {
            window.location = "/";
        }
    }).catch(error => {
        console.error(error);
    })
}

function login() {
    var username = document.getElementById("username_input").value;
    var password = document.getElementById("password_input").value;
    console.log("Login: " + username + " : " + password);

    fetch('/login-auth', {
        headers: {
            "Username": username,
            "Password": password
        },
        credentials: 'omit'
    })
    .then(response => response.json())
    .then(data => {
        if (data["success"]) {
            setCookie("token", data["message"], 7);
            window.location = "/"
        } else {
            // document.getElementById("username_input").classList.add("error_input");
            // document.getElementById("password_input").classList.add("error_input");

            const alerter = document.getElementById("error_alert");
            alerter.style.display = 'block';
            alerter.textContent = data["message"]
        }
    }).catch(error => {
        console.error(error);
    })
}