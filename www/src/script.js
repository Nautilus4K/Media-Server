const musicBlock = document.getElementById("music_block")
const moviesBlock = document.getElementById("movies_block")

const musicTable = document.getElementById("music_list")

var musicData = {}

function formatTime(sec) {
    sec = Math.floor(sec);

    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;

    if (h > 0) {
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    } else {
        return `${m}:${s.toString().padStart(2, '0')}`;
    }
}

function switchMedia(type) {
    if (type === 'movies') {
        // Movies
        console.log("SwitchTo: Movies")

        // Hide the music thingy
        musicBlock.style.display = 'none';

        // Show the movies one
        moviesBlock.style.display = 'flex';
    } else if (type == 'music') {
        // Music
        console.log("SwitchTo: Music")

        // Do the opposite of the first logics above
        moviesBlock.style.display = 'none';
        musicBlock.style.display = 'flex';

        // Refresh the whole thing by clearing the ?
        // Guaranteed to be safe here
        musicTable.innerHTML = "<tr><th class=\"title_col\">Title</th><th class=\"artist_col\">Artist</th><th class=\"duration_col\">Duration</th></tr><tr><td>Loading...</td></tr>";

        fetch("/api/music_list", {
            method: "GET",
        }).then(response => response.json())
        .then((json) => {
            // Collect all music data first
            const musicDataPromises = json["result"].map(id => 
                fetch("/api/get_music_data/" + id, {
                    method: 'GET'
                })
                .then(response => response.json())
                .then(json => ({
                    id: id,
                    data: json["result"]
                }))
                .catch(error => {
                    console.error("Error fetching music data for id", id, ":", error);
                    return null;
                })
            );

            // console.log(musicDataPromises);
            musicTable.innerHTML = "<tr><th class=\"title_col\">Title</th><th class=\"artist_col\">Artist</th><th class=\"duration_col\">Duration</th></tr>";
            // Wait for all fetches to complete
            Promise.all(musicDataPromises).then(musicDataArray => {
                // Filter out any failed fetches
                const validData = musicDataArray.filter(item => item !== null);
                
                // Sort alphabetically by title (A to Z)
                validData.sort((a, b) => 
                    a.data.title.localeCompare(b.data.title)
                );
                
                // Now render the sorted data
                validData.forEach(item => {
                    // console.log(item.id, item.data);
                    musicData[item.id] = item.data;
                    
                    let musicRow = document.createElement("tr");
                    let titleCell = document.createElement("td");
                    let artistCell = document.createElement("td");
                    let durationCell = document.createElement("td");

                    let songSelectBtn = document.createElement('button');
                    songSelectBtn.innerHTML = '<img src="/src/play.svg" class="play">';
                    songSelectBtn.className = "play_container";
                    songSelectBtn.onclick = () => {
                        requestMusic(item.id);
                    };
                    // console.log(songSelectBtn.onclick);
                    // console.log(item.id);
                    // songSelectBtn.textContent = item.name;
                    titleCell.appendChild(songSelectBtn);
                    
                    // titleCell.textContent = item.data.title;
                    // Title cell contains the album cover art AND the title
                    // Let's do this
                    // Check if cover exists
                    let coverArt = document.createElement('img')

                    // Create a data URL from base64
                    const coverUrl = '/music_cover/' + item.id + '?64';
                    
                    // Display in an <img> tag
                    coverArt.src = coverUrl;

                    titleCell.appendChild(coverArt);

                    let titleText = document.createElement('p');
                    titleText.textContent = item.data.title;
                    titleCell.appendChild(titleText);

                    artistCell.textContent = item.data.artist;
                    durationCell.textContent = Math.ceil(item.data.duration) + "s";
                    
                    titleCell.className = "title_col";
                    artistCell.className = "artist_col";
                    durationCell.className = "duration_col";
                    
                    musicRow.appendChild(titleCell);
                    musicRow.appendChild(artistCell);
                    musicRow.appendChild(durationCell);
                    musicTable.appendChild(musicRow);
                });
            });

            // musicData = musicDataPromises; // Now use this globally
        }).catch(error => {
            console.error("Error fetching music list json:", error);
        });
    }
}

// Seek logics
const progressBar = document.getElementById("progress_bar");
const progressFill = document.getElementById("progress_fill");
const player = document.getElementById("player")
const playButton = document.getElementById("playbutton");

const musicCurrentTimeDisplay = document.getElementById("music_time_current");
const musicDurationDisplay = document.getElementById("music_time_duration");

const musicCover = document.getElementById("music_cover");
const musicTitle = document.getElementById("music_title");
const musicArtist = document.getElementById("music_artist");

function requestMusic(id) {
    console.log("requestMusic:", id);
    player.src = "/music/" + id;

    const coverUrl = '/music_cover/' + id + '?500';
    musicCover.src = coverUrl;

    musicArtist.textContent = musicData[id].artist;
    musicTitle.textContent = musicData[id].title;

    if (!playing) playMusic();
    else {
        playMusic();
        playMusic(); // Idk why this fixes it but whatever
    }
}

let playing = false;
function playMusic() {
    console.log("playMusic");

    if (!playing) {
        playing = true;
        player.play();
        playButton.src = "/src/pause.svg";
    } else {
        playing = false;
        player.pause();
        playButton.src = "/src/play.svg";
    }
}

progressBar.addEventListener("click", (e) => {
    const rect = progressBar.getBoundingClientRect();

    // Position within progress bar
    const clickX = e.clientX - rect.left

    // Convert to 0.0 -> 1.0
    const percentage = clickX / rect.width;

    // Apply
    progressFill.style.flex = percentage;
    player.currentTime = percentage * player.duration;
});

player.addEventListener("timeupdate", () => {
    const progress = player.currentTime / player.duration;
    progressFill.style.flex = progress;

    musicCurrentTimeDisplay.textContent = formatTime(player.currentTime);
    musicDurationDisplay.textContent = formatTime(player.duration);
});

// First start logics
switchMedia('music'); // Default at music