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

export default getCurrentTimeStamp = getCurrentTimeStamp;