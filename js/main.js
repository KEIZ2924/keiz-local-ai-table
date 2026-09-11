let LEVEL_ORDER = []; // 用于存储 header.json 里的 level_order 排序规则

// Tag 列排序权重（按第一个标签）
const TAG_ORDER = [
    "LN",
    "SC",
    "SB",
    "6K",
    "8K",
    "未収録",
    "FAILED",
];

function tagWeight(tagStr) {
    if (!tagStr) return 9999;
    const first = String(tagStr).split("/")[0].trim();
    const idx = TAG_ORDER.indexOf(first);
    return idx === -1 ? 5000 : idx;
}

const App = {
    filtered: [],

    async init() {
        try {
            await DataStore.load();
        } catch (e) {
            console.error(e);
            alert("Failed to load data: " + e.message);
            return;
        }

        const header = DataStore.header || {};

        if (header.level_order && Array.isArray(header.level_order)) {
            LEVEL_ORDER = header.level_order;
        }

        const tableName = document.getElementById("table-name");
        if (header.name) tableName.textContent = header.name;

        Table.init();
        this.initFilterOptions();
        this.bindEvents();
        await this.loadAbout();        // ★ 新增

        const sortKey = CONFIG.defaultSort.key;
        const sortOrder = CONFIG.defaultSort.order;
        this.sortSongs(sortKey, sortOrder);
        this.updateSortIndicators(sortKey, sortOrder);

        this.refresh();
    },

    // ★ 新增方法
    async loadAbout() {
        const aboutContent = document.getElementById("about-content");
        if (!aboutContent) return;

        try {
            const res = await fetch("README.md");
            if (!res.ok) throw new Error(`README.md load failed: ${res.status}`);
            const md = await res.text();

            if (typeof marked !== "undefined") {
                aboutContent.innerHTML = marked.parse(md);
            } else {
                aboutContent.textContent = md;
            }
        } catch (e) {
            aboutContent.innerHTML =
                `<p class="error">Failed to load README.md: ${e.message}</p>`;
        }
    },

    initFilterOptions() {
        const levelSelect = document.getElementById("filter-level");

        if (LEVEL_ORDER.length > 0) {
            for (const level of LEVEL_ORDER) {
                const opt = document.createElement("option");
                opt.value = level;
                opt.textContent = level;
                levelSelect.appendChild(opt);
            }
        } else {
            for (const level of DataStore.getAllLevels()) {
                const opt = document.createElement("option");
                opt.value = level;
                opt.textContent = level;
                levelSelect.appendChild(opt);
            }
        }

        const tagSelect = document.getElementById("filter-tag");
        for (const tag of DataStore.getAllTags()) {
            const opt = document.createElement("option");
            opt.value = tag;
            opt.textContent = Table.TAG_DISPLAY[tag] || tag;
            tagSelect.appendChild(opt);
        }

        const pageSizeSelect = document.getElementById("page-size");
        pageSizeSelect.value = String(Pagination.pageSize);
    },

    bindEvents() {
        document.getElementById("filter-level").addEventListener("change", e => {
            Filters.level = e.target.value;
            Pagination.reset();
            this.refresh();
        });

        document.getElementById("filter-tag").addEventListener("change", e => {
            Filters.tag = e.target.value;
            Pagination.reset();
            this.refresh();
        });

        let searchTimer = null;
        document.getElementById("search-input").addEventListener("input", e => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                Filters.search = e.target.value.trim();
                Pagination.reset();
                this.refresh();
            }, 200);
        });

        document.getElementById("reset-btn").addEventListener("click", () => {
            Filters.reset();
            Pagination.reset();
            document.getElementById("filter-level").value = "";
            document.getElementById("filter-tag").value = "";
            document.getElementById("search-input").value = "";
            this.refresh();
        });

        document.getElementById("first-page").addEventListener("click", () => {
            Pagination.page = 1;
            this.renderPage();
        });
        document.getElementById("prev-page").addEventListener("click", () => {
            if (Pagination.page > 1) Pagination.page--;
            this.renderPage();
        });
        document.getElementById("next-page").addEventListener("click", () => {
            if (Pagination.page < Pagination.totalPages) Pagination.page++;
            this.renderPage();
        });
        document.getElementById("last-page").addEventListener("click", () => {
            Pagination.page = Pagination.totalPages;
            this.renderPage();
        });

        document.getElementById("page-size").addEventListener("change", e => {
            Pagination.pageSize = parseInt(e.target.value, 10);
            Pagination.reset();
            this.renderPage();
        });

        document.querySelectorAll("th.sortable").forEach(th => {
            th.addEventListener("click", () => {
                const key = th.dataset.sort;
                const current = th.dataset.order;
                const nextOrder = current === "asc" ? "desc" : "asc";
                this.sortSongs(key, nextOrder);
                this.updateSortIndicators(key, nextOrder);
                Pagination.reset();
                this.refresh();
            });
        });
    },

    sortSongs(key, order) {
        const dir = order === "desc" ? -1 : 1;

        DataStore.songs.sort((a, b) => {
            const va = a[key] || "";
            const vb = b[key] || "";

            if (key === "level") {
                let indexA = LEVEL_ORDER.indexOf(va);
                let indexB = LEVEL_ORDER.indexOf(vb);
                if (indexA === -1) indexA = 9999;
                if (indexB === -1) indexB = 9999;
                return (indexA - indexB) * dir;
            }

            if (key === "chart_tag") {
                if (!va && !vb) return 0;
                if (!va) return 1;
                if (!vb) return -1;
                return (tagWeight(va) - tagWeight(vb)) * dir;
            }

            if (key === "comment") {
                if (!va && !vb) return 0;
                if (!va) return 1;
                if (!vb) return -1;
                return String(va).localeCompare(String(vb), "ja") * dir;
            }

            return String(va).localeCompare(String(vb), "ja") * dir;
        });
    },

    updateSortIndicators(activeKey, order) {
        document.querySelectorAll("th.sortable").forEach(th => {
            if (th.dataset.sort === activeKey) {
                th.dataset.order = order;
            } else {
                delete th.dataset.order;
            }
        });
    },

    refresh() {
        this.filtered = Filters.apply(DataStore.songs);
        Pagination.setTotal(this.filtered.length);
        this.renderPage();
    },

    renderPage() {
        const pageData = Pagination.slice(this.filtered);
        Table.render(pageData);

        document.getElementById("total-count").textContent =
            `${this.filtered.length} songs`;

        document.getElementById("page-info").textContent =
            `Page ${Pagination.page} / ${Pagination.totalPages}`;

        const atFirst = Pagination.page <= 1;
        const atLast = Pagination.page >= Pagination.totalPages;
        document.getElementById("first-page").disabled = atFirst;
        document.getElementById("prev-page").disabled = atFirst;
        document.getElementById("next-page").disabled = atLast;
        document.getElementById("last-page").disabled = atLast;

        document.getElementById("footer-info").textContent =
            `${DataStore.songs.length} songs · showing ${pageData.length}`;
    },
};

document.addEventListener("DOMContentLoaded", () => App.init());