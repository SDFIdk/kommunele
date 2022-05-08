const express = require('express');
const app = express();

const port = 3000;


app.get('/', (req, res) => {
    res.sendFile('public/index.html', { root: __dirname });
});

app.use(express.static('public/data'));
app.use(express.static('public/images'));
app.use(express.static('public/icons'));
app.use(express.static('public/js'));
app.use(express.static('public/css'));

app.listen(port, () => {
    console.log('Listening on port ' + port);
});