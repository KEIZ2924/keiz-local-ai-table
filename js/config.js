// 全局配置
const CONFIG = {
    dataUrl: "data.json",
    headerUrl: "header.json",

    // 默认每页条数
    defaultPageSize: 50,

    // 默认排序
    defaultSort: { key: "level", order: "asc" },

    // level 排序权重（用于 level 列排序）
    // 未列出的 level 会排在末尾
    levelOrder: null,  // 会从 header.json 的 level_order 读取
};