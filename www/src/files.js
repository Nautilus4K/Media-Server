const elements = document.querySelectorAll(".folder_btn");

console.log(elements.length); // if this is 0, that's your answer
elements.forEach((element) => {
    const randomDelay = Math.random() * 0.3;
    
    // Explicitly define the sub-properties so they do not overwrite each other
    element.style.animationName = "folderEntryAnim";
    element.style.animationDuration = "0.5s";
    element.style.animationTimingFunction = "var(--ease_custom)";
    element.style.animationFillMode = "forwards";
    element.style.animationDelay = `${randomDelay}s`;
});

const path_bar = document.getElementById("path_bar");

path_bar.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        godir();
    }
})

path_bar.focus();
path_bar.setSelectionRange(path_bar.value.length, path_bar.value.length);

function godir() {
    let target_relative_path = path_bar.value;
    if (target_relative_path[0] != '/') target_relative_path = '/' + target_relative_path;

    window.location = "/files" + target_relative_path;
}