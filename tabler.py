"""
从同目录下的 selected_song.db 读取数据，导出为 BMS 难易度表标准 JSON 格式。

输出: data.json

用法:
    python export_json.py

要求:
    selected_song.db 与脚本位于同一目录
"""

import json
import re
import sqlite3
from pathlib import Path
from typing import Optional
from collections import Counter


# ============ 常量 ============
# sl- / st+ 区间标记（纯前缀，后面无数字）
RANGE_PATTERN = re.compile(r'^(sl-|st\+)$', re.IGNORECASE)

# sl<数值> / st<数值>（允许负数）
NUM_PATTERN = re.compile(r'^(sl|st)(-?\d+(?:\.\d+)?)$', re.IGNORECASE)

# 标签文本
TAG_FAILED = "FAILED"      # 无分析结果
LEVEL_UNKNOWN = "?"        # 未分析时 level 显示符号


# ============ level 提取 ============
def extract_level(
    tag_value: Optional[str],
    is_ln: int,
    is_sc: int,
    is_no_song: int = 0,
) -> str:
    """
    规则（优先级）:
        1. is_no_song = 1 -> "NO SONG"
        2. is_ln = 1      -> "LN"
        3. is_sc = 1      -> "SC"
        4. tag 段等于 "sl-"  -> "sl-"
        5. tag 段等于 "st+"  -> "st+"
        6. tag 段为 "sl12.5" -> "st0"
        7. tag 段为 sl<数值> / st<数值>：
             负数   -> "st0" / "sl0"
             非负数 -> 四舍五入，封顶 12
        8. 找不到 -> ""
    """
    if is_no_song:
        return "NO SONG"
    if is_ln:
        return "LN"
    if is_sc:
        return "SC"
    if not tag_value:
        return ""

    parts = [p.strip() for p in str(tag_value).split("/") if p.strip()]

    for part in parts:
        # ---- 1. sl- / st+ 纯前缀 ----
        m_range = RANGE_PATTERN.match(part)
        if m_range:
            prefix = m_range.group(1).lower()
            if prefix == "sl-":
                return "sl-"
            if prefix == "st+":
                return "st+"

        # ---- 2. sl<数值> / st<数值> ----
        m_num = NUM_PATTERN.match(part)
        if not m_num:
            continue

        prefix = m_num.group(1).lower()
        num_str = m_num.group(2)

        try:
            num = float(num_str)
        except ValueError:
            continue

        # 2.1 sl12.5 -> st0 特判
        if prefix == "sl" and num_str == "12.5":
            return "st0"

        # 2.2 负数 -> st0 / sl0
        if num < 0:
            return f"{prefix}0"

        # 2.3 四舍五入 + 封顶 12
        level_int = int(num + 0.5)
        if level_int > 12:
            level_int = 12

        return f"{prefix}{level_int}"

    return ""


# ============ 读取数据库 ============
def load_records(db_path: Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute('SELECT * FROM "selected_song"')
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


# ============ 导出 JSON ============
def export_json(db_path: Path, output_path: Path) -> Path:
    records = load_records(db_path)

    data = []
    for r in records:
        title = r.get("full_title") or r.get("title") or ""
        artist = r.get("full_artist") or r.get("artist") or ""

        level = extract_level(
            tag_value=r.get("tag"),
            is_ln=r.get("is_ln") or 0,
            is_sc=r.get("is_sc") or 0,
            is_no_song=r.get("is_no_song") or 0,
        )

        # comment 直接沿用 selected_song.db 的 tag
        comment = r.get("tag") or ""

        # ---- chart_tag 处理 ----
        raw_chart_tag = (r.get("chart_tag") or "").strip()
        chart_tags = [t.strip() for t in raw_chart_tag.split("/") if t.strip()]

        # 没有分析结果（level 为空，且不是 NO SONG）
        # -> level 记为 "?"，chart_tag 追加 "FAILED"
        if not level and not (r.get("is_no_song") or 0):
            level = LEVEL_UNKNOWN
            if TAG_FAILED not in chart_tags:
                chart_tags.append(TAG_FAILED)

        chart_tag_str = "/".join(chart_tags)

        data.append({
            "md5": r.get("md5") or "",
            "sha256": r.get("sha256") or "",
            "title": title,
            "artist": artist,
            "level": level,
            "url": "",
            "url_diff": "",
            "comment": comment,
            "chart_tag": chart_tag_str,
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已导出 JSON: {output_path}")
    print(f"共 {len(data)} 条记录")

    # level 分布
    level_counter = Counter(item["level"] for item in data)
    print("level 分布:")
    for level, cnt in sorted(level_counter.items(), key=lambda x: (x[0] == "", x[0])):
        display = level if level else "(空)"
        print(f"  {display:10s}: {cnt}")

    # chart_tag 中 "FAILED" 统计
    failed_count = sum(
        1 for item in data
        if TAG_FAILED in [t.strip() for t in (item["chart_tag"] or "").split("/")]
    )
    print(f"{TAG_FAILED}: {failed_count} 条")

    return output_path


# ============ 入口 ============
if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    db_path = script_dir / "selected_song.db"
    output_path = script_dir / "data.json"

    if not db_path.exists():
        print(f"错误: 找不到数据库 {db_path}")
        print("请把本脚本放在 selected_song.db 同目录下运行。")
        raise SystemExit(1)

    try:
        export_json(db_path, output_path)
        print(f"\n完成！")
    except Exception as e:
        print(f"发生错误: {e}")
        raise