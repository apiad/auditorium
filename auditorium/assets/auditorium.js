var allSlides = document.getElementsByClassName("slide");
var currentSlide = 0;


function customScrollTo(start, to, duration) {
    var start = start,
        change = to - start,
        currentTime = 0,
        increment = 20;

    var animateScroll = function(){
        currentTime += increment;
        var val = Math.easeInOutQuad(currentTime, start, change, duration);
        window.scrollTo(0, val);

        if(currentTime < duration) {
            setTimeout(animateScroll, increment);
        }
    };
    animateScroll();
    window.scrollTo(0, to);
}

Math.easeInOutQuad = function (t, b, c, d) {
    t /= d/2;
    if (t < 1) return c/2*t*t + b;
    t--;
    return -c/2 * (t*(t-2) - 1) + b;
};

function goToSlide(slide, duration) {
    var element = allSlides[slide];

    var destinationY = element.offsetTop;
    var currentY = allSlides[currentSlide].offsetTop;

    customScrollTo(currentY, destinationY, duration);
    currentSlide = slide;

    let socket = new WebSocket("ws://localhost:8000/ws");

    socket.onopen = function(event) {
        socket.send(JSON.stringify({
            slide: element.id
        }));
    };

    socket.onmessage = function(event) {
        data = JSON.parse(event.data);
        console.log(data);
        command = commands[data.type];
        command(data);
    };
}

goToSlide(0, 500);

function goToNext() {
    let nextSlide = currentSlide + 1;

    if (nextSlide < allSlides.length) {
        goToSlide(nextSlide, 500);
    }
}

function goToPrevious() {
    let previousSlide = currentSlide - 1;

    if (previousSlide >= 0) {
        goToSlide(previousSlide, 500);
    }
}

function createElements(elements) {
    var els = [];

    elements.forEach(element => {
        if (document.getElementById(element.id)) {
            return;
        }

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
            allSlides[currentSlide].appendChild(el);
        });
    },

    update: function(data) {
        updateElement(data.content);
    },
}

window.onkeypress = function (event) {
    if (event.keyCode == 32) {
        goToNext();
        return
    }

    print(event);
};