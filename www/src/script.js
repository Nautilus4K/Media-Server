const musicBlock = document.getElementById("music_block")
const moviesBlock = document.getElementById("movies_block")

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
    }
}

// First start logics
switchMedia('music') // Default at music