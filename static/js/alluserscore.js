let currentSortColumn = 2; // デフォルト: 得点
let sortDirection = 'desc'; // 降順

// 表ごとのソート状態を管理するオブジェクト
const sortStates = {
    all_score: { currentSortColumn: 2, sortDirection: 'desc' },
    filtered_score: { currentSortColumn: 2, sortDirection: 'desc' },
    monthly_score: { currentSortColumn: 2, sortDirection: 'desc' }
};

function handleSort(tableId, columnIndex) {
    const tbody = document.getElementById(tableId);
    if (!tbody) return;

    const { currentSortColumn, sortDirection } = sortStates[tableId];

    const rows = Array.from(tbody.querySelectorAll('tr'));
    const newSortDirection = (currentSortColumn === columnIndex && sortDirection === 'asc') ? 'desc' : 'asc';

    const sortedRows = rows.sort((a, b) => {
        const aText = a.children[columnIndex]?.textContent.trim() || '';
        const bText = b.children[columnIndex]?.textContent.trim() || '';

        const aNum = parseFloat(aText.replace('%', ''));
        const bNum = parseFloat(bText.replace('%', ''));

        if (!isNaN(aNum) && !isNaN(bNum)) {
        return newSortDirection === 'asc' ? aNum - bNum : bNum - aNum;
        } else {
        return newSortDirection === 'asc' ? aText.localeCompare(bText) : bText.localeCompare(aText);
        }
    });

    // 順位の再計算（得点列で順位を計算）
    let prevScore = null;
    let rank = 0;
    sortedRows.forEach((row, index) => {
        const score = row.children[2]?.textContent.trim();
        if (prevScore !== score) {
        rank = index + 1;
        }
        row.children[0].textContent = rank;
        prevScore = score;
    });

    tbody.innerHTML = '';
    sortedRows.forEach(row => tbody.appendChild(row));

    // ソート状態更新
    sortStates[tableId] = { currentSortColumn: columnIndex, sortDirection: newSortDirection };

    // ソートアイコン更新
    // まずそのテーブル内の全てのアイコンをクリア
    const table = tbody.closest('table');
    table.querySelectorAll('.sort-indicator').forEach(el => el.textContent = '');

    // ソートしている列のアイコンだけ更新
    const header = table.querySelector(`thead tr th:nth-child(${columnIndex + 1}) .sort-indicator`);
    if (header) {
        header.textContent = newSortDirection === 'asc' ? '▲' : '▼';
    }
}