const express = require('express');
const app = express();

const port = 4444;


app.get('/', (req, res) => {
    res.sendFile('public/index.html', { root: __dirname });
});

app.use(express.static('public'));

app.listen(port, 'localhost',() => {
    console.log('Listening on port ' + port);
});
