function copyHint(id) {
    document.querySelector('textarea').textContent =
        document.getElementById(id).textContent;
}

function askName(force) {
    var name = localStorage.name;
    if (!name || force) {
        name = prompt('Who are you?');
        if (name) {
            localStorage.name = name;
        }
    }
    if (name) {
        document.cookie = 'claimer=' + name + ';path=/';
        document.getElementById('claimer').textContent = name;
    }
}

askName(false);
