An example of streaming data into the perspective viewer, simulating a simple market
blotter. The example creates random rows of tick data updating the table every 50ms
and limiting the data set to 500 rows.

This example has no server component, and all market data is randomly created in the
browser. It is a good example of Perspective's optimized real-time windowing
performance using the `limit` parameter, as memory usage will stay consistent, as well
as its interactivity during frequent re-renders.

## index.css
````css
perspective-viewer {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
}
````
## index.html
````html
<!DOCTYPE html>
<html>
    <head>
        <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,minimum-scale=1,user-scalable=no" />
        <link rel="preload" href="https://cdn.jsdelivr.net/npm/@finos/perspective/dist/wasm/perspective-server.wasm" as="fetch" type="application/wasm" crossorigin="anonymous" />
        <link rel="preload" href="https://cdn.jsdelivr.net/npm/@finos/perspective-viewer/dist/wasm/perspective-viewer.wasm" as="fetch" type="application/wasm" crossorigin="anonymous" />
        <link rel="stylesheet" href="index.css" />
        <link rel="stylesheet" crossorigin="anonymous" href="https://cdn.jsdelivr.net/npm/@finos/perspective-viewer/dist/css/themes.css" />
        <script type="module" src="streaming.js"></script>
    </head>
    <body>
        <perspective-viewer></perspective-viewer>
    </body>
</html>
````
## Streamming.js
````js
import "https://cdn.jsdelivr.net/npm/@finos/perspective-viewer@3.7.0/dist/cdn/perspective-viewer.js";
import "https://cdn.jsdelivr.net/npm/@finos/perspective-viewer-datagrid@3.7.0/dist/cdn/perspective-viewer-datagrid.js";
import "https://cdn.jsdelivr.net/npm/@finos/perspective-viewer-d3fc@3.7.0/dist/cdn/perspective-viewer-d3fc.js";

import perspective from "https://cdn.jsdelivr.net/npm/@finos/perspective@3.7.0/dist/cdn/perspective.js";

var SECURITIES = [
    "AAPL.N",
    "AMZN.N",
    "QQQ.N",
    "NVDA.N",
    "TSLA.N",
    "FB.N",
    "MSFT.N",
    "TLT.N",
    "XIV.N",
    "YY.N",
    "CSCO.N",
    "GOOGL.N",
    "PCLN.N",
];

var CLIENTS = [
    "Homer",
    "Marge",
    "Bart",
    "Lisa",
    "Maggie",
    "Moe",
    "Lenny",
    "Carl",
    "Krusty",
];

// Create 5 random rows of data.
function newRows() {
    var rows = [];
    for (var x = 0; x < 50; x++) {
        rows.push({
            name: SECURITIES[Math.floor(Math.random() * SECURITIES.length)],
            client: CLIENTS[Math.floor(Math.random() * CLIENTS.length)],
            lastUpdate: new Date(),
            chg: Math.random() * 20 - 10,
            bid: Math.random() * 10 + 90,
            ask: Math.random() * 10 + 100,
            vol: Math.random() * 10 + 100,
        });
    }
    return rows;
}

// Get element from the DOM.
var elem = document.getElementsByTagName("perspective-viewer")[0];

// Create a new Perspective WebWorker instance.
var worker = await perspective.worker();

// Create a new Perspective table in our `worker`, and limit it it 500 rows.
var table = await worker.table(newRows(), {
    limit: 500,
});

// Load the `table` in the `<perspective-viewer>` DOM reference.
await elem.load(Promise.resolve(table));

elem.restore({
    plugin: "Datagrid",
    columns_config: {
        "(+)chg": { fg_gradient: 7.93, number_fg_mode: "bar" },
        "(-)chg": { fg_gradient: 8.07, number_fg_mode: "bar" },
        chg: { bg_gradient: 9.97, number_bg_mode: "gradient" },
    },
    plugin_config: {
        editable: false,
        scroll_lock: true,
    },
    settings: true,
    theme: "Pro Light",
    group_by: ["name"],
    split_by: ["client"],
    columns: ["(-)chg", "chg", "(+)chg"],
    filter: [],
    sort: [["chg", "desc"]],
    expressions: {
        "(-)chg": 'if("chg"<0){"chg"}else{0}',
        "(+)chg": 'if("chg">0){"chg"}else{0}',
    },
    aggregates: { "(-)chg": "avg", chg: "avg", "(+)chg": "avg" },
});

// Add more rows every 50ms using the `update()` method on the `table` directly.
(function postRow() {
    table.update(newRows());
    setTimeout(postRow, 10);
})();
````