let LEVEL_ORDER = []; // 用于存储 header.json 里的 level_order 排序规则

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

        // 读取 header.json 里的 level_order 存入全局变量
        if (header.level_order && Array.isArray(header.level_order)) {
            LEVEL_ORDER = header.level_order;
        }

        const tableName = document.getElementById("table-name");
        // 不再显示 Symbol，仅设置标题
        if (header.name) tableName.textContent = header.name;

        Table.init();
        this.initFilterOptions();
        this.bindEvents();

        const sortKey = CONFIG.defaultSort.key;
        const sortOrder = CONFIG.defaultSort.order;
        this.sortSongs(sortKey, sortOrder);
        this.updateSortIndicators(sortKey, sortOrder);

        this.refresh();
    },

    initFilterOptions() {
        const levelSelect = document.getElementById("filter-level");

        // 优先使用 header.json 里的 level_order 生成下拉菜单
        if (LEVEL_ORDER.length > 0) {
            for (const level of LEVEL_ORDER) {
                const opt = document.createElement("option");
                opt.value = level;
                opt.textContent = level;
                levelSelect.appendChild(opt);
            }
        } else {
            // 备用方案：如果 header.json 没读到，按数据里出现的顺序
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

        // 已移除 filter-comment 绑定

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
                // 使用 header.json 里的 level_order 索引作为排序权重
                let indexA = LEVEL_ORDER.indexOf(va);
                let indexB = LEVEL_ORDER.indexOf(vb);

                // 如果数据里的 level 不在 header.json 列表里，放到最后
                if (indexA === -1) indexA = 9999;
                if (indexB === -1) indexB = 9999;

                return (indexA - indexB) * dir;
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