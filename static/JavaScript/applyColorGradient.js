'use strict';

const usymMapping = {
    "QQQ": {
        "RGBLight": [135, 206, 235],
        "RGBDark": [15, 62, 115],
        "Count": 0,
        "Total": 0,
        "Colour": "Blue",
    },
    "SPY": {
        "RGBLight": [255, 165, 0],
        "RGBDark": [255, 45, 0],
        "Count": 0,
        "Total": 0,
        "Colour": "Orange",
    },
    "SPX": {
        "RGBLight": [144, 238, 144],
        "RGBDark": [0, 100, 32],
        "Count": 0,
        "Total": 0,
        "Colour": "Green",
    },
}

// need to modify the adjustment sensitivity
function applyRGB(usym, index, rows, isNextBDayExpire) {
    if (isNextBDayExpire){
        return "rgb(255, 0, 0)";
    }
    let setup = usymMapping[usym];

    let modifiedRgbValue = setup["RGBDark"].map( (rgbDarkVal, ind) => {
        let rgbLightVal = setup["RGBLight"][ind];
        return rgbDarkVal + (rgbLightVal - rgbDarkVal) * (index / (rows - 1));
    })
    
    // Ensure values are clamped between 0 and 255
    modifiedRgbValue = modifiedRgbValue.map(value => Math.max(0, Math.min(255, value)));
    return `rgb(${modifiedRgbValue[0]}, ${modifiedRgbValue[1]}, ${modifiedRgbValue[2]})`;
}

function isWeekendInNY() {
    // Create a date object for the current date and time
    const now = new Date();

    // Convert to New York Time (UTC-5 or UTC-4 depending on Daylight Saving Time)
    const options = { timeZone: 'America/New_York', weekday: 'long' };
    const nyDate = new Intl.DateTimeFormat('en-US', options).format(now);

    // Get the day of the week
    const day = new Date(nyDate).getDay();

    // Check if it's Saturday (6) or Sunday (0)
    return day === 0 || day === 6;
}

function applyGradient(container){
    const tbody = container.getElementsByTagName('tbody')[0];
    const isWeekend = isWeekendInNY();
    // reset counts as 0
    for (let usym in usymMapping){
        usymMapping[usym]["Count"] = 0;
        usymMapping[usym]["Total"] = 0;
    }
    if (!tbody) return;
    const rows = tbody.getElementsByTagName('tr');
    const headers = Array.from(container.getElementsByTagName('th')).map(th => th.textContent.trim());
    const usymIndex = headers.indexOf("Underlying");
    const ulIndex = headers.indexOf("%UL");
    const bDayDteIndex = headers.indexOf("Business DTE");
    if (rows.length === 0) return;
    // We want to know how many rows there might be
    for (let row of rows){
        const cells = row.getElementsByTagName('td');
        let usym = cells[usymIndex].textContent.trim().substr(0, 3);
        let ul_pct = parseFloat(cells[ulIndex].textContent.trim());
        // exclude PS
        if (usym === "SPX" && ul_pct < 93){
            usymMapping["SPX"]["Total"]++;
        }else if (usym !== "SPX"){
            usymMapping[usym]["Total"]++;
        }
    }

    // now apply colour gradient for each row
    for (let row of rows){
        const cells = row.getElementsByTagName('td');
        let usym = cells[usymIndex].textContent.trim().substr(0, 3);
        let bDayDte = parseInt(cells[bDayDteIndex].textContent.trim());
        let ul_pct = parseFloat(cells[ulIndex].textContent.trim());
        if (usym === "SPX" && ul_pct > 93){
            if (bDayDte <= 1 && bDayDte > 0 && !isWeekend){
                row.style.backgroundColor = "rgb(255, 0, 0)"; // Red
            }else if (bDayDte > 1){
                row.style.backgroundColor = "rgb(177, 156, 217)"; // Light Purple
            }
            continue;
        }
        let usymCount = usymMapping[usym]["Count"];
        let usymTotal = usymMapping[usym]["Total"];
        row.style.backgroundColor = applyRGB(usym, usymCount, usymTotal, bDayDte <= 1 && bDayDte > 0);
        usymMapping[usym]["Count"]++;
    }
}
