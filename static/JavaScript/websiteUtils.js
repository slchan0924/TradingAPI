'use strict'
function showOverlay(document) {
    const overlay = document.getElementById('overlay');
    if (overlay){
        const overlayStyle = overlay.style;
        if (overlayStyle){
            overlayStyle.display = 'flex';
        }
    }
}

function hideOverlay(document) {
    const overlay = document.getElementById('overlay');
    if (overlay){
        const overlayStyle = overlay.style;
        if (overlayStyle){
            overlayStyle.display = 'none';
        }
    }
}

function removeColumn(table, colName){
    const headerRow = table.rows[0];
    let columnIndex = -1;

    // Find the index of the column with the specified name
    for (let i = 0; i < headerRow.cells.length; i++) {
        if (headerRow.cells[i].innerText === colName) {
            columnIndex = i;
            break;
        }
    }

    // If the column was found, remove it
    if (columnIndex !== -1) {
        for (let i = 0; i < table.rows.length; i++) {
            if (table.rows[i].cells.length > columnIndex) {
                table.rows[i].deleteCell(columnIndex);
            }
        }
    }
}