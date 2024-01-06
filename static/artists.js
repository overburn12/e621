var artistListString = [];

function loadArtistList() {
    fetch('/artists_list')
        .then(response => response.json())
        .then(data => {
            artistListString = data;
        })
        .catch(error => console.error('Error fetching artist list:', error));
}


function saveArtistList() {
    fetch('/artists_list', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(artistListString),
    })
    .then(response => {
        if (response.ok) {
            console.log('Artist list updated successfully');
        } else {
            console.error('Error updating artist list');
        }
    })
    .catch(error => console.error('Error updating artist list:', error));
}

function addArtist(artistName) {
    var element = document.getElementById('add_' + artistName);
    if (element) {
        element.style.display = 'none';
    }
    artistListString.push(artistName);
    saveArtistList();
}

function removeArtist(artistName) {
    var index = artistListString.indexOf(artistName);
    if (index > -1) {
        artistListString.splice(index, 1);
    }
    saveArtistList();
}

function isArtistFavorited(artistName) {
    return artistListString.includes(artistName);
}

//reload when traveling back in history
window.onpopstate = function(event) {
    loadArtistList();
};

loadArtistList();