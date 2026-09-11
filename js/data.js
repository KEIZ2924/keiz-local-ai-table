const DataStore = {
    songs: [],
    header: {},

    async load() {
        const [songsRes, headerRes] = await Promise.all([
            fetch(CONFIG.dataUrl).then(r => {
                if (!r.ok) throw new Error(`data.json load failed: ${r.status}`);
                return r.json();
            }),
            fetch(CONFIG.headerUrl).then(r => {
                if (!r.ok) return {};
                return r.json();
            }).catch(() => ({})),
        ]);

        this.songs = songsRes;
        this.header = headerRes || {};
    },

    getAllLevels() {
        const levels = new Set();
        for (const s of this.songs) {
            if (s.level) levels.add(s.level);
        }
        const arr = Array.from(levels);
        arr.sort((a, b) => levelWeight(a) - levelWeight(b));
        return arr;
    },

    getAllTags() {
        const tags = new Set();
        for (const s of this.songs) {
            if (!s.chart_tag) continue;
            for (const t of s.chart_tag.split("/")) {
                const trimmed = t.trim();
                if (trimmed) tags.add(trimmed);
            }
        }
        return Array.from(tags).sort();
    },
};

function levelWeight(level) {
    if (!level) return 9999;
    const s = level.toLowerCase().trim();

    if (s === "no song") return 4000;
    if (s === "ln") return 3000;
    if (s === "sc") return 3100;
    if (s === "?") return 4500;

    if (s === "sl-") return 900;
    if (s === "st+") return 1950;

    let m = s.match(/^sl(\d+)/);
    if (m) return 1000 + parseInt(m[1], 10);

    m = s.match(/^st(\d+)/);
    if (m) return 2000 + parseInt(m[1], 10);

    return 9999;
}