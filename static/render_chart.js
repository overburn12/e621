
function renderChart() {
    const timeColumn = document.getElementById('timeColumn').value;
    const dataColumn = document.getElementById('dataColumn').value;
    const granularity = document.getElementById('timeGranularity').value;
    const queryData = sqlResponse;

    saveFieldSettings();

    // Process the data to fit into the chart
    // This will depend on the structure of your queryData
    const processedData = processDataForChart(queryData, timeColumn, dataColumn, granularity);
    
    const minWidthPerDataPoint = 10; // Minimum width per data point in pixels
    const extraWidth = 100; // Extra width for axes and borders
    const totalWidth = minWidthPerDataPoint * processedData.labels.length + extraWidth;
    
    // Set the width of the canvas
    const canvas = document.getElementById('myChart');
    canvas.style.width = totalWidth + 'px';
    canvas.style.height = '500px';

    // Destroy the existing chart instance if it exists
    if (myChart) {
        myChart.destroy();
    }
    
    // Get the context of the canvas
    const ctx = canvas.getContext('2d');

    myChart = new Chart(ctx, {
        type: 'line', // or 'bar', depending on your preference
        data: {
            labels: processedData.labels,
            datasets: [{
                label: 'Data',
                data: processedData.data
                // other dataset properties
            }]
        },
        options: {
            responsive: false,
            maintainAspectRatio: false,
            scales: {
                y: {
                    ticks: {
                      stepSize: 1
                    }
                },
                x: {
                    ticks: {
                        autoSkip: true, // Automatically skip labels to avoid overlap
                        maxRotation: 45, // Maximum label rotation in degrees
                        minRotation: 45 // Minimum label rotation in degrees
                    }
                }
            }
        }
    });
}

function processDataForChart(data, timeColumn, dataColumn, granularity) {
    // Ensure there is data to process
    if (!data || !data.rows || data.rows.length === 0) {
        console.error("No data to process");
        return { labels: [], data: [] };
    }

    // Generate a complete list of time blocks
    const fullTimeBlocks = generateTimeBlocks(data, timeColumn, granularity);

    // Merge actual query data into the generated time blocks
    const mergedData = mergeDataIntoTimeBlocks(data, fullTimeBlocks, timeColumn, dataColumn);

    return {
        labels: mergedData.map(item => item.time),
        data: mergedData.map(item => item.value)
    };
}
   

function generateTimeBlocks(data, timeColumn, granularity) {
    if (data.rows.length === 0) {
        return [];
    }
    // Get the first and last time values from the data
    const firstTime = new Date(data.rows[0][timeColumn]);
    const lastTime = new Date(data.rows[data.rows.length - 1][timeColumn]);

    let timeBlocks = [];
    let currentTime = new Date(firstTime);

    while (currentTime <= lastTime) {
        timeBlocks.push(formatTime(currentTime, granularity));
        incrementTime(currentTime, granularity);
    }

    return timeBlocks;
}

function formatTime(date, granularity) {
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0'); // JavaScript months are 0-indexed
    const day = date.getDate().toString().padStart(2, '0');
    const hour = date.getHours().toString().padStart(2, '0');

    switch (granularity) {
        case 'yearly':
            return `${year}`;
        case 'monthly':
            return `${year}-${month}`;
        case 'daily':
            return `${year}-${month}-${day}`;
        case 'hourly':
            return `${year}-${month}-${day} ${hour}:00`;
        // Add cases for minutely and secondly if needed
        default:
            return `${year}-${month}-${day} ${hour}:00`; // Default to hourly if granularity is not specified
    }
}

function incrementTime(date, granularity) {
    switch (granularity) {
        case 'yearly':
            date.setFullYear(date.getFullYear() + 1);
            break;
        case 'monthly':
            date.setMonth(date.getMonth() + 1);
            break;
        case 'daily':
            date.setDate(date.getDate() + 1);
            break;
        case 'hourly':
            date.setHours(date.getHours() + 1);
            break;
        case 'minutely':
            date.setMinutes(date.getMinutes() + 1);
            break;
        case 'secondly':
            date.setSeconds(date.getSeconds() + 1);
            break;
    }
}

function mergeDataIntoTimeBlocks(data, timeBlocks, timeColumn, dataColumn) {
    // Convert data rows into a map for easier lookup
    const dataMap = new Map(data.rows.map(row => [row[timeColumn], row[dataColumn]]));
    
    // Merge actual data into the time blocks
    const mergedData = timeBlocks.map(block => {
        const value = dataMap.has(block) ? dataMap.get(block) : 0;
        return {
            time: block,
            value: value
        };
    });

    return mergedData;
}