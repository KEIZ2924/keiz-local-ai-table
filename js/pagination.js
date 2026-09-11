// 分页状态

const Pagination = {
    page: 1,
    pageSize: CONFIG.defaultPageSize,
    total: 0,

    get totalPages() {
        return Math.max(1, Math.ceil(this.total / this.pageSize));
    },

    setTotal(n) {
        this.total = n;
        // 页码越界修正
        const maxPage = this.totalPages;
        if (this.page > maxPage) this.page = maxPage;
        if (this.page < 1) this.page = 1;
    },

    // 对给定数组做分页，返回当前页的切片
    slice(songs) {
        const start = (this.page - 1) * this.pageSize;
        return songs.slice(start, start + this.pageSize);
    },

    reset() {
        this.page = 1;
    },
};