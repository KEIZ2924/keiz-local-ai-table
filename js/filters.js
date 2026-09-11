const Filters = {
    level: "",
    tag: "",
    search: "",

    apply(songs) {
        return songs.filter(s => this.matches(s));
    },

    matches(song) {
        if (this.level && song.level !== this.level) return false;

        if (this.tag) {
            const tags = (song.chart_tag || "").split("/").map(t => t.trim());
            if (!tags.includes(this.tag)) return false;
        }

        if (this.search) {
            const q = this.search.toLowerCase();
            const hay = [
                song.title || "",
                song.artist || "",
                song.md5 || "",
            ].join("\n").toLowerCase();
            if (!hay.includes(q)) return false;
        }

        return true;
    },

    reset() {
        this.level = "";
        this.tag = "";
        this.search = "";
    },
};