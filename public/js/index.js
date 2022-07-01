'use strict';

(async (w, d) => {
    const DomHasLoaded = new Promise((resolve) => {
            if (d.readyState !== 'loading') { resolve(); };
        }),
        buttonSelect = d.querySelector('#buttonSelect'),
        municipalitySelector = d.querySelector('#municipalitySelector'),
        municipalityImage = d.querySelector('#municipalityImage'),
        municipalityImageResult = d.querySelector('#municipalityImageResult'),
        resultTemplate = d.querySelector('#resultTemplate'),
        hiddenMenu = d.querySelector('#hiddenMenu');

    let imageTheme = 'green',
        imagePath = '/images/' + imageTheme + '/',
        municipalityList = null,
        relations = null,
        currentMunicipalityId = null,
        guessList = d.querySelector('#guessList');

    const selectAnswer = (name) => {
        const guessedName = name ?? null,
            guessedCode = municipalityList?.[guessedName] ?? null;

        if (guessedCode === null) {
            console.error('Could not find the municipality in the list!');
            return false;
        };

        // Determine the distance and direction to the correct answer.
        const relation = relations?.[guessedCode]?.[currentMunicipalityId] ?? null,
            distance = relation?.[0] ?? 'N/A',
            direction = relation?.[1] ?? 'N/A',
            correctGuess = (currentMunicipalityId === guessedCode);

        // Add guess to the list.
        const newResult = resultTemplate.content.cloneNode(true);
        newResult.querySelector('li').className = (correctGuess) ? 'correct' : '';
        newResult.querySelector('span:nth-child(1)').dataset.name = guessedName;
        newResult.querySelector('span:nth-child(2)').dataset.distance = (correctGuess) ? '' : Math.round(distance / 1000.0, 2);
        newResult.querySelector('i').style.transform = (correctGuess) ? '' : 'rotate(' + (360.0 - direction * 180.0/Math.PI) + 'deg)';
        guessList.appendChild(newResult);

        if (correctGuess) {
            // Hide the input box if the guess was correct.
            municipalitySelector.disabled = buttonSelect.disabled = true;
            // Show the resulting image if the guess was correct.
            municipalityImage.className = 'hideImg';
            municipalityImageResult.className = 'showImg';
        };
        return (correctGuess);
    },
    getter = (file, fn) => {
        fetch(file)
            .then(res => res.json())
            .then(out => fn(out))
    };

    DomHasLoaded.then(() => {
        municipalityImageResult.addEventListener('load', () => {
            d.documentElement.style.setProperty('--map-width', (municipalityImageResult.scrollWidth / parseFloat(getComputedStyle(d.documentElement).fontSize)) + 'rem');
        });

        hiddenMenu.addEventListener('change', (event) => {
            //console.log(hiddenMenu.checked, event);
        });

        d.forms.guess.addEventListener('submit', (event) => {
            event.preventDefault();
            const guess = municipalitySelector.value.replaceAll(/(^\w)|([-\s]\w)/g, w => w.toLocaleUpperCase()) || null,
                guessForm = d.forms.guess;
            if (!selectAnswer(guess) || !guessForm.reportValidity()) {
                guessForm.classList.toggle('shake');
                w.setTimeout(() => guessForm.classList.toggle('shake'), 400);
            };
            guessForm.reset();
        });

        w.addEventListener('click', (event) => {
            if (d.querySelector('dialog').open) {
                console.log(this, event);
            } else if (d.querySelector('#hiddenMenu:checked') && (!d.querySelector('#menu').contains(event.target))) {
                hiddenMenu.checked = false;
            };
        });

        const municipalityListElm = d.querySelector('#municipalityList'),
            todayString = (new Date()).toLocaleDateString('en-CA', {year: 'numeric', month: '2-digit', day: '2-digit'}).replaceAll('-', ''),
            initData = [
                getter('/data/date_list.json', (out) => {
                    // Set the municipality image.
                    currentMunicipalityId = out?.[todayString] ?? 'NotFound';
                    const imgSrc = imagePath + currentMunicipalityId;
                    municipalityImage.src = imgSrc + '.png';
                    municipalityImageResult.src = imgSrc + '_result.png';
                }),
                getter('/data/municipality_list.json', (out) => {
                    municipalityList = out;
                    const group = d.createDocumentFragment();
                    Object.keys(municipalityList).every(item => ~group.appendChild(new Option(item)));
                    municipalityListElm.appendChild(group);
                }),
                getter('/data/relations.json', out => relations = out)
            ];

        Promise.all([...initData]).then(() => d.body.className = 'showSite');
    });
})(window, document);
