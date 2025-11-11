const musicBlock = document.getElementById("music_block")
const moviesBlock = document.getElementById("movies_block")

const musicTable = document.getElementById("music_list")

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
        musicTable.innerHTML = "<tr><th class=\"title_col\">Title</th><th class=\"artist_col\">Artist</th><th class=\"duration_col\">Duration</th></tr>";

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
                    
                    let musicRow = document.createElement("tr");
                    let titleCell = document.createElement("td");
                    let artistCell = document.createElement("td");
                    let durationCell = document.createElement("td");

                    let songSelectBtn = document.createElement('button');
                    songSelectBtn.textContent = "‣";
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
                    if (item.data.cover && item.data.cover_mime) {
                        let coverArt = document.createElement('img')

                        // Create a data URL from base64
                        const coverUrl = `data:${item.data.cover_mime};base64,${item.data.cover}`;
                        
                        // Display in an <img> tag
                        coverArt.src = coverUrl;

                        titleCell.appendChild(coverArt);
                    }

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
        }).catch(error => {
            console.error("Error fetching music list json:", error);
        });
    }
}

function requestMusic(id) {
    console.log("requestMusic:", id);
}

// First start logics
switchMedia('music'); // Default at music