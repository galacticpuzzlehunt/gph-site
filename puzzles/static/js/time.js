function updateTimestamps() {
    for (const time of document.querySelectorAll('time')) {
        const format = time.getAttribute('data-format');
        if (!format) continue;
        const options = {hour12: false, timeZoneName: 'short'};
        for (const [code] of format.matchAll(/%-?[a-z]/ig))
            switch (code) {
                case '%A': options.weekday = 'long'; break;
                case '%Y': options.year = 'numeric'; break;
                case '%B': options.month = 'long'; break;
                case '%b': options.month = 'short'; break;
                case '%-d': options.day = 'numeric'; break;
                case '%H': options.hour = '2-digit'; break;
                case '%-I': options.hour = 'numeric'; break;
                case '%M': options.minute = '2-digit'; break;
                case '%p': options.hour12 = true; break;
                case '%Z': break;
                default: console.error('Unrecognized strftime code ' + code);
            }
        const local = new Date(time.dateTime).toLocaleString([], options);
        time.setAttribute('title', 'Local time: ' + local);
    }
}

$(updateTimestamps);
