const Table = {
    tbody: null,
    emptyState: null,

    TAG_DISPLAY: {
        "未収録": "Unrecorded",
        "FAILED": "FAILED",
    },

    BMS_IR_URL: "https://www.bms-ir.org/new/song?songmd5=",

    init() {
        this.tbody = document.getElementById("song-tbody");
        this.emptyState = document.getElementById("empty-state");
    },

    render(songs) {
        if (!this.tbody) return;
        this.tbody.innerHTML = "";

        if (songs.length === 0) {
            this.emptyState.hidden = false;
            return;
        }
        this.emptyState.hidden = true;

        const frag = document.createDocumentFragment();
        for (const song of songs) {
            frag.appendChild(this.buildRow(song));
        }
        this.tbody.appendChild(frag);
    },

    buildRow(song) {
        const tr = document.createElement("tr");

        // level
        const tdLevel = document.createElement("td");
        tdLevel.appendChild(this.buildLevelBadge(song.level));
        tr.appendChild(tdLevel);

        // title（超链接）
        const tdTitle = document.createElement("td");
        tdTitle.appendChild(this.buildTitleLink(song));
        tr.appendChild(tdTitle);

        // artist
        const tdArtist = document.createElement("td");
        tdArtist.textContent = song.artist || "";
        tdArtist.title = song.artist || "";
        tr.appendChild(tdArtist);

        // tags
        const tdTags = document.createElement("td");
        if (song.chart_tag) {
            for (const tag of song.chart_tag.split("/")) {
                const t = tag.trim();
                if (!t) continue;
                const span = document.createElement("span");
                span.className = "tag-badge";
                if (t === "未収録") {
                    span.classList.add("tag-unrecorded");
                } else if (t === "FAILED") {
                    span.classList.add("tag-failed");
                }
                span.textContent = this.TAG_DISPLAY[t] || t;
                tdTags.appendChild(span);
            }
        }
        tr.appendChild(tdTags);

        // comment
        const tdComment = document.createElement("td");
        tdComment.textContent = song.comment || "";
        tdComment.title = song.comment || "";
        tr.appendChild(tdComment);

        return tr;
    },

    buildTitleLink(song) {
        const a = document.createElement("a");
        a.className = "title-link";
        a.textContent = song.title || "";
        a.title = song.title || "";
        if (song.md5) {
            a.href = this.BMS_IR_URL + encodeURIComponent(song.md5);
            a.target = "_blank";
            a.rel = "noopener noreferrer";
        }
        return a;
    },

    buildLevelBadge(level) {
        const span = document.createElement("span");
        span.className = "level-badge";
        if (!level) {
            span.textContent = "-";
            return span;
        }
        const lower = level.toLowerCase();
        if (lower === "ln") {
            span.classList.add("level-ln");
        } else if (lower === "sc") {
            span.classList.add("level-sc");
        } else if (lower === "no song") {
            span.classList.add("level-nosong");
        } else if (lower === "?") {
            span.classList.add("level-unknown");
        }
        span.textContent = level;
        return span;
    },
};