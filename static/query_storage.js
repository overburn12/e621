
function saveQuery() {
    const title = prompt("Enter a title for the query:");
    if (title) {
        const query = document.getElementById('queryInput').value;
        let queries = JSON.parse(localStorage.getItem('queries')) || [];
        queries.push({ title, query });
        localStorage.setItem('queries', JSON.stringify(queries));
        updateSavedQueriesList();
    }
}

function updateSavedQueriesList() {
    let queries = JSON.parse(localStorage.getItem('queries')) || [];
    let listHtml = queries.map((item, index) => 
        `<div onclick="loadQuery(${index})">${index}. ${item.title}</div>`
    ).join('');
    document.getElementById('savedQueriesList').innerHTML = listHtml;
}

function loadQuery(index) {
    let queries = JSON.parse(localStorage.getItem('queries'));
    document.getElementById('queryInput').value = queries[index].query;
}

function newQuery() {
    document.getElementById('queryInput').value = '';
}

function renameQuery() {
    const index = prompt("Enter the index of the query to rename:");
    if (index !== null) {
        const newTitle = prompt("Enter the new title:");
        let queries = JSON.parse(localStorage.getItem('queries'));
        if (queries[index]) {
            queries[index].title = newTitle;
            localStorage.setItem('queries', JSON.stringify(queries));
            updateSavedQueriesList();
        }
    }
}

function deleteQuery() {
    const index = prompt("Enter the index of the query to delete:");
    if (index !== null) {
        let queries = JSON.parse(localStorage.getItem('queries'));
        if (queries[index]) {
            queries.splice(index, 1);
            localStorage.setItem('queries', JSON.stringify(queries));
            updateSavedQueriesList();
        }
    }
}