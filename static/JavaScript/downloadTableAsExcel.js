/**
 * Click a button and download a table in CSV format to PC
 * @param {string} tableId ID from HTML table 
 * @param {string} fileName File Name to be downloaded
 * @param {Array<String>} customCols List of columns we want to output
 * @param {boolean} displayCol Do we want to display the column header? 
 * @param {Array<string>} dataCols Display order of the columns in csv file
 * @param {Array<string>} prefix Array of strings we want to prepend to each row
 */
function downloadTableAsExcel(tableId, fileName, customCols, displayCol, rowDisplayOrder, dataCols, prefix = []) {
    const table = document.getElementById(tableId);
    let csv = [];
    
    // Get headers
    const headers = Array.from(table.querySelectorAll("thead th")).map(th => th.innerText);
    if (!customCols.length && displayCol){
        csv.push(headers.join(","));
    }else if (displayCol){
        csv.push(customCols.join(","));
    }
    
    const rowCount = prefix.length + customCols.length;
    const tableData = {}; // key = SPY -> SPXW/SPX -> QQQ -> Put Spreads
    const dataColIndices = dataCols.map( (col) => {
        return headers.indexOf(col);
    })
    // Get rows and format as data that I want to see!
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    rows.forEach( (row) => {
        const cells = row.querySelectorAll("td");
        let usym;
        let ul_pct;
        headers.forEach( (header, ind) => {
            if (header === "Underlying"){
                usym = cells[ind].innerText.substr(0, 3); // truncate SPXW to SPX
                tableData[usym] = tableData[usym] || [];
            }
            if (usym === "SPX" && header === "%UL"){
                ul_pct = parseFloat(cells[ind].innerText);
                if (ul_pct >= 94){
                    tableData["PutSpread"] = tableData["PutSpread"] || [];
                }
            }
        })

        let rowObj = dataColIndices.reduce( (acc, dataColIndex, ind) => {
            acc[dataCols[ind]] = cells[dataColIndex].innerText.replace(",", "");
            return acc;
        }, {});
        if (usym === "SPX" && ul_pct >= 94){
            tableData["PutSpread"].push(rowObj);
        }else{
            tableData[usym].push(rowObj);
        }
    })

    rowDisplayOrder.forEach( (rowOrder) => {
        if (rowOrder in tableData){
            let usymData = tableData[rowOrder];
            usymData.sort( (a, b) => {
                if (a.DTE !== b.DTE){
                    return parseInt(b.DTE) - parseInt(a.DTE);
                }
                return parseInt(b.Strike) - parseInt(a.Strike);
            })
            usymData.forEach( (row) => {
                let rowData = JSON.parse(JSON.stringify(prefix));
                customCols.forEach( (col) => {
                    rowData.push(row[col]);
                })
                csv.push(rowData.join(","));
            })
            csv.push(new Array(rowCount).fill("").join(","));
            csv.push(new Array(rowCount).fill("").join(","));
        }
    })


    // Create a CSV blob
    const csvString = csv.join("\n");
    const blob = new Blob([csvString], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    
    // Create a link and click it to download
    const a = document.createElement("a");
    a.href = url;
    a.download = fileName + ".csv"; // The name of the downloaded file
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}