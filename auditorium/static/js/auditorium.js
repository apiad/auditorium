var animations = [];

Reveal.addEventListener('slidechanged', function (event) {
    animations.forEach(function (interval) {
        clearInterval(interval);
    });

    animations = [];

    setupAnimations(event.currentSlide);
    setupInput(event.currentSlide);
});

function setupAnimations(parent) {
    parent.querySelectorAll("animation").forEach(function (el) {
        var slide = el.attributes['data-slide'].value;
        var currentSlide = Reveal.getCurrentSlide().id;
        var time = Number(el.attributes['data-time'].value) * 1000;

        interval = setInterval(function () {
            if (slide === currentSlide) {
                console.log("Executing animation", {
                    slide,
                    time,
                    id: el.id,
                });

                fetch("/update", {
                    method: 'POST',
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        type: 'animation',
                        slide: slide,
                        id: el.id,
                    })
                }).then(resp => resp.json()).then(json => {
                    for (item_id in json) {
                        document.querySelector("#" + item_id).innerHTML = json[item_id];
                    }
                });
            }
        }, time);

        animations.push(interval);
    });
}

function setupInput(parent) {
    parent.querySelectorAll("input").forEach(function (el) {
        event = el.attributes['data-event'].value;

        el[event] = function() {
            var newValue = el.value;
            var slide = el.attributes['data-slide'].value;
            var item_id = el.id;
            var updateInfo = {
                type: 'input',
                slide: slide,
                id: item_id,
                value: newValue,
            };

            console.log("Updating", updateInfo);

            fetch('update', {
                method: 'POST',
                headers: {
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updateInfo)
            }).then(resp => resp.json()).then(json => {
                for (item_id in json) {
                    document.querySelector("#" + item_id).innerHTML = json[item_id];
                }
            });
        }
    });
}

Reveal.addEventListener('ready', function () {
    setupAnimations(Reveal.getCurrentSlide());
    setupInput(Reveal.getCurrentSlide());
});
