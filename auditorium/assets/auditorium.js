var allSlides = document.getElementsByClassName("slide");
var currentSlide = allSlides[0].id;
var body = document.getElementsByTagName("body")[0];
var hash = window.location.hash;

if (hash !== "") {
    currentSlide = hash.substr(1);
}

function customScrollTo(from, towards, duration) {
    var start = from.offsetTop,
        to = towards.offsetTop,
        change = to - start;

    from.scrollIntoView();

    const startTime = window.performance.now();

    var animateScroll = function(timestamp){
        elapsed = timestamp - startTime;
        var val = Math.easeInOutQuad(elapsed, start, change, duration);
        window.scrollTo(0, val);

        if(elapsed < duration) {
            window.requestAnimationFrame(animateScroll);
        }
        else{
            if (from != towards) {
                from.replaceChildren();
            }
            towards.scrollIntoView();
        }
    };
    window.requestAnimationFrame(animateScroll);
}

Math.easeInOutQuad = function (t, b, c, d) {
    t /= d/2;
    if (t < 1) return c/2*t*t + b;
    t--;
    return -c/2 * (t*(t-2) - 1) + b;
};

function goToSlide(slide, duration) {
    var element = allSlides[slide];
    customScrollTo(allSlides[currentSlide], element, duration);
    currentSlide = slide;
    window.location.hash = "#" + String(currentSlide);

    socket.send(JSON.stringify({
        slide: element.id,
        event: "render"
    }));
}

let socket = new WebSocket("ws://localhost:8000/ws");

socket.onopen = function(event) {
    goToSlide(currentSlide, 0);
};

socket.onmessage = function(event) {
    data = JSON.parse(event.data);
    console.log(data);
    command = commands[data.type];
    command(data);
};

var lastKeyCode = null;
var askedKeypress = false;

window.onkeypress = function (event) {
    socket.send(JSON.stringify({
        slide: currentSlide,
        event: "keypress",
        keycode: event.keyCode,
    }));
};

function createElements(elements, parent) {
    elements.forEach(element => {
        if (document.getElementById(element.id)) {
            return;
        }

        var el = document.createElement(element.tag)
        el.id = element.id

        if (element.text) {
            el.textContent = element.text;
        }

        el.style.setProperty("transition-duration", element.transition_duration);
        el.className = element.clss;

        for(var key in element.style) {
            el.style.setProperty(key, element.style[key]);
        }

        if (element.props !== null) {
            for(var key in element.props) {
                el.setAttribute(key, element.props[key]);
            }
        }

        element.children.forEach(child => {
            el.appendChild(createElements(child));
        });

        if (element.parent !== null) {
            document.getElementById(element.parent).appendChild(el);
        }
        else {
            parent.appendChild(el);
        }
    });
}

function destroyElements(elements) {
    elements.forEach(el => {
        document.getElementById(el).remove()
    });
}

function updateElement(element) {
    var el = document.getElementById(element.id);

    if (element.text) {
        el.textContent = element.text;
    }

    el.style.setProperty("transition-duration", element.transition_duration);
    el.className = element.clss;

    for(var key in element.style) {
        el.style.setProperty(key, element.style[key]);
    }

    element.children.forEach(child => {
        updateElement(child);
    });
}

commands = {
    create: function(data) {
        createElements(data.content, allSlides[currentSlide]);
    },

    update: function(data) {
        updateElement(data.content);
    },

    destroy: function(data) {
        destroyElements(data.content);
    },

    goto: function(data) {
        goToSlide(data.slide, data.time);
    },

    keypress: function(data) {
        if (data.immediate) {
            socket.send(JSON.stringify({
                slide: allSlides[currentSlide].id,
                event: "keypress",
                keycode: lastKeyCode,
            }));
            lastKeyCode = null;
        }
        else {
            waitingKeypress = true;
        }
    }
}
