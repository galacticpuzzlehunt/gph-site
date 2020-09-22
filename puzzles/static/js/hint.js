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
        name = prompt('Who are you? (personal Discord name/username; this is for internal use)');
    }

    if (name) {
        document.cookie = 'claimer=' + encodeURIComponent(name) + ';path=/;max-age=1209600'; // 2 weeks
        document.getElementById('claimer').textContent = name;
    }
}

askName(false);
