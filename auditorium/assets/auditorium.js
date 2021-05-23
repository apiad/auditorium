var allSlides = document.getElementsByClassName("slide");
var currentSlide = allSlides[0];

let socket = new WebSocket("ws://localhost:8000/ws");

socket.onopen = function(event) {
    socket.send(JSON.stringify({
        slide: currentSlide.id
    }));
};

socket.onmessage = function(event) {
    data = JSON.parse(event.data);
    console.log(data);
    command = commands[data.type];
    command(data);
};

function createElement(element) {
    var el = document.createElement(element.tag)
    el.id = element.id

    if (element.text) {
        el.textContent = element.text;
    }

    element.children.forEach(child => {
        el.appendChild(createElement(child));
    });

    return el;
}

function updateElement(element) {
    var el = document.getElementById(element.id);

    if (element.text) {
        el.textContent = element.text;
    }

    element.children.forEach(child => {
        updateElement(child);
    });
}

commands = {
    build: function(data) {
        currentSlide.appendChild(createElement(data.content));
    },

    update: function(data) {
        updateElement(data.content);
    },
}
