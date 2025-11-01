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
                    console.log(item.id, item.data);
                    
                    let musicRow = document.createElement("tr");
                    let titleCell = document.createElement("td");
                    let artistCell = document.createElement("td");
                    let durationCell = document.createElement("td");
                    
                    titleCell.textContent = item.data.title;
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

// First start logics
switchMedia('music') // Default at music