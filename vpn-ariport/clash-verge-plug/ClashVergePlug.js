/**
 * Clash Verge 订阅扩展脚本
 * ---------------------------------------------------------------
 * 功能：
 *   1. 按地区自动建组（日本 / 新加坡 / 韩国 / 美国 …）
 *   2. 地区节点较多时，按【代理协议】再细分一层（SS / VMess / VLESS / HY2 …）
 *      例：🇯🇵 日本自动 → 🇯🇵 日本-SS、🇯🇵 日本-VMess、🇯🇵 日本-HY2
 *   3. 命中 excludeCN 的节点（香港 / 台湾 / 中国内地 …）全部归入 🇨🇳 国内自动
 *   4. 🌍 国外自动 汇总所有非国内节点，🌍 国外容灾 按地区顺序兜底
 *   5. 自动把这些组塞进主入口 select 组（如 🚀 节点选择）的最前面
 *
 * 入口函数：main(config)   —— Clash Verge Rev 脚本约定的唯一入口
 */

function main(config) {
    "use strict";

    /* ==================================================
     * 1. 全局配置（想改行为只动这里）
     * ================================================== */

    const SETTINGS = {

        // 测速地址
        testUrl: "https://cp.cloudflare.com/generate_204",

        // 测速周期（秒）
        interval: 300,

        // 允许延迟差（毫秒），差值小于它就不切换
        tolerance: 80,

        // 容灾组的健康检查周期（秒）
        fallbackInterval: 60,

        // 命中即视为「国内节点」：进 🇨🇳 国内自动，不进 国外自动
        // 想自己调整，改这个正则即可
        excludeCN: /香港|🇭🇰|HK|Hong\s*Kong|台湾|🇹🇼|🇨🇳|TW|Taiwan|中国|CN|China|内地/i,

        // 地区节点数 ≥ 该值 且 协议种类 ≥ 2 时，才按协议细分（太少细分没意义）
        subdivideMinNodes: 6,

        // 地区父组类型：
        //   "url-test" → 在子组里选延迟最低的（推荐）
        //   "fallback" → 按子组顺序容灾，前一个挂了才切下一个
        regionParentType: "url-test",

        // 是否把 🇨🇳 国内自动 注入主入口 select 组
        // 国内节点一般用来访问国内资源 / 落地，不需要的话设为 false
        injectCNGroup: true
    };

    /* ==================================================
     * 2. 固定组名
     * ================================================== */

    const NAME = {
        overseasAuto: "🌍 国外自动",
        overseasFailover: "🌍 国外容灾",
        cnAuto: "🇨🇳 国内自动"
    };

    /* ==================================================
     * 3. 地区规则
     *
     * key   = 父组名（脚本自动生成，订阅里已有同名组则跳过）
     * value = 关键字，命中任意一个即算该地区
     * 顺序 = 🌍 国外容灾 的兜底优先级
     * ================================================== */

    const REGION_RULES = {

        "🇯🇵 日本自动": [
            "日本", "🇯🇵", "JP", "Japan", "东京", "大阪", "埼玉"
        ],

        "🇸🇬 新加坡自动": [
            "新加坡", "🇸🇬", "SG", "Singapore", "狮城"
        ],

        "🇰🇷 韩国自动": [
            "韩国", "🇰🇷", "KR", "Korea", "首尔", "韓"
        ],

        "🇺🇸 美国自动": [
            "美国", "🇺🇸", "US", "USA", "United States", "洛杉矶", "圣何塞", "西雅图", "纽约", "达拉斯"
        ]

        // 需要更多地区，照抄一行即可，例如：
        // "🇬🇧 英国自动": ["英国", "🇬🇧", "UK", "GB", "London", "伦敦"],
        // "🇩🇪 德国自动": ["德国", "🇩🇪", "DE", "Germany", "法兰克福"]
    };

    /* ==================================================
     * 4. 协议显示名 / 排序
     * ================================================== */

    const PROTOCOL_LABEL = {
        ss: "SS",
        ssr: "SSR",
        vmess: "VMess",
        vless: "VLESS",
        trojan: "Trojan",
        hysteria: "Hysteria",
        hysteria2: "HY2",
        tuic: "TUIC",
        wireguard: "WG",
        snell: "Snell",
        anytls: "AnyTLS",
        mieru: "Mieru",
        http: "HTTP",
        socks5: "SOCKS5",
        ssh: "SSH"
    };

    // 越小越靠前（= 容灾优先 / 展示优先）
    const PROTOCOL_ORDER = [
        "hysteria2", "tuic", "vless", "vmess", "trojan",
        "ss", "ssr", "anytls", "snell", "hysteria",
        "wireguard", "mieru", "http", "socks5", "ssh"
    ];

    // 订阅里常见的「假节点」，直接丢掉
    const BLACKLIST = [
        "剩余", "流量", "官网", "订阅", "套餐", "到期", "重置", "DIRECT", "REJECT"
    ];

    /* ==================================================
     * 5. 工具函数
     * ================================================== */

    function log(msg) {
        try { console.log("[auto-group] " + msg); } catch (e) { /* 某些环境无 console */ }
    }

    // 短代码（JP / US / HK / CN …）要求独立出现，避免 US 命中 RUSSIA、HK 命中 SHKH
    function isShortCode(keyword) {
        return /^[a-z0-9]{1,3}$/i.test(keyword);
    }

    function matchesKeyword(name, keyword) {
        const k = String(keyword || "");
        if (!k) return false;

        const lower = name.toLowerCase();

        if (isShortCode(k)) {
            // 前后不能紧跟字母/数字
            const re = new RegExp("(^|[^a-z0-9])" + k.toLowerCase() + "([^a-z0-9]|$)");
            return re.test(lower);
        }

        return lower.indexOf(k.toLowerCase()) !== -1;
    }

    function matchAny(name, keywords) {
        for (let i = 0; i < keywords.length; i++) {
            if (matchesKeyword(name, keywords[i])) return true;
        }
        return false;
    }

    /* ==================================================
     * 6. 读取节点 & 清理
     * ================================================== */

    const proxies = config.proxies || [];

    if (!proxies.length) {
        log("没有节点，原样返回");
        return config;
    }

    // name -> 协议类型（订阅里 proxies[].type 是权威来源）
    const proxyType = {};
    proxies.forEach(p => {
        if (p && p.name) {
            proxyType[p.name] = String(p.type || "").toLowerCase();
        }
    });

    // 节点名里没有 type 时的兜底猜测
    function guessProtocol(name) {
        const n = name.toLowerCase();
        if (/hysteria2|hy2/.test(n)) return "hysteria2";
        if (/hysteria/.test(n)) return "hysteria";
        if (/tuic/.test(n)) return "tuic";
        if (/vless/.test(n)) return "vless";
        if (/vmess|v2ray/.test(n)) return "vmess";
        if (/trojan/.test(n)) return "trojan";
        if (/ssr/.test(n)) return "ssr";
        if (/shadowsocks|(^|[^a-z])ss([^a-z]|$)/.test(n)) return "ss";
        if (/wireguard|(^|[^a-z])wg([^a-z]|$)/.test(n)) return "wireguard";
        if (/anytls/.test(n)) return "anytls";
        if (/mieru/.test(n)) return "mieru";
        return "unknown";
    }

    function protocolOf(name) {
        return proxyType[name] || guessProtocol(name);
    }

    function protocolRank(p) {
        const i = PROTOCOL_ORDER.indexOf(p);
        return i === -1 ? PROTOCOL_ORDER.length : i;
    }

    const nodes = proxies
        .map(p => p.name)
        .filter(name => !BLACKLIST.some(k => name.indexOf(k) !== -1));

    if (!nodes.length) {
        log("节点被黑名单全部过滤，原样返回");
        return config;
    }

    /* ==================================================
     * 7. 组构造器
     * ================================================== */

    const oldGroups = config["proxy-groups"] || [];
    const newGroups = [];

    // 已存在的组名（订阅自带的），用来做「不重复创建」判断
    const exists = {};
    oldGroups.forEach(g => { exists[g.name] = true; });

    function addGroup(group) {
        newGroups.push(group);
        exists[group.name] = true;
    }

    function urlTest(name, list) {
        return {
            name: name,
            type: "url-test",
            proxies: list,
            url: SETTINGS.testUrl,
            interval: SETTINGS.interval,
            tolerance: SETTINGS.tolerance
        };
    }

    function fallback(name, list) {
        return {
            name: name,
            type: "fallback",
            proxies: list,
            url: SETTINGS.testUrl,
            interval: SETTINGS.fallbackInterval
        };
    }

    /* ==================================================
     * 8. 建一个地区组
     *
     * 节点少 / 只有一种协议  → 单个 url-test 组（保持原逻辑）
     * 节点多且协议多样       → 先建 XX-SS / XX-VMess … 子组，
     *                          再建父组把子组串起来
     * ================================================== */

    function createRegion(regionName, matched) {

        // 订阅里已经有这个组 → 尊重订阅原样，不再动它
        if (exists[regionName]) return;

        // 父组基准名："🇯🇵 日本自动" → "🇯🇵 日本"
        const base = regionName.replace(/自动$/, "");

        // 按协议归类
        const byProtocol = {};
        const protocols = [];

        matched.forEach(node => {
            const p = protocolOf(node);
            if (!byProtocol[p]) {
                byProtocol[p] = [];
                protocols.push(p);
            }
            byProtocol[p].push(node);
        });

        // 协议排序：先按固定优先级，再按节点数
        protocols.sort((a, b) =>
            protocolRank(a) - protocolRank(b) ||
            byProtocol[b].length - byProtocol[a].length
        );

        // —— 情况一：不细分 ——
        if (protocols.length < 2 || matched.length < SETTINGS.subdivideMinNodes) {
            addGroup(urlTest(regionName, matched));
            log("建组 " + regionName + "（" + matched.length + " 节点）");
            return;
        }

        // —— 情况二：按协议细分 ——
        const children = [];

        protocols.forEach(p => {
            const label = PROTOCOL_LABEL[p] || "OTHER";
            const childName = base + "-" + label;
            const list = byProtocol[p];

            children.push(childName);

            if (exists[childName]) return;  // 同名子组已存在，只引用不重建

            addGroup(urlTest(childName, list));
            log("建子组 " + childName + "（" + list.length + " 节点）");
        });

        if (!children.length) return;

        addGroup(
            SETTINGS.regionParentType === "fallback"
                ? fallback(regionName, children)
                : urlTest(regionName, children)
        );

        log("建父组 " + regionName + "（" + children.length + " 个子组）");
    }

    /* ==================================================
     * 9. 逐个地区建组
     * ================================================== */

    Object.keys(REGION_RULES).forEach(regionName => {
        const matched = nodes.filter(node => matchAny(node, REGION_RULES[regionName]));
        if (!matched.length) return;
        createRegion(regionName, matched);
    });

    /* ==================================================
     * 10. 国内 / 国外划分
     *
     * excludeCN 命中 → 国内；否则 → 国外
     * ================================================== */

    const cnNodes = [];
    const overseasNodes = [];

    nodes.forEach(node => {
        if (SETTINGS.excludeCN.test(node)) {
            cnNodes.push(node);
        } else {
            overseasNodes.push(node);
        }
    });

    // 🌍 国外自动：所有非国内节点一起测速
    if (overseasNodes.length && !exists[NAME.overseasAuto]) {
        addGroup(urlTest(NAME.overseasAuto, overseasNodes));
        log("建组 " + NAME.overseasAuto + "（" + overseasNodes.length + " 节点）");
    }

    // 🇨🇳 国内自动：被 excludeCN 命中的节点全部收进来
    if (cnNodes.length && !exists[NAME.cnAuto]) {
        addGroup(urlTest(NAME.cnAuto, cnNodes));
        log("建组 " + NAME.cnAuto + "（" + cnNodes.length + " 节点）");
    }

    /* ==================================================
     * 11. 🌍 国外容灾
     *
     * 顺序 = REGION_RULES 顺序 → 最后 国外自动
     * 即：日本挂了走新加坡，以此类推，全都挂了走国外自动
     * ================================================== */

    const failoverMembers = [];

    Object.keys(REGION_RULES).forEach(regionName => {
        if (exists[regionName]) failoverMembers.push(regionName);
    });

    if (exists[NAME.overseasAuto]) {
        failoverMembers.push(NAME.overseasAuto);
    }

    if (failoverMembers.length > 1 && !exists[NAME.overseasFailover]) {
        addGroup(fallback(NAME.overseasFailover, failoverMembers));
        log("建组 " + NAME.overseasFailover + "（" + failoverMembers.length + " 个成员）");
    }

    /* ==================================================
     * 12. 没有新组 → 原样返回
     * ================================================== */

    if (!newGroups.length) {
        log("没有新增分组");
        return config;
    }

    /* ==================================================
     * 13. 合并分组：新组在前，订阅原有组在后
     * ================================================== */

    config["proxy-groups"] = newGroups.concat(oldGroups);

    /* ==================================================
     * 14. 注入主入口 select 组
     *
     * 条件：type=select 且成员 ≥ 5 且名字不带 自动/测速/故障/容灾
     * 做法：插到 proxies 数组最前面（不删原有成员）
     * ================================================== */

    const injectNames = [];

    function pushInject(n) {
        if (exists[n] && injectNames.indexOf(n) === -1) injectNames.push(n);
    }

    pushInject(NAME.overseasAuto);
    pushInject(NAME.overseasFailover);
    Object.keys(REGION_RULES).forEach(pushInject);
    if (SETTINGS.injectCNGroup) pushInject(NAME.cnAuto);

    const entryGroups = config["proxy-groups"].filter(group => {
        if (group.type !== "select") return false;
        if (!group.proxies || group.proxies.length < 5) return false;
        if (/自动|测速|故障|容灾/i.test(group.name)) return false;
        return true;
    });

    entryGroups.forEach(group => {
        const todo = injectNames.filter(n => group.proxies.indexOf(n) === -1);
        if (!todo.length) return;
        Array.prototype.unshift.apply(group.proxies, todo);
        log("注入入口组 " + group.name + " → " + todo.join(" / "));
    });

    return config;
}
