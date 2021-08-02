function copyHint(id) {
    document.querySelector('textarea').textContent =
        document.getElementById(id).textContent;
}

// We used to use localStorage here, which is a lot easier to access on the
// client-side, but can lead to confusingly inconsistent state between the
// client and server. In particular, if the user's cookie expired but they have
// their name in localStorage and they click a claim link, the server will
// think they're anonymous (since it can't see localStorage) but they'll think
// they're not (after this JavaScript runs). So we use cookies on both server
// and client side so they have a consistent view of whether the user has ID'ed
// themselves.
function askName(force) {
    var name;
    var claimerCookie = document.cookie.split('; ').find(row => row.startsWith('claimer='));
    if (claimerCookie) {
        name = decodeURIComponent(claimerCookie.slice(8));
    }

    if (!name || force) {
        name = prompt('Who are you? (personal Discord name/username, excluding the #0000 tag; this is for internal use)');
    }

    if (name) {
        document.cookie = 'claimer=' + encodeURIComponent(name) + ';path=/;max-age=1209600'; // 2 weeks
        document.getElementById('claimer').textContent = name;
    }
}
askName(false);

function getUpdates() {
    openSocket('/ws/hints', data => {
        const {id, content} = JSON.parse(data);
        const elt = document.getElementById('h' + id);
        if (content && elt)
            elt.outerHTML = content;
        else if (content)
            document.getElementsByClassName('hint-table')[0].innerHTML += content;
        else if (elt)
            elt.remove();
        updateTimestamps();
    });
    setInterval(updateDurations, 1000);
}

function updateDurations() {
    for (const time of document.querySelectorAll('time')) {
        let secs = Math.max(0, (Date.now() - new Date(time.dateTime)) / 1000 | 0);
        const hours = secs / (60 * 60) | 0;
        secs -= hours * 60 * 60;
        const mins = secs / 60 | 0;
        secs -= mins * 60;
        if (hours > 0)
            time.textContent = `${hours}h${mins}m`;
        else if (mins > 0)
            time.textContent = `${mins}m${secs}s`;
        else
            time.textContent = `${secs}s`;
    }
}
