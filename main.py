import sqlite3
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable, Set


# ============ 标签阈值常量 ============
LN_RATIO_THRESHOLD = 0.05
SC_RATIO_SB_MIN = 0.075
SC_RATIO_SC_MIN = 0.15

# tag 解析关键词
TAG_PREFIX_ST = "st"
TAG_PREFIX_MANJI = "卍"

# 标签文本
TAG_LN = "LN"
TAG_SB = "SB"
TAG_SC = "SC"
TAG_UNRECORDED = "未収録"
TAG_NO_SONG = "NO SONG"
TAG_6K = "6K"
TAG_8K = "8K"

TAG_SEP = "/"

# ============ 6K / 8K 对应的 playlist_id ============
PLAYLIST_ID_6K = 108
PLAYLIST_ID_8K = 109

# ============ NO SONG 来源 playlist 白名单 ============
NO_SONG_PLAYLIST_IDS: set[int] = {51, 54, 61, 62, 82, 87,92,100, 103, 107}


@dataclass
class ChartRecord:
    md5: str
    title: str
    subtitle: str
    artist: str
    subartist: str
    path: Optional[str]
    tag: Optional[str]
    sha256: Optional[str]
    n: Optional[int]
    ln: Optional[int]
    s: Optional[int]
    ls: Optional[int]
    mode: Optional[int]
    playlist_symbols: List[str] = field(default_factory=list)
    playlist_ids: List[int] = field(default_factory=list)   # 新增：所属 playlist_id 集合

    chart_tags: List[str] = field(default_factory=list)
    is_ln: int = 0
    is_sb: int = 0
    is_sc: int = 0
    is_unrecorded: int = 0
    is_no_song: int = 0
    is_6k: int = 0
    is_8k: int = 0

    @property
    def full_title(self) -> str:
        return f"{self.title} {self.subtitle}".strip() if self.subtitle else self.title

    @property
    def full_artist(self) -> str:
        return f"{self.artist} {self.subartist}".strip() if self.subartist else self.artist

    @property
    def playlist_symbols_str(self) -> str:
        return ",".join(self.playlist_symbols) if self.playlist_symbols else ""

    @property
    def playlist_ids_str(self) -> str:
        return ",".join(str(i) for i in sorted(self.playlist_ids)) if self.playlist_ids else ""

    @property
    def chart_tag_str(self) -> str:
        return TAG_SEP.join(self.chart_tags) if self.chart_tags else ""


# ============ 标签规则 ============
TagRule = Callable[[ChartRecord], bool]
TAG_RULES: List[tuple[str, TagRule]] = []


def register_tag(name: str):
    def deco(fn: TagRule):
        TAG_RULES.append((name, fn))
        return fn
    return deco


@register_tag(TAG_LN)
def rule_ln(rec: ChartRecord) -> bool:
    n, ln, s, ls = rec.n or 0, rec.ln or 0, rec.s or 0, rec.ls or 0
    total = n + ln + s + ls
    if total <= 0:
        return False
    return (ln + ls) / total > LN_RATIO_THRESHOLD


@register_tag(TAG_SB)
def rule_sb(rec: ChartRecord) -> bool:
    n, ln, s, ls = rec.n or 0, rec.ln or 0, rec.s or 0, rec.ls or 0
    total = n + ln + s + ls
    if total <= 0:
        return False
    ratio = (s + ls) / total
    return SC_RATIO_SB_MIN <= ratio < SC_RATIO_SC_MIN


@register_tag(TAG_SC)
def rule_sc(rec: ChartRecord) -> bool:
    n, ln, s, ls = rec.n or 0, rec.ln or 0, rec.s or 0, rec.ls or 0
    total = n + ln + s + ls
    if total <= 0:
        return False
    return (s + ls) / total >= SC_RATIO_SC_MIN


# ---- 6K / 8K：根据 playlist_id 判断 ----
@register_tag(TAG_6K)
def rule_6k(rec: ChartRecord) -> bool:
    """包含于 playlist_id = 108 即标记为 6K"""
    return PLAYLIST_ID_6K in rec.playlist_ids


@register_tag(TAG_8K)
def rule_8k(rec: ChartRecord) -> bool:
    """包含于 playlist_id = 109 即标记为 8K"""
    return PLAYLIST_ID_8K in rec.playlist_ids


def is_unrecorded_tag(tag_value: Optional[str]) -> bool:
    """解析 tag 字段，判断是否为"未収録"状态"""
    if not tag_value:
        return False
    parts = [p.strip() for p in str(tag_value).split(TAG_SEP) if p.strip()]
    if not parts:
        return False
    has_st = any(p.startswith(TAG_PREFIX_ST) for p in parts)
    has_manji = any(p.startswith(TAG_PREFIX_MANJI) for p in parts)
    return has_st and not has_manji


@register_tag(TAG_UNRECORDED)
def rule_unrecorded(rec: ChartRecord) -> bool:
    # 只要属于 6K 或 8K 其中之一（满足一个即可），就不标记未収録
    if PLAYLIST_ID_6K in rec.playlist_ids or PLAYLIST_ID_8K in rec.playlist_ids:
        return False
    return is_unrecorded_tag(rec.tag)


@register_tag(TAG_NO_SONG)
def rule_no_song(rec: ChartRecord) -> bool:
    return not rec.path or not str(rec.path).strip()


def compute_all_tags(record: ChartRecord) -> List[str]:
    return [name for name, fn in TAG_RULES if fn(record)]


def apply_tags(record: ChartRecord) -> None:
    tags = compute_all_tags(record)
    record.chart_tags = tags
    record.is_ln = int(TAG_LN in tags)
    record.is_sb = int(TAG_SB in tags)
    record.is_sc = int(TAG_SC in tags)
    record.is_unrecorded = int(TAG_UNRECORDED in tags)
    record.is_no_song = int(TAG_NO_SONG in tags)
    record.is_6k = int(TAG_6K in tags)
    record.is_8k = int(TAG_8K in tags)


# ============ Playlist 映射（symbol + playlist_id） ============
def build_playlist_maps(
    conn: sqlite3.Connection
) -> tuple[Dict[str, List[str]], Dict[str, Set[int]]]:
    """
    返回两个映射：
        md5 -> [symbol, ...]
        md5 -> {playlist_id, ...}
    """
    playlist_map: Dict[str, List[str]] = {}
    playlist_ids_map: Dict[str, Set[int]] = {}
    cur = conn.cursor()

    try:
        cur.execute('PRAGMA table_info("playlist_entry")')
        pe_cols = {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        print("警告: playlist_entry 表不存在，跳过 playlist 关联")
        return playlist_map, playlist_ids_map

    pe_playlist_field = None
    for cand in ("playlist_id", "playlist", "pid"):
        if cand in pe_cols:
            pe_playlist_field = cand
            break
    if pe_playlist_field is None:
        print("警告: playlist_entry 表找不到 playlist_id 字段")
        return playlist_map, playlist_ids_map

    pe_md5_field = "md5" if "md5" in pe_cols else None
    if pe_md5_field is None:
        print("警告: playlist_entry 表找不到 md5 字段")
        return playlist_map, playlist_ids_map

    try:
        cur.execute('PRAGMA table_info("playlist")')
        p_cols = {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        print("警告: playlist 表不存在，跳过 playlist 关联")
        return playlist_map, playlist_ids_map

    p_id_field = None
    for cand in ("id", "playlist_id", "pid"):
        if cand in p_cols:
            p_id_field = cand
            break
    if p_id_field is None:
        print("警告: playlist 表找不到 id 字段")
        return playlist_map, playlist_ids_map

    if "symbol" not in p_cols:
        print("警告: playlist 表找不到 symbol 字段")
        return playlist_map, playlist_ids_map

    # ---- 1. md5 -> playlist_id 集合 ----
    sql_ids = f"""
    SELECT pe."{pe_md5_field}" AS md5,
           pe."{pe_playlist_field}" AS pid
    FROM "playlist_entry" pe
    WHERE pe."{pe_md5_field}" IS NOT NULL
      AND TRIM(pe."{pe_md5_field}") <> ''
    """
    try:
        cur.execute(sql_ids)
        for md5, pid in cur.fetchall():
            md5 = str(md5).strip()
            if not md5:
                continue
            try:
                pid_int = int(pid)
            except (TypeError, ValueError):
                continue
            playlist_ids_map.setdefault(md5, set()).add(pid_int)
    except sqlite3.OperationalError as e:
        print(f"警告: 读取 playlist_id 失败: {e}")

    # ---- 2. md5 -> symbol ----
    sql_sym = f"""
    SELECT pe."{pe_md5_field}" AS md5,
           p."symbol"         AS symbol
    FROM "playlist_entry" pe
    INNER JOIN "playlist" p
        ON pe."{pe_playlist_field}" = p."{p_id_field}"
    WHERE pe."{pe_md5_field}" IS NOT NULL
      AND TRIM(pe."{pe_md5_field}") <> ''
      AND p."symbol" IS NOT NULL
      AND TRIM(p."symbol") <> ''
    """
    try:
        cur.execute(sql_sym)
        for md5, symbol in cur.fetchall():
            md5 = str(md5).strip()
            symbol = str(symbol).strip()
            if not md5 or not symbol:
                continue
            playlist_map.setdefault(md5, [])
            if symbol not in playlist_map[md5]:
                playlist_map[md5].append(symbol)
    except sqlite3.OperationalError as e:
        print(f"警告: 读取 playlist symbol 失败: {e}")

    print(f"已读取 playlist 映射: {len(playlist_map)} 个 md5 有关联 symbol, "
          f"{len(playlist_ids_map)} 个 md5 有关联 playlist_id")
    return playlist_map, playlist_ids_map


# ============ 主查询 ============
def extract_chart_data(db_path: str | Path) -> List[ChartRecord]:
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # ---- 探测 playlist_entry 字段 ----
    cur.execute('PRAGMA table_info("playlist_entry")')
    pe_cols = {row[1] for row in cur.fetchall()}
    pe_playlist_field = None
    for cand in ("playlist_id", "playlist", "pid"):
        if cand in pe_cols:
            pe_playlist_field = cand
            break
    if pe_playlist_field is None:
        raise RuntimeError("playlist_entry 表找不到 playlist_id 字段")

    # ---- 探测 song 表字段 ----
    cur.execute('PRAGMA table_info("song")')
    song_cols = {row[1] for row in cur.fetchall()}
    if "hash" not in song_cols:
        raise RuntimeError("song 表找不到 hash 字段")

    # ============ 子查询 1: 本地有的谱面 ============
    local_sql = r"""
        SELECT
            s."hash"            AS md5,
            s."title"           AS title,
            s."subtitle"        AS subtitle,
            s."artist"          AS artist,
            s."subartist"       AS subartist,
            s."path"            AS path,
            s."tag"             AS tag,
            ci."sha256"         AS sha256,
            ci."n"              AS n,
            ci."ln"             AS ln,
            ci."s"              AS s,
            ci."ls"             AS ls,
            ci."mode"           AS mode
        FROM "song" s
        INNER JOIN "chart_info" ci
            ON s."hash" = ci."md5"
        WHERE s."hash" IS NOT NULL
          AND TRIM(s."hash") <> ''
          AND ci."mode" = 7
          AND s."path" LIKE 'E:\!_BMS_\!SONGS\BMS!_PACK\%' ESCAPE '!'
    """

    # ============ 子查询 2: NO SONG ============
    if NO_SONG_PLAYLIST_IDS:
        no_song_ids = sorted(NO_SONG_PLAYLIST_IDS)
        placeholders = ",".join("?" for _ in no_song_ids)
        no_song_where = f'pe."{pe_playlist_field}" IN ({placeholders})'
        no_song_params: List[object] = list(no_song_ids)
    else:
        no_song_where = "1=0"
        no_song_params = []

    no_song_sql = f"""
        SELECT
            pe."md5"            AS md5,
            MIN(pe."title")     AS title,
            NULL                AS subtitle,
            MIN(pe."artist")    AS artist,
            NULL                AS subartist,
            NULL                AS path,
            NULL                AS tag,
            NULL                AS sha256,
            NULL                AS n,
            NULL                AS ln,
            NULL                AS s,
            NULL                AS ls,
            NULL                AS mode
        FROM "playlist_entry" pe
        WHERE pe."md5" IS NOT NULL
          AND TRIM(pe."md5") <> ''
          AND {no_song_where}
          AND NOT EXISTS (
              SELECT 1 FROM "song" s2
              WHERE s2."hash" = pe."md5"
          )
        GROUP BY pe."md5"
    """

    combined_sql = f"""
    SELECT * FROM (
        {local_sql}
        UNION ALL
        {no_song_sql}
    )
    GROUP BY md5
    """

    try:
        cur.execute(combined_sql, no_song_params)
        rows = cur.fetchall()
    except sqlite3.OperationalError as e:
        print(f"查询出错: {e}")
        conn.close()
        return []

    playlist_map, playlist_ids_map = build_playlist_maps(conn)

    results: List[ChartRecord] = []
    for row in rows:
        md5 = row["md5"]
        record = ChartRecord(
            md5=md5,
            title=row["title"] or "",
            subtitle=row["subtitle"] or "",
            artist=row["artist"] or "",
            subartist=row["subartist"] or "",
            path=row["path"],
            tag=row["tag"],
            sha256=row["sha256"],
            n=row["n"],
            ln=row["ln"],
            s=row["s"],
            ls=row["ls"],
            mode=row["mode"],
            playlist_symbols=playlist_map.get(md5, []),
            playlist_ids=sorted(playlist_ids_map.get(md5, set())),
        )
        apply_tags(record)
        results.append(record)

    conn.close()
    return results


# ============ 建库 ============
def create_selected_db(
    records: List[ChartRecord],
    output_filename: str = "selected_song.db",
) -> Path:
    script_dir = Path(__file__).resolve().parent
    output_db_path = script_dir / output_filename

    if output_db_path.exists():
        output_db_path.unlink()
        print(f"已删除已存在的旧文件: {output_db_path}")

    conn = sqlite3.connect(str(output_db_path))
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE "selected_song" (
            "md5"               TEXT PRIMARY KEY,
            "title"             TEXT,
            "subtitle"          TEXT,
            "artist"            TEXT,
            "subartist"         TEXT,
            "full_title"        TEXT,
            "full_artist"       TEXT,
            "path"              TEXT,
            "tag"               TEXT,
            "sha256"            TEXT,
            "n"                 INTEGER,
            "ln"                INTEGER,
            "s"                 INTEGER,
            "ls"                INTEGER,
            "mode"              INTEGER,
            "playlist_symbols"  TEXT,
            "playlist_ids"      TEXT,
            "chart_tag"         TEXT,
            "is_ln"             INTEGER DEFAULT 0,
            "is_sb"             INTEGER DEFAULT 0,
            "is_sc"             INTEGER DEFAULT 0,
            "is_unrecorded"     INTEGER DEFAULT 0,
            "is_no_song"        INTEGER DEFAULT 0,
            "is_6k"             INTEGER DEFAULT 0,
            "is_8k"             INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE "selected_song_tags" (
            "md5"  TEXT NOT NULL,
            "tag"  TEXT NOT NULL,
            PRIMARY KEY ("md5", "tag"),
            FOREIGN KEY ("md5") REFERENCES "selected_song"("md5") ON DELETE CASCADE
        )
    """)

    cur.execute('CREATE INDEX "idx_selected_path" ON "selected_song" ("path")')
    cur.execute('CREATE INDEX "idx_selected_playlist" ON "selected_song" ("playlist_symbols")')
    cur.execute('CREATE INDEX "idx_selected_playlist_ids" ON "selected_song" ("playlist_ids")')
    cur.execute('CREATE INDEX "idx_selected_tag" ON "selected_song" ("chart_tag")')
    cur.execute('CREATE INDEX "idx_selected_is_ln" ON "selected_song" ("is_ln")')
    cur.execute('CREATE INDEX "idx_selected_is_sb" ON "selected_song" ("is_sb")')
    cur.execute('CREATE INDEX "idx_selected_is_sc" ON "selected_song" ("is_sc")')
    cur.execute('CREATE INDEX "idx_selected_is_unrecorded" ON "selected_song" ("is_unrecorded")')
    cur.execute('CREATE INDEX "idx_selected_is_no_song" ON "selected_song" ("is_no_song")')
    cur.execute('CREATE INDEX "idx_selected_is_6k" ON "selected_song" ("is_6k")')
    cur.execute('CREATE INDEX "idx_selected_is_8k" ON "selected_song" ("is_8k")')
    cur.execute('CREATE INDEX "idx_tags_tag" ON "selected_song_tags" ("tag")')
    cur.execute('CREATE INDEX "idx_tags_md5" ON "selected_song_tags" ("md5")')

    insert_sql = """
    INSERT INTO "selected_song" (
        "md5", "title", "subtitle", "artist", "subartist",
        "full_title", "full_artist", "path", "tag",
        "sha256", "n", "ln", "s", "ls", "mode",
        "playlist_symbols", "playlist_ids", "chart_tag",
        "is_ln", "is_sb", "is_sc", "is_unrecorded", "is_no_song",
        "is_6k", "is_8k"
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    data = [
        (
            r.md5, r.title, r.subtitle, r.artist, r.subartist,
            r.full_title, r.full_artist, r.path, r.tag,
            r.sha256, r.n, r.ln, r.s, r.ls, r.mode,
            r.playlist_symbols_str, r.playlist_ids_str, r.chart_tag_str,
            r.is_ln, r.is_sb, r.is_sc, r.is_unrecorded, r.is_no_song,
            r.is_6k, r.is_8k,
        )
        for r in records
    ]
    cur.executemany(insert_sql, data)

    tag_rows = [
        (r.md5, tag)
        for r in records
        for tag in r.chart_tags
    ]
    cur.executemany(
        'INSERT INTO "selected_song_tags" ("md5", "tag") VALUES (?, ?)',
        tag_rows,
    )

    conn.commit()

    cur.execute('SELECT COUNT(*) FROM "selected_song"')
    count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM "selected_song" WHERE "is_no_song" = 1')
    no_song_count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM "selected_song" WHERE "is_no_song" = 0')
    local_count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM "selected_song" WHERE "is_6k" = 1')
    k6_count = cur.fetchone()[0]

    cur.execute('SELECT COUNT(*) FROM "selected_song" WHERE "is_8k" = 1')
    k8_count = cur.fetchone()[0]

    cur.execute("""
        SELECT "chart_tag", COUNT(*) FROM "selected_song"
        GROUP BY "chart_tag" ORDER BY COUNT(*) DESC
    """)
    tag_stats = cur.fetchall()

    cur.execute("""
        SELECT "tag", COUNT(*) FROM "selected_song_tags"
        GROUP BY "tag" ORDER BY COUNT(*) DESC
    """)
    tag_table_stats = cur.fetchall()

    conn.close()

    print(f"已生成新数据库: {output_db_path}")
    print(f"共写入 {count} 条记录（本地有: {local_count} 条，NO SONG: {no_song_count} 条）")
    print(f"其中 6K: {k6_count} 条，8K: {k8_count} 条")
    print("NO SONG 白名单 playlist_id:", sorted(NO_SONG_PLAYLIST_IDS))
    print("chart_tag（组合）分布:")
    for tag_value, cnt in tag_stats:
        display = tag_value if tag_value else "(空)"
        print(f"  {display:20s}: {cnt}")
    print("单标签分布（来自关联表）:")
    for tag_value, cnt in tag_table_stats:
        print(f"  {tag_value:20s}: {cnt}")

    return output_db_path


def print_summary(records: List[ChartRecord], limit: int = 10):
    print(f"共提取到 {len(records)} 条符合要求的谱面记录。")
    print("=" * 100)
    for i, rec in enumerate(records[:limit], 1):
        n, ln, s, ls = rec.n or 0, rec.ln or 0, rec.s or 0, rec.ls or 0
        total = n + ln + s + ls or 1
        print(f"[{i}] MD5: {rec.md5}")
        print(f"    标题: {rec.full_title}")
        print(f"    副标题: {rec.subtitle!r}")
        print(f"    路径: {rec.path!r}")
        print(f"    原始 tag: {rec.tag!r}")
        print(f"    N/LN/S/LS: {n}/{ln}/{s}/{ls}  "
              f"ln_ratio={(ln+ls)/total:.4f}  sc_ratio={(s+ls)/total:.4f}")
        print(f"    Playlist symbols: {', '.join(rec.playlist_symbols) if rec.playlist_symbols else '无'}")
        print(f"    Playlist IDs: {rec.playlist_ids_str or '无'}")
        print(f"    => chart_tag: {rec.chart_tag_str or '(空)'}")
        print(f"    => 布尔: is_ln={rec.is_ln} is_sb={rec.is_sb} "
              f"is_sc={rec.is_sc} is_unrecorded={rec.is_unrecorded} "
              f"is_no_song={rec.is_no_song} is_6k={rec.is_6k} is_8k={rec.is_8k}")
        print("-" * 60)
    if len(records) > limit:
        print(f"... 还有 {len(records) - limit} 条记录未显示。")


if __name__ == "__main__":
    DB_PATH = r"E:\_BMS_\_Lunatic Rave2_\LR2files\Database\song.db"

    try:
        records = extract_chart_data(DB_PATH)
        print_summary(records)

        if records:
            output_path = create_selected_db(records)
            print(f"\n完成！新数据库路径: {output_path}")
        else:
            print("没有符合条件的数据，未生成新数据库。")

    except FileNotFoundError as e:
        print(e)
    except Exception as e:
        print(f"发生错误: {e}")