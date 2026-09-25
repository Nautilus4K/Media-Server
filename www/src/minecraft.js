var fetched_status = false;
var is_running = false;

const start_btn_element = document.getElementById("startbtn");
const console_output = document.getElementById("console_output")
const console_input = document.getElementById("console_input")

async function fetchSvStatus() {
    fetch("/mc-get-status")
    .then(response => response.json())
    .then(data => {
        is_running = data;
        fetched_status = true;

        // console.log(is_running);
        // The problem is that if the startSv fetch cycle is still running but this thing returns is_running = false
        // then the button will be enabled while the server isnt even started yet and is in the process of turning on
        // which causes a race condition, etc...
        if (is_running) start_btn_element.disabled = false;

        if (is_running) {
            start_btn_element.classList.add("started");
            start_btn_element.innerHTML = '<span class="nf nf-md-play_outline"></span> RUNNING';
            start_btn_element.style.width = "140px";
        } else if (!start_btn_element.disabled) {
            start_btn_element.classList.remove("started");
            start_btn_element.innerHTML = '<span class="nf nf-md-play"></span> START';
            start_btn_element.style.width = "130px";

            console_output.textContent = "";
            currentLatestLine = -1;
        }

        // Okay... so the server is up and running
        if (is_running) {
            setTimeout(fetchConsole, 250);
        } else {
            setTimeout(fetchSvStatus, 1000); // We do not fetch the console anymore, so we need to fetch the sv status by ourselves
        }
    })
}

var currentLatestLine = -1;
async function fetchConsole() {
    // console.log(currentLatestLine);
    fetch("/mc-get-console", {
        headers: {
            "Token": getCookie("token"),
            "Start": (currentLatestLine + 1)
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.length > 0) {
            data.forEach((line) => {
                if (console_output.textContent == "") console_output.textContent += line;
                else console_output.textContent += ("\n" + line);
            })
            currentLatestLine += data.length;
            console_output.scrollTo({
                'top': console_output.scrollHeight,
                'behavior': 'smooth'
            })
        }

        setTimeout(fetchSvStatus, 250);
    })
}

setTimeout(fetchSvStatus, 200);

console_input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        e.preventDefault();
        sendCmd();
    }
});
function sendCmd() {
    if (!is_running || !fetched_status) return;

    // Status is FETCHED, and the server is RUNNING
    fetch('/mc-input-command', {
        headers: {
            "Token": getCookie("token"),
            "Command": console_input.value
        }
    })

    console_input.value = "";
}


function startSv() {
    if (is_running) return;

    // console.log("Start MC Sv")
    start_btn_element.disabled = true;
    start_btn_element.innerHTML = "STARTING...";
    start_btn_element.style.width = "150px";

    fetch('/mc-kickstart', {
        headers: {
            "Token": getCookie("token")
        }
    })
}