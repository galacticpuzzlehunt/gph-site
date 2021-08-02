function showNotify(data) {
    const {title, text, link} = JSON.parse(data);
    toastr.info(text, title, {
        timeOut: 30000, extendedTimeOut: 30000, closeButton: true,
        onclick: () => window.open(link, '_blank'),
    });
}

function openSocket(path, callback) {
    const url = (location.protocol === 'https:' ? 'wss' : 'ws') +
        '://' + window.location.host + path;
    const queue = [];
    let socket = null;
    (async () => {
        while (true) {
            await new Promise(res => {
                const newSocket = new WebSocket(url);
                newSocket.onclose = res;
                newSocket.onerror = res;
                newSocket.onmessage = e => callback(e.data);
                newSocket.onopen = () => {
                    while (queue.length)
                        newSocket.send(queue.shift());
                    socket = newSocket;
                };
            });
            socket = null;
            await new Promise(res => setTimeout(res, 10000));
        }
    })();
    return data => {
        if (socket)
            socket.send(data);
        else
            queue.push(data);
    };
}
