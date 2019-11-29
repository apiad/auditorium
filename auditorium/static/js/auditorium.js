setTimeout(function () {
    document.querySelectorAll("animation").forEach(function (el) {
        var slide = el.attributes['data-slide'].value;
        var currentSlide = Reveal.getCurrentSlide().id;
        var time = Number(el.attributes['data-time'].value);

        setInterval(function () {
            if (slide === currentSlide) {
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
    });
}, 1000)

document.querySelectorAll("input").forEach(function (el) {
    event = el.attributes['data-event'].value;

    el[event] = function(ev) {
        var newValue = el.value;
        var slide = el.attributes['data-slide'].value;
        var item_id = el.id;
        var url = "update/" + slide + "/" + item_id + "/" + newValue;

        fetch('update', {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                type: 'input',
                slide: slide,
                id: item_id,
                value: newValue,
            })
        }).then(resp => resp.json()).then(json => {
            for (item_id in json) {
                document.querySelector("#" + item_id).innerHTML = json[item_id];
            }
        });
    }
});
