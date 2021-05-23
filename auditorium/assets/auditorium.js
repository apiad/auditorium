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

function createElements(elements) {
    var els = [];

    elements.forEach(element => {
        var el = document.createElement(element.tag)
        el.id = element.id

        if (element.text) {
            el.textContent = element.text;
        }

        el.className = element.clss;

        el.style.setProperty('transition-duration', element.transition_duration);
        el.style.setProperty('transition-property', element.transition_property);

        for(var key in element.style) {
            el.style.setProperty(key, element.style[key]);
        }

        element.children.forEach(child => {
            el.appendChild(createElements(child));
        });

        els.push(el);
    });

    return els;
}

function updateElement(element) {
    var el = document.getElementById(element.id);

    if (element.text) {
        el.textContent = element.text;
    }

    el.className = element.clss;

    el.style.setProperty('transition-duration', element.transition_duration);
    el.style.setProperty('transition-property', element.transition_property);

    for(var key in element.style) {
        el.style.setProperty(key, element.style[key]);
    }

    element.children.forEach(child => {
        updateElement(child);
    });
}

commands = {
    build: function(data) {
        createElements(data.content).forEach(el => {
            currentSlide.appendChild(el);
        });
    },

    update: function(data) {
        updateElement(data.content);
    },
}
