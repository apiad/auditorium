/* global Reveal */

var animations = [];

function setupAnimations(parent) {
    parent.querySelectorAll("animation").forEach(function (el) {
        var slide = el.attributes["data-slide"].value;
        var currentSlide = Reveal.getCurrentSlide().id;
        var time = Number(el.attributes["data-time"].value) * 1000;

        var interval = setInterval(function () {
            if (slide === currentSlide) {
                console.log("Executing animation", {
                    slide,
                    time,
                    id: el.id,
                });

                fetch("/update", {
                    method: "POST",
                    headers: {
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        type: "animation",
                        slide: slide,
                        id: el.id,
                    })
                }).then(resp => resp.json()).then(json => {
                    for (var itemId in json) {
                        document.querySelector("#" + itemId).innerHTML = json[itemId];
                    }
                });
            }
        }, time);

        animations.push(interval);
    });
}

function setupInput(parent) {
    parent.querySelectorAll("input").forEach(function (el) {
        event = el.attributes["data-event"].value;

        el[event] = function() {
            var newValue = el.value;
            var slide = el.attributes["data-slide"].value;
            var itemId = el.id;
            var updateInfo = {
                type: "input",
                slide,
                id: itemId,
                value: newValue,
            };

            console.log("Updating", updateInfo);

            fetch("update", {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(updateInfo)
            }).then(resp => resp.json()).then(json => {
                for (itemId in json) {
                    document.querySelector("#" + itemId).innerHTML = json[itemId];
                }
            });
        }
    });
}


Reveal.addEventListener("ready", function () {
    setupAnimations(Reveal.getCurrentSlide());
    setupInput(Reveal.getCurrentSlide());
});


Reveal.addEventListener("slidechanged", function (event) {
    animations.forEach(function (interval) {
        clearInterval(interval);
    });

    animations = [];

    setupAnimations(event.currentSlide);
    setupInput(event.currentSlide);
});
