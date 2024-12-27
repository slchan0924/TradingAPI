// Populate timezone selector
const timezones = Intl.supportedValuesOf('timeZone');

const selectedTZs = [
    "Asia/Tokyo",
    "Asia/Hong_Kong",
    "Europe/London",
    "Europe/Berlin",
    "America/New_York",
    "America/Los_Angeles"
]

const timezoneSelector = document.getElementById('timezone-selector');
const currentTimeDisplay = document.getElementById('current-time');
selectedTZs.forEach((timezone) => {
    const option = document.createElement('option');
    if (timezones.indexOf(timezone) > -1) {
        option.value = timezone;
        option.textContent = timezone.replace("_", " ");
    }else{
        option.value = 'invalidTimezone';
        option.textContent = 'Invalid Timezone!';
    }
    timezoneSelector.appendChild(option);
});

const savedTimezone = localStorage.getItem('selectedTimezone');
if (savedTimezone) {
    timezoneSelector.value = savedTimezone;
}

// Function to update the current time
function updateTime() {
    const selectedTimezone = timezoneSelector.value;
    localStorage.setItem('selectedTimezone', selectedTimezone);
    const options = { 
        timeZone: selectedTimezone, 
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit',
        hour12: false 
    };
    const timeString = new Intl.DateTimeFormat([], options).format(new Date());
    currentTimeDisplay.textContent = timeString;
}

// Event listener for timezone change
timezoneSelector.addEventListener('change', updateTime);

// Initial time display
updateTime();
setInterval(updateTime, 1000); // Update every second