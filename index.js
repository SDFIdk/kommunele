const express = require('express');
const app = express();

const port = 3000;


app.get('/', function(req, res) {
    res.sendFile('index.html', {root: __dirname});
});

app.use(express.static('data'));
app.use(express.static('images'));
app.use(express.static('icons'));

app.listen(port, () => {
    console.log('Listening on port ${port}');
});