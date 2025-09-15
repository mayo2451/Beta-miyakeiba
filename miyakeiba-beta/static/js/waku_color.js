document.querySelectorAll(".uma").forEach(row => {
	const numStr = row.dataset.uman;
	const totalStr = row.dataset.total;

	if (!numStr || !totalStr) return;
	
	const num = parseInt(numStr);
	const total = parseInt(totalStr);
	let colorClass = "";

	if (total === 18) {
		if ([1,2].includes(num)) colorClass = "waku-1";
		if ([3,4].includes(num)) colorClass = "waku-2";
		if ([5,6].includes(num)) colorClass = "waku-3";
		if ([7,8].includes(num)) colorClass = "waku-4";
		if ([9,10].includes(num)) colorClass = "waku-5";
		if ([11,12].includes(num)) colorClass = "waku-6";
		if ([13,14,15].includes(num)) colorClass = "waku-7";
		if ([16,17,18].includes(num)) colorClass = "waku-8";
	} else if (total === 17) {
		if ([1,2].includes(num)) colorClass = "waku-1";
		if ([3,4].includes(num)) colorClass = "waku-2";
		if ([5,6].includes(num)) colorClass = "waku-3";
		if ([7,8].includes(num)) colorClass = "waku-4";
		if ([9,10].includes(num)) colorClass = "waku-5";
		if ([11,12].includes(num)) colorClass = "waku-6";
		if ([13,14].includes(num)) colorClass = "waku-7";
		if ([15,16,17].includes(num)) colorClass = "waku-8";
	} else if (total === 16) {
		if ([1,2].includes(num)) colorClass = "waku-1";
		if ([3,4].includes(num)) colorClass = "waku-2";
		if ([5,6].includes(num)) colorClass = "waku-3";
		if ([7,8].includes(num)) colorClass = "waku-4";
		if ([9,10].includes(num)) colorClass = "waku-5";
		if ([11,12].includes(num)) colorClass = "waku-6";
		if ([13,14].includes(num)) colorClass = "waku-7";
		if ([15,16].includes(num)) colorClass = "waku-8";
	} else if (total === 15) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2,3].includes(num)) colorClass = "waku-2";
		if ([4,5].includes(num)) colorClass = "waku-3";
		if ([6,7].includes(num)) colorClass = "waku-4";
		if ([8,9].includes(num)) colorClass = "waku-5";
		if ([10,11].includes(num)) colorClass = "waku-6";
		if ([12,13].includes(num)) colorClass = "waku-7";
		if ([14,15].includes(num)) colorClass = "waku-8";
	} else if (total === 14) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3,4].includes(num)) colorClass = "waku-3";
		if ([5,6].includes(num)) colorClass = "waku-4";
		if ([7,8].includes(num)) colorClass = "waku-5";
		if ([9,10].includes(num)) colorClass = "waku-6";
		if ([11,12].includes(num)) colorClass = "waku-7";
		if ([13,14].includes(num)) colorClass = "waku-8";
	} else if (total === 13) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4,5].includes(num)) colorClass = "waku-4";
		if ([6,7].includes(num)) colorClass = "waku-5";
		if ([8,9].includes(num)) colorClass = "waku-6";
		if ([10,11].includes(num)) colorClass = "waku-7";
		if ([12,13].includes(num)) colorClass = "waku-8";
	} else if (total === 12) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5,6].includes(num)) colorClass = "waku-5";
		if ([7,8].includes(num)) colorClass = "waku-6";
		if ([9,10].includes(num)) colorClass = "waku-7";
		if ([11,12].includes(num)) colorClass = "waku-8";
	} else if (total === 11) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5].includes(num)) colorClass = "waku-5";
		if ([6,7].includes(num)) colorClass = "waku-6";
		if ([8,9].includes(num)) colorClass = "waku-7";
		if ([10,11].includes(num)) colorClass = "waku-8";
	} else if (total === 10) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5].includes(num)) colorClass = "waku-5";
		if ([6].includes(num)) colorClass = "waku-6";
		if ([7,8].includes(num)) colorClass = "waku-7";
		if ([9,10].includes(num)) colorClass = "waku-8";
	} else if (total === 9) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5].includes(num)) colorClass = "waku-5";
		if ([6].includes(num)) colorClass = "waku-6";
		if ([7].includes(num)) colorClass = "waku-7";
		if ([8,9].includes(num)) colorClass = "waku-8";
	} else if (total === 8) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5].includes(num)) colorClass = "waku-5";
		if ([6].includes(num)) colorClass = "waku-6";
		if ([7].includes(num)) colorClass = "waku-7";
		if ([8].includes(num)) colorClass = "waku-8";
	} else if (total === 7) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5].includes(num)) colorClass = "waku-5";
		if ([6].includes(num)) colorClass = "waku-6";
		if ([7].includes(num)) colorClass = "waku-7";
	} else if (total === 6) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5].includes(num)) colorClass = "waku-5";
		if ([6].includes(num)) colorClass = "waku-6";
	} else if (total === 5) {
		if ([1].includes(num)) colorClass = "waku-1";
		if ([2].includes(num)) colorClass = "waku-2";
		if ([3].includes(num)) colorClass = "waku-3";
		if ([4].includes(num)) colorClass = "waku-4";
		if ([5].includes(num)) colorClass = "waku-5";
  	}

	if (colorClass) {
		row.classList.add(colorClass);
		const tds = row.querySelectorAll("td");
		if (tds.length >= 4) {
			tds[0].classList.add(colorClass, "soft-bg");
			tds[1].classList.add(colorClass, "soft-bg");
			tds[2].classList.add(colorClass, "soft-bg");
			tds[3].classList.add(colorClass, "soft-bg");
		}
	}
});
