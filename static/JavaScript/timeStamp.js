'use strict';
function getCurrentTimeStamp(tz, time){
    const options = {
        timeZone: tz,
        year: 'numeric',
        month: 'numeric',
        day: 'numeric',
        hour: 'numeric',
        minute: 'numeric',
        second: 'numeric',
    };
    let formatter = new Intl.DateTimeFormat([], options);
    let currentDate = formatter.format(time);
    return currentDate;
}

function createTsDiv(document, date){
    let timeStampDiv = document.createElement('div');
    timeStampDiv.className = 'top-right';
    timeStampDiv.id = 'timestamp';
    timeStampDiv.innerText = `Last Refreshed: ${date}`;
    return timeStampDiv;
}