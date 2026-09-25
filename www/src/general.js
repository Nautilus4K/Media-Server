function setCookie(cname, cvalue, exdays) {
    const d = new Date();
    d.setTime(d.getTime() + (exdays*24*60*60*1000));
    let expires = "expires="+ d.toUTCString();
    document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
}

function getCookie(cname) {
    let name = cname + "=";
    let decodedCookie = decodeURIComponent(document.cookie);
    let ca = decodedCookie.split(';');
    for(let i = 0; i <ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) == ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
        }
    }
    return "";
}

if (!(window.location.pathname === "/login" || window.location.pathname === "/status") && getCookie("token") == "") {
    window.location = "/login";
}

var usermenu_on = false;
function usermenu() {
    const usermenu_div = document.getElementById("usermenu")

    if (!usermenu_on) {
        // console.log("Open menu")
        // Open usermenu
        usermenu_on = true
        usermenu_div.classList.remove("hidden");
    } else {
        // console.log("Close menu")
        // Close usermenu
        usermenu_on = false;
        usermenu_div.classList.add("hidden");
    }
}

document.addEventListener("click", (event) => {
    // const clicked_id = event.target.id;
    // console.log("Clicked")

    if (!event.target.closest("#username, #username_btn, #usermenu")) {
        if (usermenu_on) {
            usermenu();
        }
    } 

    if (!event.target.closest("#sidebar, #favicon, #favicon_img")) {
        const sidebar = document.getElementById("sidebar");
        if (sidebar && sidebar.classList.contains("open")) {
            toggleSidebar();
        }
    }
});

function faviconClicked() {
    const mediaQuery = window.matchMedia('(min-width: 768px)');
    // console.log(`Viewport width: ${viewportWidth}px`);

    if (mediaQuery.matches) {
        // 1366x768 ig? This is a desktop
        window.location = "https://github.com/Nautilus4K/Media-Server"
    } else {
        // Not a desktop
        toggleSidebar()
    }
}

function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    sidebar.classList.toggle("open")
}
