function updateTimestamps() {
    for (const time of document.querySelectorAll('time')) {
        const format = time.getAttribute('data-format');
        if (!format) continue;
        const options = {hour12: false, timeZoneName: 'short'};
        var escaped = false;
        for (const [code] of format.matchAll(/[a-z\\]/ig)) {
        	if (escaped) {
        		escaped = false;
        		continue;
        	}
            switch (code) {
                case 'l': options.weekday = 'long'; break;
                case 'D': options.weekday = 'short'; break;
                case 'Y': options.year = 'numeric'; break;
                case 'y': options.year = '2-digit'; break;
                case 'F': options.month = 'long'; break;
                case 'm': options.month = '2-digit'; break;
                case 'n': options.month = 'numeric'; break;
                case 'M': 
                case 'N': 
                case 'b': options.month = 'short'; break;
                case 'd': options.day = '2-digit'; break;
                case 'j': options.day = 'numeric'; break;
                case 'G': options.hour = 'numeric'; 
                		options.hour12 = false;
                		break;
                case 'H': options.hour = '2-digit'; 
                		options.hour12 = false;
                		break;
                case 'g': options.hour = 'numeric'; 
                		options.hour12 = true;
                		break;
                case 'h': options.hour = '2-digit'; 
                		options.hour12 = true;
                		break;
                case 'i': options.minute = '2-digit'; break;
                case 'A': 
                case 'a': options.hour12 = 'true'; break;
                case 'T': break;
                case '\\': escaped = true; break;
            }
        }
        const local = new Date(time.dateTime).toLocaleString([], options);
        const title = time.getAttribute('title');
        time.setAttribute('title', title + local);
    }
}

$(updateTimestamps);
