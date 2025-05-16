function main(config, filename) {
    // —— ① 只在指定订阅中生效 —— 
    const SUBSCRIBE_KEYWORD = '良心';
    if (!filename.includes(SUBSCRIBE_KEYWORD)) {
      return config;
    }
  
    // —— ② 您的 newGroup 字符串 —— 
    const newGroupStr = `
      { 
        name: '超级自动选择', 
        type: 'url-test', 
        proxies: [
          '🇯🇵日本高速01|BGP|流媒体',
          '🇯🇵日本高速02|BGP|流媒体',
          '🇯🇵日本高速03|BGP|流媒体',
          '🇰🇷韩国高速01|BGP|流媒体',
          '🇰🇷韩国高速02|BGP|流媒体',
          '🇦🇺澳大利亚高速01|BGP|流媒体',
          '🇦🇺澳大利亚高速02|BGP|流媒体',
          '🇯🇵日本专线02|BGP|流媒体',
          '🇯🇵日本专线03|BGP|流媒体',
          '🇰🇷韩国专线01|BGP|流媒体',
          '🇰🇷韩国专线02|BGP|流媒体',
          '🇺🇸美国01|流媒体',
          '🇺🇸美国02|流媒体',
          '🇬🇧英国01|流媒体'
        ], 
        url: 'http://www.gstatic.com/generate_204', 
        interval: 3600, 
        tolerance: 150 
      }
    `;
  
    // —— ③ 解析成 JS 对象 —— 
    let newGroup;
    try {
      newGroup = Function('"use strict";return (' + newGroupStr + ');')();
    } catch (err) {
      console.error('解析 newGroup 字符串失败:', err);
      return config;
    }
  
    // —— ④ 找到第一个 type: 'select' 的组 —— 
    const selectGroup = config['proxy-groups'] &&
                        config['proxy-groups'].find(g => g.type === 'select');
    if (!selectGroup) {
      console.warn('未找到任何 type: select 的代理组，跳过注入');
      return config;
    }
  
    // —— ⑤ 确保该 select 组的 proxies 数组存在 —— 
    if (!Array.isArray(selectGroup.proxies)) {
      selectGroup.proxies = [];
    }
  
    // —— ⑥ 去重后追加 newGroup.name —— 
    if (!selectGroup.proxies.includes(newGroup.name)) {
      selectGroup.proxies.unshift(newGroup.name);
    }
  
    // —— ⑦ 将 newGroup 本身注入到 proxy-groups（仅首次） —— 
    if (!config['proxy-groups'].some(g => g.name === newGroup.name)) {
      config['proxy-groups'].push(newGroup);
    }
  
    return config;
  }
  