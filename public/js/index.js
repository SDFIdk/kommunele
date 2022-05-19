'use strict';

(async (w, d) => {
    const DomHasLoaded = new Promise((resolve) => {
            if (d.readyState !== 'loading') { resolve(); };
        }),
        buttonSelect = d.querySelector('#button-select'),
        municipalitySelector = d.querySelector('#municipality-selector'),
        municipalityImage = d.querySelector('#municipality-image'),
        municipalityImageResult = d.querySelector('#municipality-image-result'),
        resultTemplate = d.querySelector('#resultTemplate');

    let municipalityList = null,
        relations = null,
        currentMunicipalityId = null,
        guessList = d.querySelector('#guess-list');

    const selectAnswer = (name) => {
        const matchedGuess = municipalityList.find(item => item.name.toLocaleLowerCase() === name),
            guessedName = matchedGuess?.name ?? null,
            guessedCode = matchedGuess?.id ?? null;

        if (guessedCode === null) {
            console.error('Could not find the municipality in the list!');
            return false;
        };

        // Determine the distance and direction to the correct answer.
        const relation = relations.find(item => item.dst_id === currentMunicipalityId && item.src_id === guessedCode) ?? null,
            distance = relation?.distance ?? 'N/A',
            direction = relation?.direction ?? 'N/A',
            correctGuess = (currentMunicipalityId === guessedCode);

        // Add guess to the list.
        const newResult = resultTemplate.content.cloneNode(true);
        newResult.querySelector('tr').className = (correctGuess) ? 'correct' : '';
        newResult.querySelector('td:nth-child(1)').dataset.name = guessedName;
        newResult.querySelector('td:nth-child(2)').dataset.distance = (correctGuess) ? '' : Math.round(distance / 1000.0, 2);
        newResult.querySelector('i').style.transform = (correctGuess) ? '' : 'rotate(' + (360.0 - direction * 180.0/Math.PI) + 'deg)';
        guessList.prepend(newResult);


        if (correctGuess) {
            // Hide the input box if the guess was correct.
            municipalitySelector.disabled = buttonSelect.disabled = true;
            // Show the resulting image if the guess was correct.
            municipalityImage.className = 'hideImg';
            municipalityImageResult.className = 'showImg';
        };
        return (correctGuess);
    };

    DomHasLoaded.then(() => {
        d.forms.guess.addEventListener('submit', (event) => {
            event.preventDefault();
            const guess = municipalitySelector.value.toLocaleLowerCase() || '';
            if (!selectAnswer(guess) || !d.forms.guess.checkValidity()) {
                d.forms.guess.classList.toggle('shake');
                w.setTimeout(() => {
                    d.forms.guess.classList.toggle('shake');
                }, 400);
            };
            municipalitySelector.value = '';
        });

        const municipalityListElm = d.querySelector('#municipality-list'),
            today = new Date(),
            todayString = today.getFullYear().toString() + (today.getMonth() + 1).toString().padStart(2, '0') + today.getDate().toString().padStart(2, '0'),
            initData = [
                fetch('/data/date_list.json')
                    .then(res => res.json())
                    .then((out) => {
                        // Set the municipality image.
                        const currentMunicipality = out.find(item => item.date === todayString) ?? null;
                        currentMunicipalityId = currentMunicipality?.id ?? 'NotFound';
                        municipalityImage.src = '/images/' + currentMunicipalityId + '.png';
                        municipalityImageResult.src = '/images/' + currentMunicipalityId + '_result.png';
                    }),
                fetch('/data/municipality_list.json')
                    .then(res => res.json())
                    .then((out) => {
                        municipalityList = out;
                        const group = d.createDocumentFragment();
                        out.forEach(item => {
                            group.appendChild(new Option(item.name));
                        });
                        municipalityListElm.appendChild(group);
                    }),
                fetch('/data/relations.json')
                    .then(res => res.json())
                    .then((out) => { relations = out; })
            ];
        Promise.all([...initData]).then(() => { d.body.className = 'showSite'; });
    });
})(window, document);